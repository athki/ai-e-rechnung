"""Commit-Wächter: nichts aus der Sperrliste darf ins Repo – weder in Dateien noch in PDFs noch
in der Commit-Message.

Die Sperrliste liegt neben der Config des Werkzeugs (sperrliste.txt), oder dort, wohin
RECHNUNG_SPERRLISTE zeigt. Gibt es keine, ist der Wächter still. Nur Standardbibliothek, damit
der Hook auch ohne virtuelle Umgebung läuft.

Format: ein Begriff je Zeile, # leitet einen Kommentar ein.
  Begriff     Groß-/Kleinschreibung egal
  =Begriff    Groß-/Kleinschreibung genau so
Kurze Begriffe (bis 4 Zeichen) zählen nur als ganzes Wort, damit „AB“ nicht in „Tabelle“ anschlägt,
und in den Rohbytes einer PDF gar nicht – dort tauchen zwei, drei Buchstaben zufällig auf; Text und
Metadaten der PDF prüfen sie trotzdem.
Begriffe mit mindestens 5 Ziffern (IBAN, Steuernummer, Telefon) werden zusätzlich ohne
Leerzeichen, Schrägstriche, Punkte und Bindestriche verglichen.

Aufruf:
  sperrliste.py staged             gestagte Dateien (pre-commit)
  sperrliste.py nachricht <datei>  Commit-Message (commit-msg)
  sperrliste.py alle               alle Dateien, die Git verfolgt, im Arbeitsstand
  sperrliste.py push <remote>      jeder Commit, der hochgehen soll (pre-push, Refs auf stdin):
                                   geänderte Dateien, Commit-Message, Autor und Committer

Die Meldung nennt Datei, Fundzeile und die Zeile der Sperrliste – nie den Begriff selbst.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

KURZ = 4
TRENNER = re.compile(r"[\s/.\-]")


@dataclass
class Begriff:
    zeile: int
    kurz: bool
    muster: re.Pattern[str]
    ziffern: str | None   # normalisierte Form für den Vergleich ohne Trenner, sonst None


def sperrliste_pfad(env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if env.get("RECHNUNG_SPERRLISTE"):
        return Path(env["RECHNUNG_SPERRLISTE"]).expanduser()
    if env.get("RECHNUNG_CONFIG"):
        return Path(env["RECHNUNG_CONFIG"]).expanduser().parent / "sperrliste.txt"
    basis = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else Path.home() / ".config"
    return basis / "rechnung" / "sperrliste.txt"


def lade(pfad: Path) -> list[Begriff]:
    begriffe = []
    for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
        roh = zeile.split("#", 1)[0].strip()
        if not roh:
            continue
        genau = roh.startswith("=")
        text = roh[1:].strip() if genau else roh
        if not text:
            continue
        muster = re.escape(text)
        if len(text) <= KURZ:
            muster = r"(?<!\w)" + muster + r"(?!\w)"
        flags = 0 if genau else re.IGNORECASE
        ziffern = None
        if sum(z.isdigit() for z in text) >= 5:
            ziffern = TRENNER.sub("", text).lower()
        begriffe.append(Begriff(nr, len(text) <= KURZ, re.compile(muster, flags), ziffern))
    return begriffe


def treffer(text: str, begriffe: list[Begriff], roh: bool = False) -> list[tuple[int, int]]:
    """(Zeile der Sperrliste, Fundzeile im Text) je Treffer; Fundzeile 0 = nur ohne Trenner gefunden.

    roh=True: Binärdaten – kurze Begriffe zählen dort nicht.
    """
    gefunden = []
    kompakt = None
    for b in begriffe:
        if roh and b.kurz:
            continue
        m = b.muster.search(text)
        if m:
            gefunden.append((b.zeile, text.count("\n", 0, m.start()) + 1))
            continue
        if b.ziffern:
            if kompakt is None:
                kompakt = TRENNER.sub("", text).lower()
            if b.ziffern in kompakt:
                gefunden.append((b.zeile, 0))
    return gefunden


def pdf_texte(daten: bytes) -> list[tuple[str, str]]:
    """Text und Metadaten einer PDF über poppler. Fehlt poppler, ist das ein Fehler, kein Freibrief."""
    if not shutil.which("pdftotext") or not shutil.which("pdfinfo"):
        raise SystemExit("sperrliste: pdftotext/pdfinfo fehlen – PDFs lassen sich nicht prüfen.")
    with tempfile.TemporaryDirectory(prefix="sperrliste-") as tmp:
        pdf = Path(tmp) / "x.pdf"
        pdf.write_bytes(daten)
        text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return [("PDF-Text", text), ("PDF-Metadaten", info)]


def pruefe_inhalt(name: str, daten: bytes, begriffe: list[Begriff]) -> list[str]:
    teile = [("Dateiname", name)]
    if daten.startswith(b"%PDF"):
        teile += pdf_texte(daten)
        teile.append(("PDF-Rohdaten", daten.decode("latin-1")))
    else:
        teile.append(("Inhalt", daten.decode("utf-8", errors="replace")))
    meldungen = []
    for art, text in teile:
        for zeile, fund in treffer(text, begriffe, roh=art == "PDF-Rohdaten"):
            if fund == 0:
                ort = f"{art}, ohne Trenner"
            elif art in ("Inhalt", "PDF-Text"):
                ort = f"{art}, Zeile {fund}"
            else:
                ort = art
            meldungen.append(f"{name}: {ort} – Begriff aus Zeile {zeile} der Sperrliste")
    return meldungen


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def staged() -> list[tuple[str, bytes]]:
    namen = _git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split(b"\0")
    return [(n.decode(), _git("show", f":{n.decode()}")) for n in namen if n]


def alle() -> list[tuple[str, bytes]]:
    namen = _git("ls-files", "-z").split(b"\0")
    return [(n.decode(), Path(n.decode()).read_bytes()) for n in namen if n and Path(n.decode()).is_file()]


NULL = "0" * 40


def zu_pushende_commits(remote: str, zeilen: list[str]) -> list[str]:
    """Commits, die das Ziel noch nicht hat – aus den Zeilen, die Git dem pre-push-Hook gibt."""
    commits: list[str] = []
    for zeile in zeilen:
        teile = zeile.split()
        if len(teile) != 4 or teile[1].strip("0") == "":
            continue                                    # unbekannt oder Branch wird gelöscht
        lokal, fern = teile[1], teile[3]
        neu_beim_ziel = ["rev-list", lokal, "--not", f"--remotes={remote}"]
        try:
            ausgabe = _git(*(neu_beim_ziel if fern.strip("0") == "" else ["rev-list", f"{fern}..{lokal}"]))
        except subprocess.CalledProcessError:
            ausgabe = _git(*neu_beim_ziel)              # Ziel weiter als unser Stand: lieber mehr prüfen
        commits += ausgabe.decode().split()
    return list(dict.fromkeys(commits))


def pruefe_commit(sha: str, begriffe: list[Begriff]) -> list[str]:
    kurz = sha[:10]
    meldungen = []
    for art, format_ in (("Autor/Committer", "%an%n%ae%n%cn%n%ce"), ("Commit-Message", "%B")):
        text = _git("show", "-s", f"--format={format_}", sha).decode("utf-8", errors="replace")
        for zeile, _ in treffer(text, begriffe):
            meldungen.append(f"Commit {kurz}: {art} – Begriff aus Zeile {zeile} der Sperrliste")
    eltern = _git("rev-list", "--parents", "-n", "1", sha).decode().split()[1:]
    vergleich = [eltern[0], sha] if eltern else ["--root", sha]
    namen = _git("diff-tree", "-r", "--no-commit-id", "--name-only", "-z", "--diff-filter=ACMR",
                 *vergleich).split(b"\0")
    for n in filter(None, namen):
        name = n.decode()
        meldungen += pruefe_inhalt(f"Commit {kurz}: {name}", _git("show", f"{sha}:{name}"), begriffe)
    return meldungen


def main(argv: list[str]) -> int:
    pfad = sperrliste_pfad()
    if not pfad.is_file():
        return 0
    begriffe = lade(pfad)
    if not argv or argv[0] not in ("staged", "nachricht", "alle", "push"):
        print(__doc__, file=sys.stderr)
        return 2

    meldungen: list[str] = []
    if argv[0] == "nachricht":
        text = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
        text = "\n".join(z for z in text.splitlines() if not z.startswith("#"))
        for zeile, fund in treffer(text, begriffe):
            meldungen.append(f"Commit-Message: Zeile {fund or '?'} – Begriff aus Zeile {zeile} der Sperrliste")
    elif argv[0] == "push":
        for sha in zu_pushende_commits(argv[1] if len(argv) > 1 else "", sys.stdin.read().splitlines()):
            meldungen += pruefe_commit(sha, begriffe)
    else:
        for name, daten in (staged() if argv[0] == "staged" else alle()):
            meldungen += pruefe_inhalt(name, daten, begriffe)

    if meldungen:
        print(f"sperrliste: abgewiesen ({len(meldungen)} Treffer gegen {pfad}):", file=sys.stderr)
        for m in meldungen:
            print(f"  {m}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
