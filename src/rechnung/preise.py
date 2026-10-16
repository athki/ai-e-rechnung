"""Preise an der AI vorbei: Preisliste, Bestätigung, rechnung.privat.yaml.

Die AI schreibt in rechnung.yaml, was geleistet wurde und wie viel davon: Kürzel aus der Preisliste,
Menge, Einheit. Die Beträge bestätigt der Mensch mit `rechnung preise <nr>` (im Web später ein
Formular über dieselben Funktionen); sie landen als Schnappschuss in rechnung.privat.yaml, zusammen
mit dem Hash der Positionen, für die sie gelten. Ändert sich danach eine Position, ist die
Bestätigung veraltet, und `bauen` baut nichts, weder Pro forma noch Rechnung.

Hat eine Position einen Preis in der Liste, braucht es den Menschen nicht: `aus_liste()` übernimmt
ihn (aufgerufen von `resolve` und `bauen`), für neue oder geänderte Positionen; was der Mensch für
eine unveränderte Position bestätigt hat, bleibt. Jede Position trägt ihre Quelle (`mensch` oder
`liste`), `festschreiben` weist auf übernommene hin. Auslagen und Fremdwährung bleiben beim Menschen.

Laden und Prüfen der Dateien macht resolve.py; hier stehen Hash, Stand und das Schreiben.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

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

# Woher ein Preis kommt
Quelle = Literal["mensch", "liste"]
MENSCH: Quelle = "mensch"
LISTE: Quelle = "liste"

# Preise der Liste gelten in dieser Währung; bei anderen füllt `rechnung preise` nichts vor.
LISTENWAEHRUNG = "EUR"


class PreisFehler(meldung.Fehler):
    art = meldung.PREISE


def betrag(text: str) -> Decimal | None:
    """Eingabe eines Preises: 1200, 1200.50 oder 1200,50; sonst None."""
    text = text.strip().replace(" ", "")
    if text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    try:
        wert = Decimal(text)
    except ArithmeticError:
        return None
    return wert if wert.is_finite() and wert >= 0 else None


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


def position_hash(p: Position) -> str:
    """Hash einer Position (Kürzel, Menge, Einheit, Beschreibung): erkennt sie nach einer Änderung an
    anderen Positionen wieder, damit ihr bestätigter Preis bleibt."""
    daten = {"kuerzel": p.kuerzel, "menge": _menge(p.menge), "einheit": p.einheit, "beschreibung": p.beschreibung}
    return hashlib.sha256(json.dumps(daten, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


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
        "# Ändert sich eine Position in rechnung.yaml, ist die Bestätigung veraltet: `rechnung preise` neu",
        "# (Positionen mit Listenpreis füllt `resolve` selbst). quelle: mensch = bestätigt, liste = übernommen.",
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
            zeilen.append(f"    quelle: {p.quelle}")
            if p.position:
                zeilen.append(f"    position: {p.position}")
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
    quellen: list[Quelle] | None = None,
) -> Privat:
    """Hält die Preise für die aktuellen Positionen fest und schreibt rechnung.privat.yaml.

    Für den Menschen (CLI im eigenen Terminal, Formular, Demo und Tests) und für `aus_liste()`.
    7 % nur, wo `rules.satz_position()` es für diese Rechnung erlaubt.
    """
    positionen = entwurf.positionen
    ermaessigt = ermaessigt if ermaessigt is not None else [False] * len(positionen)
    quellen = quellen if quellen is not None else [MENSCH] * len(positionen)
    if len(einzelpreise) != len(positionen) or len(ermaessigt) != len(positionen) or len(quellen) != len(positionen):
        raise PreisFehler(f"{len(positionen)} Positionen, aber {len(einzelpreise)} Preise.",
                          geschwaerzt="Anzahl der Preise passt nicht zu den Positionen.")
    neu = []
    for p, eingabe, preis, sieben, quelle in zip(positionen, entwurf.eingabe.positionen, einzelpreise,
                                                 ermaessigt, quellen):
        if preis < 0:
            raise PreisFehler(f"Position {p.pos}: Preis ist negativ.",
                              geschwaerzt=f"Position {p.pos}: Preis ist negativ.")
        if sieben and not p.sieben_erlaubt:
            satz = rules.satz_position(int(entwurf.entscheidung.satz), entwurf.stammdaten.kleinunternehmer, True)
            regel = satz.regel if isinstance(satz, rules.Abbruch) else "R10"
            text = (f"Position {p.pos}: 7 % geht hier nicht – das Ergebnis {entwurf.entscheidung.ergebnis} "
                    f"weist keine deutsche Umsatzsteuer aus (RULES.md {regel}).")
            raise PreisFehler(text, art=meldung.AUSSERHALB, geschwaerzt=text)
        neu.append({"kuerzel": p.kuerzel, "einzelpreis": preis, "steuersatz": Decimal(7) if sieben else None,
                    "quelle": quelle, "position": position_hash(eingabe)})
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


def _aus_liste(entwurf: Entwurf) -> tuple[list[Decimal], list[bool], list[Quelle]] | None:
    """Preise, Sätze und Quellen, wie `aus_liste()` sie festhielte; None, wenn das nicht ganz geht."""
    if entwurf.preise == BESTAETIGT or not entwurf.positionen:
        return None
    alt: dict[str, list] = {}
    if entwurf.privat.waehrung == entwurf.waehrung:
        for pp in entwurf.privat.positionen:
            if pp.position:
                alt.setdefault(pp.position, []).append(pp)
    einzelpreise: list[Decimal] = []
    ermaessigt: list[bool] = []
    quellen: list[Quelle] = []
    for p, eingabe in zip(entwurf.positionen, entwurf.eingabe.positionen):
        vorher = alt.get(position_hash(eingabe))
        if vorher:
            pp = vorher.pop(0)
            if pp.steuersatz is not None and not p.sieben_erlaubt:
                return None
            einzelpreise.append(pp.einzelpreis)
            ermaessigt.append(pp.steuersatz is not None)
            quellen.append(pp.quelle)
        elif p.vorschlag is not None:
            einzelpreise.append(p.vorschlag)
            ermaessigt.append(p.vorschlag_sieben)
            quellen.append(LISTE)
        else:
            return None
    return einzelpreise, ermaessigt, quellen


def liste_reicht(entwurf: Entwurf) -> bool:
    """Fehlen Preise, die `aus_liste()` alle füllen kann? Dann braucht es den Menschen nicht."""
    return _aus_liste(entwurf) is not None


def aus_liste(entwurf: Entwurf, am: datetime | None = None) -> Privat | None:
    """Füllt fehlende oder veraltete Preise aus der Preisliste, ohne den Menschen (entscheidungen 2026-10-16).

    Je Position: Hat der Mensch für genau diese Position (gleicher Hash, gleiche Währung) schon einen
    Preis bestätigt, bleibt er samt Quelle; sonst gilt der Listenpreis (Quelle `liste`, 7 % wie die
    Liste vorschlägt und die Rechnung erlaubt). Fehlt für eine Position beides (Auslage, Fremdwährung)
    oder ginge ein bestätigter 7-%-Satz nicht mehr, ändert sich nichts: None, der Mensch bestätigt.
    Festgeschriebene Rechnungen prüft der Aufrufer.
    """
    werte = _aus_liste(entwurf)
    if werte is None:
        return None
    einzelpreise, ermaessigt, quellen = werte
    return bestaetigen(entwurf, einzelpreise, ermaessigt, am=am, quellen=quellen)


def aus_der_liste(privat: Privat) -> int:
    """Wie viele Positionen ihren Preis aus der Liste haben, ohne einzelne Bestätigung."""
    return sum(p.quelle == LISTE for p in privat.positionen)


def stand_text(stand_: str, privat: Privat) -> str:
    """Stand der Preise in Worten, ohne Betrag – für die AI und das Terminal."""
    if stand_ == FEHLEN:
        return "fehlen"
    if stand_ == VERALTET:
        return "veraltet (Positionen oder Währung geändert)"
    n, gesamt = aus_der_liste(privat), len(privat.positionen)
    if n == 0:
        return "bestätigt"
    if n == gesamt:
        return "aus der Preisliste übernommen (nicht einzeln bestätigt)"
    return f"bestätigt, {n} von {gesamt} Positionen aus der Preisliste übernommen"
