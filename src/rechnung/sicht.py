"""Geschwärzte Sicht: was die AI vom Werkzeug zu sehen bekommt.

Die AI weiß, was geleistet wurde und wie viel davon – nie, wer beteiligt ist und was es kostet.
Sie bekommt, was sie selbst in `rechnung.yaml` schreibt, die Rechnungsnummer, die Sprache der
Rechnung und vom Werkzeug Ergebnis, Leistungsort, Regeln, Warnungen und die Art eines Abbruchs.
Nie Namen, Anschriften, USt-IdNrn., Bankdaten, Land oder Unternehmerstatus des Kunden, Daten des
Ausstellers, Preise, Beträge oder Summen.

Diese Stelle gibt es einmal; CLI (unter dem Schalter `RECHNUNG_GESCHWAERZT`), später MCP-Server und
Web-Demo nutzen sie. Sie wählt aus, was gezeigt werden darf (Positivliste), statt Privates
herauszusuchen: Ein neues Feld erscheint erst, wenn es hier steht.
"""

from __future__ import annotations

import os
from pathlib import Path

from rechnung import config, meldung
from rechnung.models import Resolved

SCHALTER = "RECHNUNG_GESCHWAERZT"

AI, PRIVAT = "ai", "privat"

# Jedes Feld von rechnung.yaml (models.Input), Unterfelder mit Punkt. Die AI liest und schreibt die
# Datei; „privat“ heißt: Der Wert gehört nicht in ihre Sicht und zieht in Schritt 2 aus der Datei
# aus. tests/test_sicht.py lässt jedes neue Feld ohne Einstufung scheitern.
EINSTUFUNG: dict[str, str] = {
    "kunde": AI,                    # Kürzel; den Kunden wählt der Mensch
    "datum": AI,
    "leistungsdatum": AI,
    "leistungsdatum_bis": AI,
    "sprache": AI,
    "waehrung": AI,
    "zahlungsziel_tage": AI,
    "referenz": PRIVAT,             # Bestellnummer des Kunden
    "einleitung": AI,
    "leistung.taetigkeit": AI,
    "leistung.einordnung": AI,
    "leistung.ort": AI,
    "leistungsort": AI,
    "begruendung": AI,
    "positionen.beschreibung": AI,
    "positionen.menge": AI,
    "positionen.einheit": AI,
    "positionen.einzelpreis": PRIVAT,
    "positionen.steuersatz": AI,    # nur der Schalter 7 %, kein Betrag
    "belege.datei": AI,             # Dateinamen wählt der Mensch; der Skill rät zu neutralen
    "belege.text": AI,
}

# Feldnamen (letzter Teil), deren Wert eine geschwärzte Meldung nie zeigt.
PRIVATE_FELDER = tuple(sorted({f.rsplit(".", 1)[-1] for f, e in EINSTUFUNG.items() if e == PRIVAT}))


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


def ergebnis(r: Resolved) -> dict:
    """Das Ergebnis von `resolve`, so weit die AI es sehen darf.

    Was sie selbst geschrieben hat (Daten, Leistung, Positionen ohne Preis), dazu Nummer, Sprache und
    die Entscheidung des Werkzeugs. Kein Wert aus Kunden- oder Ausstellerdatei, kein Betrag.
    """
    return {
        "nummer": r.nummer,
        "kunde": r.kunde.kuerzel,
        "datum": r.datum.isoformat(),
        "leistungsdatum": r.leistungsdatum.isoformat(),
        "leistungsdatum_bis": r.leistungsdatum_bis.isoformat() if r.leistungsdatum_bis else None,
        "sprache": r.sprache,
        "leistung": {
            "taetigkeit": r.leistung.taetigkeit,
            "einordnung": r.leistung.einordnung,
            "ort": r.leistung.ort,
        },
        "leistungsort": r.leistungsort,
        "leistungsort_manuell": r.leistungsort_manuell,
        "ergebnis": r.ergebnis,
        "regeln": list(r.regeln),
        "positionen": [
            {"pos": p.pos, "beschreibung": p.beschreibung, "menge": str(p.menge), "einheit": p.einheit,
             "steuersatz": str(p.steuersatz)}
            for p in r.positionen
        ],
        "belege": [b.datei for b in r.belege],
        "warnungen": list(r.warnungen),
    }
