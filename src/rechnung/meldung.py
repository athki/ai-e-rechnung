"""Art eines Abbruchs und seine geschwärzte Fassung.

Jeder fachliche Fehler des Werkzeugs sagt, wer handeln muss (`art`), und kann eine Fassung seiner
Meldung ohne private Werte mitbringen (`geschwaerzt`). Die geschwärzte Sicht (`sicht.py`) gibt nur
diese Fassung aus; fehlt sie, hält sie die Meldung zurück. Blattmodul ohne Importe aus dem Paket,
damit jede Fehlerklasse davon erben kann.
"""

from __future__ import annotations

# Die vier Arten (entscheidungen 2026-10-13): was die AI bei einem Abbruch tut.
EINGABE = "eingabe"          # eigener Fehler in rechnung.yaml – selbst beheben
FRAGE = "frage"              # Tatsache, die nur der Mensch kennt – fragen, nie raten
STAMMDATEN = "stammdaten"    # Kunden-, Ausstellerdatei oder Config unvollständig – der Mensch trägt ein
AUSSERHALB = "ausserhalb"    # bewusst außerhalb des Geltungsbereichs – erklären und anhalten
ARTEN = (EINGABE, FRAGE, STAMMDATEN, AUSSERHALB)


class Fehler(Exception):
    """Fachlicher Abbruch mit Art und, wo vorhanden, geschwärzter Meldung.

    Ohne Angabe gilt die Art der Klasse; `frage` ist die vorsichtige Voreinstellung: Die AI handelt
    nicht allein, sondern gibt an den Menschen ab.
    """

    art: str = FRAGE

    def __init__(self, meldung: str = "", *, art: str | None = None, geschwaerzt: str | None = None):
        super().__init__(meldung)
        if art is not None:
            if art not in ARTEN:
                raise ValueError(f"unbekannte Art {art!r}")
            self.art = art
        self.geschwaerzt = geschwaerzt
