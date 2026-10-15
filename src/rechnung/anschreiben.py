"""Anschreiben zur Rechnung: Die AI entwirft den Text, das Werkzeug setzt die Werte lokal ein.

Die AI schreibt `anschreiben.md` in den Rechnungsordner, mit Platzhaltern aus einer festen Liste
(`[nummer]`, `[brutto]`, `[anrede]` …), nie mit Namen oder Beträgen. `rechnung anschreiben <nr>`
setzt die Werte aus rechnung.resolved.json ein und gibt den Text aus; das Werkzeug verschickt nichts.
Ein unbekannter Platzhalter ist ein Abbruch, kein stiller Text.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from rechnung import meldung, render
from rechnung.models import Resolved

DATEI = "anschreiben.md"

# Platzhalter -> Bedeutung. Die Liste ist fest; neue Felder kommen hierher, nicht in den Text.
FELDER: dict[str, str] = {
    "nummer": "Rechnungsnummer",
    "datum": "Rechnungsdatum",
    "leistungsdatum": "Leistungsdatum bzw. -zeitraum",
    "faelligkeit": "zahlbar bis",
    "netto": "Nettobetrag mit Währung",
    "brutto": "Rechnungsbetrag mit Währung",
    "anrede": "Anrede aus der Kundendatei oder Standard, ohne Komma",
    "firma": "Firma bzw. Name des Kunden",
    "referenz": "Referenz des Kunden (Bestellnummer)",
    "name": "Name des Ausstellers",
}

PLATZHALTER = re.compile(r"\[([a-z_]+)\]")


class AnschreibenFehler(meldung.Fehler):
    art = meldung.EINGABE


def lesen(ordner: Path) -> str:
    pfad = ordner / DATEI
    if not pfad.is_file():
        text = f"{DATEI} fehlt im Rechnungsordner {ordner.name}. Die AI oder der Mensch schreibt den Entwurf dort hinein."
        raise AnschreibenFehler(text, geschwaerzt=text)
    return pfad.read_text(encoding="utf-8")


def platzhalter(text: str) -> list[str]:
    """Die Platzhalter im Entwurf, in Reihenfolge, ohne Doppelte; bricht bei einem unbekannten ab."""
    namen = list(dict.fromkeys(PLATZHALTER.findall(text)))
    unbekannt = [n for n in namen if n not in FELDER]
    if unbekannt:
        meldung_ = (f"Unbekannte Platzhalter in {DATEI}: {', '.join(f'[{n}]' for n in unbekannt)}. "
                    f"Erlaubt: {', '.join(f'[{n}]' for n in FELDER)}.")
        raise AnschreibenFehler(meldung_, geschwaerzt=meldung_)
    return namen


def _geld(betrag: Decimal, waehrung: str, sprache: str) -> str:
    """Wie auf der Rechnung: de „1.200,50 EUR“, en „EUR 1,200.50“."""
    text = f"{betrag:,.2f}"
    if sprache == "de":
        return text.replace(",", "#").replace(".", ",").replace("#", ".") + f" {waehrung}"
    return f"{waehrung} {text}"


def werte(r: Resolved) -> dict[str, str | None]:
    leistung = render.datum(r.leistungsdatum, r.sprache)
    if r.leistungsdatum_bis:
        leistung += f" – {render.datum(r.leistungsdatum_bis, r.sprache)}"
    return {
        "nummer": r.nummer,
        "datum": render.datum(r.datum, r.sprache),
        "leistungsdatum": leistung,
        "faelligkeit": render.datum(r.faelligkeit, r.sprache),
        "netto": _geld(r.netto, r.waehrung, r.sprache),
        "brutto": _geld(r.brutto, r.waehrung, r.sprache),
        "anrede": r.anrede,
        "firma": r.kunde.firma,
        "referenz": r.referenz,
        "name": r.aussteller.name,
    }


def einsetzen(text: str, r: Resolved) -> str:
    """Setzt alle Platzhalter ein. Ein Platzhalter ohne Wert (keine Referenz) ist ein Abbruch."""
    namen = platzhalter(text)
    w = werte(r)
    leer = [n for n in namen if not w[n]]
    if leer:
        meldung_ = f"Kein Wert für {', '.join(f'[{n}]' for n in leer)} in Rechnung {r.nummer}."
        raise AnschreibenFehler(meldung_, geschwaerzt=meldung_)
    return PLATZHALTER.sub(lambda m: str(w[m.group(1)]), text)
