"""MCP-Server: das Werkzeug für eine AI, mit der geschwärzten Sicht als einziger Sicht.

Die AI weiß, was geleistet wurde und wie viel davon – nie, wer beteiligt ist und was es kostet.
Außerhalb von Claude Code gibt es weder Hook noch Deny-Regeln; hier ist der Server die Sperre: Er
bietet nur die Werkzeuge unten an, und jedes gibt nur die geschwärzte Sicht zurück (`sicht.py`),
unabhängig von RECHNUNG_GESCHWAERZT. Was ein Werkzeug zurückgibt, geht an den Modellanbieter.

Darüber hinaus sieht die AI hier auch das Kürzel des Kunden nicht: Den Kunden wählt der Mensch
(Startoption `--kunde`, sonst Auswahl im Client per Elicitation), nur wenn der Client das nicht
kann, nennt er der AI das Kürzel selbst. Preise bestätigt der Mensch im eigenen Terminal
(`rechnung preise`) oder, mit `--preise-im-client`, in einem Formular des Clients.

Die Werkzeuge entsprechen den Abschnitten des Skills `.claude/skills/rechnung/SKILL.md`.
Optional importierbar: braucht das Extra `mcp` (`pip install 'ai-e-rechnung[mcp]'`); der Kern
importiert dieses Modul nie.
"""

# Ohne `from __future__ import annotations`: das SDK wertet die Annotationen der Werkzeuge aus, und
# die Resolver (waehle_kunde, formular) sind lokale Namen.

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from mcp.server.elicitation import AcceptedElicitation, ElicitationResult
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.resolve import Elicit, Resolve
from pydantic import BaseModel, Field, create_model

from rechnung import (
    __version__,
    anschreiben as anschreiben_mod,
    begruendung as begruendung_mod,
    config,
    festschreiben as festschreiben_mod,
    meldung,
    preise as preise_mod,
    pruefen as pruefen_mod,
    render as render_mod,
    resolve as resolve_mod,
    rules,
    sicht,
)
from rechnung.models import Beleg, Leistung, Position, Resolved

ANLEITUNG = """\
Rechnungen für ein deutsches Kleingewerbe. Du schreibst, was geleistet wurde und wie viel davon;
das Werkzeug entscheidet Leistungsort und Steuer und setzt Namen, Anschriften und Beträge selbst ein.
Du siehst nie, wer beteiligt ist und was es kostet – und fragst auch nicht danach.

Ablauf: neu → preisliste → schreiben → resolve (dem Menschen zeigen, er bestätigt) → Preise beim
Menschen → resolve → bauen → pruefen. Will der Mensch erst eine Pro forma für den Kunden:
bauen und pruefen mit pro_forma=true. Als gesendet einfrieren (Pro forma oder Rechnung) und
festschreiben macht der Mensch selbst im Terminal (`rechnung pro-forma`, `rechnung festschreiben`).

Nie raten: leistungsdatum, leistung.taetigkeit, leistung.einordnung und leistung.ort kommen vom
Menschen; schlag eine Einordnung vor und lass sie dir bestätigen. Kein Preis, kein Steuersatz,
keine Referenz, kein Leistungsort von dir.

Abbrüche beginnen mit `Abbruch (<art>):`
- eingabe: dein Fehler in den Feldern – selbst beheben.
- frage: eine Tatsache, die nur der Mensch kennt – fragen, nie raten.
- stammdaten: Kunden- oder Ausstellerdatei unvollständig – der Mensch trägt es selbst ein, nicht im Chat.
- ausserhalb: bewusst außerhalb des Geltungsbereichs – erklären und anhalten.
- preise: Preise fehlen oder sind veraltet – der Mensch bestätigt sie selbst; nie nach Beträgen fragen.
Ändere nie einordnung oder ort, um an einem Abbruch vorbeizukommen.

Was der Mensch dir in den Chat tippt, siehst du – auch Beträge. Bitte ihn, sie dort nicht zu nennen.
"""

ZURUECKGEHALTEN = ("Abbruch (frage): Unerwarteter Fehler; die Meldung ist zurückgehalten, weil sie private "
                   "Daten enthalten könnte. Der Mensch sieht sie, wenn er dasselbe Kommando im eigenen "
                   "Terminal ausführt.")


@dataclass(frozen=True)
class Einstellungen:
    kunde: str | None = None          # fest gewählter Kunde (Web-Demo, Startoption --kunde)
    preise_im_client: bool = False    # Preisbestätigung per Elicitation statt nur im Terminal


# ---------------------------------------------------------------- Hilfen


@contextmanager
def _sperre() -> Iterator[None]:
    """Jeder Fehler geht nur geschwärzt hinaus: fachliche mit ihrer Fassung, alles andere zurückgehalten."""
    try:
        yield
    except ToolError:
        raise
    except meldung.Fehler as e:
        raise ToolError(sicht.abbruch(e)) from None
    except Exception:
        raise ToolError(ZURUECKGEHALTEN) from None


def _abbruch(text: str, art: str = meldung.FRAGE) -> ToolError:
    return ToolError(sicht.abbruch(meldung.Fehler(text, art=art, geschwaerzt=text)))


def _ohne_kunde(s: dict) -> dict:
    return {k: v for k, v in s.items() if k != "kunde"}


def _offen_fuer_aenderungen(ordner: Path) -> None:
    if festschreiben_mod.ist_festgeschrieben(ordner):
        raise _abbruch(f"Rechnung {ordner.name} ist festgeschrieben und wird nicht mehr geändert.",
                       meldung.AUSSERHALB)


PREISE_TEXT = {
    preise_mod.BESTAETIGT: "bestätigt",
    preise_mod.FEHLEN: "fehlen",
    preise_mod.VERALTET: "veraltet (Positionen oder Währung geändert)",
}


def _preise_weg(nummer: str, cfg: config.Config, einstellungen: Einstellungen) -> str:
    """Wie der Mensch die Preise bestätigt – ohne dass ein Betrag durch die AI geht."""
    wurzel = "RECHNUNG_GEWERBE=<wurzel> " if os.environ.get("RECHNUNG_GEWERBE") else ""
    terminal = f"im eigenen Terminal: {wurzel}rechnung preise {nummer}"
    if einstellungen.preise_im_client:
        return f"Werkzeug preise_bestaetigen (Formular für den Menschen) oder {terminal}"
    return terminal


# Felder von rechnung.yaml, die `lesen` zurückgibt (Positivliste aus sicht.EINSTUFUNG, ohne das Kürzel)
# und die `schreiben` setzt; alle anderen setzt nur der Mensch (Rechnungsdatum, Sprache, Währung,
# Zahlungsziel, festgelegter Leistungsort).
LESBAR = [f for f in dict.fromkeys(k.split(".")[0] for k, e in sicht.EINSTUFUNG.items() if e == sicht.AI)
          if f != "kunde"]
SCHREIBBAR = ("leistungsdatum", "leistungsdatum_bis", "einleitung", "leistung", "positionen", "belege")
REIHENFOLGE = ("kunde", "datum", "leistungsdatum", "leistungsdatum_bis", "sprache", "waehrung",
               "zahlungsziel_tage", "einleitung", "leistung", "leistungsort", "begruendung", "positionen",
               "belege")


def _unterfelder(feld: str) -> set[str]:
    return {k.split(".", 1)[1] for k, e in sicht.EINSTUFUNG.items() if k.startswith(f"{feld}.") and e == sicht.AI}


def _gefiltert(feld: str, wert: Any) -> Any:
    """Nur eingestufte Unterfelder; was sonst in der Datei steht (z. B. ein Preis), kommt nicht hinaus."""
    erlaubt = _unterfelder(feld)
    if not erlaubt:
        return wert.isoformat() if isinstance(wert, date) else wert
    if feld == "belege":
        wert = [{"datei": b} if isinstance(b, str) else b for b in (wert or [])]
    if isinstance(wert, list):
        return [{k: v for k, v in e.items() if k in erlaubt} for e in wert if isinstance(e, dict)]
    if isinstance(wert, dict):
        return {k: v for k, v in wert.items() if k in erlaubt}
    return None


def _zahl(wert: Decimal) -> int | float:
    return int(wert) if wert == wert.to_integral_value() else float(str(wert))


def _yaml_text(nummer: str, daten: dict) -> str:
    kopf = (f"# Rechnung {nummer}\n"
            "# Geschrieben über den MCP-Server (Werkzeug `schreiben`). Preise und die Referenz des Kunden\n"
            f"# stehen nicht hier: `rechnung preise {nummer}` (rechnung.privat.yaml). Einordnung: RULES.md Teil 4.\n\n")
    geordnet = {k: daten[k] for k in REIHENFOLGE if k in daten and daten[k] is not None}
    geordnet |= {k: v for k, v in daten.items() if k not in geordnet and v is not None}
    return kopf + yaml.safe_dump(geordnet, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _kunden(cfg: config.Config) -> list[str]:
    ordner = resolve_mod.kunden_ordner(cfg)
    return sorted(p.stem for p in ordner.glob("*.yaml")) if ordner.is_dir() else []


class Kundenwahl(BaseModel):
    kunde: str


def _hat_elicitation(ctx: Context) -> bool:
    caps = ctx.client_capabilities
    return bool(caps and caps.elicitation)


# ---------------------------------------------------------------- Server


def erstelle(einstellungen: Einstellungen | None = None) -> MCPServer:
    """Der Server mit seinen Werkzeugen. `rechnung mcp` startet ihn über stdio; Tests rufen ihn direkt."""
    einstellungen = einstellungen or Einstellungen()
    # Den Schalter RECHNUNG_GESCHWAERZT braucht es hier nicht: Kein Werkzeug gibt etwas anderes aus als
    # sicht.* und geschwärzte Abbrüche (_sperre); die Bibliothek selbst liest den Schalter nicht.
    server = MCPServer("rechnung", version=__version__, instructions=ANLEITUNG)

    # ------------------------------------------------ neu

    def waehle_kunde(ctx: Context, kunde: str = "") -> Any:
        if einstellungen.kunde:
            return Kundenwahl(kunde=einstellungen.kunde)   # ohne Frage; das SDK verpackt es als angenommen
        if kunde:
            return Kundenwahl(kunde=kunde)
        if not _hat_elicitation(ctx):
            raise _abbruch(
                "Dieser Client kann den Kunden nicht abfragen. Bitte den Menschen, die Rechnung im eigenen "
                "Terminal anzulegen (rechnung neu --kunde <kürzel>) und dir nur die Nummer zu nennen – oder "
                "dir das Kürzel zu nennen; dann rufst du neu mit kunde auf.")
        with _sperre():
            kuerzel = _kunden(config.laden())
        if not kuerzel:
            raise _abbruch("Im Gewerbe-Ordner gibt es keine Kundendatei (stammdaten/kunden/). Der Mensch legt "
                           "eine an.", meldung.STAMMDATEN)
        wahl = create_model("Kundenwahl", kunde=(Literal[tuple(kuerzel)], Field(title="Kunde")))  # type: ignore[valid-type]
        return Elicit("Für welchen Kunden ist die Rechnung? (Die Auswahl geht nicht an die AI.)", wahl)

    @server.tool()
    def neu(
        wahl: Annotated[ElicitationResult[Kundenwahl], Resolve(waehle_kunde)],
        leistungsdatum: Annotated[str, Field(description="JJJJ-MM-TT, nur was der Mensch gesagt hat")] = "",
        taetigkeit: Annotated[str, Field(description="Was geleistet wurde, in den Worten des Menschen")] = "",
        einordnung: Annotated[str, Field(description=f"Begriff aus § 3a UStG: {', '.join(rules.EINORDNUNGEN)}")] = "",
        ort: Annotated[str, Field(description="Nur bei kulturell … unterhaltend: Land (ISO, z. B. FR) oder online")] = "",
        kunde: Annotated[str, Field(description="Nur, wenn der Mensch dir das Kürzel ausdrücklich genannt hat. "
                                                "Sonst leer lassen: der Server fragt ihn selbst.")] = "",
    ) -> dict:
        """Legt eine neue Rechnung an und gibt ihre Nummer zurück. Den Kunden wählt der Mensch; du
        erfährst nicht, wer es ist. Die Nummer vergibt das Werkzeug. Fülle die Felder nur mit dem, was
        der Mensch gesagt hat; der Rest geht später mit `schreiben`."""
        if not isinstance(wahl, AcceptedElicitation):
            raise _abbruch("Der Mensch hat keinen Kunden gewählt; nichts angelegt.")
        with _sperre():
            try:
                tag = date.fromisoformat(leistungsdatum) if leistungsdatum else None
            except ValueError:
                raise _abbruch(f"leistungsdatum muss JJJJ-MM-TT sein, nicht {leistungsdatum!r}.", meldung.EINGABE)
            if einordnung and einordnung not in rules.EINORDNUNGEN:
                raise _abbruch(f"einordnung muss eine von {', '.join(rules.EINORDNUNGEN)} sein.", meldung.EINGABE)
            cfg = config.laden()
            ordner, nummer = resolve_mod.neu(cfg, wahl.data.kunde, tag, None, None, None,
                                            taetigkeit or None, einordnung or None, ort or None)
            k = resolve_mod.lade_kunde(cfg, wahl.data.kunde)
            return {"nummer": nummer, "sprache": k.sprache or cfg.sprache,
                    "weiter": f"preisliste ansehen, dann schreiben({nummer}, …)"}

    # ------------------------------------------------ preisliste, lesen, schreiben

    @server.tool()
    def preisliste() -> dict:
        """Die Preisliste ohne Preise: Kürzel, Einheit, Art (leistung oder auslage), Bezeichnung.
        Positionen in rechnung.yaml nehmen ein Kürzel von hier, mit derselben Einheit."""
        with _sperre():
            liste = resolve_mod.lade_preisliste(config.laden())
            return {"preisliste": [{"kuerzel": k, "einheit": e.einheit, "art": e.art, "bezeichnung": e.bezeichnung}
                                   for k, e in liste.items()]}

    @server.tool()
    def lesen(nummer: str) -> dict:
        """Der aktuelle Inhalt von rechnung.yaml, so weit du ihn sehen darfst (ohne den Kunden)."""
        with _sperre():
            ordner = resolve_mod.finde_ordner(config.laden(), nummer)
            daten = resolve_mod._yaml(ordner / resolve_mod.INPUT_DATEI)
            return {"nummer": ordner.name} | {f: _gefiltert(f, daten[f]) for f in LESBAR if f in daten}

    @server.tool()
    def schreiben(
        nummer: str,
        leistungsdatum: Annotated[date | None, Field(description="Tag der Leistung; nur was der Mensch sagt")] = None,
        leistungsdatum_bis: Annotated[date | None, Field(description="nur bei einem Zeitraum")] = None,
        leistung: Annotated[Leistung | None, Field(
            description="taetigkeit in den Worten des Menschen; einordnung ein Begriff aus § 3a UStG "
                        f"({', '.join(rules.EINORDNUNGEN)}); ort nur bei kulturell … unterhaltend")] = None,
        positionen: Annotated[list[Position] | None, Field(
            description="Kürzel und Einheit aus der Preisliste, Menge; beschreibung nur, wenn die "
                        "Bezeichnung der Liste nicht reicht. Ersetzt alle Positionen.")] = None,
        einleitung: Annotated[str | None, Field(
            description="Ein Satz in der Sprache der Rechnung, nach der Anrede; ohne Beträge und Namen")] = None,
        belege: Annotated[list[Beleg] | None, Field(
            description="Dateinamen in belege/, die der Mensch gewählt hat. Ersetzt alle Belege.")] = None,
    ) -> dict:
        """Schreibt die angegebenen Felder in rechnung.yaml; nicht angegebene bleiben, wie sie sind.
        Einen Preis, einen Steuersatz, eine Referenz oder einen Leistungsort kannst du nicht schreiben –
        das ist Sache des Menschen. Danach: resolve."""
        with _sperre():
            ordner = resolve_mod.finde_ordner(config.laden(), nummer)
            _offen_fuer_aenderungen(ordner)
            pfad = ordner / resolve_mod.INPUT_DATEI
            daten = resolve_mod._yaml(pfad)
            neu_ = {
                "leistungsdatum": leistungsdatum,
                "leistungsdatum_bis": leistungsdatum_bis,
                "einleitung": einleitung,
                "leistung": leistung.model_dump(exclude_none=True) if leistung else None,
                "positionen": [p.model_dump(exclude_none=True) | {"menge": _zahl(p.menge)} for p in positionen]
                if positionen is not None else None,
                "belege": [b.datei if b.text is None else b.model_dump(exclude_none=True) for b in belege]
                if belege is not None else None,
            }
            geaendert = [k for k, v in neu_.items() if v is not None]
            daten |= {k: v for k, v in neu_.items() if v is not None}
            pfad.write_text(_yaml_text(ordner.name, daten), encoding="utf-8")
            return {"nummer": ordner.name, "geschrieben": geaendert, "weiter": f"resolve({ordner.name})"}

    # ------------------------------------------------ resolve, begruendung, offen

    @server.tool()
    def resolve(nummer: str) -> dict:
        """Löst die Rechnung auf: Leistungsort, Ergebnis, angewandte Regeln (RULES.md), Warnungen und
        Stand der Preise – ohne Kunde, Preise und Beträge. Zeig es dem Menschen; weiter erst, wenn er
        bestätigt."""
        with _sperre():
            cfg = config.laden()
            entwurf = resolve_mod.entwurf(cfg, nummer)
            if entwurf.preise != preise_mod.BESTAETIGT:
                s = _ohne_kunde(sicht.entwurf(entwurf))
                s["preise"] = PREISE_TEXT[entwurf.preise]
                s["preise_bestaetigen"] = _preise_weg(entwurf.nummer, cfg, einstellungen)
                return s
            ergebnis, _ = resolve_mod.resolve(cfg, nummer)
            return _ohne_kunde(sicht.ergebnis(ergebnis)) | {"preise": PREISE_TEXT[preise_mod.BESTAETIGT]}

    @server.tool()
    def begruendung(nummer: str) -> str:
        """Begründung der Steuerentscheidung als Markdown (Fakten, Regeln mit Status und Nachweis),
        geschwärzt. Erst, wenn die Preise bestätigt sind und resolve das Ergebnis geschrieben hat."""
        with _sperre():
            ordner = resolve_mod.finde_ordner(config.laden(), nummer)
            text, spur_passt = begruendung_mod.begruende(ordner, geschwaerzt=True, ohne_kuerzel=True)
            if not spur_passt:
                text += "\n\nRot: Das Werkzeug entscheidet heute auf denselben Fakten anders.\n"
            return text

    @server.tool()
    def offen() -> dict:
        """Alle Rechnungen, die noch nicht festgeschrieben sind, und was ihnen fehlt."""
        with _sperre():
            cfg = config.laden()
            wurzel = cfg.ordner("ausgang")
            liste = []
            for ordner in sorted(wurzel.glob("*/*")):
                if not (ordner / resolve_mod.INPUT_DATEI).is_file() or festschreiben_mod.ist_festgeschrieben(ordner):
                    continue
                try:
                    e = resolve_mod.entwurf_aus(cfg, ordner)
                except meldung.Fehler as f:
                    liste.append({"nummer": ordner.name, "stand": sicht.abbruch(f)})
                    continue
                stand = "bereit: bauen" if e.preise == preise_mod.BESTAETIGT else f"Preise {PREISE_TEXT[e.preise]}"
                liste.append({"nummer": ordner.name, "stand": stand})
            return {"offen": liste}

    # ------------------------------------------------ bauen, pruefen

    @server.tool()
    def bauen(nummer: str, pro_forma: bool = False) -> dict:
        """Baut die PDF (mit pro_forma eine Pro forma zur Prüfung durch den Kunden). Die PDF selbst
        bekommst du nicht; der Mensch öffnet sie. Ohne bestätigte Preise baut es nichts."""
        with _sperre():
            cfg = config.laden()
            ordner = resolve_mod.finde_ordner(cfg, nummer)
            _offen_fuer_aenderungen(ordner)
            ergebnis, json_ziel = resolve_mod.resolve(cfg, nummer)
            pdf = render_mod.baue_pdf(ergebnis, json_ziel.parent, cfg.engine,
                                      belege_quelle=json_ziel.parent / "belege", eigene=cfg.vorlage,
                                      pro_forma=pro_forma)
            return {"nummer": ergebnis.nummer, "pdf": pdf.name, "ergebnis": ergebnis.ergebnis,
                    "warnungen": list(ergebnis.warnungen), "weiter": f"pruefen({ergebnis.nummer})"}

    @server.tool()
    def pruefen(nummer: str, pro_forma: bool = False) -> dict:
        """Weist im Text der PDF die Pflichtangaben nach (§ 14 Abs. 4 UStG). Den gesuchten Text siehst
        du nicht; bei einem Mangel sag dem Menschen, welche Angabe fehlt."""
        with _sperre():
            ordner = resolve_mod.finde_ordner(config.laden(), nummer)
            r = Resolved.model_validate(json.loads((ordner / resolve_mod.RESOLVED_DATEI).read_text(encoding="utf-8")))
            liste = pruefen_mod.pruefe(r, pruefen_mod.pdf_pfad(ordner, r, pro_forma), pro_forma)
            abweichungen = festschreiben_mod.pruefe_unveraendert(ordner)
            maengel = sum(not b.gefunden for b in liste) + len(abweichungen)
            return {
                "nummer": ordner.name,
                "gruen": maengel == 0,
                "angaben": [{"angabe": b.angabe, "gefunden": b.gefunden, "paragraf": b.paragraf} for b in liste],
                "abweichungen": abweichungen,
            }

    # ------------------------------------------------ anschreiben

    @server.tool()
    def anschreiben_schreiben(
        nummer: str,
        text: Annotated[str, Field(description=(
            "Begleittext in der Sprache der Rechnung, Markdown. Namen, Beträge und Daten nur als Platzhalter: "
            + ", ".join(f"[{n}] ({b})" for n, b in anschreiben_mod.FELDER.items())
            + ". [anrede] ohne Komma, das Komma setzt du dahinter."))],
    ) -> dict:
        """Schreibt den Entwurf des Anschreibens (anschreiben.md). Eingesetzt wird beim Menschen
        (rechnung anschreiben <nr> im eigenen Terminal); das Werkzeug verschickt nichts."""
        with _sperre():
            ordner = resolve_mod.finde_ordner(config.laden(), nummer)
            _offen_fuer_aenderungen(ordner)
            namen = anschreiben_mod.platzhalter(text)
            (ordner / anschreiben_mod.DATEI).write_text(text, encoding="utf-8")
            return {"nummer": ordner.name, "platzhalter": namen}

    @server.tool()
    def anschreiben_pruefen(nummer: str) -> dict:
        """Prüft die Platzhalter in anschreiben.md, ohne etwas einzusetzen."""
        with _sperre():
            ordner = resolve_mod.finde_ordner(config.laden(), nummer)
            namen = anschreiben_mod.platzhalter(anschreiben_mod.lesen(ordner))
            return {"nummer": ordner.name, "gueltig": True, "platzhalter": namen,
                    "einsetzen": f"im eigenen Terminal des Menschen: rechnung anschreiben {ordner.name}"}

    # ------------------------------------------------ Preise im Client (optional)

    if einstellungen.preise_im_client:
        _preise_werkzeug(server)

    return server


def _preise_werkzeug(server: MCPServer) -> None:
    """Preisbestätigung per Elicitation: Formular im Client, Werte gehen an den Server, nicht an die AI.

    Nur mit `--preise-im-client`: Ob ein Client Formular und Antwort wirklich am Modell vorbeiführt,
    ist je Client zu prüfen (entscheidungen.md). Das Ergebnis an die AI nennt keinen Betrag.
    """

    def formular(ctx: Context, nummer: str) -> Any:
        if not _hat_elicitation(ctx):
            raise _abbruch(f"Dieser Client kann kein Formular zeigen. Der Mensch bestätigt die Preise im "
                           f"eigenen Terminal: rechnung preise {nummer}", meldung.PREISE)
        with _sperre():
            e = resolve_mod.entwurf(config.laden(), nummer)
            _offen_fuer_aenderungen(e.ordner)
        felder: dict[str, Any] = {}
        for p in e.positionen:
            art = ", Auslage – Betrag vom Beleg" if p.art == "auslage" else ""
            vorschlag = str(rules.mindestens_zwei(p.vorschlag)) if p.vorschlag is not None else ""
            felder[f"preis_{p.pos}"] = (str, Field(default=vorschlag, title=f"{p.pos}. {p.beschreibung}",
                                                   description=f"Einzelpreis in {e.waehrung} für {p.menge} "
                                                               f"{p.einheit}{art}"))
            if p.sieben_erlaubt:
                felder[f"sieben_{p.pos}"] = (bool, Field(default=p.vorschlag_sieben,
                                                         title=f"{p.pos}. 7 % (ermäßigt, § 12 Abs. 2 UStG)"))
        felder["referenz"] = (str, Field(default="", title="Referenz des Kunden für diese Rechnung",
                                         description="leer: unverändert; '-' entfernt sie"))
        modell = create_model(f"Preise_{e.nummer.replace('-', '_')}", **felder)
        return Elicit(f"Preise für Rechnung {e.nummer} bestätigen. Mit „Annehmen“ hältst du sie fest. "
                      f"Die Werte gehen an das Werkzeug, nicht an die AI.", modell)

    @server.tool()
    def preise_bestaetigen(
        nummer: str,
        antwort: Annotated[ElicitationResult[BaseModel], Resolve(formular)],
    ) -> dict:
        """Zeigt dem Menschen ein Formular mit den Preisen (vorbefüllt aus der Preisliste) und hält
        seine Bestätigung fest. Du siehst keinen Betrag, nur ob bestätigt wurde."""
        if not isinstance(antwort, AcceptedElicitation):
            return {"nummer": nummer, "preise": "nicht bestätigt"}
        with _sperre():
            e = resolve_mod.entwurf(config.laden(), nummer)
            werte = antwort.data.model_dump()
            einzelpreise, ermaessigt = [], []
            for p in e.positionen:
                preis = preise_mod.betrag(str(werte.get(f"preis_{p.pos}", "")))
                if preis is None:
                    raise _abbruch(f"Position {p.pos}: kein gültiger Betrag. Der Mensch ruft das Formular erneut "
                                   f"auf oder bestätigt im eigenen Terminal: rechnung preise {nummer}",
                                   meldung.PREISE)
                einzelpreise.append(preis)
                ermaessigt.append(bool(werte.get(f"sieben_{p.pos}", False)))
            referenz_eingabe = str(werte.get("referenz", "")).strip()
            referenz: Any = (preise_mod.UNVERAENDERT if not referenz_eingabe
                             else None if referenz_eingabe == "-" else referenz_eingabe)
            preise_mod.bestaetigen(e, einzelpreise, ermaessigt, referenz=referenz)
            return {"nummer": e.nummer, "preise": "bestätigt", "weiter": f"resolve({e.nummer})"}


def starten(einstellungen: Einstellungen) -> None:
    """`rechnung mcp`: stdio – stdout gehört dem Protokoll."""
    erstelle(einstellungen).run("stdio")
