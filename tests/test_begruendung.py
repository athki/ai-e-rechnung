"""Begründung je Rechnung (RULES.md R35): RULES.md als Quelle, Spur, Fakten, Festlegung, Pro forma."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rechnung import begruendung as b, config, resolve as r, rules
from rechnung.cli import app

from test_resolve import gewerbe, lege_an  # noqa: F401 – Fixture
from test_rules import AKTIVE_REGELN, ALLE

REPO = Path(__file__).parent.parent
REGELN, QUELLEN = b.regeln_laden()


# ---------------------------------------------------------------- RULES.md als Quelle

def test_rules_md_hat_jede_aktive_regel_in_fester_form():
    assert set(REGELN) == AKTIVE_REGELN
    for regel in REGELN.values():
        assert regel.nachweis in b.NACHWEISE


def moegliche_spur_regeln() -> set[str]:
    """Jede ID, die in `regeln` einer resolved.json stehen kann."""
    ids = {"R32", "R33", "R34"}   # resolve.regel_trace()
    for m in ALLE:
        k = rules.kern(m)
        if isinstance(k, rules.KernErgebnis):
            ids |= set(k.regeln)
    return ids


def test_jede_regel_der_spur_hat_einen_vollstaendigen_eintrag():
    for rid in moegliche_spur_regeln():
        regel = REGELN[rid]
        for feld in ("Quelle", "Regel", "Annahmen", "Status", "Nachweis"):
            assert regel.felder.get(feld, "").strip(), (rid, feld)
        for q in re.findall(r"\bQ\d+\b", regel.felder["Quelle"]):
            assert q in QUELLEN, (rid, q)


AUSSAGEN = re.findall(r"^def ((R\d+(?:_R\d+)*)_\w+) : Prop", (REPO / "lean/Rechnung/Aussagen.lean")
                      .read_text(encoding="utf-8"), flags=re.M)


def test_nachweis_bewiesen_genau_bei_lean_aussagen():
    """`bewiesen` steht genau bei den Regeln mit Lean-Aussage, und jede Regel nennt genau ihre Aussagen."""
    assert AUSSAGEN, "keine Aussagen in lean/Rechnung/Aussagen.lean gefunden"
    erwartet: dict[str, set[str]] = {}
    for name, ids in AUSSAGEN:
        for rid in ids.split("_"):
            erwartet.setdefault(rid, set()).add(f"Aussage.{name}")
    for rid, regel in REGELN.items():
        genannt = set(re.findall(r"`(Aussage\.\w+)`", regel.felder["Nachweis"]))
        assert genannt == erwartet.get(rid, set()), rid
        assert (regel.nachweis == "bewiesen") == (rid in erwartet), rid


def test_annahmen_aus_passt_stehen_in_rules_md():
    """Jede Regel, die ein Feld von `Passt` (Bruecke.lean) nennt, hat in RULES.md echte Annahmen."""
    bruecke = (REPO / "lean/Rechnung/Bruecke.lean").read_text(encoding="utf-8")
    ids = {rid for feld in re.findall(r"^\s+annahme_((?:R\d+_)+)", bruecke, flags=re.M)
           for rid in feld.rstrip("_").split("_")}
    assert ids >= {"R3", "R4", "R5", "R6", "R13"}
    for rid in ids:
        annahmen = REGELN[rid].felder.get("Annahmen", "").strip()
        assert annahmen and not annahmen.startswith("keine"), rid


GUT = """\
#### R1 – Probe

- **Quelle:** Q1.
- **Regel:** Text.
- **Status:** Annahme – ungeprüft.
- **Nachweis:** getestet – Probe.
"""


@pytest.mark.parametrize("kaputt", [
    GUT.replace("**Regel:**", "**Regl:**"),
    GUT.replace("- **Nachweis:** getestet – Probe.\n", ""),
    GUT.replace("Annahme – ungeprüft", "geprüft"),
    GUT.replace("getestet – Probe", "vermutet"),
    GUT + "freier Text ohne Feld\n",
])
def test_parser_ist_streng(kaputt):
    assert b.regeln_lesen(GUT)[0]["R1"].nachweis == "getestet"
    with pytest.raises(b.BegruendungFehler):
        b.regeln_lesen(kaputt)


def test_entfallene_regel_wird_nicht_gelesen():
    assert "R36" not in REGELN


# ---------------------------------------------------------------- Begründung einer Rechnung

def aufgeloest(nummer: str) -> Path:
    _, ziel = r.resolve(config.laden(), nummer)
    return ziel.parent


def test_begruendung_folgt_der_spur(gewerbe):
    ordner = aufgeloest(lege_an(gewerbe, "sample-ltd"))
    text, passt = b.begruende(ordner)
    ergebnis = b.lade(ordner)
    assert passt
    positionen = [text.index(f"### {i}. {rid} – {REGELN[rid].titel}") for i, rid in enumerate(ergebnis.regeln, 1)]
    assert positionen == sorted(positionen)
    assert "Sitz bzw. Wohnsitz des Kunden (R3)" in text
    assert "| Unternehmer | `kunden/sample-ltd.yaml: unternehmer` | ja |" in text
    assert "Spur:** geprüft" in text
    assert "Ein Steuerberater hat RULES.md nicht geprüft" in text
    # Der Pflichttext steht wörtlich bei R31, dem einzigen Hinweis dieser Rechnung.
    hinweis = next(iter(ergebnis.hinweis.values()))
    assert text.count(f"**Auf der Rechnung:** „{hinweis}“") == 1
    assert text.index("Auf der Rechnung") > text.index("### 5. R31")
    assert "R37" not in text and "Begründung der Festlegung" not in text


def test_festlegung_wird_als_solche_gezeigt(gewerbe):
    ordner = aufgeloest(lege_an(gewerbe, "exemple-sarl", leistungsort="CH",
                                begruendung="Leistung an die Niederlassung in Zürich"))
    text, passt = b.begruende(ordner)
    assert passt
    assert "manuell festgelegt (R37)" in text
    assert text.count("„Leistung an die Niederlassung in Zürich“") == 2   # Kopf und R37
    assert "**Fundstelle aus § 3a:** keine" in text
    assert "„nie anders als\n  das Gesetz“ gilt nur ohne Festlegung" in text


def test_ermaessigter_satz_steht_bei_den_fakten(gewerbe):
    positionen = ("  - beschreibung: Vortrag\n    menge: 1\n    einheit: pauschal\n    einzelpreis: 100\n"
                  "  - beschreibung: Nutzungsrechte\n    menge: 1\n    einheit: pauschal\n    einzelpreis: 50\n"
                  "    steuersatz: 7\n")
    ordner = aufgeloest(lege_an(gewerbe, "muster-gmbh", positionen=positionen))
    text, passt = b.begruende(ordner)
    assert passt
    assert "`rechnung.yaml: positionen[2].steuersatz` | 7 | § 12 Abs. 2 UStG (R10)" in text


def test_geaenderte_eingabe_wird_gemeldet(gewerbe):
    ordner = aufgeloest(lege_an(gewerbe, "sample-ltd"))
    with (ordner / r.INPUT_DATEI).open("a", encoding="utf-8") as f:
        f.write("referenz: nachgereicht\n")
    text, passt = b.begruende(ordner)
    assert passt
    assert "nach dem letzten `resolve` geändert" in text


def test_abweichende_spur_ist_rot(gewerbe):
    ordner = aufgeloest(lege_an(gewerbe, "sample-ltd"))
    pfad = ordner / r.RESOLVED_DATEI
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["regeln"] = [rid for rid in daten["regeln"] if rid != "R31"]
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    text, passt = b.begruende(ordner)
    assert not passt
    assert "**weicht ab**" in text and "Regeln heute" in text
    lauf = CliRunner().invoke(app, ["begruendung", str(ordner)])
    assert lauf.exit_code == 1
    assert "weicht ab" in lauf.output


def test_ohne_resolved_json_nennt_den_weg(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    with pytest.raises(b.BegruendungFehler, match="rechnung resolve"):
        b.begruende(r.finde_ordner(config.laden(), nummer))


def test_regelstand(gewerbe):
    ordner = aufgeloest(lege_an(gewerbe, "sample-ltd"))
    ergebnis = b.lade(ordner)
    st, spur = b.stand(ordner, ergebnis), b.spur_pruefen(ergebnis)
    gleich = b.text(ergebnis, REGELN, QUELLEN, st, spur, ergebnis.vorlage_version)
    anders = b.text(ergebnis, REGELN, QUELLEN, st, spur, "0000000")
    ohne_git = b.text(ergebnis, REGELN, QUELLEN, st, spur, "unbekannt")
    assert "beim Bau und heute gleich" in gleich and "Achtung" not in gleich
    assert f"git checkout {ergebnis.vorlage_version}" in anders
    assert "ohne Git nicht vergleichbar" in ohne_git


def test_festgeschrieben_und_pro_forma_revision(gewerbe):
    ordner = aufgeloest(lege_an(gewerbe, "sample-ltd"))
    revision = ordner / "pro-forma" / "1"
    revision.mkdir(parents=True)
    for datei in (r.INPUT_DATEI, r.RESOLVED_DATEI):
        (revision / datei).write_bytes((ordner / datei).read_bytes())
    (ordner / "status.yaml").write_text(
        "status: festgeschrieben\ngesendet_am: '2026-09-23'\n"
        "pro_forma:\n- revision: 1\n  gesendet_am: '2026-09-01'\n", encoding="utf-8")

    rechnung, _ = b.begruende(ordner)
    assert "Rechnung, festgeschrieben, gesendet am 2026-09-23" in rechnung
    assert "Pro-forma-Revisionen:** 1" in rechnung

    pro_forma, passt = b.begruende(revision)
    assert passt
    assert "Pro-forma-Revision 1, gesendet am 2026-09-01" in pro_forma
    assert "(R38)" in pro_forma


def test_befehl_nimmt_die_nummer(gewerbe):
    nummer = lege_an(gewerbe, "privat-ch", leistung="  taetigkeit: Vortrag\n  einordnung: unterrichtend\n  ort: CH")
    aufgeloest(nummer)
    lauf = CliRunner().invoke(app, ["begruendung", nummer])
    assert lauf.exit_code == 0, lauf.output
    assert "Ort der Tätigkeit (R5)" in lauf.output
