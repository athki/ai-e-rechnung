"""Geltungsbereich (RULES.md Teil 1, R39): dieselbe Kurzfassung an jeder Oberfläche, Lieferungen in
der Preisliste sichtbar markiert. Der Abbruch selbst: test_rules.py und test_resolve.py."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from rechnung import config, doctor as doctor_mod, rules
from rechnung.cli import app

from test_resolve import gewerbe  # noqa: F401 – Fixture

REPO = Path(__file__).parent.parent


def fliesstext(text: str) -> str:
    """Zeilenumbrüche, Einrückung und Zitatzeichen aus Markdown weg, damit nur der Wortlaut zählt."""
    return re.sub(r"\s+", " ", re.sub(r"^\s*> ?", "", text, flags=re.M))


def test_kurzfassung_steht_woertlich_in_readme_rules_und_skill():
    for datei in ("README.md", "RULES.md", ".claude/skills/rechnung/SKILL.md"):
        assert rules.GELTUNGSBEREICH in fliesstext((REPO / datei).read_text(encoding="utf-8")), datei


def test_kurzfassung_nennt_wortlaut_der_entscheidung():
    assert "Das Werkzeug kann noch nicht:" in rules.GELTUNGSBEREICH
    assert "noch nicht rechtlich oder steuerlich geprüft" in rules.GELTUNGSBEREICH


def test_neu_zeigt_die_kurzfassung(gewerbe):
    aus = CliRunner().invoke(app, ["neu", "--kunde", "muster-gmbh"])
    assert aus.exit_code == 0, aus.output
    assert rules.GELTUNGSBEREICH in aus.output


def test_doctor_zeigt_die_kurzfassung_auch_bei_rot(monkeypatch):
    for status in (doctor_mod.OK, doctor_mod.FEHLER):
        monkeypatch.setattr(doctor_mod, "alle", lambda: [doctor_mod.Pruefung("Probe", status)])
        assert rules.GELTUNGSBEREICH in CliRunner().invoke(app, ["doctor"]).output


def test_preisliste_markiert_lieferungen(gewerbe):
    aus = CliRunner().invoke(app, ["preisliste"])
    assert aus.exit_code == 0, aus.output
    [buch] = [z for z in aus.output.splitlines() if z.strip().startswith("buch ")]
    assert "lieferung" in buch and rules.VERMERK_LIEFERUNG in buch
    assert rules.VERMERK_LIEFERUNG not in aus.output.replace(buch, "")


def test_beispiel_preisliste_fuehrt_eine_lieferung():
    from rechnung import resolve as r
    liste = r.lade_preisliste(config.laden(env={}, pfad=REPO / "fehlt.toml"))
    assert [k for k, e in liste.items() if e.art == rules.LIEFERUNG] == ["buch"]
