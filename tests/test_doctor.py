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


def test_doctor_lean_fehlt_ist_nur_warnung(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda programm: None)
    assert doctor.pruefe_lean().status == doctor.WARNUNG


def test_doctor_lean_nennt_festgelegte_version(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.shutil, "which", lambda programm: "/usr/bin/" + programm)
    monkeypatch.setattr(doctor, "_version", lambda *args: "elan 9.9.9")
    datei = tmp_path / "lean-toolchain"
    datei.write_text("leanprover/lean4:v4.0.0\n", encoding="utf-8")
    p = doctor.pruefe_lean(datei)
    assert p.status == doctor.OK and "v4.0.0" in p.detail


# ---------------------------------------------------------------- Lean (Schritt 8.3)

LEAN = REPO / "lean"


def test_lean_version_ist_fest():
    """Eine exakte Lean-Version, nie `stable`: der Beweis-Container baut mit derselben wie der Host."""
    toolchain = (LEAN / "lean-toolchain").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"leanprover/lean4:v\d+\.\d+\.\d+", toolchain), toolchain


def test_lean_beweise_ohne_sorry_und_native_decide():
    """Fängt schon in pytest, was die Axiom-Prüfung im Beweis-Container verweigern würde."""
    for datei in (LEAN / "Rechnung").rglob("*.lean"):
        text = datei.read_text(encoding="utf-8")
        assert not re.search(r"\bsorry\b|\bnative_decide\b", text), datei


def test_lean_nicht_im_rechnungs_image():
    """Das Rechnungs-Image bleibt ohne Lean; nur der Beweis-Container bekommt lean/."""
    assert "lean" in (REPO / ".dockerignore").read_text(encoding="utf-8").split()
    beweise = (REPO / "Dockerfile.beweise").read_text(encoding="utf-8")
    assert re.search(r"^FROM rechnung$", beweise, flags=re.M)
    assert "lean/lean-toolchain" in beweise
