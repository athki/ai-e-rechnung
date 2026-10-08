"""`rechnung festschreiben`: macht eine Rechnung unveränderbar.

Der Begriff kommt aus der Buchhaltung: Nach den GoBD ist ein Beleg ab dem Zeitpunkt seiner
Ausstellung unveränderbar aufzubewahren. Ausgestellt im Sinne des § 14 UStG ist eine Rechnung,
wenn sie den Empfänger erreicht – deshalb ist `--gesendet-am` Pflicht und kein Beiwerk.

Das Werkzeug verschickt nichts. Es hält fest, dass du verschickt hast, und zieht daraus die
Konsequenz: Status in status.yaml, Schreibschutz auf PDF und resolved.json, Hashes gespeichert.
Danach verweigert `bauen` den Neubau. Eine Korrektur ist eine Stornorechnung plus eine neue
Rechnung, nie eine Änderung am Original.

Vor dem Festschreiben darf beliebig oft gebaut und geprüft werden; nichts friert von selbst ein.
"""

from __future__ import annotations

import hashlib
import os
import stat
from datetime import date
from pathlib import Path

import yaml

STATUS_DATEI = "status.yaml"
ENTWURF = "entwurf"
FESTGESCHRIEBEN = "festgeschrieben"


class FestschreibFehler(Exception):
    pass


def hash_datei(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def status_lesen(ordner: Path) -> dict:
    pfad = ordner / STATUS_DATEI
    if not pfad.is_file():
        return {"status": ENTWURF}
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    if not isinstance(daten, dict):
        raise FestschreibFehler(f"{pfad} enthält kein YAML-Objekt.")
    return daten


def ist_festgeschrieben(ordner: Path) -> bool:
    return status_lesen(ordner).get("status") == FESTGESCHRIEBEN


def schreibschutz(pfad: Path) -> None:
    """Schreibrechte entziehen – der letzte, spürbare Halt vor einer Änderung."""
    modus = pfad.stat().st_mode
    pfad.chmod(modus & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def schreibschutz_aufheben(pfad: Path) -> None:
    pfad.chmod(pfad.stat().st_mode | stat.S_IWUSR)


def festschreiben(ordner: Path, gesendet_am: date, am: date | None = None) -> dict:
    """Friert die Rechnung ein.

    `gesendet_am` ist der Tag, an dem die Rechnung an den Kunden ging – die Pflichtangabe.
    `am` ist der Tag des Festschreibens selbst (Default heute); beide können auseinanderfallen,
    wenn man Freitag verschickt und Montag festschreibt.
    """
    pdf = ordner / "rechnung.pdf"
    resolved = ordner / "rechnung.resolved.json"
    eingabe = ordner / "rechnung.yaml"

    if ist_festgeschrieben(ordner):
        vorher = status_lesen(ordner)
        raise FestschreibFehler(
            f"Rechnung ist bereits festgeschrieben (gesendet am "
            f"{vorher.get('gesendet_am', 'unbekannt')}). Für eine Korrektur eine Stornorechnung "
            f"und eine neue Rechnung schreiben."
        )
    for pflicht in (pdf, resolved, eingabe):
        if not pflicht.is_file():
            raise FestschreibFehler(f"{pflicht.name} fehlt – erst `rechnung bauen` ausführen.")

    daten = {
        "status": FESTGESCHRIEBEN,
        "gesendet_am": gesendet_am.isoformat(),
        "festgeschrieben_am": (am or date.today()).isoformat(),
        "hash": {
            "rechnung.yaml": hash_datei(eingabe),
            "rechnung.resolved.json": hash_datei(resolved),
            "rechnung.pdf": hash_datei(pdf),
        },
    }
    (ordner / STATUS_DATEI).write_text(
        yaml.safe_dump(daten, allow_unicode=True, sort_keys=False), encoding="utf-8")

    for datei in (pdf, resolved):
        schreibschutz(datei)
    schreibschutz(ordner / STATUS_DATEI)
    return daten


def pruefe_unveraendert(ordner: Path) -> list[str]:
    """Vergleicht die gespeicherten Hashes mit den Dateien. Gibt die Abweichungen zurück."""
    daten = status_lesen(ordner)
    if daten.get("status") != FESTGESCHRIEBEN:
        return []
    abweichungen = []
    for name, erwartet in (daten.get("hash") or {}).items():
        pfad = ordner / name
        if not pfad.is_file():
            abweichungen.append(f"{name} fehlt")
        elif hash_datei(pfad) != erwartet:
            abweichungen.append(f"{name} wurde nach dem Festschreiben geändert")
    return abweichungen


def schreibbar_machen(ordner: Path) -> None:
    """Nur für Tests und Aufräumarbeiten: nimmt den Schreibschutz wieder weg."""
    for datei in ordner.iterdir():
        if datei.is_file() and not os.access(datei, os.W_OK):
            schreibschutz_aufheben(datei)
