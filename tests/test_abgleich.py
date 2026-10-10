"""Erschöpfender Abgleich von rules.py mit dem bewiesenen Lean-Modell (Schritt 8.6).

`lean/abgleich/kern.json` hält für jede mögliche Eingabe von `kern()` und `satz_position()` und für
jedes Einordnungswort die Antwort des Lean-Modells (`lean/Abgleich.lean`; dass keine Eingabe fehlt,
ist dort bewiesen). Die Datei ist eingecheckt; `make lean` und `make beweise` prüfen, dass sie zum
Lean-Stand passt, `make abgleich` schreibt sie neu. Hier wird rules.py dagegen gehalten.

Weicht rules.py ab, nennt der Test die Eingabe und beide Antworten. Dann nicht eine Seite still
angleichen: klären, wer falsch liegt (Gesetz, RULES.md, Modell oder Code).
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from rechnung import rules

from test_rules import AKTIVE_REGELN, ALLE

DATEI = Path(__file__).parent.parent / "lean" / "abgleich" / "kern.json"
LEAN = json.loads(DATEI.read_text(encoding="utf-8"))


def antwort_kern(m: rules.Merkmale) -> dict:
    """Die Antwort von rules.py in der Form der Lean-Datei."""
    k = rules.kern(m)
    if isinstance(k, rules.Abbruch):
        return {"abbruch": {"regel": k.regel, "grund": k.grund}}
    return {"ort_quelle": k.ort_quelle, "ort": k.ort, "ergebnis": k.ergebnis, "satz": k.satz,
            "regeln": list(k.regeln), "fundstelle": rules.fundstelle(k)}


def antwort_satz(satz: int, kleinunternehmer: bool, ermaessigt: bool) -> dict:
    s = rules.satz_position(satz, kleinunternehmer, ermaessigt)
    if isinstance(s, rules.Abbruch):
        return {"abbruch": {"regel": s.regel, "grund": s.grund}}
    return {"satz": s}


def abweichungen(eintraege: list[dict], python) -> list[str]:
    zeilen = []
    for e in eintraege:
        p = python(e["eingabe"])
        if p != e["antwort"]:
            zeilen.append(f"Eingabe {e['eingabe']}\n  Lean:   {e['antwort']}\n  Python: {p}")
    return zeilen


def bericht(zeilen: list[str], gesamt: int) -> str:
    return f"{len(zeilen)} von {gesamt} Eingaben weichen ab:\n" + "\n".join(zeilen[:10])


# ---------------------------------------------------------------- kern()

def test_kern_eingaben_sind_genau_die_von_python():
    """Lean und Python zählen dieselben 3456 Eingaben auf, keine doppelt."""
    lean = [rules.Merkmale(**e["eingabe"]) for e in LEAN["kern"]]
    assert len(lean) == len(set(lean)) == 3456
    assert set(lean) == set(ALLE)


def test_kern_antwortet_wie_lean():
    """Für jede Eingabe: Ort, Quelle, Ergebnis, Satz, Regel-Trace in derselben Reihenfolge und
    Fundstelle, oder Abbruch mit derselben Regel und demselben Grund."""
    zeilen = abweichungen(LEAN["kern"], lambda e: antwort_kern(rules.Merkmale(**e)))
    assert not zeilen, bericht(zeilen, len(LEAN["kern"]))


def test_lean_nennt_nur_regeln_aus_rules_md():
    """Lean liest RULES.md nicht; jede Regel, die das Modell nennt, muss dort stehen."""
    regeln = set()
    for e in LEAN["kern"] + LEAN["satz_position"]:
        a = e["antwort"]
        regeln |= {a["abbruch"]["regel"]} if "abbruch" in a else set(a.get("regeln", ()))
    assert regeln <= AKTIVE_REGELN, regeln - AKTIVE_REGELN


# ---------------------------------------------------------------- satz_position()

def test_satz_position_eingaben_sind_vollstaendig():
    """Der Satz kommt aus kern(): nur 19 oder 0 (in Lean bewiesen, `satz_aus_kern`)."""
    eingaben = [tuple(e["eingabe"].values()) for e in LEAN["satz_position"]]
    assert len(eingaben) == len(set(eingaben))
    assert set(eingaben) == set(itertools.product((19, 0), (True, False), (True, False)))
    assert {k.satz for m in ALLE if isinstance(k := rules.kern(m), rules.KernErgebnis)} == {19, 0}


def test_satz_position_antwortet_wie_lean():
    zeilen = abweichungen(LEAN["satz_position"], lambda e: antwort_satz(**e))
    assert not zeilen, bericht(zeilen, len(LEAN["satz_position"]))


# ---------------------------------------------------------------- Einordnung → Gruppe, Fundstelle

def test_einordnungen_wie_lean():
    lean = {e["wort"]: (e["gruppe"], e["fundstelle"]) for e in LEAN["einordnung"]}
    assert len(lean) == len(LEAN["einordnung"])
    assert lean == rules.EINORDNUNGEN
