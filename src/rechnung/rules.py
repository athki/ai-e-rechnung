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


def ist_unternehmer(kunde: Kunde) -> bool | None:
    """`unternehmer` aus der Kundendatei; ein EU-Kunde mit USt-IdNr. gilt als Unternehmer (R3)."""
    if kunde.unternehmer is not None:
        return kunde.unternehmer
    if kunde.ustid and kategorie(kunde.land) == EU:
        return True
    return None


@dataclass(frozen=True)
class Ort:
    """Der Leistungsort und wie er zustande kam."""

    land: str
    regeln: tuple[str, ...]
    fundstelle: str | None   # für den Hinweistext; None bei manueller Festlegung


def unternehmer_fehlt(kunde: Kunde) -> str:
    kuerzel = kunde.kuerzel or kunde.firma
    zeilen = [
        f"Kunde {kuerzel}, Land {kunde.land}: `unternehmer` ist nicht gesetzt. Davon hängt der "
        f"Leistungsort ab (§ 3a Abs. 1 und 2 UStG). In stammdaten/kunden/{kuerzel}.yaml eintragen:",
        "  unternehmer: true     # bezieht die Leistung für sein Unternehmen",
        "  unternehmer: false    # Privatperson",
    ]
    if kategorie(kunde.land) == EU:
        zeilen.append("Ein Unternehmer in der EU braucht außerdem `ustid:` (§ 14a Abs. 1 UStG).")
    return "\n".join(zeilen)


def leistungsort(kunde: Kunde, leistung: Leistung) -> Ort:
    """Leistungsort aus Status des Kunden, Einordnung der Leistung und Ort (R3–R8, RULES.md Teil 4)."""
    gruppe, fundstelle = EINORDNUNGEN[leistung.einordnung]
    unternehmer = ist_unternehmer(kunde)
    if unternehmer:
        return Ort(kunde.land, ("R3",), "§ 3a Abs. 2 UStG")
    if unternehmer is None:
        # Im Inland führt jede Antwort zum Inland – außer eine Tätigkeit wird woanders erbracht.
        if kunde.land == "DE" and gruppe != TAETIGKEIT:
            return Ort("DE", ("R3", "R4"), None)
        raise RegelFehler(unternehmer_fehlt(kunde))
    if gruppe == TAETIGKEIT:
        assert leistung.ort is not None   # models.Leistung verlangt ihn
        if leistung.ort == "online":
            return Ort(kunde.land, ("R6",), fundstelle)
        return Ort(leistung.ort, ("R5",), fundstelle)
    if gruppe == KATALOG and kategorie(kunde.land) == DRITTLAND:
        return Ort(kunde.land, ("R7",), "§ 3a Abs. 4 UStG")
    return Ort("DE", ("R8",) if gruppe == KATALOG else ("R4",), "§ 3a Abs. 1 UStG")


# ---------------------------------------------------------------- Ergebnis (R10–R12, R18, R29)

@dataclass(frozen=True)
class Entscheidung:
    ort: Ort
    ergebnis: Ergebnis
    satz: Decimal
    unternehmer: bool | None
    regeln: tuple[str, ...]


def entscheide(
    kunde: Kunde, leistung: Leistung, aussteller: Stammdaten, festgelegt: str | None = None
) -> Entscheidung:
    """Vom Leistungsort zu Ergebnis und Satz. `festgelegt` ist ein manuell gesetzter Leistungsort (R37).

    Für Kleinunternehmer (§ 19 UStG) bestimmt dieselbe Tabelle den Leistungsort; steuerfrei ist nur,
    was im Inland steuerbar ist (R13), Steuer weist ein Kleinunternehmer nie aus (R14).
    """
    ort = Ort(festgelegt, ("R37",), None) if festgelegt else leistungsort(kunde, leistung)
    unternehmer = ist_unternehmer(kunde)
    ku = aussteller.kleinunternehmer
    regeln = ["R1", "R2", *ort.regeln, "R9"]
    k = kategorie(ort.land)
    if k == INLAND and ku:
        ergebnis: Ergebnis = "kleinunternehmer"
        regeln += ["R13", "R16"]
    elif k == INLAND:
        ergebnis = "inland"
        regeln.append("R10")
    elif k == EU:
        if not unternehmer:
            raise RegelFehler(
                f"Leistungsort {ort.land} ist ein anderer EU-Staat, der Kunde ist kein Unternehmer: Die "
                f"Umsatzsteuer wäre dort zu erklären. Das deckt das Werkzeug nicht ab (RULES.md R18)."
            )
        ergebnis = "reverse_charge"
        if ku:
            # § 19 Abs. 1 Satz 2 UStG schließt § 14a Abs. 1 Satz 3 aus: keine USt-IdNrn. nötig (R15).
            regeln += ["R11", "R15", "R28", "R30"]
        else:
            _ustids_vorhanden(kunde, aussteller)
            regeln += ["R11", "R28", "R29", "R30"]
    else:
        ergebnis = "nicht_steuerbar"
        regeln += ["R17", "R31"] if ku else ["R31"]
    satz = REGELSATZ if ergebnis == "inland" else NULLSATZ
    if satz == NULLSATZ:
        regeln.append("R14" if ku else "R12")
    return Entscheidung(ort, ergebnis, satz, unternehmer, tuple(regeln))


def _ustids_vorhanden(kunde: Kunde, aussteller: Stammdaten) -> None:
    """R29: Bei Steuerschuldnerschaft des Empfängers stehen beide USt-IdNrn. auf der Rechnung."""
    kuerzel = kunde.kuerzel or kunde.firma
    if not kunde.ustid:
        raise RegelFehler(
            f"Kunde {kuerzel}, Land {kunde.land} (EU): `ustid` fehlt. Bei Steuerschuldnerschaft des "
            f"Leistungsempfängers gehört seine USt-IdNr. auf die Rechnung (§ 14a Abs. 1 UStG). In "
            f"stammdaten/kunden/{kuerzel}.yaml ergänzen; ist der Kunde Privatperson: unternehmer: false."
        )
    if not aussteller.ustid:
        raise RegelFehler(
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
