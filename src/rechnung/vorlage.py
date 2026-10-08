"""Standardvorlage und eigener Vorlagen-Ordner.

Die Standardvorlage liegt in vorlage/ im Repo. Ein eigener Ordner (Option `vorlage`,
RECHNUNG_VORLAGE) enthält nur die Dateien, die anders sein sollen, unter demselben relativen
Pfad – meist nur style/defaults.sty. Beim Build kommt zuerst die Standardvorlage ins
Temp-Verzeichnis, darüber der eigene Ordner; gleiche Namen gewinnt der eigene. Dateien ohne
Gegenstück (etwa ein Logo) kommen einfach dazu.

Welche eigenen Dateien beteiligt waren, hält resolved.json fest (`vorlage_eigen`, Hash je Datei).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rechnung import config

STANDARD = config.REPO / "vorlage"

# Die Jinja-Vorlagen: werden gefüllt, nicht kopiert.
JINJA = ("rechnung.tex.j2", "issuer.tex.j2")
# Was render.py zur Laufzeit erzeugt – eine eigene Datei dieses Namens hätte keine Wirkung.
ERZEUGT = ("rechnung.tex", "include/issuer.tex")


class VorlageFehler(config.ConfigFehler):
    pass


def standard_dateien(standard: Path = STANDARD) -> list[str]:
    """Die Dateien der Standardvorlage, die ein Build benutzt (relativ, mit /)."""
    dateien = [f"style/{p.name}" for p in (standard / "style").glob("*.sty")]
    dateien += ["include/currency.tex", *JINJA]
    return sorted(dateien)


def eigene_dateien(ordner: Path) -> list[str]:
    """Alle Dateien im eigenen Vorlagen-Ordner, relativ und sortiert. Versteckte zählen nicht."""
    if not ordner.is_dir():
        raise VorlageFehler(f"Vorlagen-Ordner existiert nicht: {ordner} (Option `vorlage`)")
    return sorted(
        p.relative_to(ordner).as_posix()
        for p in ordner.rglob("*")
        if p.is_file() and not any(teil.startswith(".") for teil in p.relative_to(ordner).parts)
    )


def nachweis(ordner: Path | None) -> dict[str, str] | None:
    """{relativer Pfad: sha256} der eigenen Dateien; None ohne eigenen Ordner."""
    if ordner is None:
        return None
    return {
        rel: hashlib.sha256((ordner / rel).read_bytes()).hexdigest()
        for rel in eigene_dateien(ordner)
    }


# \newcommand{\Name}, \definecolor{Name}, \newif\ifName – die drei Arten von Stellschrauben.
STELLSCHRAUBE = re.compile(
    r"\\newcommand\*?\{?\\(?P<befehl>[A-Za-z@]+)"
    r"|\\definecolor\{(?P<farbe>[^}]+)\}"
    r"|\\newif\\if(?P<schalter>[A-Za-z@]+)"
)


def stellschrauben(text: str) -> set[str]:
    """Namen der Stellschrauben in einer defaults.sty (Kommentare zählen nicht)."""
    namen = set()
    for zeile in text.splitlines():
        zeile = re.split(r"(?<!\\)%", zeile, maxsplit=1)[0]
        for m in STELLSCHRAUBE.finditer(zeile):
            if m["befehl"]:
                namen.add("\\" + m["befehl"])
            elif m["farbe"]:
                namen.add(f"Farbe {m['farbe']}")
            else:
                namen.add("\\if" + m["schalter"])
    return namen


def fehlende_stellschrauben(eigene: Path, standard: Path = STANDARD) -> list[str]:
    """Stellschrauben der Standard-defaults.sty, die in der eigenen fehlen."""
    pfad = "style/defaults.sty"
    soll = stellschrauben((standard / pfad).read_text(encoding="utf-8"))
    ist = stellschrauben((eigene / pfad).read_text(encoding="utf-8"))
    return sorted(soll - ist)
