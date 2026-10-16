"""MCP-Server: das Werkzeug für eine AI, mit der geschwärzten Sicht als einziger Sicht.

Die AI weiß, was geleistet wurde und wie viel davon – nie, wer beteiligt ist und was es kostet.
Außerhalb von Claude Code gibt es weder Hook noch Deny-Regeln; hier ist der Server die Sperre: Er
bietet nur die Werkzeuge unten an, und jedes gibt nur die geschwärzte Sicht zurück (`sicht.py`),
unabhängig von RECHNUNG_GESCHWAERZT. Was ein Werkzeug zurückgibt, geht an den Modellanbieter.

Darüber hinaus sieht die AI hier auch das Kürzel des Kunden nicht: Den Kunden wählt der Mensch
(Startoption `--kunde`, sonst Auswahl im Client per Elicitation), nur wenn der Client das nicht
kann, nennt er der AI das Kürzel selbst. Preise bestätigt der Mensch im eigenen Terminal
(`rechnung preise`) oder, mit `--preise-im-client`, in einem Formular des Clients.

Im Demo-Betrieb (RECHNUNG_DEMO, `rechnung mcp --demo`) gibt es nur die erfundenen Stammdaten aus
stammdaten.example/; dann nennt das Werkzeug `kunden` der AI die Testkunden, damit der Mensch ohne
Terminal auswählen kann, und jede Antwort trägt den Prototyp-Hinweis.

Jede Antwort zu einer Rechnung trägt `naechster_schritt` (schritt.py), aus dem Stand der Rechnung.

Die Werkzeuge entsprechen den Abschnitten des Skills `.claude/skills/rechnung/SKILL.md`.
Optional importierbar: braucht das Extra `mcp` (`pip install 'ai-e-rechnung[mcp]'`); der Kern
importiert dieses Modul nie.
"""

# Ohne `from __future__ import annotations`: das SDK wertet die Annotationen der Werkzeuge aus, und
# die Resolver (waehle_kunde, formular) sind lokale Namen.

import inspect
import json
from collections.abc import Callable, Iterator
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
    schritt as schritt_mod,
    sicht,
)
from rechnung.models import Beleg, Leistung, Position, Resolved

ANLEITUNG = f"""\
Rechnungen für ein deutsches Kleingewerbe. Du schreibst, was geleistet wurde und wie viel davon;
das Werkzeug entscheidet Leistungsort und Steuer und setzt Namen, Anschriften und Beträge selbst ein.
Du siehst nie, wer beteiligt ist und was es kostet – und fragst auch nicht danach.

Ablauf: neu → preisliste → schreiben → resolve (dem Menschen zeigen, er bestätigt) → bauen →
pruefen. Preise aus der Preisliste übernimmt resolve selbst; nur was die Liste nicht hat (Auslagen),
trägt der Mensch ein. Jede Antwort nennt in naechster_schritt, was als Nächstes kommt. Will der Mensch erst eine Pro forma für den Kunden:
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
- preise: Preise fehlen, die die Liste nicht hat – der Mensch trägt sie selbst ein; nie nach Beträgen fragen.
Ändere nie einordnung oder ort, um an einem Abbruch vorbeizukommen.

Was der Mensch dir in den Chat tippt, siehst du – auch Beträge. Bitte ihn, sie dort nicht zu nennen.

{rules.GELTUNGSBEREICH} Sag das dem Menschen einmal, bevor du die erste Rechnung anlegst.
"""

DEMO_ANLEITUNG = """
Demo-Betrieb: Es gibt nur erfundene Testkunden und einen erfundenen Aussteller. Das Werkzeug kunden
zeigt die Testkunden mit Kürzel und Fall; zeig sie dem Menschen, wenn er keinen nennt, und lass ihn
wählen. Ihre Namen bleiben auch hier in allen anderen Antworten geschwärzt – so sähe es mit echten
Daten aus. Sag dem Menschen, dass dies ein Prototyp mit Testdaten ist.
"""

DEMO_HINWEIS = f"Demo mit erfundenen Testdaten. {rules.GELTUNGSBEREICH}"

ZURUECKGEHALTEN = ("Abbruch (frage): Unerwarteter Fehler; die Meldung ist zurückgehalten, weil sie private "
                   "Daten enthalten könnte. Der Mensch sieht sie, wenn er dasselbe Kommando im eigenen "
                   "Terminal ausführt.")


@dataclass(frozen=True)
class Einstellungen:
    kunde: str | None = None          # fest gewählter Kunde (Web-Demo, Startoption --kunde)
    preise_im_client: bool = False    # Preisbestätigung per Elicitation statt nur im Terminal
    demo: bool | None = None          # None: aus der Config (RECHNUNG_DEMO); Tests setzen es direkt


# ---------------------------------------------------------------- Hilfen


def _mit_geltungsbereich(f: Callable[..., Any]) -> Callable[..., Any]:
    """Hängt die Kurzfassung des Geltungsbereichs an die Beschreibung eines Werkzeugs (unter @server.tool())."""
    f.__doc__ = f"{inspect.cleandoc(f.__doc__ or '')}\n\n{rules.GELTUNGSBEREICH}"
    return f


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


def _preise_weg(nummer: str, einstellungen: Einstellungen) -> str:
    """Wie der Mensch Preise einträgt, die die Liste nicht hat – ohne dass ein Betrag durch die AI geht."""
    terminal = f"im eigenen Terminal: {schritt_mod.befehl(f'preise {nummer}')}"
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


def _fall(pfad: Path) -> str:
    """Die Kommentarzeilen am Anfang einer Beispiel-Kundendatei: welchen Fall sie zeigt."""
    zeilen = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if not zeile.startswith("#"):
            break
        zeilen.append(zeile.lstrip("# ").strip())
    return " ".join(zeilen).removesuffix("Erfunden.").strip()


def _demo(einstellungen: Einstellungen) -> bool:
    """Demo-Betrieb: aus der Config (RECHNUNG_DEMO); ist sie kaputt, nicht."""
    if einstellungen.demo is not None:
        return einstellungen.demo
    try:
        return config.laden().demo
    except config.ConfigFehler:
        return False


class Kundenwahl(BaseModel):
    kunde: str


def _hat_elicitation(ctx: Context) -> bool:
    caps = ctx.client_capabilities
    return bool(caps and caps.elicitation)


# ---------------------------------------------------------------- Server


def erstelle(einstellungen: Einstellungen | None = None) -> MCPServer:
    """Der Server mit seinen Werkzeugen. `rechnung mcp` startet ihn über stdio; Tests rufen ihn direkt."""
    einstellungen = einstellungen or Einstellungen()
    demo = _demo(einstellungen)
    # Den Schalter RECHNUNG_GESCHWAERZT braucht es hier nicht: Kein Werkzeug gibt etwas anderes aus als
    # sicht.* und geschwärzte Abbrüche (_sperre); die Bibliothek selbst liest den Schalter nicht.
    server = MCPServer("rechnung", version=__version__, instructions=ANLEITUNG + (DEMO_ANLEITUNG if demo else ""))

    def mit_schritt(daten: dict, cfg: config.Config, ordner: Path, naechster: str | None = None) -> dict:
        """Jede Antwort zu einer Rechnung: dazu der nächste Schritt, im Demo-Betrieb der Hinweis."""
        schritt = naechster or schritt_mod.naechster(cfg, ordner, _preise_weg(ordner.name, einstellungen))
        return daten | {"naechster_schritt": schritt} | ({"hinweis": DEMO_HINWEIS} if demo else {})

    # ------------------------------------------------ neu

    def waehle_kunde(ctx: Context, kunde: str = "") -> Any:
        if einstellungen.kunde:
            return Kundenwahl(kunde=einstellungen.kunde)   # ohne Frage; das SDK verpackt es als angenommen
        if kunde:
            return Kundenwahl(kunde=kunde)
        if not _hat_elicitation(ctx):
            if demo:
                raise _abbruch("Dieser Client kann den Kunden nicht abfragen. Zeig dem Menschen die Testkunden "
                               "(Werkzeug kunden) und lass ihn einen wählen; dann rufst du neu mit kunde auf.\n\n"
                               + DEMO_HINWEIS)
            raise _abbruch(
                "Dieser Client kann den Kunden nicht abfragen. Bitte den Menschen, dir das Kürzel seines Kunden "
                "zu nennen (der Dateiname in stammdaten/kunden/ ohne .yaml); dann rufst du neu mit kunde auf. "
                f"Oder er legt die Rechnung im eigenen Terminal an ({schritt_mod.befehl('neu --kunde <kürzel>')}) "
                "und nennt dir nur die Nummer.\n\n" + rules.GELTUNGSBEREICH)
        with _sperre():
            kuerzel = _kunden(config.laden())
        if not kuerzel:
            raise _abbruch("Im Gewerbe-Ordner gibt es keine Kundendatei (stammdaten/kunden/). Der Mensch legt "
                           "eine an.", meldung.STAMMDATEN)
        wahl = create_model("Kundenwahl", kunde=(Literal[tuple(kuerzel)], Field(title="Kunde")))  # type: ignore[valid-type]
        return Elicit("Für welchen Kunden ist die Rechnung? (Die Auswahl geht nicht an die AI.)\n\n"
                      + rules.GELTUNGSBEREICH, wahl)

    @server.tool()
    @_mit_geltungsbereich
    def neu(
        wahl: Annotated[ElicitationResult[Kundenwahl], Resolve(waehle_kunde)],
        leistungsdatum: Annotated[str, Field(description="JJJJ-MM-TT, nur was der Mensch gesagt hat")] = "",
        taetigkeit: Annotated[str, Field(description="Was geleistet wurde, in den Worten des Menschen")] = "",
        einordnung: Annotated[str, Field(description=f"Begriff aus § 3a UStG: {', '.join(rules.EINORDNUNGEN)}")] = "",
        ort: Annotated[str, Field(description="Nur bei kulturell … unterhaltend: Land (ISO, z. B. FR) oder online")] = "",
        kunde: Annotated[str, Field(description="Nur, wenn der Mensch dir das Kürzel ausdrücklich genannt oder "
                                                "aus den Testkunden (Werkzeug kunden) gewählt hat. Sonst leer "
                                                "lassen: der Server fragt ihn selbst.")] = "",
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
            return mit_schritt({"nummer": nummer, "sprache": k.sprache or cfg.sprache, "hinweis": rules.GELTUNGSBEREICH},
                           cfg, ordner, f"Preisliste ansehen, mit dem Menschen klären, was geleistet wurde, "
                                        f"dann schreiben({nummer}, …).")

    # ------------------------------------------------ preisliste, lesen, schreiben

    @server.tool()
    def preisliste() -> dict:
        """Die Preisliste ohne Preise: Kürzel, Einheit, Art (leistung, auslage oder lieferung),
        Bezeichnung. Positionen in rechnung.yaml nehmen ein Kürzel von hier, mit derselben Einheit.
        Eine Lieferung (Ware) kann das Werkzeug noch nicht: nicht verwenden, dem Menschen sagen."""
        with _sperre():
            liste = resolve_mod.lade_preisliste(config.laden())
            return {"preisliste": [{"kuerzel": k, "einheit": e.einheit, "art": e.art, "bezeichnung": e.bezeichnung}
                                   | ({"hinweis": rules.VERMERK_LIEFERUNG} if e.art == rules.LIEFERUNG else {})
                                   for k, e in liste.items()]}

    @server.tool()
    def lesen(nummer: str) -> dict:
        """Der aktuelle Inhalt von rechnung.yaml, so weit du ihn sehen darfst (ohne den Kunden)."""
        with _sperre():
            cfg = config.laden()
            ordner = resolve_mod.finde_ordner(cfg, nummer)
            daten = resolve_mod._yaml(ordner / resolve_mod.INPUT_DATEI)
            return mit_schritt({"nummer": ordner.name} | {f: _gefiltert(f, daten[f]) for f in LESBAR if f in daten},
                           cfg, ordner)

    @server.tool()
    @_mit_geltungsbereich
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
            cfg = config.laden()
            ordner = resolve_mod.finde_ordner(cfg, nummer)
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
            return mit_schritt({"nummer": ordner.name, "geschrieben": geaendert}, cfg, ordner,
                           f"resolve({ordner.name})")

    # ------------------------------------------------ resolve, begruendung, offen

    @server.tool()
    def resolve(nummer: str) -> dict:
        """Löst die Rechnung auf: Leistungsort, Ergebnis, angewandte Regeln (RULES.md), Warnungen und
        Stand der Preise – ohne Kunde, Preise und Beträge. Fehlende Preise übernimmt es aus der
        Preisliste. Zeig es dem Menschen; weiter erst, wenn er bestätigt."""
        with _sperre():
            cfg = config.laden()
            entwurf = resolve_mod.mit_listenpreisen(cfg, nummer)
            if entwurf.preise != preise_mod.BESTAETIGT:
                s = _ohne_kunde(sicht.entwurf(entwurf))
                s["preise"] = preise_mod.stand_text(entwurf.preise, entwurf.privat)
                return mit_schritt(s, cfg, entwurf.ordner)
            ergebnis, ziel = resolve_mod.resolve(cfg, nummer)
            privat = resolve_mod.lade_privat(ziel.parent)
            return mit_schritt(_ohne_kunde(sicht.ergebnis(ergebnis))
                           | {"preise": preise_mod.stand_text(preise_mod.BESTAETIGT, privat)}, cfg, ziel.parent)

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
                    stand = sicht.abbruch(f)
                else:
                    stand = f"Preise {preise_mod.stand_text(e.preise, e.privat)}"
                liste.append({"nummer": ordner.name, "stand": stand,
                              "naechster_schritt": schritt_mod.naechster(cfg, ordner,
                                                                         _preise_weg(ordner.name, einstellungen))})
            return {"offen": liste} | ({"hinweis": DEMO_HINWEIS} if demo else {})

    # ------------------------------------------------ bauen, pruefen

    @server.tool()
    def bauen(nummer: str, pro_forma: bool = False) -> dict:
        """Baut die PDF (mit pro_forma eine Pro forma zur Prüfung durch den Kunden). Die PDF selbst
        bekommst du nicht; der Mensch öffnet sie. Fehlende Preise übernimmt es aus der Preisliste;
        fehlt einer, den die Liste nicht hat, baut es nichts."""
        with _sperre():
            cfg = config.laden()
            ordner = resolve_mod.finde_ordner(cfg, nummer)
            _offen_fuer_aenderungen(ordner)
            ergebnis, json_ziel = resolve_mod.resolve(cfg, nummer)
            pdf = render_mod.baue_pdf(ergebnis, json_ziel.parent, cfg.engine,
                                      belege_quelle=json_ziel.parent / "belege", eigene=cfg.vorlage,
                                      pro_forma=pro_forma)
            privat = resolve_mod.lade_privat(ordner)
            pro_forma_schritt = (f"pruefen({ergebnis.nummer}, pro_forma=true); danach schickt der Mensch die Pro "
                                 f"forma und hält sie fest: "
                                 + schritt_mod.befehl(f"pro-forma {ergebnis.nummer} --gesendet-am JJJJ-MM-TT"))
            return mit_schritt({"nummer": ergebnis.nummer, "pdf": pdf.name, "ergebnis": ergebnis.ergebnis,
                            "preise": preise_mod.stand_text(preise_mod.BESTAETIGT, privat),
                            "warnungen": list(ergebnis.warnungen)}, cfg, ordner,
                           pro_forma_schritt if pro_forma else None)

    @server.tool()
    def pruefen(nummer: str, pro_forma: bool = False) -> dict:
        """Weist im Text der PDF die Pflichtangaben nach (§ 14 Abs. 4 UStG). Den gesuchten Text siehst
        du nicht; bei einem Mangel sag dem Menschen, welche Angabe fehlt."""
        with _sperre():
            cfg = config.laden()
            ordner = resolve_mod.finde_ordner(cfg, nummer)
            r = Resolved.model_validate(json.loads((ordner / resolve_mod.RESOLVED_DATEI).read_text(encoding="utf-8")))
            liste = pruefen_mod.pruefe(r, pruefen_mod.pdf_pfad(ordner, r, pro_forma), pro_forma)
            abweichungen = festschreiben_mod.pruefe_unveraendert(ordner)
            maengel = sum(not b.gefunden for b in liste) + len(abweichungen)
            return mit_schritt({
                "nummer": ordner.name,
                "gruen": maengel == 0,
                "angaben": [{"angabe": b.angabe, "gefunden": b.gefunden, "paragraf": b.paragraf} for b in liste],
                "abweichungen": abweichungen,
            }, cfg, ordner)

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
            cfg = config.laden()
            ordner = resolve_mod.finde_ordner(cfg, nummer)
            _offen_fuer_aenderungen(ordner)
            namen = anschreiben_mod.platzhalter(text)
            (ordner / anschreiben_mod.DATEI).write_text(text, encoding="utf-8")
            return mit_schritt({"nummer": ordner.name, "platzhalter": namen}, cfg, ordner)

    @server.tool()
    def anschreiben_pruefen(nummer: str) -> dict:
        """Prüft die Platzhalter in anschreiben.md, ohne etwas einzusetzen."""
        with _sperre():
            cfg = config.laden()
            ordner = resolve_mod.finde_ordner(cfg, nummer)
            namen = anschreiben_mod.platzhalter(anschreiben_mod.lesen(ordner))
            return mit_schritt({"nummer": ordner.name, "gueltig": True, "platzhalter": namen,
                            "einsetzen": "im eigenen Terminal des Menschen: "
                                         + schritt_mod.befehl(f"anschreiben {ordner.name}")}, cfg, ordner)

    # ------------------------------------------------ Preise im Client (optional)

    if demo:
        _kunden_werkzeug(server)
    if einstellungen.preise_im_client:
        _preise_werkzeug(server, mit_schritt)

    return server


def _kunden_werkzeug(server: MCPServer) -> None:
    """Nur im Demo-Betrieb: Die Testkunden sind erfunden (stammdaten.example/, erzwungen), deshalb darf
    die AI sie dem Menschen zeigen – damit er ohne Terminal und ohne Formular wählen kann."""

    @server.tool()
    def kunden() -> dict:
        """Die erfundenen Testkunden des Demo-Betriebs: Kürzel, Name, Land und welchen Fall sie zeigen.
        Zeig sie dem Menschen und lass ihn wählen; dann neu mit kunde."""
        with _sperre():
            cfg = config.laden()
            if not cfg.demo:
                raise _abbruch("kunden gibt es nur im Demo-Betrieb.", meldung.AUSSERHALB)
            ordner = resolve_mod.kunden_ordner(cfg)
            liste = []
            for kuerzel in _kunden(cfg):
                k = resolve_mod.lade_kunde(cfg, kuerzel)
                liste.append({"kuerzel": kuerzel, "name": k.firma, "land": k.land,
                              "fall": _fall(ordner / f"{kuerzel}.yaml")})
            return {"kunden": liste, "hinweis": DEMO_HINWEIS}


def _preise_werkzeug(server: MCPServer, mit_schritt: Callable[..., dict]) -> None:
    """Preisbestätigung per Elicitation: Formular im Client, Werte gehen an den Server, nicht an die AI.

    Nur mit `--preise-im-client`: Ob ein Client Formular und Antwort wirklich am Modell vorbeiführt,
    ist je Client zu prüfen (entscheidungen.md). Das Ergebnis an die AI nennt keinen Betrag.
    """

    def formular(ctx: Context, nummer: str) -> Any:
        if not _hat_elicitation(ctx):
            raise _abbruch(f"Dieser Client kann kein Formular zeigen. Der Mensch bestätigt die Preise im "
                           f"eigenen Terminal: {schritt_mod.befehl(f'preise {nummer}')}", meldung.PREISE)
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
                                   f"auf oder bestätigt im eigenen Terminal: "
                                   f"{schritt_mod.befehl(f'preise {nummer}')}", meldung.PREISE)
                einzelpreise.append(preis)
                ermaessigt.append(bool(werte.get(f"sieben_{p.pos}", False)))
            referenz_eingabe = str(werte.get("referenz", "")).strip()
            referenz: Any = (preise_mod.UNVERAENDERT if not referenz_eingabe
                             else None if referenz_eingabe == "-" else referenz_eingabe)
            preise_mod.bestaetigen(e, einzelpreise, ermaessigt, referenz=referenz)
            return mit_schritt({"nummer": e.nummer, "preise": "bestätigt"}, config.laden(), e.ordner,
                           f"resolve({e.nummer})")


def starten(einstellungen: Einstellungen) -> None:
    """`rechnung mcp`: stdio – stdout gehört dem Protokoll."""
    erstelle(einstellungen).run("stdio")
