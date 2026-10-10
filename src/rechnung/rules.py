"""Die Regeln: Leistungsort, Ergebnis, Steuersatz, Hinweistext, Fälligkeit, Rechnungsnummer.

Umsetzung von RULES.md; die Regel-IDs (R1 …) im Code verweisen dorthin.
Jede Funktion hier hat einen Test in tests/test_rules.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from rechnung.models import TAETIGKEITEN, Ergebnis, Kunde, Leistung, Stammdaten

# EU-Mitgliedstaaten, Stand 2026-09-23. Vereinigtes Königreich seit 2021 Drittland.
# Bei einer Änderung: Datum hier nachziehen.
EU_LAENDER: frozenset[str] = frozenset({
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
    "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
})

# Ländernamen für den Steuerhinweis (nicht_steuerbar nennt den Leistungsort im Klartext).
LAENDER: dict[str, tuple[str, str]] = {
    "AE": ("Vereinigte Arabische Emirate", "United Arab Emirates"),
    "AT": ("Österreich", "Austria"),
    "AU": ("Australien", "Australia"),
    "BE": ("Belgien", "Belgium"),
    "BG": ("Bulgarien", "Bulgaria"),
    "BR": ("Brasilien", "Brazil"),
    "CA": ("Kanada", "Canada"),
    "CH": ("Schweiz", "Switzerland"),
    "CN": ("China", "China"),
    "CY": ("Zypern", "Cyprus"),
    "CZ": ("Tschechien", "Czechia"),
    "DE": ("Deutschland", "Germany"),
    "DK": ("Dänemark", "Denmark"),
    "EE": ("Estland", "Estonia"),
    "ES": ("Spanien", "Spain"),
    "FI": ("Finnland", "Finland"),
    "FR": ("Frankreich", "France"),
    "GB": ("Vereinigtes Königreich", "United Kingdom"),
    "GR": ("Griechenland", "Greece"),
    "HR": ("Kroatien", "Croatia"),
    "HU": ("Ungarn", "Hungary"),
    "IE": ("Irland", "Ireland"),
    "IL": ("Israel", "Israel"),
    "IN": ("Indien", "India"),
    "IS": ("Island", "Iceland"),
    "IT": ("Italien", "Italy"),
    "JP": ("Japan", "Japan"),
    "KR": ("Südkorea", "South Korea"),
    "LI": ("Liechtenstein", "Liechtenstein"),
    "LT": ("Litauen", "Lithuania"),
    "LU": ("Luxemburg", "Luxembourg"),
    "LV": ("Lettland", "Latvia"),
    "MT": ("Malta", "Malta"),
    "MX": ("Mexiko", "Mexico"),
    "NL": ("Niederlande", "Netherlands"),
    "NO": ("Norwegen", "Norway"),
    "NZ": ("Neuseeland", "New Zealand"),
    "PL": ("Polen", "Poland"),
    "PT": ("Portugal", "Portugal"),
    "RO": ("Rumänien", "Romania"),
    "SE": ("Schweden", "Sweden"),
    "SG": ("Singapur", "Singapore"),
    "SI": ("Slowenien", "Slovenia"),
    "SK": ("Slowakei", "Slovakia"),
    "TR": ("Türkei", "Türkiye"),
    "US": ("Vereinigte Staaten", "United States"),
    "ZA": ("Südafrika", "South Africa"),
}

REGELSATZ = Decimal(19)
NULLSATZ = Decimal(0)


class RegelFehler(Exception):
    """Der Fall ist nicht entscheidbar oder die Angaben passen nicht zusammen."""


def land_name(land: str, sprache: str = "de") -> str:
    if land not in LAENDER:
        raise RegelFehler(
            f"Land {land} ist in rules.LAENDER nicht hinterlegt. Eintragen (deutscher und "
            f"englischer Name), damit der Steuerhinweis den Leistungsort nennen kann."
        )
    return LAENDER[land][0 if sprache == "de" else 1]


# ---------------------------------------------------------------- Leistungsort (RULES.md R1–R9)

INLAND, EU, DRITTLAND = "inland", "eu", "drittland"
TAETIGKEIT, KATALOG, GRUNDREGEL = "taetigkeit", "katalog", "grundregel"

# Einordnung -> (Gruppe, Fundstelle). Die Wörter sind die Begriffe aus § 3a UStG; RULES.md Teil 4
# führt dieselbe Tabelle, tests/test_rules.py hält beide und models.Einordnung zusammen.
EINORDNUNGEN: dict[str, tuple[str, str]] = {
    **{wort: (TAETIGKEIT, "§ 3a Abs. 3 Nr. 3 UStG") for wort in TAETIGKEITEN},
    "rechte": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 1 UStG"),
    "werbung": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 2 UStG"),
    "beratung": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 3 UStG"),
    "datenverarbeitung": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 4 UStG"),
    "informationen": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 5 UStG"),
    "personal": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 7 UStG"),
    "verzicht-recht": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 8 UStG"),
    "verzicht-taetigkeit": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 9 UStG"),
    "vermietung": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 10 UStG"),
    "energienetze": (KATALOG, "§ 3a Abs. 4 Satz 2 Nr. 14 UStG"),
    "sonstige": (GRUNDREGEL, "§ 3a Abs. 1 und 2 UStG"),
}


def kategorie(land: str) -> str:
    """R1: Inland, übriges Gemeinschaftsgebiet oder Drittlandsgebiet (§ 1 Abs. 2a UStG)."""
    if land == "DE":
        return INLAND
    return EU if land in EU_LAENDER else DRITTLAND


# ---------------------------------------------------------------- Der Entscheidungskern
#
# Die Steuerentscheidung hängt nur von wenigen Merkmalen ab. `kern()` rechnet ausschließlich mit
# ihnen: keine Ländercodes, keine Texte, keine Ausnahmen. So ist die Menge aller Eingaben endlich
# und klein, und das Lean-Modell (RULES.md, Schritt 8.6) kann sie vollständig gegen diese Funktion
# prüfen. `entscheide()` übersetzt Kunde, Leistung und Aussteller in Merkmale und das Ergebnis
# zurück in Länder und Meldungen.

ORT_KUNDE, ORT_TAETIGKEIT, ORT_AUSSTELLER, ORT_FESTGELEGT = "kunde", "taetigkeit", "aussteller", "festgelegt"


@dataclass(frozen=True)
class Merkmale:
    """Alles, wovon die Steuerentscheidung abhängt (RULES.md Teil 4)."""

    kunde: str                    # Kategorie des Kundenlands: inland | eu | drittland
    unternehmer: bool | None      # aus der Kundendatei; None = nicht angegeben
    kunde_ustid: bool             # Kunde hat eine USt-IdNr.
    gruppe: str                   # Gruppe der Einordnung: taetigkeit | katalog | grundregel
    taetigkeit_ort: str | None    # nur bei taetigkeit: inland | eu | drittland | online
    kleinunternehmer: bool        # Aussteller nach § 19 UStG
    aussteller_ustid: bool        # Aussteller hat eine USt-IdNr.
    aussteller_inland: bool       # Aussteller betreibt sein Unternehmen vom Inland aus (R4)
    festgelegt: str | None        # manuell festgelegter Leistungsort: inland | eu | drittland (R37)


@dataclass(frozen=True)
class KernErgebnis:
    """Leistungsort als Quelle und Kategorie, dazu Ergebnis, Satz und angewandte Regeln."""

    ort_quelle: str               # kunde | taetigkeit | aussteller | festgelegt
    ort: str                      # inland | eu | drittland
    ergebnis: Ergebnis
    satz: int                     # 19 oder 0; 7 % wählt der Mensch je Position (R10)
    regeln: tuple[str, ...]


@dataclass(frozen=True)
class Abbruch:
    """Das Werkzeug entscheidet nicht und sagt, warum (Grundsatz: strenger, nie anders)."""

    regel: str                    # R4, R18, R19 oder R29; bei satz_position() R12 oder R14
    grund: str                    # aussteller_ausland | unternehmer_fehlt | eu_privat | kunde_ustid_fehlt
                                  # | eigene_ustid_fehlt | satz_ohne_steuer


def kern(m: Merkmale) -> KernErgebnis | Abbruch:
    """Die Entscheidungstabelle aus RULES.md Teil 4, als reine Funktion über Merkmale."""
    # R4: Das Werkzeug bildet das deutsche UStG ab und rechnet nur für Aussteller mit Sitz im Inland.
    if not m.aussteller_inland:
        return Abbruch("R4", "aussteller_ausland")

    # R3-Annahme: Ein EU-Kunde mit USt-IdNr. gilt als Unternehmer, wenn nichts anderes angegeben ist.
    unternehmer = m.unternehmer
    if unternehmer is None and m.kunde == EU and m.kunde_ustid:
        unternehmer = True

    # Leistungsort (R3–R8, R37)
    if m.festgelegt is not None:
        quelle, ort, ort_regeln = ORT_FESTGELEGT, m.festgelegt, ("R37",)
    elif unternehmer:
        quelle, ort, ort_regeln = ORT_KUNDE, m.kunde, ("R3",)
    elif unternehmer is None:
        # Im Inland führt jede Antwort zum Inland – außer eine Tätigkeit wird woanders erbracht (R19).
        if m.kunde != INLAND or m.gruppe == TAETIGKEIT:
            return Abbruch("R19", "unternehmer_fehlt")
        quelle, ort, ort_regeln = ORT_AUSSTELLER, INLAND, ("R3", "R4")
    elif m.gruppe == TAETIGKEIT:
        if m.taetigkeit_ort == "online":
            quelle, ort, ort_regeln = ORT_KUNDE, m.kunde, ("R6",)
        else:
            assert m.taetigkeit_ort is not None   # models.Leistung verlangt den Ort
            quelle, ort, ort_regeln = ORT_TAETIGKEIT, m.taetigkeit_ort, ("R5",)
    elif m.gruppe == KATALOG and m.kunde == DRITTLAND:
        quelle, ort, ort_regeln = ORT_KUNDE, m.kunde, ("R7",)
    else:
        quelle, ort, ort_regeln = ORT_AUSSTELLER, INLAND, ("R8",) if m.gruppe == KATALOG else ("R4",)

    regeln = ["R1", "R2", *ort_regeln, "R9"]
    ku = m.kleinunternehmer
    if ort == INLAND:
        ergebnis: Ergebnis = "kleinunternehmer" if ku else "inland"
        regeln += ["R13", "R16"] if ku else ["R10"]
    elif ort == EU:
        if unternehmer is None:
            # Nur bei festgelegtem Ort möglich: Unternehmer → Reverse Charge, Privatperson → R18.
            return Abbruch("R19", "unternehmer_fehlt")
        if not unternehmer:
            return Abbruch("R18", "eu_privat")
        ergebnis = "reverse_charge"
        if ku:
            # § 19 Abs. 1 Satz 2 UStG schließt § 14a Abs. 1 Satz 3 aus: keine USt-IdNrn. nötig (R15).
            regeln += ["R11", "R15", "R28", "R30"]
        else:
            if not m.kunde_ustid:
                return Abbruch("R29", "kunde_ustid_fehlt")
            if not m.aussteller_ustid:
                return Abbruch("R29", "eigene_ustid_fehlt")
            regeln += ["R11", "R28", "R29", "R30"]
    else:
        ergebnis = "nicht_steuerbar"
        regeln += ["R17", "R31"] if ku else ["R31"]
    satz = 19 if ergebnis == "inland" else 0
    if satz == 0:
        regeln.append("R14" if ku else "R12")
    return KernErgebnis(quelle, ort, ergebnis, satz, tuple(regeln))


def satz_position(satz: int, kleinunternehmer: bool, ermaessigt: bool) -> int | Abbruch:
    """Satz einer Position: der Satz der Rechnung, oder 7 %, wenn der Mensch die Position als
    ermäßigt einordnet (§ 12 Abs. 2 UStG, R10). Ermäßigt geht nur, wo deutsche Steuer ausgewiesen
    wird; sonst Abbruch (R14 beim Kleinunternehmer, sonst R12)."""
    if not ermaessigt:
        return satz
    if satz == 0:
        return Abbruch("R14" if kleinunternehmer else "R12", "satz_ohne_steuer")
    return 7


# ---------------------------------------------------------------- Übersetzung: Daten ↔ Merkmale

# Fundstelle für den Hinweistext, je nachdem, welche Regel den Leistungsort bestimmt hat (R31).
FUNDSTELLE: dict[str, str] = {
    "R3": "§ 3a Abs. 2 UStG",
    "R4": "§ 3a Abs. 1 UStG",
    "R5": "§ 3a Abs. 3 Nr. 3 UStG",
    "R6": "§ 3a Abs. 3 Nr. 3 UStG",
    "R7": "§ 3a Abs. 4 UStG",
    "R8": "§ 3a Abs. 1 UStG",
}


@dataclass(frozen=True)
class Ort:
    """Der Leistungsort und wie er zustande kam."""

    land: str
    regeln: tuple[str, ...]
    fundstelle: str | None   # für den Hinweistext; None bei manueller Festlegung


@dataclass(frozen=True)
class Entscheidung:
    ort: Ort
    ergebnis: Ergebnis
    satz: Decimal
    unternehmer: bool | None
    regeln: tuple[str, ...]


def merkmale(kunde: Kunde, leistung: Leistung, aussteller: Stammdaten, festgelegt: str | None = None) -> Merkmale:
    ort = leistung.ort
    return Merkmale(
        kunde=kategorie(kunde.land),
        unternehmer=kunde.unternehmer,
        kunde_ustid=bool(kunde.ustid),
        gruppe=EINORDNUNGEN[leistung.einordnung][0],
        taetigkeit_ort=None if ort is None else ("online" if ort == "online" else kategorie(ort)),
        kleinunternehmer=aussteller.kleinunternehmer,
        aussteller_ustid=bool(aussteller.ustid),
        aussteller_inland=kategorie(aussteller.land) == INLAND,
        festgelegt=None if festgelegt is None else kategorie(festgelegt),
    )


def entscheide(
    kunde: Kunde, leistung: Leistung, aussteller: Stammdaten, festgelegt: str | None = None
) -> Entscheidung:
    """Steuerentscheidung für eine Rechnung: Merkmale bilden, `kern()` fragen, zurückübersetzen.

    `festgelegt` ist ein manuell gesetzter Leistungsort (R37). Bricht mit RegelFehler ab, wenn der
    Kern nicht entscheidet; die Meldung nennt Kunde, Feld und Ausweg.
    """
    m = merkmale(kunde, leistung, aussteller, festgelegt)
    k = kern(m)
    if isinstance(k, Abbruch):
        raise RegelFehler(_meldung(k, kunde, festgelegt or leistung.ort))
    land = {
        ORT_KUNDE: kunde.land,
        ORT_TAETIGKEIT: leistung.ort,
        ORT_AUSSTELLER: aussteller.land,   # nach kern() immer das Inland (R4)
        ORT_FESTGELEGT: festgelegt,
    }[k.ort_quelle]
    assert land is not None
    ort_regeln = tuple(r for r in k.regeln if r in FUNDSTELLE or r == "R37")
    fundstelle = None if k.ort_quelle == ORT_FESTGELEGT else FUNDSTELLE[ort_regeln[-1]]
    unternehmer = m.unternehmer if m.unternehmer is not None else (True if m.kunde == EU and m.kunde_ustid else None)
    return Entscheidung(
        ort=Ort(land, ort_regeln, fundstelle),
        ergebnis=k.ergebnis,
        satz=Decimal(k.satz),
        unternehmer=unternehmer,
        regeln=k.regeln,
    )


def _meldung(a: Abbruch, kunde: Kunde, ort: str | None) -> str:
    kuerzel = kunde.kuerzel or kunde.firma
    if a.grund == "aussteller_ausland":
        return (
            "stammdaten/ich.yaml: `land` ist nicht DE. Das Werkzeug bildet das deutsche "
            "Umsatzsteuergesetz ab und rechnet nur für Aussteller mit Sitz in Deutschland (RULES.md R4)."
        )
    if a.grund == "unternehmer_fehlt":
        zeilen = [
            f"Kunde {kuerzel}, Land {kunde.land}: `unternehmer` ist nicht gesetzt. Davon hängt der "
            f"Leistungsort ab (§ 3a Abs. 1 und 2 UStG). In stammdaten/kunden/{kuerzel}.yaml eintragen:",
            "  unternehmer: true     # bezieht die Leistung für sein Unternehmen",
            "  unternehmer: false    # Privatperson",
        ]
        if kategorie(kunde.land) == EU:
            zeilen.append("Ein Unternehmer in der EU braucht außerdem `ustid:` (§ 14a Abs. 1 UStG).")
        return "\n".join(zeilen)
    if a.grund == "eu_privat":
        return (
            f"Leistungsort {ort if ort and ort != 'online' else kunde.land} ist ein anderer EU-Staat, der "
            f"Kunde ist kein Unternehmer: Die Umsatzsteuer wäre dort zu erklären. Das deckt das Werkzeug "
            f"nicht ab (RULES.md R18)."
        )
    if a.grund == "kunde_ustid_fehlt":
        return (
            f"Kunde {kuerzel}, Land {kunde.land} (EU): `ustid` fehlt. Bei Steuerschuldnerschaft des "
            f"Leistungsempfängers gehört seine USt-IdNr. auf die Rechnung (§ 14a Abs. 1 UStG). In "
            f"stammdaten/kunden/{kuerzel}.yaml ergänzen; ist der Kunde Privatperson: unternehmer: false."
        )
    return (
        "Eigene USt-IdNr. fehlt in stammdaten/ich.yaml: Bei Steuerschuldnerschaft des "
        "Leistungsempfängers gehört sie auf die Rechnung (§ 14a Abs. 1 UStG)."
    )


def frist_reverse_charge(leistung_bis: date) -> date:
    """R30: Rechnung bis zum 15. des Monats, der auf den Monat der Leistung folgt (§ 14a Abs. 1 Satz 2)."""
    if leistung_bis.month == 12:
        return date(leistung_bis.year + 1, 1, 15)
    return date(leistung_bis.year, leistung_bis.month + 1, 15)


# ---------------------------------------------------------------- Pflichttexte (R28, R31)

def hinweis(e: Entscheidung, sprache: str = "de") -> dict[str, str] | None:
    """Textbaustein für Block 8, in der Sprache der Rechnung.

    None, wenn Umsatzsteuer ausgewiesen wird. Der Rückgabewert bleibt ein Dict mit genau einem
    Schlüssel, damit die Sprache im eingefrorenen Ergebnis sichtbar bleibt.
    """
    if e.ergebnis == "reverse_charge":
        # § 14a Abs. 1 Satz 1 UStG verlangt für einen Umsatz in einem anderen Mitgliedstaat wörtlich
        # "Steuerschuldnerschaft des Leistungsempfängers"; die Steuerschuld des Kunden folgt aus
        # Art. 196 MwStSystRL. § 14a Abs. 5 und § 13b UStG regeln den umgekehrten Fall
        # (inländischer Empfänger schuldet die Steuer) und stehen deshalb hier nicht.
        texte = {
            "de": ("Steuerschuldnerschaft des Leistungsempfängers "
                   "(§ 14a Abs. 1 UStG, Art. 196 MwStSystRL)."),
            "en": ("Reverse charge: VAT is owed by the recipient "
                   "(Art. 196 VAT Directive 2006/112/EC, § 14a (1) German VAT Act)."),
        }
    elif e.ergebnis == "nicht_steuerbar":
        fundstelle = f" ({e.ort.fundstelle})" if e.ort.fundstelle else ""
        # Der Nachsatz zum Reverse Charge passt nur, wenn der Kunde Unternehmer ist (R31).
        nachsatz = "; the reverse charge may apply in the recipient's country." if e.unternehmer else "."
        texte = {
            "de": (f"Leistungsort: {land_name(e.ort.land, 'de')}. Die Leistung ist in Deutschland "
                   f"nicht steuerbar{fundstelle}."),
            "en": f"Place of supply: {land_name(e.ort.land, 'en')}. Not subject to German VAT{nachsatz}",
        }
    elif e.ergebnis == "kleinunternehmer":
        # § 34a Nr. 5 UStDV: Hinweis, dass die Steuerbefreiung für Kleinunternehmer gilt (R16).
        texte = {
            "de": "Steuerfrei als Leistung eines Kleinunternehmers (§ 19 Abs. 1 UStG).",
            "en": "VAT exempt: small business exemption under section 19 (1) of the German VAT Act (UStG).",
        }
    else:
        return None
    return {sprache: texte[sprache]}


def faelligkeit(datum: date, tage: int) -> date:
    if tage < 0:
        raise RegelFehler(f"zahlungsziel_tage darf nicht negativ sein: {tage}")
    return datum + timedelta(days=tage)


def runde(betrag: Decimal) -> Decimal:
    """Kaufmännisch auf zwei Stellen."""
    return betrag.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def mindestens_zwei(betrag: Decimal) -> Decimal:
    """Zwei Nachkommastellen, mehr bleiben erhalten.

    Für Einzelpreise: 0.00 soll auch als 0.00 im Ergebnis stehen, ein Stundensatz von
    33.335 aber nicht auf 33.34 verkürzt werden – gerundet wird erst die Zeilensumme.
    """
    return betrag if betrag.as_tuple().exponent <= -2 else betrag.quantize(Decimal("0.01"))


def nummer(format_: str, jahr: int, lfd: int) -> str:
    try:
        return format_.format(jahr=jahr, lfd=lfd)
    except (KeyError, IndexError, ValueError) as e:
        raise RegelFehler(
            f"nummer_format {format_!r} ist ungültig ({e}). Erlaubt sind die Platzhalter "
            f"{{jahr}} und {{lfd}}, z. B. \"MM-{{jahr}}-{{lfd:04d}}\"."
        ) from e


LFD_MUSTER = re.compile(r"(\d{1,6})$")


def naechste_lfd(jahresordner: Path) -> int:
    """Höchste laufende Nummer im Jahresordner plus eins.

    Gelesen werden die Ziffern am Ende des Ordnernamens, unabhängig vom Präfix – ein Wechsel
    des Nummernformats zählt also weiter, statt wieder bei 1 zu beginnen. Kein Zähler-File.
    """
    hoechste = 0
    if jahresordner.is_dir():
        for eintrag in jahresordner.iterdir():
            if not eintrag.is_dir():
                continue
            treffer = LFD_MUSTER.search(eintrag.name)
            if treffer:
                hoechste = max(hoechste, int(treffer.group(1)))
    return hoechste + 1


def waehrung_erlaubt(waehrung: str, saetze: list[Decimal]) -> None:
    """Fremdwährung nur ohne deutschen USt-Ausweis.

    Sobald deutsche Umsatzsteuer ausgewiesen wird, verlangt § 14 Abs. 4 Nr. 8 UStG den
    Steuerbetrag zusätzlich in Euro, umgerechnet mit dem amtlichen Monatskurs. Diese Mechanik
    gibt es (noch) nicht, deshalb bricht resolve hier ab statt falsch zu rechnen.
    """
    if waehrung != "EUR" and any(s != NULLSATZ for s in saetze):
        raise RegelFehler(
            f"Währung {waehrung} mit Umsatzsteuerausweis: Dann muss der Steuerbetrag zusätzlich "
            f"in Euro angegeben werden (amtlicher Umrechnungskurs, § 16 Abs. 6 UStG). Das kann "
            f"das Werkzeug noch nicht. Entweder in EUR fakturieren oder die Einordnung prüfen."
        )
