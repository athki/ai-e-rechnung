"""Hilfen für Tests: Preise bestätigen, wie es der Mensch mit `rechnung preise` täte."""

from __future__ import annotations

from decimal import Decimal

from rechnung import config, preise, resolve as r


def bestaetige(nummer: str, *einzelpreise: str | Decimal, sieben: list[bool] | None = None,
               referenz: str | None | object = preise.UNVERAENDERT, cfg: config.Config | None = None):
    """Bestätigt die Preise einer Rechnung; ohne Angabe die Preise der Liste."""
    c = cfg or config.laden()
    e = r.entwurf(c, nummer)
    werte = [Decimal(str(p)) for p in einzelpreise] or [p.vorschlag for p in e.positionen]
    return preise.bestaetigen(e, werte, sieben, referenz)  # type: ignore[arg-type]


def privat_schreiben(ordner, text: str) -> None:
    """Schreibt rechnung.privat.yaml von Hand – für Fälle, die `bestaetigen` gar nicht erst zulässt."""
    (ordner / preise.PRIVAT_DATEI).write_text(text, encoding="utf-8")
