"""Der PreToolUse-Hook .claude/hooks/schutz.sh sperrt Schreibzugriffe auf geschützte Dateien."""

import json
import shutil
import subprocess

import pytest

from rechnung.config import REPO

HOOK = REPO / ".claude" / "hooks" / "schutz.sh"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="jq fehlt")


def hook(tmp_path, werkzeug, gewerbe=None, **tool_input):
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path),
           "RECHNUNG_CONFIG": str(tmp_path / "fehlt.toml")}
    if gewerbe:
        env["RECHNUNG_GEWERBE"] = str(gewerbe)
    eingabe = json.dumps({"tool_name": werkzeug, "tool_input": tool_input})
    return subprocess.run([str(HOOK)], input=eingabe, capture_output=True, text=True, env=env)


@pytest.mark.parametrize("pfad", [
    "/g/rechnung-ausgang/2026/2026-0001/rechnung.resolved.json",
    "/g/rechnung-ausgang/2026/2026-0001/rechnung.pdf",
    "/g/rechnung-ausgang/2026/2026-0001/belege/flug.PDF",
    "/g/rechnung-ausgang/2026/2026-0001/status.yaml",
    "/g/stammdaten/ich.yaml",
    "/g/rechnung-ausgang/2026/2026-0001/pro-forma/1/rechnung.yaml",
])
@pytest.mark.parametrize("werkzeug", ["Write", "Edit", "MultiEdit"])
def test_geschuetzte_pfade_blockiert(tmp_path, werkzeug, pfad):
    aus = hook(tmp_path, werkzeug, file_path=pfad)
    assert aus.returncode == 2, aus.stderr
    assert "schutz.sh" in aus.stderr


@pytest.mark.parametrize("pfad", [
    "/g/rechnung-ausgang/2026/2026-0001/rechnung.yaml",
    "/g/stammdaten/kunden/sample-ltd.yaml",
    str(REPO / "stammdaten.example" / "ich.yaml"),
    str(REPO / "src" / "rechnung" / "cli.py"),
])
def test_erlaubte_pfade(tmp_path, pfad):
    assert hook(tmp_path, "Write", file_path=pfad).returncode == 0


def test_ich_yaml_unter_umbenanntem_stammdatenordner(tmp_path):
    env_gewerbe = tmp_path / "Gewerbe mit Leerzeichen"
    aus = subprocess.run(
        [str(HOOK)],
        input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": f"{env_gewerbe}/daten/ich.yaml"}}),
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path),
             "RECHNUNG_CONFIG": str(tmp_path / "fehlt.toml"),
             "RECHNUNG_GEWERBE": str(env_gewerbe), "RECHNUNG_STAMMDATEN": "daten"},
    )
    assert aus.returncode == 2


def test_festgeschriebene_rechnung_ist_gesperrt(tmp_path):
    ordner = tmp_path / "2026-0001"
    (ordner / "belege").mkdir(parents=True)
    (ordner / "status.yaml").write_text(
        "status: festgeschrieben\ngesendet_am: 2026-09-22\n", encoding="utf-8")
    assert hook(tmp_path, "Edit", file_path=str(ordner / "rechnung.yaml")).returncode == 2
    assert hook(tmp_path, "Write", file_path=str(ordner / "belege" / "notiz.txt")).returncode == 2

    (ordner / "status.yaml").write_text("status: entwurf\n", encoding="utf-8")
    assert hook(tmp_path, "Edit", file_path=str(ordner / "rechnung.yaml")).returncode == 0


@pytest.mark.parametrize("befehl", [
    "echo {} > /g/2026-0001/rechnung.resolved.json",
    "cp alt.pdf /g/2026-0001/rechnung.pdf",
    "sed -i '' 's/entwurf/gesendet/' /g/2026-0001/status.yaml",
    "rm /g/2026-0001/rechnung.pdf",
    "echo x | tee /g/stammdaten/ich.yaml",
    "chmod u+w /g/2026-0001/rechnung.pdf",
    """python3 -c "from pathlib import Path; Path('/g/2026-0001/status.yaml').write_text('x')" """,
    "cp entwurf.pdf '/g/2026-0001/rechnung.pdf'",
    "rm -rf /g/2026-0001/pro-forma/1",
    "echo x > /g/2026-0001/pro-forma/1/rechnung.yaml",
])
def test_bash_schreiben_blockiert(tmp_path, befehl):
    assert hook(tmp_path, "Bash", command=befehl).returncode == 2


@pytest.mark.parametrize("befehl", [
    "pdftotext /g/2026-0001/rechnung.pdf - | head",
    # Lesende Befehle, die nur zufällig ein > oder einen geschützten Namen im Text haben.
    """python3 -c "import re; re.findall(r'<word[^>]*>', open('/g/2026-0001/rechnung.pdf').read())" """,
    "grep -c resolved /g/2026-0001/rechnung.resolved.json",
    "latexmk -pdf -interaction=nonstopmode beispiel.tex",
    "cat > README.md <<EOF\nDie Datei rechnung.resolved.json ist abgeleitet.\nEOF",
    # Dokumentation schreiben, die geschützte Dateinamen nur erwähnt.
    """python3 -c "from pathlib import Path; Path('CLAUDE.md').write_text('belege: [flug.pdf]')" """,
    "cat /g/2026-0001/rechnung.resolved.json",
    "cat /g/2026-0001/status.yaml 2>/dev/null",
    "uv run rechnung bauen 2026-0001 > /dev/null 2>&1",
    "ls /g/2026-0001 > liste.txt",
    "ls /g/2026-0001/pro-forma/1",
    "uv run rechnung pro-forma 2026-0001 --gesendet-am 2026-06-11",
])
def test_bash_lesen_erlaubt(tmp_path, befehl):
    assert hook(tmp_path, "Bash", command=befehl).returncode == 0


def test_settings_json_deny_regeln():
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    deny = settings["permissions"]["deny"]
    for muster in ["rechnung.resolved.json", "*.pdf", "status.yaml", "stammdaten/ich.yaml", "pro-forma/**"]:
        assert f"Write(//**/{muster})" in deny
        assert f"Edit(//**/{muster})" in deny
    befehl = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert befehl.endswith(".claude/hooks/schutz.sh")
