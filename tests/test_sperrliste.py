"""Commit-Wächter (.githooks/sperrliste.py) mit einer erfundenen Musterliste."""

import importlib.util
import shutil
import subprocess
import sys

import pytest

from rechnung.config import REPO

spec = importlib.util.spec_from_file_location("sperrliste", REPO / ".githooks" / "sperrliste.py")
sperrliste = importlib.util.module_from_spec(spec)
sys.modules["sperrliste"] = sperrliste   # Dataclasses brauchen das Modul in sys.modules
spec.loader.exec_module(sperrliste)

MUSTERLISTE = """\
# Musterliste – erfunden
Erika Geheimnis
Geheimweg 12
DE00 1234 5678 9012 3456 78   # IBAN, mit Leerzeichen eingetragen
999/888/77777                 # Steuernummer
=ZZ                           # Kürzel, nur genau so und als ganzes Wort
QRX                           # kurz: ganzes Wort, Groß/Klein egal
"""

HAT_POPPLER = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext fehlt")


@pytest.fixture
def liste(tmp_path, monkeypatch):
    pfad = tmp_path / "sperrliste.txt"
    pfad.write_text(MUSTERLISTE, encoding="utf-8")
    monkeypatch.setenv("RECHNUNG_SPERRLISTE", str(pfad))
    return sperrliste.lade(pfad)


def zeilen(text, liste):
    return [z for z, _ in sperrliste.treffer(text, liste)]


# ---------------------------------------------------------------- Regeln

def test_gross_klein_egal(liste):
    assert zeilen("Rechnung von ERIKA GEHEIMNIS", liste) == [2]


def test_ziffern_ohne_trenner(liste):
    assert zeilen("IBAN DE00123456789012345678", liste) == [4]
    assert zeilen("St.-Nr. 99988877777", liste) == [5]


def test_kurz_nur_als_ganzes_wort(liste):
    assert zeilen("ZZ-2026-0001", liste) == [6]
    assert zeilen("Puzzle, ZZZ, zz", liste) == []          # Teilwort bzw. falsche Schreibung
    assert zeilen("Flug QRX–FRA", liste) == [7]
    assert zeilen("qrx", liste) == [7]
    assert zeilen("QRXY", liste) == []


def test_sauberer_text(liste):
    assert zeilen("Max Mustermann, Musterstraße 1, 12345 Musterstadt", liste) == []


def test_pfad_neben_der_config():
    assert sperrliste.sperrliste_pfad({"RECHNUNG_CONFIG": "/c/config.toml"}).as_posix() == "/c/sperrliste.txt"
    assert sperrliste.sperrliste_pfad(
        {"RECHNUNG_SPERRLISTE": "/s.txt", "RECHNUNG_CONFIG": "/c/config.toml"}).as_posix() == "/s.txt"
    assert sperrliste.sperrliste_pfad({"XDG_CONFIG_HOME": "/x"}).as_posix() == "/x/rechnung/sperrliste.txt"


@pytest.mark.parametrize("env", [
    {}, {"RECHNUNG_CONFIG": "/c/config.toml"}, {"XDG_CONFIG_HOME": "/x"},
    {"RECHNUNG_SPERRLISTE": "/s.txt", "RECHNUNG_CONFIG": "/c/config.toml"},
])
def test_hook_und_doctor_suchen_am_selben_ort(env):
    from rechnung import config
    assert sperrliste.sperrliste_pfad(env) == config.sperrliste_pfad(env)


def test_meldung_nennt_den_begriff_nicht(liste):
    [meldung] = sperrliste.pruefe_inhalt("a.txt", "x\nErika Geheimnis\n".encode(), liste)
    assert "Geheimnis" not in meldung
    assert "Zeile 2" in meldung and "Zeile 2 der Sperrliste" in meldung


def test_kurze_begriffe_nicht_in_rohdaten(liste):
    assert zeilen("\x8aZZ%\x00", liste) == [6]
    assert [z for z, _ in sperrliste.treffer("\x8aZZ%\x00", liste, roh=True)] == []
    assert [z for z, _ in sperrliste.treffer("Erika Geheimnis", liste, roh=True)] == [2]


@HAT_POPPLER
def test_pdf_text_wird_geprueft(tmp_path):
    pfad = tmp_path / "liste.txt"
    pfad.write_text("Mustermann\n", encoding="utf-8")
    daten = (REPO / "vorlage" / "beispiel.pdf").read_bytes()
    meldungen = sperrliste.pruefe_inhalt("beispiel.pdf", daten, sperrliste.lade(pfad))
    assert any("PDF-Text" in m for m in meldungen)


# ---------------------------------------------------------------- Hooks im echten Git

def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    git(r, "config", "user.name", "Test")
    git(r, "config", "user.email", "test@example.com")
    shutil.copytree(REPO / ".githooks", r / ".githooks")
    git(r, "config", "core.hooksPath", ".githooks")
    return r


def test_commit_mit_gesperrtem_inhalt_wird_abgewiesen(repo, liste):
    (repo / "notiz.txt").write_text("Gezahlt von Erika Geheimnis\n", encoding="utf-8")
    git(repo, "add", "notiz.txt")
    aus = git(repo, "commit", "-m", "Notiz", check=False)
    assert aus.returncode != 0
    assert "Zeile 2 der Sperrliste" in aus.stderr
    assert "Geheimnis" not in aus.stderr


def test_commit_message_wird_geprueft(repo, liste):
    (repo / "a.txt").write_text("sauber\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    aus = git(repo, "commit", "-m", "Rechnung ZZ-2026-0001", check=False)
    assert aus.returncode != 0
    assert "Commit-Message" in aus.stderr


def test_sauberer_commit_geht_durch(repo, liste):
    (repo / "a.txt").write_text("Max Mustermann\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    assert git(repo, "commit", "-m", "Beispiel", check=False).returncode == 0


def test_doctor_waechter(repo, tmp_path):
    from rechnung import doctor
    liste = tmp_path / "liste.txt"
    env = {"RECHNUNG_SPERRLISTE": str(liste)}
    assert doctor.pruefe_waechter(env, repo).status == doctor.OK          # keine Sperrliste
    liste.write_text("Erika Geheimnis\n", encoding="utf-8")
    assert doctor.pruefe_waechter(env, repo).status == doctor.OK          # Liste da, Wächter an
    git(repo, "config", "--unset", "core.hooksPath")
    aus = doctor.pruefe_waechter(env, repo)
    assert aus.status == doctor.FEHLER and "make hooks" in aus.detail
    assert doctor.pruefe_waechter(env, tmp_path / "kein-repo").status == doctor.OK


def test_ohne_sperrliste_still(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_SPERRLISTE", str(tmp_path / "gibt-es-nicht.txt"))
    (repo / "a.txt").write_text("Erika Geheimnis\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    aus = git(repo, "commit", "-m", "ohne Liste", check=False)
    assert aus.returncode == 0 and aus.stderr == ""
