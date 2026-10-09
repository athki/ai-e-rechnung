"""Laden, Rechnen, Einfrieren: rechnung.yaml -> rechnung.resolved.json.

Alle Entscheidungen stecken in rules.py, alle Beträge sind Decimal. Diese Datei fügt zusammen
und schreibt das Ergebnis.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import ValidationError

from rechnung import config, rules, vorlage
from rechnung.models import (
    Input,
    Kunde,
    Leistung,
    Resolved,
    ResolvedPosition,
    Stammdaten,
    Steuergruppe,
)
from rechnung.models import EINHEITEN

INPUT_DATEI = "rechnung.yaml"
RESOLVED_DATEI = "rechnung.resolved.json"


class ResolveFehler(Exception):
    """Fachlicher Fehler mit einer Meldung, die sagt, was zu tun ist."""


# ---------------------------------------------------------------- Laden

# PyYAML-Meldung (Teilstring) -> was es meistens bedeutet und was zu tun ist.
_YAML_ERKLAERUNG: list[tuple[str, str]] = [
    ("mapping values are not allowed",
     "Doppelpunkt mit Leerzeichen mitten im Wert. Den ganzen Wert in Anführungszeichen setzen."),
    ("found character '\\t'",
     "Tabulator in der Einrückung. YAML rückt nur mit Leerzeichen ein."),
    ("while scanning a quoted scalar",
     "Anführungszeichen wird nicht geschlossen."),
    ("while parsing a flow mapping",
     "Geschweifte Klammer { wird nicht geschlossen. Platzhalter wie {Betrag} ganz entfernen."),
    ("while parsing a flow sequence",
     "Eckige Klammer [ wird nicht geschlossen."),
    ("found '<block sequence start>'",
     "Listeneintrag ohne Schlüssel darüber. Oft ist ein Block nur halb auskommentiert, "
     "z. B. „# belege:“ über „  - flug.pdf“: beide Zeilen gleich behandeln."),
    ("expected <block end>",
     "Einrückung passt nicht zu den Zeilen darüber. Gleiche Ebene, gleich viele Leerzeichen."),
    ("did not find expected '-' indicator",
     "Listeneintrag ohne „- “ oder falsch eingerückt."),
    ("did not find expected key",
     "Einrückung oder Listenstrich passt nicht; oft ist ein Block nur halb auskommentiert."),
]


def _yaml_fehler(pfad: Path, text: str, e: yaml.YAMLError) -> ResolveFehler:
    """Eine YAML-Syntaxmeldung, die man ohne Traceback versteht: Ort, Zeile, Erklärung."""
    mark = getattr(e, "problem_mark", None)
    roh = " ".join(str(t) for t in (getattr(e, "context", None), getattr(e, "problem", None)) if t)
    erklaerung = next((d for muster, d in _YAML_ERKLAERUNG if muster in roh), "YAML-Syntax ist ungültig.")
    if mark is None:
        return ResolveFehler(f"{pfad}: {erklaerung}\n  (YAML: {roh or e})")
    zeile, spalte = mark.line + 1, mark.column + 1
    zeilen = text.splitlines()
    # Steht der Fehler am Dateiende, ist die letzte Zeile mit Inhalt die interessante.
    nr = min(zeile, len(zeilen))
    while nr > 1 and not zeilen[nr - 1].strip():
        nr -= 1
    auszug = zeilen[nr - 1] if zeilen else ""
    zeiger = " " * (spalte - 1) + "^" if nr == zeile else ""
    meldung = [f"{pfad}, Zeile {zeile}, Spalte {spalte}: {erklaerung}", f"  {nr:>4} | {auszug}"]
    if zeiger:
        meldung.append(f"       | {zeiger}")
    meldung.append(f"  (YAML: {roh})")
    return ResolveFehler("\n".join(meldung))


def _yaml(pfad: Path) -> dict:
    if not pfad.is_file():
        raise ResolveFehler(f"Datei fehlt: {pfad}")
    text = pfad.read_text(encoding="utf-8")
    try:
        daten = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise _yaml_fehler(pfad, text, e) from None
    if daten is None:
        raise ResolveFehler(f"Datei ist leer: {pfad}")
    if not isinstance(daten, dict):
        raise ResolveFehler(f"Datei muss ein YAML-Objekt enthalten: {pfad}")
    return daten


def _klammer_dict(wert: object) -> bool:
    """`{354.82}` oder `{Event}` am Wertanfang liest YAML als Dictionary mit leeren Werten.

    Nicht gemeint ist ein Block, dessen Felder nur noch leer sind – etwa `leistung:` direkt nach
    `rechnung neu`; dort sagt die Meldung des Modells, was fehlt.
    """
    return (isinstance(wert, dict) and bool(wert) and all(v is None for v in wert.values())
            and not set(wert) <= set(Leistung.model_fields))


def _wert(wert: object) -> str:
    if _klammer_dict(wert):
        return "{" + ", ".join(str(k) for k in wert) + "}"  # type: ignore[union-attr]
    if isinstance(wert, str):
        return f"„{wert}“"
    return str(wert)


def _fehler(pfad: Path, e: ValidationError) -> ResolveFehler:
    zeilen = [f"{pfad}:"]
    for f in e.errors():
        feld = ".".join(str(t) for t in f["loc"])
        msg = f["msg"].removeprefix("Value error, ")
        wert = f.get("input")
        # Den Wert nur zeigen, wenn er zum Feld gehört: nicht bei fehlenden Feldern und nicht bei
        # Prüfungen über das ganze Objekt, deren input die ganze Datei ist.
        if f["type"] != "missing" and f["loc"] and not (isinstance(wert, dict) and not _klammer_dict(wert)):
            msg += f" (Wert: {_wert(wert)})"
        zeilen.append(f"  {feld}: {msg}" if f["loc"] else f"  {msg}")
        if _klammer_dict(wert):
            zeilen.append("    → Geschweifte Klammern entfernen: {…} am Anfang eines Werts macht YAML "
                          "zu einem Dictionary. Platzhalter durch den echten Wert ersetzen.")
    return ResolveFehler("\n".join(zeilen))


def stammdaten_ordner(cfg: config.Config, beispiel: bool = False) -> Path:
    """stammdaten/ im Gewerbe-Ordner, oder stammdaten.example/ im Demo-Modus."""
    if beispiel or cfg.demo:
        return config.BEISPIEL_STAMMDATEN
    return cfg.ordner("stammdaten")


def kunden_ordner(cfg: config.Config, beispiel: bool = False) -> Path:
    if beispiel or cfg.demo:
        return config.BEISPIEL_STAMMDATEN / "kunden"
    return cfg.ordner("kunden")


def lade_stammdaten(cfg: config.Config, beispiel: bool = False) -> Stammdaten:
    pfad = stammdaten_ordner(cfg, beispiel) / "ich.yaml"
    if not pfad.is_file():
        raise ResolveFehler(
            f"Stammdaten fehlen: {pfad}\n"
            f"`rechnung init --stammdaten` legt dort ein ausgefülltes Gerüst an."
        )
    try:
        return Stammdaten.model_validate(_yaml(pfad))
    except ValidationError as e:
        raise _fehler(pfad, e) from e


def lade_kunde(cfg: config.Config, kuerzel: str, beispiel: bool = False) -> Kunde:
    pfad = kunden_ordner(cfg, beispiel) / f"{kuerzel}.yaml"
    if not pfad.is_file():
        vorhanden = sorted(p.stem for p in kunden_ordner(cfg, beispiel).glob("*.yaml"))
        raise ResolveFehler(
            f"Kunde {kuerzel!r} nicht gefunden: {pfad}\n"
            f"Vorhanden: {', '.join(vorhanden) or '(keine)'}"
        )
    try:
        kunde = Kunde.model_validate(_yaml(pfad))
    except ValidationError as e:
        raise _fehler(pfad, e) from e
    kunde.kuerzel = kuerzel
    return kunde


def lade_input(ordner: Path) -> Input:
    pfad = ordner / INPUT_DATEI
    try:
        return Input.model_validate(_yaml(pfad))
    except ValidationError as e:
        raise _fehler(pfad, e) from e


# ---------------------------------------------------------------- Ordner und Nummer

def jahresordner(cfg: config.Config, jahr: int) -> Path:
    return cfg.ordner("ausgang") / str(jahr)


def neue_nummer(cfg: config.Config, jahr: int) -> str:
    lfd = rules.naechste_lfd(jahresordner(cfg, jahr))
    return rules.nummer(cfg.nummer_format, jahr, lfd)


def finde_ordner(cfg: config.Config, nummer: str) -> Path:
    """Findet den Rechnungsordner zu einer Nummer. Akzeptiert auch das Ende der Nummer."""
    wurzel = cfg.ordner("ausgang")
    treffer = [p for p in sorted(wurzel.glob("*/*")) if p.is_dir() and p.name == nummer]
    if not treffer:
        treffer = [p for p in sorted(wurzel.glob("*/*")) if p.is_dir() and p.name.endswith(nummer)]
    if not treffer:
        raise ResolveFehler(f"Keine Rechnung {nummer!r} unter {wurzel}")
    if len(treffer) > 1:
        namen = ", ".join(p.name for p in treffer)
        raise ResolveFehler(f"{nummer!r} ist mehrdeutig: {namen}")
    return treffer[0]


LEISTUNGSDATUM_PFLICHT = "# PFLICHT: Tag der Leistung, JJJJ-MM-TT"
TAETIGKEIT_PFLICHT = "# PFLICHT: was geleistet wird, in eigenen Worten"
EINORDNUNG_PFLICHT = "# PFLICHT: ein Wort aus der Liste unten"
ORT_KOMMENTAR = "# nur bei kulturell … unterhaltend: Land (z. B. GB) oder online"


def leistung_zeilen(taetigkeit: str | None, einordnung: str | None, ort: str | None) -> str:
    """Der leistung:-Block für `rechnung neu`: vorbefüllt, was angegeben ist, sonst leer und markiert."""
    def wert(w: str | None) -> str:
        return json.dumps(w, ensure_ascii=False) if w else ""
    zeilen = [
        f"  taetigkeit: {wert(taetigkeit)}" if taetigkeit else f"  taetigkeit:             {TAETIGKEIT_PFLICHT}",
        f"  einordnung: {einordnung}" if einordnung else f"  einordnung:             {EINORDNUNG_PFLICHT}",
        f"  ort: {ort}" if ort else f"  # ort:                  {ORT_KOMMENTAR}",
    ]
    return "\n".join(zeilen)

GERUEST = """\
# Rechnung {nummer}
# Die einzige Datei, die von Hand geschrieben wird. Alles andere leitet `rechnung bauen` ab.
# Nach jeder Änderung: `rechnung resolve {nummer}` zeigt, was daraus folgt.

kunde: {kuerzel}            # Datei stammdaten/kunden/{kuerzel}.yaml
datum: {datum}              # Rechnungsdatum
{leistungsdatum_zeile}
# leistungsdatum_bis:       # nur bei einem Zeitraum
{sprache_zeile}{waehrung_zeile}# zahlungsziel_tage: {zahlungsziel}   # Default aus der Config
# referenz:                 # Bestellnummer oder Event des Kunden, falls vorhanden
# einleitung:               # ein Satz über der Tabelle; ohne Angabe bleibt die Stelle leer

# Was geleistet wird und wie es nach § 3a UStG einzuordnen ist – daraus folgt der Leistungsort.
# Maßgeblich ist die Hauptleistung; Nebenleistungen wie Reisekosten folgen ihr.
leistung:
{leistung_zeilen}
#
# einordnung – genau ein Wort:
#   § 3a Abs. 3 Nr. 3 – an Privatpersonen gilt der Ort der Tätigkeit (ort: Land oder online):
#     kulturell | kuenstlerisch | wissenschaftlich | unterrichtend | sportlich | unterhaltend
#   § 3a Abs. 4 Satz 2 – an Privatpersonen im Drittland gilt deren Wohnsitz:
#     rechte              Nr. 1   Patente, Urheber-, Markenrechte und ähnliche Rechte
#     werbung             Nr. 2   Werbung, Öffentlichkeitsarbeit
#     beratung            Nr. 3   Rechtsanwalt, Steuerberater, Wirtschaftsprüfer, Sachverständiger,
#                                 Ingenieur, Aufsichtsrat, Dolmetscher, Übersetzer; rechtliche,
#                                 wirtschaftliche, technische Beratung
#     datenverarbeitung   Nr. 4
#     informationen       Nr. 5   Überlassung von Informationen, Verfahren, Erfahrungen
#     (nicht unterstützt) Nr. 6   Bank-, Finanz-, Versicherungsumsätze, Gold/Silber/Platin –
#                                 meist steuerfrei nach § 4 UStG; diese Befreiungen kennt das
#                                 Werkzeug nicht
#     personal            Nr. 7   Gestellung von Personal
#     verzicht-recht      Nr. 8   Verzicht auf ein Recht aus Nr. 1
#     verzicht-taetigkeit Nr. 9   Verzicht auf eine gewerbliche oder berufliche Tätigkeit
#     vermietung          Nr. 10  bewegliche Gegenstände, außer Beförderungsmittel
#     (weggefallen)       Nr. 11–13  heute § 3a Abs. 5 (Telekommunikation, Rundfunk,
#                                 elektronische Leistungen) – nicht unterstützt
#     energienetze        Nr. 14  Zugang zu Gas-, Strom-, Wärme-, Kältenetzen
#   § 3a Abs. 1 und 2 – keine der obigen:
#     sonstige
# Bei Unternehmern als Kunden ist der Leistungsort immer ihr Sitz; die Einordnung wird trotzdem
# festgehalten. Begriffe und Regeln: RULES.md, Teil 4.

positionen:
  - beschreibung: {beschreibung}
    menge: 1
    einheit: pauschal       # pauschal | stunde | tag | stueck | kilometer
    einzelpreis: 0.00
  # - beschreibung: Reisekosten Flug FRA-LON-FRA, Beleg anbei
  #   menge: 1
  #   einheit: pauschal
  #   einzelpreis: 0.00

# belege:                   # Dateinamen in belege/, z. B. flug.pdf
#   - flug.pdf

# Den Leistungsort leitet das Werkzeug selbst ab. Nur in Sonderfällen außerhalb von RULES.md
# festlegen – dann ist begruendung: Pflicht (RULES.md R37):
# leistungsort: CH
# begruendung: ...
"""


def neu(
    cfg: config.Config,
    kuerzel: str,
    leistungsdatum: date | None,
    datum: date | None = None,
    sprache: str | None = None,
    waehrung: str | None = None,
    taetigkeit: str | None = None,
    einordnung: str | None = None,
    ort: str | None = None,
) -> tuple[Path, str]:
    """Legt Ordner und vorbefülltes rechnung.yaml an. Gibt (Ordner, Nummer) zurück.

    Ohne Leistungsdatum bleibt das Feld leer und markiert; `resolve` bricht ab, bis es dasteht.
    Still das Rechnungsdatum einzusetzen hieße, eine Pflichtangabe zu raten. Ebenso die Einordnung
    der Leistung: ohne Angabe bleibt `leistung:` leer, mit der Liste der Begriffe als Kommentar.
    """
    kunde = lade_kunde(cfg, kuerzel)
    datum = datum or date.today()
    nummer = neue_nummer(cfg, datum.year)
    ordner = jahresordner(cfg, datum.year) / nummer
    if ordner.exists():
        raise ResolveFehler(f"Ordner existiert schon: {ordner}")
    ordner.mkdir(parents=True)
    (ordner / "belege").mkdir()

    sprache_zeile = f"sprache: {sprache}\n" if sprache else "# sprache: de | en\n"
    waehrung_zeile = f"waehrung: {waehrung}\n" if waehrung else "# waehrung: EUR | USD | GBP\n"
    leistungsdatum_zeile = (
        f"leistungsdatum: {leistungsdatum.isoformat()}" if leistungsdatum
        else f"leistungsdatum:             {LEISTUNGSDATUM_PFLICHT}"
    )
    (ordner / INPUT_DATEI).write_text(
        GERUEST.format(
            nummer=nummer,
            kuerzel=kuerzel,
            datum=datum.isoformat(),
            leistungsdatum_zeile=leistungsdatum_zeile,
            leistung_zeilen=leistung_zeilen(taetigkeit, einordnung, ort),
            sprache_zeile=sprache_zeile,
            waehrung_zeile=waehrung_zeile,
            zahlungsziel=cfg.zahlungsziel_tage,
            beschreibung=f"Leistung für {kunde.firma}",
        ),
        encoding="utf-8",
    )
    return ordner, nummer


# ---------------------------------------------------------------- Rechnen

def vorlage_version() -> str:
    """Git-Short-Hash des Repos beim Build; 'unbekannt', wenn kein Git da ist."""
    try:
        aus = subprocess.run(
            ["git", "-C", str(config.REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unbekannt"
    return aus.stdout.strip() or "unbekannt" if aus.returncode == 0 else "unbekannt"


def input_hash(ordner: Path) -> str:
    return hashlib.sha256((ordner / INPUT_DATEI).read_bytes()).hexdigest()


def regel_trace(entscheidung: rules.Entscheidung, waehrung: str) -> list[str]:
    """R35: die Regeln der Steuerentscheidung, dazu die Betragsregeln und, bei Fremdwährung, R34."""
    return [*entscheidung.regeln, "R32", "R33", *(["R34"] if waehrung != "EUR" else [])]


def rechne(
    eingabe: Input,
    stammdaten: Stammdaten,
    kunde: Kunde,
    cfg: config.Config,
    nummer: str,
    version: str = "unbekannt",
    hash_: str = "",
    eigen: dict[str, str] | None = None,
) -> Resolved:
    """Der eigentliche Kern: aus Eingabe, Stammdaten und Kunde wird das eingefrorene Ergebnis."""
    datum = eingabe.datum or date.today()
    sprache = eingabe.sprache or kunde.sprache or cfg.sprache
    waehrung = eingabe.waehrung or kunde.waehrung or cfg.waehrung

    entscheidung = rules.entscheide(kunde, eingabe.leistung, stammdaten, eingabe.leistungsort)
    basissatz = entscheidung.satz

    positionen: list[ResolvedPosition] = []
    for i, p in enumerate(eingabe.positionen, start=1):
        if p.steuersatz is not None and basissatz == rules.NULLSATZ:
            raise ResolveFehler(
                f"Position {i}: steuersatz ist gesetzt, aber das Ergebnis {entscheidung.ergebnis} weist "
                f"keine deutsche Umsatzsteuer aus (RULES.md R12). Den Satz aus der Position entfernen."
            )
        satz = p.steuersatz if p.steuersatz is not None else basissatz
        positionen.append(
            ResolvedPosition(
                pos=i,
                beschreibung=p.beschreibung,
                menge=p.menge,
                einheit=p.einheit,
                einheit_code=EINHEITEN[p.einheit],
                einzelpreis=rules.mindestens_zwei(p.einzelpreis),
                steuersatz=satz,
                zeilensumme=rules.runde(p.menge * p.einzelpreis),
            )
        )

    rules.waehrung_erlaubt(waehrung, [p.steuersatz for p in positionen])

    gruppen: list[Steuergruppe] = []
    for satz in sorted({p.steuersatz for p in positionen}, reverse=True):
        netto_gruppe = sum((p.zeilensumme for p in positionen if p.steuersatz == satz), Decimal(0))
        gruppen.append(
            Steuergruppe(
                satz=satz,
                netto=netto_gruppe,
                betrag=rules.runde(netto_gruppe * satz / Decimal(100)),
            )
        )

    netto = sum((g.netto for g in gruppen), Decimal(0))
    ust = sum((g.betrag for g in gruppen), Decimal(0))

    warnungen: list[str] = []
    if entscheidung.ergebnis == "reverse_charge":
        frist = rules.frist_reverse_charge(eingabe.leistungsdatum_bis or eingabe.leistungsdatum)
        if datum > frist:
            warnungen.append(
                f"Rechnungsdatum {datum} liegt nach der Frist {frist}: Bei Steuerschuldnerschaft des "
                f"Leistungsempfängers ist die Rechnung bis zum 15. des Folgemonats auszustellen "
                f"(§ 14a Abs. 1 Satz 2 UStG, RULES.md R30). Die Rechnung bleibt gültig."
            )

    return Resolved(
        nummer=nummer,
        datum=datum,
        leistungsdatum=eingabe.leistungsdatum,
        leistungsdatum_bis=eingabe.leistungsdatum_bis,
        faelligkeit=rules.faelligkeit(
            datum, eingabe.zahlungsziel_tage if eingabe.zahlungsziel_tage is not None else cfg.zahlungsziel_tage
        ),
        sprache=sprache,
        waehrung=waehrung,
        aussteller=stammdaten,
        kunde=kunde,
        leistung=eingabe.leistung,
        leistungsort=entscheidung.ort.land,
        leistungsort_manuell=eingabe.leistungsort is not None,
        begruendung=eingabe.begruendung,
        ergebnis=entscheidung.ergebnis,
        regeln=regel_trace(entscheidung, waehrung),
        hinweis=rules.hinweis(entscheidung, sprache),
        referenz=eingabe.referenz or kunde.referenz,
        einleitung=eingabe.einleitung,
        positionen=positionen,
        steuergruppen=gruppen,
        netto=rules.runde(netto),
        ust_betrag=rules.runde(ust),
        brutto=rules.runde(netto + ust),
        belege=eingabe.belege,
        vorlage_version=version,
        vorlage_eigen=eigen,
        input_hash=hash_,
        erzeugt_am=datetime.now().astimezone(),
        warnungen=warnungen,
    )


def resolve(cfg: config.Config, nummer: str, schreiben: bool = True) -> tuple[Resolved, Path]:
    """Löst eine bestehende Rechnung auf und schreibt das Ergebnis neben die Eingabe."""
    ordner = finde_ordner(cfg, nummer)
    eingabe = lade_input(ordner)
    stammdaten = lade_stammdaten(cfg)
    kunde = lade_kunde(cfg, eingabe.kunde)
    ergebnis = rechne(
        eingabe, stammdaten, kunde, cfg,
        nummer=ordner.name,
        version=vorlage_version(),
        hash_=input_hash(ordner),
        eigen=vorlage.nachweis(cfg.vorlage),
    )
    ziel = ordner / RESOLVED_DATEI
    if schreiben:
        ziel.write_text(
            json.dumps(json.loads(ergebnis.model_dump_json(by_alias=True)), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return ergebnis, ziel
