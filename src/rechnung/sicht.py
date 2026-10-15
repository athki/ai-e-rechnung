"""Geschwärzte Sicht: was die AI vom Werkzeug zu sehen bekommt.

Die AI weiß, was geleistet wurde und wie viel davon – nie, wer beteiligt ist und was es kostet.
Sie bekommt, was sie selbst in `rechnung.yaml` schreibt, die Rechnungsnummer, die Sprache der
Rechnung und vom Werkzeug Ergebnis, Leistungsort, Regeln, Warnungen, die Art eines Abbruchs und
den Stand der Preise (bestätigt, fehlen, veraltet).
Nie Namen, Anschriften, USt-IdNrn., Bankdaten, Land oder Unternehmerstatus des Kunden, Daten des
Ausstellers, Preise, Beträge oder Summen.

Diese Stelle gibt es einmal; CLI (unter dem Schalter `RECHNUNG_GESCHWAERZT`), später MCP-Server und
Web-Demo nutzen sie. Sie wählt aus, was gezeigt werden darf (Positivliste), statt Privates
herauszusuchen: Ein neues Feld erscheint erst, wenn es hier steht.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from rechnung import config, meldung
from rechnung.models import Leistung, Resolved

if TYPE_CHECKING:
    from rechnung.resolve import Entwurf

SCHALTER = "RECHNUNG_GESCHWAERZT"

AI, PRIVAT = "ai", "privat"

# Jedes Feld von rechnung.yaml (models.Input), Unterfelder mit Punkt. Die AI liest und schreibt die
# Datei, deshalb steht darin nur, was sie sehen darf; Preise und Referenz stehen in
# rechnung.privat.yaml. tests/test_sicht.py lässt jedes neue Feld ohne Einstufung scheitern.
EINSTUFUNG: dict[str, str] = {
    "kunde": AI,                    # Kürzel; den Kunden wählt der Mensch
    "datum": AI,
    "leistungsdatum": AI,
    "leistungsdatum_bis": AI,
    "sprache": AI,
    "waehrung": AI,
    "zahlungsziel_tage": AI,
    "einleitung": AI,
    "leistung.taetigkeit": AI,
    "leistung.einordnung": AI,
    "leistung.ort": AI,
    "leistungsort": AI,
    "begruendung": AI,
    "positionen.kuerzel": AI,       # aus der Preisliste; den Preis dazu sieht die AI nie
    "positionen.menge": AI,
    "positionen.einheit": AI,
    "positionen.beschreibung": AI,
    "belege.datei": AI,             # Dateinamen wählt der Mensch; der Skill rät zu neutralen
    "belege.text": AI,
}

# Feldnamen, deren Wert eine geschwärzte Meldung nie zeigt – auch dann nicht, wenn sie aus Versehen
# in rechnung.yaml stehen (dort sind sie unbekannt, und die Meldung nennte sonst den Wert).
PRIVATE_FELDER = ("einzelpreis", "preis", "referenz")


def aktiv(env: dict[str, str] | None = None) -> bool:
    """Fail-closed: jeder nicht-leere Wert außer `0` schaltet die Schwärzung ein."""
    wert = (os.environ if env is None else env).get(SCHALTER, "").strip()
    return wert not in ("", "0")


def pfad(p: Path | str, cfg: config.Config | None = None) -> str:
    """Pfad ohne den Namen der Gewerbe-Wurzel: `<gewerbe>/…`; sonst mit `~` statt des Home-Ordners."""
    p = Path(p)
    if cfg is not None and cfg.gewerbe is not None:
        try:
            rest = p.resolve().relative_to(cfg.gewerbe.resolve())
        except ValueError:
            pass
        else:
            return "<gewerbe>" if str(rest) == "." else f"<gewerbe>/{rest}"
    return kurz(str(p))


def kurz(text: str) -> str:
    """Den Home-Ordner in einem Text durch `~` ersetzen."""
    home = str(Path.home())
    return text.replace(home, "~") if home not in ("", "/") else text


def abbruch(e: BaseException) -> str:
    """Die Abbruchmeldung für die AI: `Abbruch (<art>): <Text>`.

    Ohne eigene geschwärzte Fassung wird die Meldung zurückgehalten (fail-closed).
    """
    art = getattr(e, "art", meldung.FRAGE)
    text = getattr(e, "geschwaerzt", None)
    if not text:
        text = ("Meldung zurückgehalten, weil sie private Daten enthalten könnte. Der Mensch sieht sie, "
                "wenn er dasselbe Kommando im eigenen Terminal ausführt.")
    return f"Abbruch ({art}): {text}"


def _sicht(nummer: str, kunde: str | None, datum: date, leistungsdatum: date, bis: date | None,
           sprache: str, leistung: Leistung, leistungsort: str, manuell: bool, ergebnis_: str,
           regeln: list[str], positionen: list[dict], belege: list[str], warnungen: list[str],
           preise: str) -> dict:
    return {
        "nummer": nummer,
        "kunde": kunde,
        "datum": datum.isoformat(),
        "leistungsdatum": leistungsdatum.isoformat(),
        "leistungsdatum_bis": bis.isoformat() if bis else None,
        "sprache": sprache,
        "leistung": {"taetigkeit": leistung.taetigkeit, "einordnung": leistung.einordnung, "ort": leistung.ort},
        "leistungsort": leistungsort,
        "leistungsort_manuell": manuell,
        "ergebnis": ergebnis_,
        "regeln": regeln,
        "positionen": positionen,
        "belege": belege,
        "warnungen": warnungen,
        "preise": preise,
    }


def ergebnis(r: Resolved) -> dict:
    """Das Ergebnis von `resolve`, so weit die AI es sehen darf.

    Was sie selbst geschrieben hat (Daten, Leistung, Positionen ohne Preis), dazu Nummer, Sprache, die
    Entscheidung des Werkzeugs und den Stand der Preise. Kein Wert aus Kunden- oder Ausstellerdatei,
    kein Betrag.
    """
    return _sicht(
        r.nummer, r.kunde.kuerzel, r.datum, r.leistungsdatum, r.leistungsdatum_bis, r.sprache, r.leistung,
        r.leistungsort, r.leistungsort_manuell, r.ergebnis, list(r.regeln),
        [{"pos": p.pos, "kuerzel": p.kuerzel, "beschreibung": p.beschreibung, "menge": str(p.menge),
          "einheit": p.einheit, "steuersatz": str(p.steuersatz)} for p in r.positionen],
        [b.datei for b in r.belege], list(r.warnungen), "bestaetigt",
    )


def entwurf(e: Entwurf) -> dict:
    """Dasselbe vor der Bestätigung der Preise: der Satz je Position ist noch der Satz der Rechnung."""
    satz = str(int(e.entscheidung.satz))
    return _sicht(
        e.nummer, e.kunde.kuerzel, e.datum, e.eingabe.leistungsdatum, e.eingabe.leistungsdatum_bis, e.sprache,
        e.eingabe.leistung, e.entscheidung.ort.land, e.eingabe.leistungsort is not None, e.entscheidung.ergebnis,
        [*e.entscheidung.regeln],
        [{"pos": p.pos, "kuerzel": p.kuerzel, "beschreibung": p.beschreibung, "menge": str(p.menge),
          "einheit": p.einheit, "steuersatz": satz} for p in e.positionen],
        [b.datei for b in e.eingabe.belege], list(e.warnungen), e.preise,
    )
