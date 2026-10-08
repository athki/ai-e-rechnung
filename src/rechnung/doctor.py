"""`rechnung doctor`: prüft, ob alles da ist, was das Werkzeug braucht.

Die TeX-Paketliste kommt aus docs/tex-pakete.txt – derselben Datei, die das Dockerfile installiert.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rechnung import config, vorlage

OK, WARNUNG, FEHLER = "ok", "warnung", "fehler"

TEX_PAKETE = config.REPO / "docs" / "tex-pakete.txt"

LATEXMK_FLAG = {"pdflatex": "-pdf", "lualatex": "-lualatex", "xelatex": "-xelatex"}

TESTDOKUMENT = r"""\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\begin{document}
Grüße aus Musterstadt: äöü ÄÖÜ ß € – „Rechnung“.
\end{document}
"""


@dataclass
class Pruefung:
    name: str
    status: str
    detail: str = ""


def tex_pakete(pfad: Path = TEX_PAKETE) -> list[tuple[str, str]]:
    """(tlmgr-paket, prüfdatei) je Zeile, ohne Kommentare."""
    pakete = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.split("#", 1)[0].strip()
        if not zeile:
            continue
        teile = zeile.split()
        if len(teile) != 2:
            raise ValueError(f"{pfad}: Zeile muss '<paket> <prüfdatei>' sein: {zeile!r}")
        pakete.append((teile[0], teile[1]))
    return pakete


def _version(programm: str, *args: str) -> str:
    try:
        aus = subprocess.run([programm, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = (aus.stdout or aus.stderr).strip().splitlines()
    return text[0] if text else ""


def pruefe_python() -> Pruefung:
    v = sys.version_info
    text = f"{v.major}.{v.minor}.{v.micro}"
    return Pruefung("Python ≥ 3.12", OK if v >= (3, 12) else FEHLER, text)


def pruefe_programm(name: str, programm: str, *version_args: str, pflicht: bool = True) -> Pruefung:
    pfad = shutil.which(programm)
    if not pfad:
        return Pruefung(name, FEHLER if pflicht else WARNUNG, f"{programm} nicht gefunden")
    return Pruefung(name, OK, _version(programm, *version_args) or pfad)


def pruefe_tex_pakete() -> Pruefung:
    try:
        pakete = tex_pakete()
    except (OSError, ValueError) as e:
        return Pruefung("TeX-Pakete", FEHLER, str(e))
    kpsewhich = shutil.which("kpsewhich")
    fehlend = []
    for paket, datei in pakete:
        if datei.startswith("bin:"):
            gefunden = shutil.which(datei[4:]) is not None
        elif kpsewhich:
            aus = subprocess.run([kpsewhich, datei], capture_output=True, text=True)
            gefunden = aus.returncode == 0 and aus.stdout.strip() != ""
        else:
            gefunden = False
        if not gefunden:
            fehlend.append(paket)
    if fehlend:
        return Pruefung("TeX-Pakete", FEHLER, "fehlt: " + " ".join(fehlend))
    return Pruefung("TeX-Pakete", OK, f"{len(pakete)} aus docs/tex-pakete.txt")


def pruefe_testlauf(engine: str) -> Pruefung:
    """Kompiliert ein Minimaldokument mit Umlauten im Temp-Verzeichnis."""
    name = f"LaTeX-Testlauf ({engine})"
    if not shutil.which("latexmk") or not shutil.which(engine):
        return Pruefung(name, FEHLER, "latexmk oder Engine fehlt")
    with tempfile.TemporaryDirectory(prefix="rechnung-doctor-") as tmp:
        tex = Path(tmp) / "test.tex"
        tex.write_text(TESTDOKUMENT, encoding="utf-8")
        cmd = [
            "latexmk", LATEXMK_FLAG[engine],
            "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
            f"-outdir={tmp}", str(tex),
        ]
        try:
            aus = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return Pruefung(name, FEHLER, "Zeitüberschreitung")
        if aus.returncode != 0 or not (Path(tmp) / "test.pdf").is_file():
            letzte = [z for z in aus.stdout.splitlines() if z.startswith("!")][:1]
            return Pruefung(name, FEHLER, letzte[0] if letzte else f"latexmk Exit {aus.returncode}")
    return Pruefung(name, OK, "PDF erzeugt")


def pruefe_fonts() -> Pruefung:
    fonts = sorted(p.name for p in (config.REPO / "vorlage" / "fonts").glob("*") if p.suffix.lower() in {".otf", ".ttf"})
    if not fonts:
        # Die Vorlage nutzt XCharter und Fira Sans aus TeX Live (siehe docs/tex-pakete.txt);
        # dieser Ordner ist nur für zusätzliche, offen lizenzierte Font-Dateien.
        return Pruefung("Fonts (vorlage/fonts)", OK, "keine eigenen – XCharter und Fira Sans aus TeX Live")
    return Pruefung("Fonts (vorlage/fonts)", OK, ", ".join(fonts))


def pruefe_config(cfg: config.Config | None, fehler: str | None) -> Pruefung:
    if fehler:
        return Pruefung("Config", FEHLER, fehler)
    assert cfg is not None
    if cfg.quelle:
        detail = str(cfg.quelle)
    elif cfg.aus_env:
        detail = "nur Umgebungsvariablen: " + ", ".join(f"RECHNUNG_{o.upper()}" for o in sorted(cfg.aus_env))
    else:
        return Pruefung("Config", WARNUNG, f"keine ({config.config_pfad()}) – Demo-Modus mit stammdaten.example/")
    return Pruefung("Config", OK, detail)


def pruefe_vorlage(cfg: config.Config | None) -> list[Pruefung]:
    """Eigener Vorlagen-Ordner: was er ersetzt, was er ergänzt, und ob defaults.sty veraltet ist."""
    if cfg is None or cfg.vorlage is None:
        return [Pruefung("Vorlage", OK, "Standardvorlage")]
    try:
        eigene = vorlage.eigene_dateien(cfg.vorlage)
    except vorlage.VorlageFehler as e:
        return [Pruefung("Vorlage", FEHLER, str(e))]
    standard = set(vorlage.standard_dateien())
    ersetzt = [d for d in eigene if d in standard]
    wirkungslos = [d for d in eigene if d in vorlage.ERZEUGT]
    dazu = [d for d in eigene if d not in standard and d not in vorlage.ERZEUGT]
    teile = [f"ersetzt: {', '.join(ersetzt) or 'nichts'}"]
    if dazu:
        teile.append(f"zusätzlich: {', '.join(dazu)}")
    ergebnis = [Pruefung("Vorlage", OK, f"{cfg.vorlage} – " + "; ".join(teile))]
    if wirkungslos:
        ergebnis.append(Pruefung("Vorlage", WARNUNG,
                                 f"ohne Wirkung, weil zur Laufzeit erzeugt: {', '.join(wirkungslos)}"))
    if "style/defaults.sty" in ersetzt:
        fehlend = vorlage.fehlende_stellschrauben(cfg.vorlage)
        if fehlend:
            ergebnis.append(Pruefung(
                "Eigene defaults.sty", WARNUNG,
                f"es fehlen Stellschrauben der Standardvorlage: {', '.join(fehlend)} – "
                f"Vorbild: vorlage/style/defaults.sty im Repo"))
        else:
            ergebnis.append(Pruefung("Eigene defaults.sty", OK, "kennt alle Stellschrauben"))
    return ergebnis


def pruefe_gewerbe(cfg: config.Config | None) -> list[Pruefung]:
    if cfg is None or cfg.gewerbe is None:
        return [Pruefung("Gewerbe-Ordner", WARNUNG, "nicht konfiguriert (Demo-Modus)")]
    if not cfg.gewerbe.is_dir():
        return [Pruefung("Gewerbe-Ordner", FEHLER, f"nicht erreichbar: {cfg.gewerbe}")]
    ergebnis = [Pruefung("Gewerbe-Ordner", OK, str(cfg.gewerbe))]
    fehlend = [getattr(cfg, n) for n in config.UNTERORDNER if not cfg.ordner(n).is_dir()]
    if fehlend:
        ergebnis.append(Pruefung("Unterordner", WARNUNG, f"fehlt: {', '.join(fehlend)} – `rechnung init` ausführen"))
    else:
        ergebnis.append(Pruefung("Unterordner", OK, ", ".join(getattr(cfg, n) for n in config.UNTERORDNER)))
    return ergebnis


def pruefe_nummer(cfg: config.Config | None) -> Pruefung:
    """Zeigt, was `nummer_format` konkret bedeutet – die nächste Nummer des laufenden Jahres."""
    from datetime import date

    from rechnung import resolve, rules

    if cfg is None:
        return Pruefung("Nächste Nummer", WARNUNG, "keine Config")
    jahr = date.today().year
    try:
        if cfg.demo:
            nummer = rules.nummer(cfg.nummer_format, jahr, 1)
            return Pruefung("Nächste Nummer", OK, f"{nummer} (Demo-Modus, Jahr leer)")
        return Pruefung("Nächste Nummer", OK, resolve.neue_nummer(cfg, jahr))
    except (rules.RegelFehler, config.ConfigFehler) as e:
        return Pruefung("Nächste Nummer", FEHLER, str(e))


def pruefe_waechter(env: dict[str, str] | None = None, repo: Path = config.REPO) -> Pruefung:
    """Gibt es eine Sperrliste, muss der Commit-Wächter in diesem Klon an sein."""
    name = "Commit-Wächter"
    if not config.sperrliste_pfad(env).is_file():
        return Pruefung(name, OK, "keine Sperrliste – nicht nötig")
    if not (repo / ".git").exists() or not shutil.which("git"):
        return Pruefung(name, OK, "kein Git-Klon – nichts zu schützen")
    aus = subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath"], capture_output=True, text=True)
    if aus.stdout.strip() != ".githooks":
        return Pruefung(name, FEHLER, "Sperrliste da, Wächter aus – `make hooks` ausführen")
    return Pruefung(name, OK, f"an, Sperrliste {config.sperrliste_pfad(env)}")


def pruefe_docker() -> Pruefung:
    if not shutil.which("docker"):
        return Pruefung("Docker (Schattencontainer)", WARNUNG, "nicht gefunden")
    try:
        aus = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return Pruefung("Docker (Schattencontainer)", WARNUNG, "docker info hängt")
    if aus.returncode != 0:
        return Pruefung("Docker (Schattencontainer)", WARNUNG, "installiert, Daemon läuft nicht")
    return Pruefung("Docker (Schattencontainer)", OK, f"Server {aus.stdout.strip()}")


def alle() -> list[Pruefung]:
    cfg, fehler = None, None
    try:
        cfg = config.laden()
    except config.ConfigFehler as e:
        fehler = str(e)
    engine = cfg.engine if cfg else config.DEFAULTS["engine"]

    return [
        pruefe_python(),
        pruefe_programm("latexmk", "latexmk", "-v"),
        pruefe_programm(f"TeX-Engine ({engine})", engine, "--version"),
        pruefe_tex_pakete(),
        pruefe_testlauf(engine),
        pruefe_programm("pdftotext", "pdftotext", "-v"),
        pruefe_fonts(),
        pruefe_config(cfg, fehler),
        *pruefe_vorlage(cfg),
        *pruefe_gewerbe(cfg),
        pruefe_nummer(cfg),
        pruefe_waechter(),
        pruefe_docker(),
    ]
