"""Geschwärzte Sicht (sicht.py): Einstufung der Felder, Schalter, Abbruch-Arten, und dass unter dem
Schalter keine Ausgabe einen Namen, eine Anschrift, eine IBAN oder einen Betrag aus den Beispieldaten
enthält."""

from __future__ import annotations

import re
import shutil
import typing
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel
from typer.testing import CliRunner

from rechnung import anschreiben, config, meldung, resolve as r, sicht
from rechnung.cli import app
from rechnung.models import Input

from hilfen import bestaetige

# ---------------------------------------------------------------- Einstufung


def _felder(modell: type[BaseModel], vorne: str = "") -> set[str]:
    """Alle Felder eines Modells, Unterfelder verschachtelter Modelle (auch in Listen) mit Punkt."""
    ergebnis = set()
    for name, info in modell.model_fields.items():
        unter = [t for t in _typen(info.annotation) if isinstance(t, type) and issubclass(t, BaseModel)]
        if unter:
            for u in unter:
                ergebnis |= _felder(u, f"{vorne}{name}.")
        else:
            ergebnis.add(f"{vorne}{name}")
    return ergebnis


def _typen(annotation) -> list:
    args = typing.get_args(annotation)
    if not args:
        return [annotation]
    return [t for a in args for t in _typen(a)]


def test_jedes_feld_von_rechnung_yaml_ist_eingestuft():
    """Ein neues Feld ohne Einstufung lässt diesen Test scheitern: erst entscheiden, ob die AI es sieht."""
    assert _felder(Input) == set(sicht.EINSTUFUNG)
    assert set(sicht.EINSTUFUNG.values()) <= {sicht.AI, sicht.PRIVAT}


def test_rechnung_yaml_hat_kein_privates_feld_mehr():
    """Preise und Referenz stehen in rechnung.privat.yaml; rechnung.yaml enthält nur, was die AI sieht."""
    assert {f for f, e in sicht.EINSTUFUNG.items() if e == sicht.PRIVAT} == set()
    assert sicht.PRIVATE_FELDER == ("einzelpreis", "preis", "referenz")


@pytest.mark.parametrize(("wert", "aktiv"), [
    (None, False), ("", False), ("0", False), (" ", False),
    ("1", True), ("ja", True), ("true", True), ("false", True), (" 0 ", False),
])
def test_schalter_ist_fail_closed(wert, aktiv):
    env = {} if wert is None else {sicht.SCHALTER: wert}
    assert sicht.aktiv(env) is aktiv


def test_pfad_ohne_namen_der_wurzel(tmp_path):
    c = config.laden(env={"RECHNUNG_GEWERBE": str(tmp_path)}, pfad=tmp_path / "fehlt.toml")
    assert sicht.pfad(tmp_path / "rechnung-ausgang" / "x", c) == "<gewerbe>/rechnung-ausgang/x"
    assert sicht.pfad(tmp_path, c) == "<gewerbe>"
    assert sicht.pfad(Path.home() / "woanders", c) == "~/woanders"


# ---------------------------------------------------------------- Abbruch


def test_abbruch_ohne_geschwaerzte_fassung_wird_zurueckgehalten():
    text = sicht.abbruch(r.ResolveFehler("Erika Beispiel, Beispielstraße 7"))
    assert text.startswith("Abbruch (frage): Meldung zurückgehalten")
    assert "Erika" not in text
    assert sicht.abbruch(ValueError("Erika")).startswith("Abbruch (frage): Meldung zurückgehalten")


def test_abbruch_nennt_art_und_geschwaerzte_fassung():
    e = meldung.Fehler("privat", art=meldung.STAMMDATEN, geschwaerzt="ohne Werte")
    assert sicht.abbruch(e) == "Abbruch (stammdaten): ohne Werte"
    with pytest.raises(ValueError):
        meldung.Fehler("x", art="unbekannt")


# ---------------------------------------------------------------- Ergebnis


def test_ergebnis_zeigt_nur_die_positivliste(gewerbe_geschwaerzt):
    nummer = neu(gewerbe_geschwaerzt, "exemple-sarl")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    s = sicht.ergebnis(ergebnis)
    assert set(s) == {"nummer", "kunde", "datum", "leistungsdatum", "leistungsdatum_bis", "sprache",
                      "leistung", "leistungsort", "leistungsort_manuell", "ergebnis", "regeln",
                      "positionen", "belege", "warnungen", "preise"}
    assert set(s["positionen"][0]) == {"pos", "kuerzel", "beschreibung", "menge", "einheit", "steuersatz"}
    assert (s["ergebnis"], s["leistungsort"], s["preise"]) == ("reverse_charge", "FR", "bestaetigt")
    # Vor der Bestätigung dieselben Felder, mit dem Stand der Preise.
    e = sicht.entwurf(r.entwurf(config.laden(), nummer))
    assert set(e) == set(s) and set(e["positionen"][0]) == set(s["positionen"][0])


# ---------------------------------------------------------------- Keine privaten Werte in der Ausgabe

PREIS, MENGE = "123.45", "3"
# Zeilensumme, USt 19 %, Brutto und Preis in beiden Schreibweisen; dazu jede Zahl mit zwei Nachkommastellen.
BETRAEGE = ("123.45", "123,45", "370.35", "370,35", "70.37", "70,37", "440.72", "440,72")
GELD = re.compile(r"\b\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\b")
# Feldwerte, die die AI sehen darf oder die als Code ohnehin im Leistungsort stehen.
NICHT_PRIVAT = {"land", "sprache", "waehrung", "unternehmer", "kleinunternehmer"}


def private_werte() -> set[str]:
    """Jeder Text aus den Beispiel-Stammdaten, der in keiner geschwärzten Ausgabe stehen darf."""
    werte: set[str] = set()

    def sammle(daten, schluessel=""):
        if isinstance(daten, dict):
            for k, v in daten.items():
                sammle(v, k)
        elif isinstance(daten, str) and schluessel not in NICHT_PRIVAT:
            werte.add(daten)
            if schluessel == "iban":
                werte.add(daten.replace(" ", ""))
    for datei in config.BEISPIEL_STAMMDATEN.rglob("*.yaml"):
        # Die Preisliste enthält als Text nur Bezeichnung, Einheit und Art – die sieht die AI.
        # Ihre Preise sind Zahlen; die fängt GELD.
        if datei.name != "preise.yaml":
            sammle(yaml.safe_load(datei.read_text(encoding="utf-8")))
    return werte


LEISTUNG = {   # Kürzel -> (einordnung, ort); Tätigkeit und Beschreibung ohne Ortsnamen
    "muster-gmbh": ("beratung", None), "exemple-sarl": ("beratung", None),
    "sample-ltd": ("unterrichtend", "GB"), "sample-inc": ("beratung", None),
    "privat-ch": ("unterrichtend", "CH"), "privat-de": ("beratung", None),
}


@pytest.fixture
def gewerbe_geschwaerzt(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path))
    monkeypatch.setenv(sicht.SCHALTER, "1")
    shutil.copytree(config.BEISPIEL_STAMMDATEN, tmp_path / "stammdaten")
    (tmp_path / "rechnung-ausgang").mkdir()
    return tmp_path


def lauf(*args: str) -> str:
    aus = CliRunner().invoke(app, list(args))
    assert not isinstance(aus.exception, (AssertionError, TypeError, AttributeError, KeyError)), aus.exception
    return aus.output


def neu(gewerbe: Path, kuerzel: str, waehrung: str = "EUR", preise: bool = True) -> str:
    einordnung, ort = LEISTUNG[kuerzel]
    args = ["neu", "--kunde", kuerzel, "--leistungsdatum", "2026-10-01", "--datum", "2026-10-05",
            "--taetigkeit", "Arbeit nach Absprache", "--einordnung", einordnung, "--waehrung", waehrung]
    if ort:
        args += ["--ort", ort]
    lauf(*args)
    ordner = sorted((gewerbe / "rechnung-ausgang" / "2026").iterdir())[-1]
    datei = ordner / r.INPUT_DATEI
    text = datei.read_text(encoding="utf-8")
    text = text.replace("menge: 1\n", f"menge: {MENGE}\n", 1).replace("  - kuerzel: ", "  - kuerzel: briefing", 1)
    datei.write_text(text, encoding="utf-8")
    if preise:
        bestaetige(ordner.name, PREIS)
    return ordner.name


# Feste Labels, die wie ein Betrag aussehen, aber keiner aus den Daten sind.
LABELS = ("Steuerbetrag 0,00",)


def pruefe_ohne_private_werte(ausgaben: list[str], geld: bool = True) -> None:
    text = "\n".join(ausgaben)
    for wert in private_werte():
        assert wert not in text, f"privater Wert {wert!r} in der geschwärzten Ausgabe"
    for betrag in BETRAEGE:
        assert betrag not in text, f"Betrag {betrag} in der geschwärzten Ausgabe"
    if geld:
        for label in LABELS:
            text = text.replace(label, "")
        assert not GELD.findall(text), GELD.findall(text)
    assert str(Path.home()) not in text


def test_neu_schreibt_keinen_kundennamen_in_rechnung_yaml(gewerbe_geschwaerzt):
    for kuerzel in LEISTUNG:
        nummer = neu(gewerbe_geschwaerzt, kuerzel)
        yaml_text = (r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI).read_text(encoding="utf-8")
        for wert in private_werte():
            assert wert not in yaml_text, (kuerzel, wert)


@pytest.mark.skipif(shutil.which("latexmk") is None or shutil.which("pdftotext") is None,
                    reason="LaTeX oder pdftotext fehlt")
def test_kein_privater_wert_in_resolve_bauen_pruefen_begruendung(gewerbe_geschwaerzt):
    # doctor nennt Versionsnummern (3.12, 4.88), die wie Beträge aussehen.
    pruefe_ohne_private_werte([lauf("doctor")], geld=False)
    ausgaben = [lauf("init")]
    for kuerzel in LEISTUNG:
        nummer = neu(gewerbe_geschwaerzt, kuerzel, "USD" if kuerzel == "sample-inc" else "EUR")
        ordner = r.finde_ordner(config.laden(), nummer)
        (ordner / anschreiben.DATEI).write_text("[anrede],\nanbei [nummer] über [brutto] für [firma].\n[name]\n",
                                                encoding="utf-8")
        for kommando in (["resolve", nummer], ["bauen", nummer], ["pruefen", nummer],
                         ["begruendung", nummer], ["bauen", nummer, "--pro-forma"],
                         ["pruefen", nummer, "--pro-forma"], ["anschreiben", nummer], ["preise", nummer]):
            ausgaben.append(lauf(*kommando))
    # Eine Rechnung ohne bestätigte Preise: resolve zeigt den Entwurf, bauen bricht ab.
    offen = neu(gewerbe_geschwaerzt, "muster-gmbh", preise=False)
    ausgaben += [lauf("resolve", offen), lauf("bauen", offen), lauf("preisliste"), lauf("offen")]
    assert any("reverse_charge" in a for a in ausgaben)
    assert any("grün:" in a for a in ausgaben)
    assert any("anschreiben.md ist gültig" in a for a in ausgaben)
    pruefe_ohne_private_werte(ausgaben)


def kunde_aendern(gewerbe: Path, kuerzel: str, alt: str, neu_: str) -> None:
    datei = gewerbe / "stammdaten" / "kunden" / f"{kuerzel}.yaml"
    text = datei.read_text(encoding="utf-8")
    assert alt in text
    datei.write_text(text.replace(alt, neu_), encoding="utf-8")


@pytest.mark.parametrize(("kuerzel", "aendern", "art"), [
    ("exemple-sarl", ("unternehmer: true\n", ""), meldung.STAMMDATEN),
    ("exemple-sarl", ("ustid: FR12345678901\n", ""), meldung.STAMMDATEN),
    ("exemple-sarl", ("land: FR", "land: XY"), meldung.STAMMDATEN),
    ("exemple-sarl", ("firma: Exemple SARL", "firma: Exemple SARL\nfirma2: x"), meldung.STAMMDATEN),
    ("exemple-sarl", ("ort: Paris", "ort: Paris: [x"), meldung.STAMMDATEN),
])
def test_abbruch_wegen_stammdaten_ohne_private_werte(gewerbe_geschwaerzt, kuerzel, aendern, art):
    nummer = neu(gewerbe_geschwaerzt, kuerzel)
    kunde_aendern(gewerbe_geschwaerzt, kuerzel, *aendern)
    aus = lauf("resolve", nummer)
    assert aus.startswith(f"Abbruch ({art}): "), aus
    assert "zurückgehalten" not in aus
    pruefe_ohne_private_werte([aus])


def test_abbruch_ausserhalb_des_geltungsbereichs(gewerbe_geschwaerzt):
    """Privatperson, Tätigkeit in einem anderen EU-Staat (R18): erklären und anhalten."""
    lauf("neu", "--kunde", "privat-de", "--leistungsdatum", "2026-10-01", "--taetigkeit", "Vortrag",
         "--einordnung", "unterrichtend", "--ort", "FR")
    datei = r.finde_ordner(config.laden(), "0001") / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8").replace("  - kuerzel: ", "  - kuerzel: briefing"),
                     encoding="utf-8")
    aus = lauf("resolve", "0001")
    assert aus.startswith("Abbruch (ausserhalb): Leistungsort FR ist ein anderer EU-Staat"), aus
    pruefe_ohne_private_werte([aus])


def test_abbruch_wegen_ausstellerdatei_ohne_private_werte(gewerbe_geschwaerzt):
    nummer = neu(gewerbe_geschwaerzt, "privat-de")
    ich = gewerbe_geschwaerzt / "stammdaten" / "ich.yaml"
    ich.write_text(ich.read_text(encoding="utf-8").replace("email: max@example.com\n", ""), encoding="utf-8")
    aus = lauf("resolve", nummer)
    assert aus.startswith("Abbruch (stammdaten): Ausstellerdatei ich.yaml:"), aus
    assert "email" in aus
    pruefe_ohne_private_werte([aus])


def test_abbruch_wegen_eigener_eingabe_bleibt_ganz_ohne_preis(gewerbe_geschwaerzt):
    nummer = neu(gewerbe_geschwaerzt, "privat-de")
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    text = datei.read_text(encoding="utf-8")
    datei.write_text(text.replace("einheit: pauschal ", "einheit: kiste ", 1)
                     .replace(f"menge: {MENGE}\n", f"menge: {MENGE}\n    einzelpreis: 12x.45\n", 1), encoding="utf-8")
    aus = lauf("resolve", nummer)
    assert aus.startswith("Abbruch (eingabe): rechnung.yaml:"), aus
    assert "einheit" in aus and "„kiste“" in aus
    assert "einzelpreis" in aus and "12x" not in aus     # aus Versehen in rechnung.yaml: Wert bleibt weg


def test_abbruch_wegen_fehlendem_leistungsdatum_ist_eine_frage(gewerbe_geschwaerzt):
    lauf("neu", "--kunde", "privat-de")
    aus = lauf("resolve", "0001")
    assert aus.startswith("Abbruch (frage): rechnung.yaml:"), aus
    assert "leistungsdatum fehlt" in aus


def test_unbekannter_kunde_nennt_keine_anderen_kuerzel(gewerbe_geschwaerzt):
    aus = lauf("neu", "--kunde", "gibt-es-nicht")
    assert aus.startswith("Abbruch (frage): Kunde 'gibt-es-nicht' nicht gefunden"), aus
    assert "muster-gmbh" not in aus


def test_ohne_schalter_bleibt_alles_wie_es_war(gewerbe_geschwaerzt, monkeypatch):
    monkeypatch.delenv(sicht.SCHALTER)
    nummer = neu(gewerbe_geschwaerzt, "exemple-sarl")
    aus = lauf("resolve", nummer)
    assert "Exemple SARL" in aus and "370,35 EUR" in aus
    kunde_aendern(gewerbe_geschwaerzt, "exemple-sarl", "unternehmer: true\n", "")
    assert "Land FR" in lauf("resolve", nummer)



# ---------------------------------------------------------------- Preise an der AI vorbei


def test_resolve_ohne_preise_zeigt_den_entwurf_und_den_weg(gewerbe_geschwaerzt):
    # In GBP gilt die Liste nicht: Die Preise trägt der Mensch ein.
    nummer = neu(gewerbe_geschwaerzt, "sample-ltd", waehrung="GBP", preise=False)
    aus = CliRunner().invoke(app, ["resolve", nummer])
    assert aus.exit_code == 0, aus.output
    assert "Ergebnis        nicht_steuerbar" in aus.output
    assert f"fehlen – der Mensch bestätigt sie im eigenen Terminal: rechnung preise {nummer}" in aus.output
    assert not (r.finde_ordner(config.laden(), nummer) / r.RESOLVED_DATEI).exists()
    pruefe_ohne_private_werte([aus.output])


def test_resolve_mit_listenpreisen_nennt_keinen_betrag(gewerbe_geschwaerzt):
    nummer = neu(gewerbe_geschwaerzt, "muster-gmbh", preise=False)
    aus = CliRunner().invoke(app, ["resolve", nummer])
    assert aus.exit_code == 0, aus.output
    assert "aus der Preisliste übernommen" in aus.output
    assert "2400" not in aus.output and "2.400" not in aus.output
    pruefe_ohne_private_werte([aus.output])


def test_bauen_ohne_preise_ist_ein_abbruch_der_art_preise(gewerbe_geschwaerzt):
    nummer = neu(gewerbe_geschwaerzt, "sample-ltd", waehrung="GBP", preise=False)
    aus = lauf("bauen", nummer)
    assert aus.startswith("Abbruch (preise): Preise für"), aus
    assert f"rechnung preise {nummer}" in aus


def test_preise_unter_dem_schalter_verweigert(gewerbe_geschwaerzt):
    nummer = neu(gewerbe_geschwaerzt, "muster-gmbh", preise=False)
    aus = CliRunner().invoke(app, ["preise", nummer], input="900\nj\n")
    assert aus.exit_code == 1
    assert aus.output.startswith("Abbruch (preise): `rechnung preise` läuft nur ohne RECHNUNG_GESCHWAERZT")
    assert not (r.finde_ordner(config.laden(), nummer) / "rechnung.privat.yaml").exists()


def test_preisliste_unter_dem_schalter_ohne_preise(gewerbe_geschwaerzt, monkeypatch):
    aus = lauf("preisliste")
    assert "vortrag" in aus and "pauschal" in aus and "Preise sind geschwärzt" in aus
    assert not GELD.findall(aus)
    monkeypatch.delenv(sicht.SCHALTER)
    assert "450,00 EUR" in lauf("preisliste")


def test_anschreiben_unter_dem_schalter_prueft_nur(gewerbe_geschwaerzt):
    nummer = neu(gewerbe_geschwaerzt, "exemple-sarl")
    datei = r.finde_ordner(config.laden(), nummer) / anschreiben.DATEI
    datei.write_text("Rechnung [nummer], [betrag]\n", encoding="utf-8")
    aus = lauf("anschreiben", nummer)
    assert aus.startswith("Abbruch (eingabe): Unbekannte Platzhalter in anschreiben.md: [betrag]"), aus
