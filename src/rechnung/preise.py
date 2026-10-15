"""Preise an der AI vorbei: Preisliste, Bestätigung, rechnung.privat.yaml.

Die AI schreibt in rechnung.yaml, was geleistet wurde und wie viel davon: Kürzel aus der Preisliste,
Menge, Einheit. Die Beträge bestätigt der Mensch mit `rechnung preise <nr>` (im Web später ein
Formular über dieselben Funktionen); sie landen als Schnappschuss in rechnung.privat.yaml, zusammen
mit dem Hash der Positionen, für die sie gelten. Ändert sich danach eine Position, ist die
Bestätigung veraltet, und `bauen` baut nichts, weder Pro forma noch Rechnung.

Laden und Prüfen der Dateien macht resolve.py; hier stehen Hash, Stand und das Schreiben.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from rechnung import meldung, rules
from rechnung.models import Position, Privat

if TYPE_CHECKING:
    from rechnung.resolve import Entwurf

PREISLISTE_DATEI = "preise.yaml"
PRIVAT_DATEI = "rechnung.privat.yaml"

# Stand der Preise einer Rechnung – auch die AI bekommt ihn zu sehen, ohne einen Betrag.
BESTAETIGT = "bestaetigt"
FEHLEN = "fehlen"
VERALTET = "veraltet"

# Preise der Liste gelten in dieser Währung; bei anderen füllt `rechnung preise` nichts vor.
LISTENWAEHRUNG = "EUR"


class PreisFehler(meldung.Fehler):
    art = meldung.PREISE


def _menge(wert: Decimal) -> str:
    """Menge ohne Darstellungsunterschiede: 2, 2.0 und 2.00 sind dieselbe Menge."""
    return format(wert.normalize(), "f")


def positionen_hash(positionen: list[Position]) -> str:
    """Hash dessen, wofür die Preise gelten: Reihenfolge, Kürzel, Menge, Einheit, Beschreibung.

    Streng gewählt (entscheidungen 2026-10-13): auch eine geänderte Beschreibung verlangt eine neue
    Bestätigung, sonst ließe sich eine Position unter bestätigtem Preis umdeuten.
    """
    daten = [{"kuerzel": p.kuerzel, "menge": _menge(p.menge), "einheit": p.einheit,
              "beschreibung": p.beschreibung} for p in positionen]
    return hashlib.sha256(json.dumps(daten, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def stand(privat: Privat, hash_: str, waehrung: str, kuerzel: list[str]) -> str:
    """`bestaetigt`, `fehlen` oder `veraltet` – für die aktuellen Positionen und die aktuelle Währung."""
    if not privat.positionen_hash:
        return FEHLEN
    if (privat.positionen_hash != hash_ or privat.waehrung != waehrung
            or [p.kuerzel for p in privat.positionen] != kuerzel):
        return VERALTET
    return BESTAETIGT


def privat_text(nummer: str, privat: Privat) -> str:
    """rechnung.privat.yaml, lesbar und mit Kopf; Beträge als Text, damit nichts gerundet wird."""
    zeilen = [
        f"# Private Werte der Rechnung {nummer}: Preise und Referenz.",
        "# Schreibt `rechnung preise`; die AI liest und schreibt diese Datei nicht.",
        "# Ändert sich eine Position in rechnung.yaml, ist die Bestätigung veraltet: `rechnung preise` neu.",
    ]
    if privat.referenz:
        zeilen.append(f"referenz: {json.dumps(privat.referenz, ensure_ascii=False)}")
    if privat.positionen_hash:
        assert privat.bestaetigt_am is not None
        zeilen += [
            f"waehrung: {privat.waehrung}",
            f"bestaetigt_am: {privat.bestaetigt_am.isoformat(timespec='seconds')}",
            f"positionen_hash: {privat.positionen_hash}",
            "positionen:",
        ]
        for p in privat.positionen:
            zeilen += [f"  - kuerzel: {p.kuerzel}", f"    einzelpreis: {rules.mindestens_zwei(p.einzelpreis)}"]
            if p.steuersatz is not None:
                zeilen.append(f"    steuersatz: {p.steuersatz}")
    return "\n".join(zeilen) + "\n"


def schreiben(ordner: Path, privat: Privat) -> Path:
    ziel = ordner / PRIVAT_DATEI
    ziel.write_text(privat_text(ordner.name, privat), encoding="utf-8")
    return ziel


class _Unveraendert:
    pass


UNVERAENDERT = _Unveraendert()


def bestaetigen(
    entwurf: Entwurf,
    einzelpreise: list[Decimal],
    ermaessigt: list[bool] | None = None,
    referenz: str | None | _Unveraendert = UNVERAENDERT,
    am: datetime | None = None,
) -> Privat:
    """Hält die Preise für die aktuellen Positionen fest und schreibt rechnung.privat.yaml.

    Nur für den Menschen: CLI im eigenen Terminal, Formular im Web, Demo und Tests. 7 % nur, wo
    `rules.satz_position()` es für diese Rechnung erlaubt.
    """
    positionen = entwurf.positionen
    ermaessigt = ermaessigt if ermaessigt is not None else [False] * len(positionen)
    if len(einzelpreise) != len(positionen) or len(ermaessigt) != len(positionen):
        raise PreisFehler(f"{len(positionen)} Positionen, aber {len(einzelpreise)} Preise.",
                          geschwaerzt="Anzahl der Preise passt nicht zu den Positionen.")
    neu = []
    for p, preis, sieben in zip(positionen, einzelpreise, ermaessigt):
        if preis < 0:
            raise PreisFehler(f"Position {p.pos}: Preis ist negativ.",
                              geschwaerzt=f"Position {p.pos}: Preis ist negativ.")
        if sieben and not p.sieben_erlaubt:
            satz = rules.satz_position(int(entwurf.entscheidung.satz), entwurf.stammdaten.kleinunternehmer, True)
            regel = satz.regel if isinstance(satz, rules.Abbruch) else "R10"
            text = (f"Position {p.pos}: 7 % geht hier nicht – das Ergebnis {entwurf.entscheidung.ergebnis} "
                    f"weist keine deutsche Umsatzsteuer aus (RULES.md {regel}).")
            raise PreisFehler(text, art=meldung.AUSSERHALB, geschwaerzt=text)
        neu.append({"kuerzel": p.kuerzel, "einzelpreis": preis, "steuersatz": Decimal(7) if sieben else None})
    alt = entwurf.privat
    privat = Privat(
        referenz=alt.referenz if isinstance(referenz, _Unveraendert) else (referenz or None),
        waehrung=entwurf.waehrung,
        positionen_hash=entwurf.positionen_hash,
        bestaetigt_am=am or datetime.now().astimezone(),
        positionen=neu,
    )
    schreiben(entwurf.ordner, privat)
    return privat


def referenz_setzen(entwurf: Entwurf, referenz: str | None) -> Privat:
    """Nur die Referenz ändern; eine Bestätigung der Preise bleibt gültig."""
    privat = entwurf.privat.model_copy(update={"referenz": referenz or None})
    schreiben(entwurf.ordner, privat)
    return privat
