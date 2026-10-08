"""Die Regeln: Steuerfall, Steuersatz, Hinweistext, Fälligkeit, Rechnungsnummer.

Regelbesteuerung. Die Kleinunternehmerregelung (§ 19 UStG) wird bewusst nicht unterstützt.
Jede Funktion hier hat einen Test in tests/test_rules.py.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from rechnung.models import Kunde, Steuerfall

# EU-Mitgliedstaaten, Stand 2026-09-23. Vereinigtes Königreich seit 2021 Drittland.
# Bei einer Änderung: Datum hier nachziehen.
EU_LAENDER: frozenset[str] = frozenset({
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
    "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
})

# Ländernamen für den Steuerhinweis (Fall C nennt den Leistungsort im Klartext).
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


def steuerfall(kunde: Kunde) -> Steuerfall:
    """A Inland · B EU-Unternehmen mit USt-IdNr. · C Drittland-Unternehmen · D sonst."""
    if kunde.land == "DE":
        return "A"
    if kunde.land in EU_LAENDER and kunde.ustid:
        return "B"
    if kunde.land not in EU_LAENDER and kunde.unternehmer:
        return "C"
    return "D"


def fall_d_erklaerung(kunde: Kunde) -> str:
    """Sagt, was fehlt – Fall D ist meist ein Datenfehler, kein gewollter Fall."""
    kuerzel = kunde.kuerzel or kunde.firma
    if kunde.land in EU_LAENDER:
        grund = f"Kunde {kuerzel}, Land {kunde.land} (EU), aber keine ustid gesetzt"
        weg = (
            f"Wenn der Kunde Unternehmer mit USt-IdNr. ist, `ustid:` in "
            f"stammdaten/kunden/{kuerzel}.yaml ergänzen – das ergibt Fall B mit 0 % "
            f"(Reverse Charge)."
        )
    else:
        fehlt = "unternehmer: false" if kunde.unternehmer is False else "unternehmer fehlt"
        grund = f"Kunde {kuerzel}, Land {kunde.land} (Drittland), {fehlt}"
        weg = (
            f"Wenn der Kunde Unternehmer ist, `unternehmer: true` in "
            f"stammdaten/kunden/{kuerzel}.yaml ergänzen – das ergibt Fall C mit 0 % "
            f"(nicht steuerbar, § 3a Abs. 2 UStG)."
        )
    return (
        f"Steuerfall D erkannt: {grund}. Das bedeutet 19 % deutsche Umsatzsteuer.\n"
        f"{weg}\n"
        f"Wenn D wirklich richtig ist, in rechnung.yaml eintragen:\n"
        f"  steuerfall: D\n"
        f"  begruendung: <warum 19 % deutsche USt korrekt sind>"
    )


def steuersatz(fall: Steuerfall) -> Decimal:
    """Satz, der aus dem Fall folgt. In Fall A darf eine Position auf 7 % abweichen."""
    return NULLSATZ if fall in ("B", "C") else REGELSATZ


def hinweis(fall: Steuerfall, land: str, sprache: str = "de") -> dict[str, str] | None:
    """Textbaustein für Block 8, in der Sprache der Rechnung.

    None, wenn Umsatzsteuer ausgewiesen wird (Fall A und D). Der Rückgabewert bleibt ein Dict
    mit genau einem Schlüssel, damit die Sprache im eingefrorenen Ergebnis sichtbar bleibt.
    """
    if fall == "B":
        # § 14a Abs. 5 UStG verlangt für die ausgehende Rechnung wörtlich
        # "Steuerschuldnerschaft des Leistungsempfängers"; die Steuerschuld des Kunden
        # folgt aus Art. 196 MwStSystRL. § 13b UStG regelt den umgekehrten Fall
        # (deutscher Empfänger schuldet die Steuer) und steht deshalb hier nicht.
        texte = {
            "de": ("Steuerschuldnerschaft des Leistungsempfängers "
                   "(§ 14a Abs. 5 UStG, Art. 196 MwStSystRL)."),
            "en": ("Reverse charge: VAT is owed by the recipient "
                   "(Art. 196 VAT Directive 2006/112/EC, § 14a (5) German VAT Act)."),
        }
    elif fall == "C":
        texte = {
            "de": (
                f"Leistungsort: {land_name(land, 'de')}. Die Leistung ist in Deutschland "
                f"nicht steuerbar (§ 3a Abs. 2 UStG)."
            ),
            "en": (
                f"Place of supply: {land_name(land, 'en')}. Not subject to German VAT; "
                f"the reverse charge may apply in the recipient's country."
            ),
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
            f"das Werkzeug noch nicht. Entweder in EUR fakturieren oder den Steuerfall prüfen."
        )
