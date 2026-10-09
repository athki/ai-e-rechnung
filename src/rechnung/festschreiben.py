"""`rechnung festschreiben`: macht eine Rechnung unveränderbar.

Der Begriff kommt aus der Buchhaltung: Nach den GoBD ist ein Beleg ab dem Zeitpunkt seiner
Ausstellung unveränderbar aufzubewahren. Ausgestellt im Sinne des § 14 UStG ist eine Rechnung,
wenn sie den Empfänger erreicht – deshalb ist `--gesendet-am` Pflicht und kein Beiwerk.

Das Werkzeug verschickt nichts. Es hält fest, dass du verschickt hast, und zieht daraus die
Konsequenz: Status in status.yaml, Schreibschutz auf PDF und resolved.json, Hashes gespeichert.
Danach verweigert `bauen` den Neubau. Eine Korrektur ist eine Stornorechnung plus eine neue
Rechnung, nie eine Änderung am Original.

Vor dem Festschreiben darf beliebig oft gebaut und geprüft werden; nichts friert von selbst ein.

Pro forma: `rechnung pro-forma <nr> --gesendet-am` friert den gesendeten Stand als Revision ein
(`pro-forma/<n>/` mit PDF und Kopien von rechnung.yaml und rechnung.resolved.json, schreibgeschützt,
Eintrag in status.yaml). Eine Pro forma ist keine Rechnung; `festschreiben` friert nur die echte ein.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from datetime import date
from pathlib import Path

import yaml

STATUS_DATEI = "status.yaml"
EINGABE_DATEI = "rechnung.yaml"
RESOLVED_DATEI = "rechnung.resolved.json"
PRO_FORMA_ORDNER = "pro-forma"
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


def _pdf(ordner: Path, pro_forma: bool = False, revision: int | None = None) -> Path:
    """Name der PDF aus Nummer und Sprache in resolved.json (render.pdf_name)."""
    from rechnung.render import pdf_name

    resolved = ordner / RESOLVED_DATEI
    if not resolved.is_file():
        raise FestschreibFehler(f"{RESOLVED_DATEI} fehlt – erst `rechnung bauen` ausführen.")
    daten = json.loads(resolved.read_text(encoding="utf-8"))
    return ordner / pdf_name(daten["nummer"], daten["sprache"], pro_forma, revision)


def _status_schreiben(ordner: Path, daten: dict) -> None:
    (ordner / STATUS_DATEI).write_text(
        yaml.safe_dump(daten, allow_unicode=True, sort_keys=False), encoding="utf-8")


def festschreiben(ordner: Path, gesendet_am: date, am: date | None = None) -> dict:
    """Friert die Rechnung ein.

    `gesendet_am` ist der Tag, an dem die Rechnung an den Kunden ging – die Pflichtangabe.
    `am` ist der Tag des Festschreibens selbst (Default heute); beide können auseinanderfallen,
    wenn man Freitag verschickt und Montag festschreibt.
    """
    resolved = ordner / RESOLVED_DATEI
    eingabe = ordner / EINGABE_DATEI
    pdf = _pdf(ordner)

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

    vorher = status_lesen(ordner)
    daten = {
        "status": FESTGESCHRIEBEN,
        "gesendet_am": gesendet_am.isoformat(),
        "festgeschrieben_am": (am or date.today()).isoformat(),
        "hash": {
            EINGABE_DATEI: hash_datei(eingabe),
            RESOLVED_DATEI: hash_datei(resolved),
            pdf.name: hash_datei(pdf),
        },
    }
    if vorher.get("pro_forma"):
        daten["pro_forma"] = vorher["pro_forma"]
    _status_schreiben(ordner, daten)

    for datei in (pdf, resolved):
        schreibschutz(datei)
    schreibschutz(ordner / STATUS_DATEI)
    return daten


def pro_forma_festhalten(ordner: Path, gesendet_am: date, am: date | None = None) -> dict:
    """Friert die Arbeitskopie der Pro forma als nächste Revision ein und gibt deren Eintrag zurück.

    Eingefroren wird, was zuletzt gebaut wurde – und nur, wenn es zum aktuellen rechnung.yaml passt.
    """
    if ist_festgeschrieben(ordner):
        raise FestschreibFehler("Die Rechnung ist festgeschrieben – eine Pro forma gibt es danach nicht mehr.")
    eingabe = ordner / EINGABE_DATEI
    resolved = ordner / RESOLVED_DATEI
    pdf = _pdf(ordner, pro_forma=True)
    if not pdf.is_file():
        raise FestschreibFehler(f"{pdf.name} fehlt – erst `rechnung bauen {ordner.name} --pro-forma` ausführen.")
    stand = json.loads(resolved.read_text(encoding="utf-8")).get("input_hash")
    if stand != hash_datei(eingabe) or pdf.stat().st_mtime < resolved.stat().st_mtime:
        raise FestschreibFehler(
            f"{pdf.name} passt nicht mehr zu rechnung.yaml – erst `rechnung bauen {ordner.name} "
            f"--pro-forma` ausführen und die neue PDF ansehen."
        )

    status = status_lesen(ordner)
    revisionen = list(status.get("pro_forma") or [])
    n = len(revisionen) + 1
    ziel = ordner / PRO_FORMA_ORDNER / str(n)
    if ziel.exists():
        raise FestschreibFehler(f"{ziel} existiert schon, steht aber nicht in status.yaml – bitte prüfen.")
    ziel.mkdir(parents=True)
    kopien = [ziel / EINGABE_DATEI, ziel / RESOLVED_DATEI, ziel / _pdf(ordner, True, n).name]
    for quelle, kopie in zip((eingabe, resolved, pdf), kopien):
        shutil.copy2(quelle, kopie)
        schreibschutz(kopie)

    eintrag = {
        "revision": n,
        "gesendet_am": gesendet_am.isoformat(),
        "festgehalten_am": (am or date.today()).isoformat(),
        "hash": {str(k.relative_to(ordner)): hash_datei(k) for k in kopien},
    }
    status.setdefault("status", ENTWURF)
    status["pro_forma"] = [*revisionen, eintrag]
    _status_schreiben(ordner, status)
    return eintrag


def pruefe_unveraendert(ordner: Path) -> list[str]:
    """Vergleicht die gespeicherten Hashes mit den Dateien. Gibt die Abweichungen zurück.

    Geprüft werden die festgeschriebene Rechnung und jede gesendete Pro-forma-Revision.
    """
    daten = status_lesen(ordner)
    erwartet = dict(daten.get("hash") or {}) if daten.get("status") == FESTGESCHRIEBEN else {}
    for eintrag in daten.get("pro_forma") or []:
        erwartet.update(eintrag.get("hash") or {})
    abweichungen = []
    for name, wert in erwartet.items():
        pfad = ordner / name
        if not pfad.is_file():
            abweichungen.append(f"{name} fehlt")
        elif hash_datei(pfad) != wert:
            abweichungen.append(f"{name} wurde nach dem Einfrieren geändert")
    return abweichungen


def schreibbar_machen(ordner: Path) -> None:
    """Nur für Tests und Aufräumarbeiten: nimmt den Schreibschutz wieder weg."""
    for datei in ordner.rglob("*"):
        if datei.is_file() and not os.access(datei, os.W_OK):
            schreibschutz_aufheben(datei)
