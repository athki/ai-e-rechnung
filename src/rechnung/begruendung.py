"""Begründung je Rechnung: die Steuerentscheidung als lesbare Kette für Prüfer (RULES.md R35).

Die Begründung entscheidet nichts und rechnet nichts. Sie liest die eingefrorene
`rechnung.resolved.json` und die Regeln aus RULES.md (Teil 3, Teil 2 für die Quellen) und legt
nebeneinander: die Fakten, auf denen entschieden wurde (über `rules.merkmale()`, dieselbe
Übersetzung wie in `resolve`), die Regeln der Spur in ihrer Reihenfolge mit Status und Nachweis, und
was davon wie gesichert ist.

Ein einziges Mal fragt sie `rules.entscheide()` selbst: um zu prüfen, dass die Spur in der Datei zu
den Fakten passt. Weicht sie ab, sagt die Begründung das und gilt als rot.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from rechnung import config, festschreiben, resolve, rules
from rechnung.models import Resolved

RULES_MD = config.REPO / "RULES.md"

FELDER = ("Quelle", "Regel", "Annahmen", "Werkzeug", "Status", "Nachweis")
PFLICHT = ("Quelle", "Status", "Nachweis")
STATUS = ("Annahme – ungeprüft", "Werkzeug-Entscheidung", "bestätigt")
NACHWEISE = ("bewiesen", "getestet", "im PDF geprüft", "keiner")

KATEGORIE_TEXT = {
    rules.INLAND: "Inland",
    rules.EU: "übriges Gemeinschaftsgebiet (EU)",
    rules.DRITTLAND: "Drittlandsgebiet",
}
GRUPPE_TEXT = {
    rules.TAETIGKEIT: "Tätigkeitsleistung",
    rules.KATALOG: "Katalogleistung",
    rules.GRUNDREGEL: "Grundregel",
}
ORT_QUELLE_TEXT = {
    rules.ORT_KUNDE: "Sitz bzw. Wohnsitz des Kunden",
    rules.ORT_TAETIGKEIT: "Ort der Tätigkeit",
    rules.ORT_AUSSTELLER: "Sitz des Ausstellers",
    rules.ORT_FESTGELEGT: "manuell festgelegt",
}
# Bei welcher Regel der Pflichttext aus `hinweis` steht (R16, R28, R31 – je „genau bei“ diesem Ergebnis).
HINWEIS_REGEL = {"kleinunternehmer": "R16", "reverse_charge": "R28", "nicht_steuerbar": "R31"}


class BegruendungFehler(Exception):
    """Die Begründung lässt sich nicht erstellen (Datei fehlt, RULES.md hat nicht die erwartete Form)."""


# ---------------------------------------------------------------- RULES.md lesen

@dataclass(frozen=True)
class Regel:
    id: str
    titel: str
    felder: dict[str, str]

    @property
    def nachweis(self) -> str:
        """Die Stufe: das erste Wort bzw. die ersten Wörter der Zeile `Nachweis:`."""
        return next(n for n in NACHWEISE if _beginnt_mit(self.felder["Nachweis"], n))


def _beginnt_mit(text: str, wort: str) -> bool:
    return re.match(re.escape(wort) + r"(?!\w)", text) is not None


def regeln_lesen(text: str) -> tuple[dict[str, Regel], dict[str, str]]:
    """Die Regeln aus Teil 3 (ohne entfallene) und die Überschriften der Quellen aus Teil 2.

    Streng: Ein Feld, das es nicht gibt, ein fehlendes Pflichtfeld oder ein Status bzw. Nachweis
    außerhalb der festen Listen bricht ab, statt eine halbe Begründung zu liefern.
    """
    regeln: dict[str, Regel] = {}
    quellen: dict[str, str] = {}
    aktuell: tuple[str, str] | None = None
    felder: dict[str, list[str]] = {}
    feld: str | None = None

    def abschliessen() -> None:
        if aktuell is None:
            return
        rid, titel = aktuell
        # Erste Zeile leer, wenn das Feld mit einer Aufzählung beginnt (R3, Annahmen); sie bleibt erhalten.
        fertig = {name: "\n".join(zeilen).rstrip() for name, zeilen in felder.items()}
        for pflicht in PFLICHT:
            if not fertig.get(pflicht, "").strip():
                raise BegruendungFehler(f"RULES.md, {rid}: Feld `{pflicht}:` fehlt.")
        if not any(_beginnt_mit(fertig["Status"], s) for s in STATUS):
            raise BegruendungFehler(f"RULES.md, {rid}: Status muss mit einem von {STATUS} beginnen.")
        if not any(_beginnt_mit(fertig["Nachweis"], n) for n in NACHWEISE):
            raise BegruendungFehler(f"RULES.md, {rid}: Nachweis muss mit einem von {NACHWEISE} beginnen.")
        regeln[rid] = Regel(rid, titel, fertig)

    for zeile in text.splitlines():
        if (m := re.match(r"^### (Q\d+) – (.+)$", zeile)):
            quellen[m.group(1)] = m.group(2).strip()
        if zeile.startswith("#") or zeile.startswith("---"):
            abschliessen()
            aktuell, felder, feld = None, {}, None
            m = re.match(r"^#### (R\d+) – (.+)$", zeile)
            if m and not m.group(2).startswith("(entfallen)"):
                aktuell = (m.group(1), m.group(2).strip())
            continue
        if aktuell is None:
            continue
        if (m := re.match(r"^- \*\*(\w+):\*\*\s?(.*)$", zeile)):
            feld = m.group(1)
            if feld not in FELDER:
                raise BegruendungFehler(f"RULES.md, {aktuell[0]}: unbekanntes Feld `{feld}:`.")
            if feld in felder:
                raise BegruendungFehler(f"RULES.md, {aktuell[0]}: Feld `{feld}:` doppelt.")
            felder[feld] = [m.group(2)]
        elif zeile.startswith("  ") and feld is not None:
            felder[feld].append(zeile[2:])
        elif zeile.strip() == "":
            if feld is not None:
                felder[feld].append("")
        else:
            raise BegruendungFehler(f"RULES.md, {aktuell[0]}: Zeile außerhalb eines Felds: {zeile!r}")
    abschliessen()
    return regeln, quellen


def regeln_laden(pfad: Path = RULES_MD) -> tuple[dict[str, Regel], dict[str, str]]:
    try:
        return regeln_lesen(pfad.read_text(encoding="utf-8"))
    except OSError as e:
        raise BegruendungFehler(f"RULES.md nicht lesbar ({pfad}): {e}") from e


# ---------------------------------------------------------------- Stand der Rechnung

@dataclass(frozen=True)
class Stand:
    """Was für ein Dokument der Ordner hält und was sich seit dem Auflösen geändert hat."""

    dokument: str                 # eine Zeile für den Kopf
    pro_forma: bool               # eine gesendete Pro-forma-Revision
    revisionen: int               # Pro-forma-Revisionen im Rechnungsordner (nur dort)
    eingabe_geaendert: bool       # rechnung.yaml passt nicht mehr zu input_hash


def stand(ordner: Path, r: Resolved) -> Stand:
    eingabe = ordner / resolve.INPUT_DATEI
    geaendert = eingabe.is_file() and resolve.input_hash(ordner) != r.input_hash
    if ordner.parent.name == festschreiben.PRO_FORMA_ORDNER and ordner.name.isdigit():
        n = int(ordner.name)
        status = festschreiben.status_lesen(ordner.parent.parent)
        eintrag = next((e for e in status.get("pro_forma") or [] if e.get("revision") == n), None)
        gesendet = eintrag.get("gesendet_am", "unbekannt") if eintrag else "unbekannt (fehlt in status.yaml)"
        return Stand(f"Pro-forma-Revision {n}, gesendet am {gesendet}", True, 0, geaendert)
    status = festschreiben.status_lesen(ordner)
    revisionen = len(status.get("pro_forma") or [])
    if status.get("status") == festschreiben.FESTGESCHRIEBEN:
        dokument = f"Rechnung, festgeschrieben, gesendet am {status.get('gesendet_am', 'unbekannt')}"
    else:
        dokument = "Rechnung, Entwurf (nicht festgeschrieben)"
    return Stand(dokument, False, revisionen, geaendert)


# ---------------------------------------------------------------- Spur prüfen

@dataclass(frozen=True)
class Spur:
    passt: bool
    ort_quelle: str | None        # aus kern(); None, wenn die Entscheidung heute nicht zustande kommt
    ort_regeln: tuple[str, ...]
    abweichung: str | None


def _festgelegt(r: Resolved) -> str | None:
    return r.leistungsort if r.leistungsort_manuell else None


def spur_pruefen(r: Resolved) -> Spur:
    """Kommt `rules.entscheide()` auf den Fakten der Datei heute zu derselben Entscheidung?"""
    try:
        e = rules.entscheide(r.kunde, r.leistung, r.aussteller, _festgelegt(r))
        k = rules.kern(rules.merkmale(r.kunde, r.leistung, r.aussteller, _festgelegt(r)))
    except rules.RegelFehler as f:
        return Spur(False, None, (), f"Heute bricht das Werkzeug auf diesen Fakten ab: {f}")
    assert isinstance(k, rules.KernErgebnis)   # sonst hätte entscheide() abgebrochen
    unterschiede = []
    regeln = resolve.regel_trace(e, r.waehrung)
    if regeln != r.regeln:
        unterschiede.append(f"Regeln heute {' '.join(regeln)}, in der Datei {' '.join(r.regeln)}")
    if e.ergebnis != r.ergebnis:
        unterschiede.append(f"Ergebnis heute {e.ergebnis}, in der Datei {r.ergebnis}")
    if e.ort.land != r.leistungsort:
        unterschiede.append(f"Leistungsort heute {e.ort.land}, in der Datei {r.leistungsort}")
    for p in r.positionen:
        satz = rules.satz_position(int(e.satz), r.aussteller.kleinunternehmer, p.steuersatz == 7)
        if isinstance(satz, rules.Abbruch) or satz != p.steuersatz:
            unterschiede.append(f"Position {p.pos}: Satz heute {satz}, in der Datei {p.steuersatz}")
    return Spur(not unterschiede, k.ort_quelle, e.ort.regeln, "; ".join(unterschiede) or None)


# ---------------------------------------------------------------- Text

def _zelle(wert: object) -> str:
    return str(wert).replace("|", "\\|").replace("\n", " ")


def _kategorie(land: str) -> str:
    try:
        return KATEGORIE_TEXT[rules.kategorie(land)]
    except rules.RegelFehler:
        return "unbekannt (nicht in rules.LAENDER)"


def _land(land: str) -> str:
    try:
        return f"{land} ({rules.land_name(land, 'de')})"
    except rules.RegelFehler:
        return land


def _ja_nein(wert: bool | None) -> str:
    return "nicht angegeben" if wert is None else ("ja" if wert else "nein")


def fakten(r: Resolved) -> list[tuple[str, str, str, str]]:
    """Die Angaben, auf denen entschieden wurde: (Angabe, Herkunft, Wert, was das Werkzeug daraus liest)."""
    kunde = f"kunden/{r.kunde.kuerzel or '<kuerzel>'}.yaml"
    gruppe, fundstelle = rules.EINORDNUNGEN[r.leistung.einordnung]
    ort = r.leistung.ort
    zeilen = [
        ("Land des Kunden", f"`{kunde}: land`", r.kunde.land, f"{_kategorie(r.kunde.land)} (R1)"),
        ("Unternehmer", f"`{kunde}: unternehmer`", _ja_nein(r.kunde.unternehmer), ""),
        ("USt-IdNr. des Kunden", f"`{kunde}: ustid`", r.kunde.ustid or "–", ""),
        ("Leistung", "`rechnung.yaml: leistung.taetigkeit`", r.leistung.taetigkeit, ""),
        ("Einordnung", "`rechnung.yaml: leistung.einordnung`", r.leistung.einordnung,
         f"{GRUPPE_TEXT[gruppe]}, {fundstelle}"),
        ("Ort der Tätigkeit", "`rechnung.yaml: leistung.ort`", ort or "–",
         "" if ort is None else ("virtuell" if ort == "online" else _kategorie(ort))),
        ("Sitz des Ausstellers", "`ich.yaml: land`", r.aussteller.land, _kategorie(r.aussteller.land)),
        ("Kleinunternehmer", "`ich.yaml: kleinunternehmer`", _ja_nein(r.aussteller.kleinunternehmer),
         "§ 19 UStG" if r.aussteller.kleinunternehmer else ""),
        ("USt-IdNr. des Ausstellers", "`ich.yaml: ustid`", r.aussteller.ustid or "–", ""),
    ]
    if r.leistungsort_manuell:
        zeilen.append(("Leistungsort festgelegt", "`rechnung.yaml: leistungsort`", r.leistungsort,
                       f"{_kategorie(r.leistungsort)} (R37)"))
    for p in r.positionen:
        if p.steuersatz == 7:
            zeilen.append((f"Ermäßigter Satz, Position {p.pos}", f"`rechnung.yaml: positionen[{p.pos}].steuersatz`",
                           "7", "§ 12 Abs. 2 UStG (R10)"))
    return zeilen


def _feld(name: str, text: str) -> str:
    """Ein Feld aus RULES.md als Aufzählungspunkt; Folgezeilen behalten ihre Einrückung."""
    zeilen = text.split("\n")
    erste = f"- **{name}:** {zeilen[0]}" if zeilen[0] else f"- **{name}:**"
    return "\n".join([erste, *(f"  {z}" if z else "" for z in zeilen[1:])])


SCHLUSS = """\
## Was davon wie gesichert ist

Diese Begründung entscheidet nichts. Sie liest die eingefrorene `rechnung.resolved.json` und die Regeln
aus RULES.md.

- **Angenommen – die Fakten.** Ob der Kunde Unternehmer ist, wo er sitzt, wo die Leistung erbracht
  wurde und wie sie einzuordnen ist, hat ein Mensch (oder eine AI) angegeben. Das Werkzeug prüft es
  nicht. Die vollständige Liste dieser Annahmen steht formal in `lean/Rechnung/Bruecke.lean` (`Passt`).
- **Angenommen – die Regeln.** Jede Regel gibt das zitierte Recht nach begründetem Verständnis wieder.
  Ein Steuerberater hat RULES.md nicht geprüft; deshalb steht keine Regel auf „bestätigt“.
- **Bewiesen – das Modell.** Für die Regeln mit Nachweis „bewiesen“ ist in Lean bewiesen, dass ein
  Modell der Entscheidung sie einhält, unter den Annahmen aus `Passt` (`lean/`, nur Leans
  Standardaxiome). Darunter: Ohne Festlegung entscheidet das Werkzeug nie anders als das Gesetz.
- **Abgeglichen – der Code.** `rules.kern()` und `rules.satz_position()` antworten auf jede mögliche
  Eingabe wie das Modell. Das ist ein vollständiger Vergleich, kein Beweis; Leans Compiler wird dafür
  vertraut.
- **Getestet.** Die Zuordnung Ländercode → Kategorie (R1), Nummern (R23), Beträge (R32, R33) und
  Währung (R34).
- **Geprüft.** Ob die Pflichtangaben in der PDF stehen, prüft `rechnung pruefen`.
"""

SCHLUSS_FESTLEGUNG = """
- **Festlegung.** Den Leistungsort hat der Mensch festgelegt (R37) und verantwortet ihn mit seiner
  Begründung. Bewiesen ist nur, dass ab dem festgelegten Ort alles dem Gesetz folgt; „nie anders als
  das Gesetz“ gilt nur ohne Festlegung.
"""


def text(r: Resolved, regeln: dict[str, Regel], quellen: dict[str, str], st: Stand, spur: Spur,
         heute: str) -> str:
    """Die Begründung als Markdown."""
    fehlend = [rid for rid in r.regeln if rid not in regeln]
    if fehlend:
        raise BegruendungFehler(f"RULES.md hat keinen Eintrag für {', '.join(fehlend)} (Regeln der Spur).")

    achtung: list[str] = []
    if st.eingabe_geaendert:
        achtung.append("`rechnung.yaml` wurde nach dem letzten `resolve` geändert. Diese Begründung zeigt "
                       "den Stand von `rechnung.resolved.json`; für den neuen Stand erst `rechnung resolve`.")
    gebaut = r.vorlage_version
    if "unbekannt" in (gebaut, heute):
        regelstand = f"beim Bau `{gebaut}`, heute `{heute}` – ohne Git nicht vergleichbar"
    elif gebaut != heute:
        regelstand = f"beim Bau `{gebaut}`, heute `{heute}`"
        achtung.append(f"Die Texte der Regeln stammen aus dem heutigen Stand `{heute}`, gebaut wurde mit "
                       f"`{gebaut}`. Den damaligen Wortlaut zeigt `git checkout {gebaut}`.")
    else:
        regelstand = f"`{gebaut}`, beim Bau und heute gleich"
    if spur.passt:
        spurtext = "geprüft – `rules.entscheide()` kommt auf denselben Fakten heute zu derselben Entscheidung."
    else:
        spurtext = "**weicht ab**"
        achtung.append(f"Die Spur in der Datei passt nicht zur heutigen Entscheidung: {spur.abweichung}")
    achtung += [f"Warnung aus `resolve`: {w}" for w in r.warnungen]

    ort = _land(r.leistungsort)
    if spur.ort_quelle:
        ort += f", {ORT_QUELLE_TEXT[spur.ort_quelle]} ({', '.join(spur.ort_regeln)})"
    kopf = [
        f"# Begründung der Steuerentscheidung – Rechnung {r.nummer}",
        "",
        f"- **Dokument:** {st.dokument}",
        f"- **Kunde:** {r.kunde.firma} ({r.kunde.land})",
        f"- **Ergebnis:** `{r.ergebnis}`",
        f"- **Leistungsort:** {ort}",
    ]
    if r.leistungsort_manuell:
        kopf.append(f"- **Begründung der Festlegung:** „{r.begruendung}“")
    if st.pro_forma:
        kopf.append("- **Pro forma:** Die Kennzeichnung ändert Leistungsort, Ergebnis, Satz und Beträge nicht "
                    "(R38); die Entscheidung ist dieselbe wie für die Rechnung.")
    if st.revisionen:
        kopf.append(f"- **Pro-forma-Revisionen:** {st.revisionen}; jede hat ihre eigene Begründung "
                    f"(`rechnung begruendung <ordner>/pro-forma/<n>`).")
    kopf += [f"- **Regelstand:** {regelstand}", f"- **Spur:** {spurtext}"]

    teile = ["\n".join(kopf), *(f"> **Achtung:** {a}" for a in achtung)]
    teile.append(
        "## Fakten\n\n"
        "Angegeben von Mensch oder AI, vom Werkzeug nicht geprüft. Die Werte stammen aus "
        "`rechnung.resolved.json`, also aus Kunden- und Stammdaten im Stand des Auflösens.\n\n"
        "| Angabe | Herkunft | Wert | Das Werkzeug liest daraus |\n| --- | --- | --- | --- |\n"
        + "\n".join(f"| {' | '.join(_zelle(w) for w in z)} |" for z in fakten(r))
    )

    kette = ["## Regeln in der Reihenfolge der Spur", "",
             "Wortlaut, Status und Nachweis aus RULES.md Teil 3. Status: gibt die Regel das Gesetz richtig "
             "wieder? Nachweis: setzt das Werkzeug sie so um, wie sie dasteht?"]
    for i, rid in enumerate(r.regeln, start=1):
        regel = regeln[rid]
        punkte = [_feld("Quelle", regel.felder["Quelle"])]
        if "Regel" in regel.felder:
            punkte.append(_feld("Regel", regel.felder["Regel"]))
        punkte.append(_feld("Annahmen", regel.felder.get("Annahmen") or "keine angegeben."))
        punkte.append(_feld("Status", regel.felder["Status"]))
        punkte.append(_feld("Nachweis", regel.felder["Nachweis"]))
        if r.hinweis and HINWEIS_REGEL.get(r.ergebnis) == rid:
            for wortlaut in r.hinweis.values():
                punkte.append(f"- **Auf der Rechnung:** „{wortlaut}“")
        if rid == "R37" and r.leistungsort_manuell:
            punkte.append(f"- **Begründung der Festlegung:** „{r.begruendung}“")
            punkte.append("- **Fundstelle aus § 3a:** keine – den Ort hat der Mensch festgelegt.")
        kette += ["", f"### {i}. {rid} – {regel.titel}", "", *punkte]
    teile.append("\n".join(kette))

    genannt = sorted({q for rid in r.regeln for q in re.findall(r"\bQ\d+\b", regeln[rid].felder["Quelle"])},
                     key=lambda q: int(q[1:]))
    teile.append("## Quellen\n\nWortlaut in RULES.md Teil 2.\n\n"
                 + "\n".join(f"- **{q}** – {quellen.get(q, 'fehlt in RULES.md')}" for q in genannt))

    teile.append(SCHLUSS.rstrip("\n") + (SCHLUSS_FESTLEGUNG.rstrip("\n") if r.leistungsort_manuell else ""))
    return "\n\n".join(teile) + "\n"


def lade(ordner: Path) -> Resolved:
    pfad = ordner / resolve.RESOLVED_DATEI
    if not pfad.is_file():
        raise BegruendungFehler(
            f"{pfad} fehlt. Erst `rechnung resolve {ordner.name}` ausführen. Bricht das ab, wurde nichts "
            f"entschieden; die Meldung nennt dann Regel und Feld."
        )
    try:
        return Resolved.model_validate(json.loads(pfad.read_text(encoding="utf-8")))
    except (ValueError, ValidationError) as e:
        raise BegruendungFehler(f"{pfad} ist nicht lesbar: {e}") from e


def begruende(ordner: Path) -> tuple[str, bool]:
    """Begründung für den Rechnungsordner (auch `pro-forma/<n>`); zweiter Wert: passt die Spur?"""
    r = lade(ordner)
    regeln, quellen = regeln_laden()
    spur = spur_pruefen(r)
    return text(r, regeln, quellen, stand(ordner, r), spur, resolve.vorlage_version()), spur.passt
