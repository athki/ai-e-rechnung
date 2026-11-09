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
    "/g/rechnung-ausgang/2026/2026-0001/rechnung.privat.yaml",
    "/g/stammdaten/preise.yaml",
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
    str(REPO / "stammdaten.example" / "preise.yaml"),
    "/g/rechnung-ausgang/2026/2026-0001/anschreiben.md",
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
    "echo 'einzelpreis: 1' >> /g/2026-0001/rechnung.privat.yaml",
    "sed -i '' 's/900/9000/' /g/stammdaten/preise.yaml",
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
    for muster in ["rechnung.resolved.json", "*.pdf", "status.yaml", "stammdaten/ich.yaml", "pro-forma/**",
                   "rechnung.privat.yaml", "stammdaten/preise.yaml"]:
        assert f"Write(//**/{muster})" in deny
        assert f"Edit(//**/{muster})" in deny
    befehl = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert befehl.endswith(".claude/hooks/schutz.sh")
    assert set(settings["hooks"]["PreToolUse"][0]["matcher"].split("|")) >= {"Read", "Grep", "Glob", "Bash"}


# ---------------------------------------------------------------- Lesesperre unter RECHNUNG_GESCHWAERZT

def lesen(tmp_path, werkzeug, schalter="1", echt=None, cwd=None, **tool_input):
    """Hook mit Test-Wurzel <tmp>/Gewerbe-Test aus der Env und, falls angegeben, echter Wurzel aus config.toml.

    Läuft unter /bin/bash: auf macOS ist das Bash 3.2, und der Hook muss dort laufen.
    """
    toml = tmp_path / "config.toml"
    toml.write_text(f'gewerbe = "{echt}"\n' if echt else "", encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path),
           "RECHNUNG_CONFIG": str(toml), "RECHNUNG_GEWERBE": str(tmp_path / "Gewerbe-Test")}
    if schalter is not None:
        env["RECHNUNG_GESCHWAERZT"] = schalter
    eingabe = {"tool_name": werkzeug, "tool_input": tool_input}
    if cwd:
        eingabe["cwd"] = str(cwd)
    return subprocess.run(["/bin/bash", str(HOOK)], input=json.dumps(eingabe), capture_output=True,
                          text=True, env=env)


@pytest.fixture
def wurzeln(tmp_path):
    for w in ("Gewerbe-Test", "Gewerbe"):
        (tmp_path / w / "stammdaten" / "kunden").mkdir(parents=True)
        (tmp_path / w / "rechnung-ausgang" / "2026" / "2026-0001" / "belege").mkdir(parents=True)
    return tmp_path


RE = "rechnung-ausgang/2026/2026-0001"


@pytest.mark.parametrize("rel", [
    "stammdaten/ich.yaml", "stammdaten/kunden/muster.yaml", f"{RE}/rechnung.resolved.json",
    f"{RE}/rechnung_2026-0001.pdf", f"{RE}/status.yaml", f"{RE}/pro-forma/1/rechnung.yaml",
    f"{RE}/belege/hotel.jpg", f"{RE}/unterlagen/mail.pdf", f"{RE}/unterlagen/notiz.txt",
    f"{RE}/../../../stammdaten/ich.yaml",
    "stammdaten/preise.yaml", f"{RE}/rechnung.privat.yaml",
])
@pytest.mark.parametrize("wurzel", ["Gewerbe-Test", "Gewerbe"])
def test_read_in_beiden_wurzeln_gesperrt(wurzeln, wurzel, rel):
    aus = lesen(wurzeln, "Read", echt=wurzeln / "Gewerbe", file_path=str(wurzeln / wurzel / rel))
    assert aus.returncode == 2, aus.stderr
    assert "RECHNUNG_GESCHWAERZT" in aus.stderr


@pytest.mark.parametrize("pfad", [
    f"Gewerbe-Test/{RE}/rechnung.yaml",
    "demo-output/inland-muster-gmbh/rechnung_DEMO-2026-0001.pdf",
    "stammdaten.example/ich.yaml",
])
def test_read_erlaubt(wurzeln, pfad):
    assert lesen(wurzeln, "Read", echt=wurzeln / "Gewerbe", file_path=str(wurzeln / pfad)).returncode == 0


def test_ohne_schalter_liest_der_hook_nicht_mit(wurzeln):
    for schalter in (None, "", "0"):
        aus = lesen(wurzeln, "Read", schalter=schalter,
                    file_path=str(wurzeln / "Gewerbe-Test" / "stammdaten" / "ich.yaml"))
        assert aus.returncode == 0, schalter


def test_grep_und_glob_ueber_die_wurzel(wurzeln):
    assert lesen(wurzeln, "Grep", pattern="x", path=str(wurzeln)).returncode == 2
    assert lesen(wurzeln, "Grep", pattern="x", path=str(wurzeln / "Gewerbe-Test" / RE)).returncode == 2
    assert lesen(wurzeln, "Glob", pattern=f"{wurzeln}/Gewerbe-Test/**/*.yaml").returncode == 2
    assert lesen(wurzeln, "Grep", pattern="x", path=str(REPO)).returncode == 0
    assert lesen(wurzeln, "Glob", pattern="**/*.py", path=str(REPO)).returncode == 0


@pytest.mark.parametrize(("befehl", "code"), [
    ("cat ~/Gewerbe-Test/stammdaten/ich.yaml", 2),
    ("cat $RECHNUNG_GEWERBE/stammdaten/kunden/a.yaml", 2),
    ("pdftotext ~/Gewerbe-Test/" + RE + "/rechnung_2026-0001.pdf -", 2),
    ("ls ~/Gewerbe-Test", 2),
    ("find ~/Gewerbe-Test/rechnung-ausgang/ -name x", 2),
    ("cat ~/Gewerbe/stammdaten/ich.yaml", 2),
    ("RECHNUNG_GESCHWAERZT=0 rechnung resolve 0001", 2),
    ("RECHNUNG_GESCHWAERZT= rechnung resolve 0001", 2),
    ('RECHNUNG_GESCHWAERZT="" rechnung resolve 0001', 2),
    ("docker run -e RECHNUNG_GESCHWAERZT=1 rechnung pruefen x", 0),
    ("export RECHNUNG_GEWERBE=/anderswo", 2),
    ("env -u RECHNUNG_GESCHWAERZT rechnung resolve 0001", 2),
    ("unset RECHNUNG_GESCHWAERZT; rechnung resolve 0001", 2),
    ("cat ~/Gewerbe-Test/" + RE + "/rechnung.yaml", 0),
    ("cat $RECHNUNG_GEWERBE/" + RE + "/rechnung.yaml", 0),
    ("uv run rechnung begruendung 0001", 0),
    ("rechnung pruefen 0001", 0),
    ("printenv RECHNUNG_GEWERBE", 0),
    ("uv run pytest -q", 0),
    # Überschreiben an einer Befehlsstelle bleibt gesperrt, in jeder Form …
    ("RECHNUNG_GEWERBE=/anderswo rechnung resolve 0001", 2),
    ("FOO=1 RECHNUNG_CONFIG=/x.toml rechnung resolve 0001", 2),
    ("cd /tmp && RECHNUNG_GEWERBE=/x rechnung neu --kunde a", 2),
    ("true; RECHNUNG_GEWERBE=/x rechnung offen", 2),
    ("echo $(RECHNUNG_GEWERBE=/x rechnung offen)", 2),
    ("env FOO=1 RECHNUNG_GEWERBE=/x rechnung offen", 2),
    ("declare -x RECHNUNG_CONFIG=/x.toml", 2),
    ('bash -c "RECHNUNG_GEWERBE=/x rechnung offen"', 2),
    ("sh -c 'RECHNUNG_GESCHWAERZT=0 rechnung offen'", 2),
    ("python3 - <<'EOF'\nprint(1)\nEOF\nRECHNUNG_GEWERBE=/x rechnung offen", 2),
    # … dieselbe Zeichenkette in Text ist keine Zuweisung (Fehlalarme aus Schritt 3c).
    ("grep -n 'RECHNUNG_GEWERBE=' src/rechnung/schritt.py", 0),
    ("grep -c 'RECHNUNG_GEWERBE=' README.md", 0),
    ("bash -e -c 'RECHNUNG_GEWERBE=/x rechnung offen'", 2),
    ('grep -rn "RECHNUNG_CONFIG=" README.md', 0),
    ("python3 - <<'EOF'\nwurzel = \"RECHNUNG_GEWERBE=<wurzel> \" if x else \"\"\nEOF", 0),
    ("python3 - <<'EOF'\nassert \"RECHNUNG_GEWERBE=\" not in text\nEOF", 0),
    ("echo 'RECHNUNG_GESCHWAERZT=0 schaltet die Schwärzung aus'", 0),
])
def test_bash_lesesperre(wurzeln, befehl, code):
    aus = lesen(wurzeln, "Bash", echt=wurzeln / "Gewerbe", command=befehl)
    assert aus.returncode == code, aus.stderr


def test_bash_in_der_wurzel(wurzeln):
    ordner = wurzeln / "Gewerbe-Test"
    assert lesen(wurzeln, "Bash", cwd=ordner, command="cat stammdaten/ich.yaml").returncode == 2
    assert lesen(wurzeln, "Bash", cwd=ordner, command="grep -r Muster .").returncode == 2
    assert lesen(wurzeln, "Bash", cwd=ordner / RE, command="cat rechnung.yaml").returncode == 0
