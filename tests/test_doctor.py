import re

import pytest

from rechnung import doctor
from rechnung.config import REPO


def test_tex_pakete_liste_ist_lesbar():
    pakete = doctor.tex_pakete()
    dateien = [d for _, d in pakete]
    assert len(dateien) == len(set(dateien)), "jede Prüfdatei nur einmal"
    # Ein tlmgr-Paket darf mehrfach vorkommen (tools liefert array.sty und tabularx.sty).
    assert {"latexmk", "latex-bin", "xcharter", "fira"} <= {p for p, _ in pakete}


def test_tex_pakete_falsches_format(tmp_path):
    datei = tmp_path / "p.txt"
    datei.write_text("fontspec\n", encoding="utf-8")
    with pytest.raises(ValueError):
        doctor.tex_pakete(datei)


def test_dockerfile_nutzt_dieselbe_paketliste():
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "docs/tex-pakete.txt" in dockerfile
    assert re.search(r"tlmgr install", dockerfile)


def test_doctor_ohne_config_ist_demo(tmp_path, monkeypatch):
    for var in ["RECHNUNG_GEWERBE", "RECHNUNG_CONFIG"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    cfg = doctor.config.laden()
    assert doctor.pruefe_config(cfg, None).status == doctor.WARNUNG
    [gewerbe] = doctor.pruefe_gewerbe(cfg)
    assert gewerbe.status == doctor.WARNUNG


def test_doctor_mit_gewerbe_meldet_fehlende_unterordner(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path))
    ergebnis = {p.name: p for p in doctor.pruefe_gewerbe(doctor.config.laden())}
    assert ergebnis["Gewerbe-Ordner"].status == doctor.OK
    assert ergebnis["Unterordner"].status == doctor.WARNUNG


def test_doctor_gewerbe_nicht_erreichbar(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path / "weg"))
    [p] = doctor.pruefe_gewerbe(doctor.config.laden())
    assert p.status == doctor.FEHLER
