"""MCP-Server (mcp_server.py): genau diese Werkzeuge, ein Durchlauf ohne private Werte, Kundenwahl,
Grenzen von `schreiben`, zurückgehaltene Fehler, Preise im Client.

Die Tests sprechen mit dem Server in-process über einen echten MCP-Client, mit und ohne Elicitation.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

pytest.importorskip("mcp")

import mcp.types as t
from mcp import Client

from rechnung import config, mcp_server, meldung, resolve as r

from hilfen import bestaetige
from test_sicht import LEISTUNG, MENGE, PREIS, gewerbe_geschwaerzt, pruefe_ohne_private_werte  # noqa: F401

WERKZEUGE = {"neu", "preisliste", "lesen", "schreiben", "resolve", "begruendung", "offen", "bauen", "pruefen",
             "anschreiben_schreiben", "anschreiben_pruefen"}

LATEX = pytest.mark.skipif(shutil.which("latexmk") is None or shutil.which("pdftotext") is None,
                           reason="LaTeX oder pdftotext fehlt")


@pytest.fixture
def gewerbe(gewerbe_geschwaerzt, monkeypatch):
    # Der Server schwärzt immer, auch ohne Schalter.
    monkeypatch.delenv("RECHNUNG_GESCHWAERZT")
    return gewerbe_geschwaerzt


class Sitzung:
    """Ein Client am Server; merkt sich jede Antwort und jede Elicitation, die er gesehen hat."""

    def __init__(self, einstellungen: mcp_server.Einstellungen | None = None,
                 antworten: list[dict | str] | None = None, elicitation: bool = True):
        self.server = mcp_server.erstelle(einstellungen)
        self.antworten = list(antworten or [])   # je Elicitation: Inhalt (accept) oder "decline"
        self.elicitation = elicitation
        self.gesehen: list[str] = []             # was an die AI ginge
        self.formulare: list[t.ElicitRequestParams] = []

    async def _elicit(self, context, params):
        self.formulare.append(params)
        antwort = self.antworten.pop(0)
        if antwort == "decline":
            return t.ElicitResult(action="decline")
        return t.ElicitResult(action="accept", content=antwort)

    def __call__(self, werkzeug: str, **args) -> tuple[bool, str]:
        async def lauf():
            async with Client(self.server, elicitation_callback=self._elicit if self.elicitation else None) as c:
                return await c.call_tool(werkzeug, args)
        ergebnis = asyncio.run(lauf())
        text = "\n".join(c.text for c in ergebnis.content if isinstance(c, t.TextContent))
        self.gesehen.append(text)
        return not ergebnis.is_error, text

    def ok(self, werkzeug: str, **args) -> str:
        gut, text = self(werkzeug, **args)
        assert gut, text
        return text

    def werkzeuge(self) -> set[str]:
        async def lauf():
            async with Client(self.server) as c:
                return await c.list_tools()
        return {w.name for w in asyncio.run(lauf()).tools}


def nummer_aus(text: str) -> str:
    import json
    return json.loads(text)["nummer"]


def anlegen(s: Sitzung, kuerzel: str) -> str:
    einordnung, ort = LEISTUNG[kuerzel]
    s.antworten.append({"kunde": kuerzel})
    nummer = nummer_aus(s.ok("neu", leistungsdatum="2026-10-01", taetigkeit="Arbeit nach Absprache",
                             einordnung=einordnung, ort=ort or ""))
    s.ok("schreiben", nummer=nummer,
         positionen=[{"kuerzel": "briefing", "menge": int(MENGE), "einheit": "pauschal"}])
    return nummer


# ---------------------------------------------------------------- Werkzeuge


def test_genau_diese_werkzeuge():
    """Ein neues Werkzeug lässt diesen Test scheitern: erst entscheiden, was es der AI zeigt."""
    assert Sitzung().werkzeuge() == WERKZEUGE
    assert Sitzung(mcp_server.Einstellungen(preise_im_client=True)).werkzeuge() == WERKZEUGE | {"preise_bestaetigen"}


def test_keine_werkzeuge_fuer_den_menschen():
    for name in ("preise", "festschreiben", "pro_forma", "pro-forma"):
        assert name not in Sitzung().werkzeuge()


# ---------------------------------------------------------------- Durchlauf


@LATEX
def test_durchlauf_ohne_private_werte_und_ohne_kuerzel(gewerbe):
    s = Sitzung()
    s.ok("preisliste")
    for kuerzel in LEISTUNG:
        nummer = anlegen(s, kuerzel)
        assert "fehlen" in s.ok("resolve", nummer=nummer)
        bestaetige(nummer, PREIS)                     # der Mensch, im eigenen Terminal
        assert "bestätigt" in s.ok("resolve", nummer=nummer)
        s.ok("lesen", nummer=nummer)
        s.ok("bauen", nummer=nummer)
        assert '"gruen": true' in s.ok("pruefen", nummer=nummer)
        s.ok("begruendung", nummer=nummer)
        s.ok("bauen", nummer=nummer, pro_forma=True)
        assert '"gruen": true' in s.ok("pruefen", nummer=nummer, pro_forma=True)
        s.ok("anschreiben_schreiben", nummer=nummer, text="[anrede],\nanbei [nummer] über [brutto].\n[name]\n")
        s.ok("anschreiben_pruefen", nummer=nummer)
    s.ok("offen")
    assert any("reverse_charge" in a for a in s.gesehen)
    pruefe_ohne_private_werte(s.gesehen)
    text = "\n".join(s.gesehen)
    for kuerzel in LEISTUNG:
        assert kuerzel not in text, f"Kürzel {kuerzel} in einer Antwort an die AI"


def test_resolve_ohne_preise_nennt_den_weg_und_keinen_betrag(gewerbe):
    s = Sitzung()
    nummer = anlegen(s, "muster-gmbh")
    text = s.ok("resolve", nummer=nummer)
    assert f"rechnung preise {nummer}" in text and "muster-gmbh" not in text
    gut, text = s("bauen", nummer=nummer)
    assert not gut and f"Abbruch ({meldung.PREISE}):" in text
    pruefe_ohne_private_werte(s.gesehen)


# ---------------------------------------------------------------- Kundenwahl


def test_kunde_per_elicitation_nur_kuerzel_im_formular(gewerbe):
    s = Sitzung(antworten=[{"kunde": "exemple-sarl"}])
    nummer = nummer_aus(s.ok("neu"))
    assert "kunde: exemple-sarl" in (r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI).read_text()
    formular = s.formulare[0]
    assert formular.requested_schema["properties"]["kunde"]["enum"] == sorted(LEISTUNG)
    pruefe_ohne_private_werte([str(formular)])


def test_kunde_abgelehnt_legt_nichts_an(gewerbe):
    s = Sitzung(antworten=["decline"])
    gut, text = s("neu")
    assert not gut and f"Abbruch ({meldung.FRAGE}):" in text
    assert not any((gewerbe / "rechnung-ausgang").rglob(r.INPUT_DATEI))


def test_ohne_elicitation_und_ohne_kuerzel_fragt_den_menschen(gewerbe):
    gut, text = Sitzung(elicitation=False)("neu")
    assert not gut and f"Abbruch ({meldung.FRAGE}):" in text and "rechnung neu --kunde" in text


def test_ohne_elicitation_mit_genanntem_kuerzel(gewerbe):
    s = Sitzung(elicitation=False)
    assert nummer_aus(s.ok("neu", kunde="sample-ltd"))


def test_fester_kunde_fragt_nicht_und_gewinnt(gewerbe):
    s = Sitzung(mcp_server.Einstellungen(kunde="privat-de"), elicitation=False)
    nummer = nummer_aus(s.ok("neu", kunde="muster-gmbh"))
    assert "kunde: privat-de" in (r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI).read_text()


def test_unbekannter_kunde_nennt_keine_anderen(gewerbe):
    gut, text = Sitzung(elicitation=False)("neu", kunde="gibtsnicht")
    assert not gut and "muster-gmbh" not in text


# ---------------------------------------------------------------- schreiben und lesen


def test_schreiben_nimmt_keinen_preis(gewerbe):
    s = Sitzung()
    nummer = anlegen(s, "muster-gmbh")
    gut, _ = s("schreiben", nummer=nummer,
               positionen=[{"kuerzel": "briefing", "menge": 1, "einheit": "pauschal", "einzelpreis": 5}])
    assert not gut
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    assert "einzelpreis" not in datei.read_text()


def test_schreiben_setzt_keinen_leistungsort_und_laesst_felder_des_menschen(gewerbe):
    s = Sitzung()
    nummer = anlegen(s, "exemple-sarl")
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    datei.write_text(datei.read_text() + "zahlungsziel_tage: 30\n", encoding="utf-8")
    s("schreiben", nummer=nummer, leistungsort="DE", begruendung="weil", einleitung="anbei die Rechnung.")
    text = datei.read_text()
    assert "leistungsort" not in text and "begruendung" not in text
    assert "zahlungsziel_tage: 30" in text and "kunde: exemple-sarl" in text
    assert "anbei die Rechnung." in text and "briefing" in text


def test_lesen_zeigt_nur_die_positivliste(gewerbe):
    s = Sitzung()
    nummer = anlegen(s, "muster-gmbh")
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    # Ein Preis, den der Mensch von Hand in die Datei geschrieben hat, geht nicht hinaus.
    datei.write_text(datei.read_text().replace("einheit: pauschal", "einheit: pauschal\n  einzelpreis: 987.65"),
                     encoding="utf-8")
    text = s.ok("lesen", nummer=nummer)
    assert "987" not in text and "muster-gmbh" not in text and "briefing" in text


def test_festgeschriebene_rechnung_wird_nicht_geschrieben(gewerbe, monkeypatch):
    s = Sitzung()
    nummer = anlegen(s, "muster-gmbh")
    monkeypatch.setattr(mcp_server.festschreiben_mod, "ist_festgeschrieben", lambda ordner: True)
    gut, text = s("schreiben", nummer=nummer, einleitung="x")
    assert not gut and f"Abbruch ({meldung.AUSSERHALB}):" in text


# ---------------------------------------------------------------- Fehler


def test_unerwarteter_fehler_wird_zurueckgehalten(gewerbe, monkeypatch):
    s = Sitzung()
    nummer = anlegen(s, "muster-gmbh")

    def kaputt(*a, **k):
        raise RuntimeError(f"{Path.home()}/geheim Muster GmbH 1.234,56")
    monkeypatch.setattr(mcp_server.resolve_mod, "entwurf", kaputt)
    gut, text = s("resolve", nummer=nummer)
    assert not gut and text.endswith(mcp_server.ZURUECKGEHALTEN) and "Muster" not in text


def test_fachlicher_abbruch_geschwaerzt(gewerbe):
    s = Sitzung()
    nummer = anlegen(s, "exemple-sarl")
    datei = gewerbe / "stammdaten" / "kunden" / "exemple-sarl.yaml"
    datei.write_text(datei.read_text().replace("ustid: FR12345678901\n", ""), encoding="utf-8")
    gut, text = s("resolve", nummer=nummer)
    assert not gut and f"Abbruch ({meldung.STAMMDATEN}):" in text
    pruefe_ohne_private_werte([text])


# ---------------------------------------------------------------- Preise im Client


def test_preise_im_client_ohne_betrag_an_die_ai(gewerbe):
    s = Sitzung(mcp_server.Einstellungen(preise_im_client=True))
    nummer = anlegen(s, "muster-gmbh")
    s.antworten.append({"preis_1": "123,45", "referenz": ""})
    text = s.ok("preise_bestaetigen", nummer=nummer)
    assert "bestätigt" in text
    assert "bestätigt" in s.ok("resolve", nummer=nummer)
    pruefe_ohne_private_werte(s.gesehen)
    # Das Formular selbst trägt den Vorschlag aus der Liste – es geht an den Menschen, nicht an die AI.
    assert "preis_1" in s.formulare[-1].requested_schema["properties"]


def test_preise_im_client_abgelehnt(gewerbe):
    s = Sitzung(mcp_server.Einstellungen(preise_im_client=True))
    nummer = anlegen(s, "muster-gmbh")
    s.antworten.append("decline")
    assert "nicht bestätigt" in s.ok("preise_bestaetigen", nummer=nummer)
    assert "fehlen" in s.ok("resolve", nummer=nummer)


def test_preise_im_client_ohne_elicitation_verweist_aufs_terminal(gewerbe):
    s = Sitzung(mcp_server.Einstellungen(preise_im_client=True))
    nummer = anlegen(s, "muster-gmbh")
    s.elicitation = False
    gut, text = s("preise_bestaetigen", nummer=nummer)
    assert not gut and f"Abbruch ({meldung.PREISE}):" in text and f"rechnung preise {nummer}" in text


# ---------------------------------------------------------------- stdio


def test_stdio_wie_ein_client(gewerbe, monkeypatch):
    """Der Server als Unterprozess über stdin/stdout – so starten ihn Claude Desktop und Claude Code."""
    import subprocess
    import sys

    rechnung = shutil.which("rechnung")
    assert rechnung, "rechnung nicht im PATH"
    aus = subprocess.run([sys.executable, str(Path(__file__).with_name("mcp_stdio.py")), rechnung, "mcp"],
                         capture_output=True, text=True, timeout=120)
    assert aus.returncode == 0, aus.stderr[-2000:]
    assert "aufgelöst (inland)" in aus.stdout
