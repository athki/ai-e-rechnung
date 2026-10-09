"""festschreiben: Status, Schreibschutz, Hashes – und dass `bauen` danach verweigert.

`--gesendet-am` ist Pflicht: Unveränderbar wird eine Rechnung, weil sie ausgestellt ist
(§ 14 UStG), und ausgestellt ist sie, wenn sie beim Empfänger war. Das Werkzeug verschickt
nichts; es hält fest, wann du verschickt hast.
"""

import os
import shutil
from datetime import date

import pytest
import yaml

from rechnung import config, festschreiben, render, resolve as r

BRAUCHT_LATEX = pytest.mark.skipif(shutil.which("latexmk") is None, reason="latexmk fehlt")

RECHNUNG = """\
kunde: sample-ltd
datum: 2026-09-23
leistungsdatum: 2026-06-10
leistung:
  taetigkeit: Teilnahme als Panelist
  einordnung: sonstige
positionen:
  - beschreibung: Teilnahme als Panelist
    menge: 1
    einheit: pauschal
    einzelpreis: 1000.00
"""


@pytest.fixture
def gewerbe(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path))
    shutil.copytree(config.BEISPIEL_STAMMDATEN, tmp_path / "stammdaten")
    config.init(config.laden())
    yield tmp_path
    for ordner in tmp_path.rglob("*"):       # Schreibschutz weg, sonst scheitert das Aufräumen
        if ordner.is_dir():
            festschreiben.schreibbar_machen(ordner)


def gebaute_rechnung():
    cfg = config.laden()
    ordner, nummer = r.neu(cfg, "sample-ltd", date(2026, 6, 10), date(2026, 9, 23))
    (ordner / r.INPUT_DATEI).write_text(RECHNUNG, encoding="utf-8")
    ergebnis, _ = r.resolve(cfg, nummer)
    render.baue_pdf(ergebnis, ordner, cfg.engine)
    return ordner, nummer


@BRAUCHT_LATEX
def test_festschreiben_haelt_beide_daten_fest(gewerbe):
    """Versanddatum und Festschreibedatum können auseinanderfallen – beide stehen drin."""
    ordner, _ = gebaute_rechnung()
    assert not festschreiben.ist_festgeschrieben(ordner)

    daten = festschreiben.festschreiben(ordner, gesendet_am=date(2026, 9, 20), am=date(2026, 9, 22))

    assert daten["status"] == "festgeschrieben"
    assert daten["gesendet_am"] == "2026-09-20"
    assert daten["festgeschrieben_am"] == "2026-09-22"
    gespeichert = yaml.safe_load((ordner / "status.yaml").read_text(encoding="utf-8"))
    pdf = festschreiben._pdf(ordner)
    assert pdf.name == f"invoice_{ordner.name}.pdf"          # Präfix nach Sprache, Nummer im Namen
    assert gespeichert["hash"][pdf.name] == festschreiben.hash_datei(pdf)
    assert len(gespeichert["hash"]) == 3


@BRAUCHT_LATEX
def test_festschreiben_entzieht_die_schreibrechte(gewerbe):
    ordner, _ = gebaute_rechnung()
    festschreiben.festschreiben(ordner, date(2026, 9, 20))

    assert festschreiben.ist_festgeschrieben(ordner)
    assert not os.access(festschreiben._pdf(ordner), os.W_OK)
    assert not os.access(ordner / "rechnung.resolved.json", os.W_OK)


@BRAUCHT_LATEX
def test_vor_dem_festschreiben_darf_beliebig_oft_gebaut_werden(gewerbe):
    """Mehrere Anläufe sind der Normalfall – eingefroren wird nur auf ausdrücklichen Befehl."""
    ordner, nummer = gebaute_rechnung()
    cfg = config.laden()
    for _ in range(3):
        ergebnis, _ = r.resolve(cfg, nummer)
        render.baue_pdf(ergebnis, ordner, cfg.engine)
    assert not festschreiben.ist_festgeschrieben(ordner)


@BRAUCHT_LATEX
def test_zweimal_festschreiben_geht_nicht(gewerbe):
    ordner, _ = gebaute_rechnung()
    festschreiben.festschreiben(ordner, date(2026, 9, 20))
    with pytest.raises(festschreiben.FestschreibFehler, match="bereits festgeschrieben"):
        festschreiben.festschreiben(ordner, date(2026, 9, 21))


@BRAUCHT_LATEX
def test_bauen_verweigert_nach_dem_festschreiben(gewerbe):
    from typer.testing import CliRunner

    from rechnung.cli import app

    ordner, nummer = gebaute_rechnung()
    festschreiben.festschreiben(ordner, date(2026, 9, 20))

    ergebnis = CliRunner().invoke(app, ["bauen", nummer])

    assert ergebnis.exit_code == 1
    assert "festgeschrieben" in ergebnis.output or "festgeschrieben" in str(ergebnis.exception or "")


@BRAUCHT_LATEX
def test_cli_verlangt_gesendet_am(gewerbe):
    from typer.testing import CliRunner

    from rechnung.cli import app

    _, nummer = gebaute_rechnung()

    ohne = CliRunner().invoke(app, ["festschreiben", nummer])
    assert ohne.exit_code != 0
    assert "gesendet-am" in ohne.output.replace("\n", "")

    zukunft = CliRunner().invoke(app, ["festschreiben", nummer, "--gesendet-am", "2099-01-01"])
    assert zukunft.exit_code == 1
    assert "Zukunft" in zukunft.output

    heute = date.today().isoformat()
    mit = CliRunner().invoke(app, ["festschreiben", nummer, "--gesendet-am", heute])
    assert mit.exit_code == 0
    assert f"gesendet am        {heute}" in mit.output


@BRAUCHT_LATEX
def test_aenderung_nach_dem_festschreiben_faellt_auf(gewerbe):
    ordner, _ = gebaute_rechnung()
    festschreiben.festschreiben(ordner, date(2026, 9, 20))
    assert festschreiben.pruefe_unveraendert(ordner) == []

    pdf = festschreiben._pdf(ordner)
    festschreiben.schreibschutz_aufheben(pdf)
    pdf.write_bytes(b"%PDF-1.7 etwas anderes")

    assert festschreiben.pruefe_unveraendert(ordner) == [
        f"{pdf.name} wurde nach dem Einfrieren geändert"]


# ---------------------------------------------------------------- Pro forma

def pro_forma_bauen(ordner, nummer):
    cfg = config.laden()
    ergebnis, _ = r.resolve(cfg, nummer)
    return render.baue_pdf(ergebnis, ordner, cfg.engine, pro_forma=True)


@BRAUCHT_LATEX
def test_pro_forma_revisionen_werden_eingefroren(gewerbe):
    ordner, nummer = gebaute_rechnung()
    arbeitskopie = pro_forma_bauen(ordner, nummer)
    assert arbeitskopie.name == f"invoice-pro-forma_{nummer}.pdf"

    erste = festschreiben.pro_forma_festhalten(ordner, date(2026, 9, 18), am=date(2026, 9, 18))
    assert erste["revision"] == 1
    rev1 = ordner / "pro-forma" / "1"
    assert sorted(p.name for p in rev1.iterdir()) == [
        f"invoice-pro-forma-1_{nummer}.pdf", "rechnung.resolved.json", "rechnung.yaml"]
    assert all(not os.access(p, os.W_OK) for p in rev1.iterdir())

    # Änderung, neu bauen, zweite Revision; die erste bleibt unberührt.
    eingabe = ordner / "rechnung.yaml"
    eingabe.write_text(eingabe.read_text(encoding="utf-8") + 'referenz: "PO 4711"\n', encoding="utf-8")
    pro_forma_bauen(ordner, nummer)
    zweite = festschreiben.pro_forma_festhalten(ordner, date(2026, 9, 20))
    assert zweite["revision"] == 2
    status = festschreiben.status_lesen(ordner)
    assert status["status"] == "entwurf"
    assert [e["gesendet_am"] for e in status["pro_forma"]] == ["2026-09-18", "2026-09-20"]
    assert "PO 4711" not in (rev1 / "rechnung.yaml").read_text(encoding="utf-8")
    assert festschreiben.pruefe_unveraendert(ordner) == []

    # Danach die echte Rechnung: festschreiben behält die Pro-forma-Revisionen in status.yaml.
    cfg = config.laden()
    ergebnis, _ = r.resolve(cfg, nummer)
    render.baue_pdf(ergebnis, ordner, cfg.engine)
    daten = festschreiben.festschreiben(ordner, date(2026, 9, 22))
    assert len(daten["pro_forma"]) == 2
    with pytest.raises(festschreiben.FestschreibFehler, match="festgeschrieben"):
        festschreiben.pro_forma_festhalten(ordner, date(2026, 9, 23))


@BRAUCHT_LATEX
def test_pro_forma_veraltet_wird_nicht_eingefroren(gewerbe):
    ordner, nummer = gebaute_rechnung()
    pro_forma_bauen(ordner, nummer)
    eingabe = ordner / "rechnung.yaml"
    eingabe.write_text(eingabe.read_text(encoding="utf-8") + 'referenz: "neu"\n', encoding="utf-8")
    with pytest.raises(festschreiben.FestschreibFehler, match="passt nicht mehr"):
        festschreiben.pro_forma_festhalten(ordner, date(2026, 9, 18))


def test_pro_forma_ohne_arbeitskopie_sagt_was_fehlt(gewerbe):
    cfg = config.laden()
    ordner, nummer = r.neu(cfg, "sample-ltd", date(2026, 6, 10), date(2026, 9, 23),
                           taetigkeit="Panel", einordnung="sonstige")
    r.resolve(cfg, nummer)
    with pytest.raises(festschreiben.FestschreibFehler, match="--pro-forma"):
        festschreiben.pro_forma_festhalten(ordner, date(2026, 9, 18))


@BRAUCHT_LATEX
def test_geaenderte_pro_forma_revision_faellt_auf(gewerbe):
    ordner, nummer = gebaute_rechnung()
    pro_forma_bauen(ordner, nummer)
    festschreiben.pro_forma_festhalten(ordner, date(2026, 9, 18))
    kopie = ordner / "pro-forma" / "1" / "rechnung.yaml"
    festschreiben.schreibschutz_aufheben(kopie)
    kopie.write_text("geändert", encoding="utf-8")
    assert festschreiben.pruefe_unveraendert(ordner) == [
        "pro-forma/1/rechnung.yaml wurde nach dem Einfrieren geändert"]


def test_festschreiben_ohne_pdf_sagt_was_fehlt(gewerbe):
    cfg = config.laden()
    ordner, _ = r.neu(cfg, "sample-ltd", date(2026, 6, 10), date(2026, 9, 23))
    with pytest.raises(festschreiben.FestschreibFehler, match="rechnung bauen"):
        festschreiben.festschreiben(ordner, date(2026, 9, 20))


def test_status_ohne_datei_ist_entwurf(tmp_path):
    assert festschreiben.status_lesen(tmp_path) == {"status": "entwurf"}
    assert not festschreiben.ist_festgeschrieben(tmp_path)
    assert festschreiben.pruefe_unveraendert(tmp_path) == []
