"""Der nächste Schritt einer Rechnung, aus ihrem Stand – für MCP-Server und `rechnung offen`.

Eine Stelle, damit AI und Mensch denselben Hinweis bekommen. Der Text nennt nie einen Kunden, einen
Betrag oder einen echten Pfad; Befehle für den Menschen kommen aus `befehl()`, je Startart richtig.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from rechnung import config, festschreiben, meldung, preise, render, resolve
from rechnung.models import Resolved

# Setzt das Dockerfile: Der Mensch ruft das Werkzeug dann über `docker run` auf.
IM_CONTAINER = "RECHNUNG_IM_CONTAINER"


def befehl(kommando: str, env: dict[str, str] | None = None) -> str:
    """Wie der Mensch `rechnung <kommando>` in seinem eigenen Terminal aufruft, ohne echten Pfad.

    Im Container über `docker run`; auf dem Host mit den Variablen, mit denen das Werkzeug hier läuft
    (der Mensch setzt seine eigenen Werte ein), und über `uv`, wenn `rechnung` nicht installiert ist.
    """
    env = os.environ if env is None else env
    if env.get(IM_CONTAINER):
        demo = "-e RECHNUNG_DEMO=1 " if env.get("RECHNUNG_DEMO") else ""
        return f"docker run -it --rm {demo}-v <dein Gewerbe-Ordner>:/gewerbe rechnung {kommando}"
    davor = []
    if env.get("RECHNUNG_CONFIG"):
        davor.append("RECHNUNG_CONFIG=<deine config.toml>")
    if env.get("RECHNUNG_GEWERBE"):
        davor.append("RECHNUNG_GEWERBE=<dein Gewerbe-Ordner>")
    if env.get("RECHNUNG_DEMO"):
        davor.append("RECHNUNG_DEMO=1")
    aufruf = "rechnung" if _installiert() else "uv --directory <repo> run rechnung"
    return " ".join([*davor, aufruf, kommando])


def _installiert() -> bool:
    """`rechnung` liegt im PATH, und zwar nicht nur in der virtuellen Umgebung des Repos (`uv run`)."""
    pfad = shutil.which("rechnung")
    if pfad is None:
        return False
    try:
        Path(pfad).resolve().relative_to(config.REPO.resolve())
    except ValueError:
        return True
    return False


ABBRUCH = {
    meldung.EINGABE: "Fehlendes oder Falsches mit schreiben ergänzen; was nur der Mensch weiß (Datum, "
                     "Tätigkeit, Einordnung, Ort), erfragen. resolve zeigt, was fehlt.",
    meldung.FRAGE: "Den Menschen fragen, was resolve als fehlend meldet; nie raten. Dann schreiben.",
    meldung.STAMMDATEN: "Der Mensch ergänzt die Stammdaten selbst, nicht im Chat; danach resolve.",
    meldung.AUSSERHALB: "Anhalten und dem Menschen erklären: Das kann das Werkzeug noch nicht.",
    meldung.PREISE: "Der Mensch bestätigt die Preise selbst.",
}


def naechster(cfg: config.Config, ordner: Path, preise_weg: str | None = None) -> str:
    """Genau ein Hinweis für den Stand der Rechnung in `ordner`.

    `preise_weg`: wie der Mensch Preise einträgt, die die Liste nicht hat (MCP: Formular oder
    Terminal); ohne Angabe der Befehl im Terminal.
    """
    nummer = ordner.name
    if festschreiben.ist_festgeschrieben(ordner):
        return "Festgeschrieben – an dieser Rechnung ändert sich nichts mehr."
    try:
        e = resolve.entwurf_aus(cfg, ordner)
    except meldung.Fehler as f:
        return ABBRUCH.get(f.art, ABBRUCH[meldung.FRAGE])
    if e.preise != preise.BESTAETIGT:
        if preise.liste_reicht(e):
            return f"resolve({nummer}) – übernimmt die Preise aus der Preisliste."
        weg = preise_weg or f"im eigenen Terminal: {befehl(f'preise {nummer}')}"
        return f"Der Mensch trägt die Preise ein, die die Liste nicht hat (Auslage oder Fremdwährung): {weg}"
    r = _resolved(ordner)
    if (r is None or r.input_hash != resolve.input_hash(ordner)
            or r.privat_hash != resolve.privat_hash(ordner)
            or not (ordner / render.pdf_name(r.nummer, r.sprache)).is_file()):
        return f"Mit dem Menschen das Ergebnis von resolve klären, dann bauen({nummer})."
    return (f"pruefen({nummer}); ist es grün, schickt der Mensch die Rechnung und schreibt sie danach fest: "
            f"{befehl(f'festschreiben {nummer} --gesendet-am JJJJ-MM-TT')}")


def _resolved(ordner: Path) -> Resolved | None:
    pfad = ordner / resolve.RESOLVED_DATEI
    if not pfad.is_file():
        return None
    try:
        return Resolved.model_validate(json.loads(pfad.read_text(encoding="utf-8")))
    except ValueError:
        return None
