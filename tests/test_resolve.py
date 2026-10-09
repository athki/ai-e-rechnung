"""resolve: Laden, Nummernvergabe, Rechnen, Einfrieren – gegen einen Temp-Gewerbe-Ordner."""

import json
import shutil
from datetime import date
from decimal import Decimal

import pytest

from rechnung import config, resolve as r
from rechnung.models import Input

RECHNUNG = """\
kunde: {kunde}
datum: 2026-09-22
leistungsdatum: 2026-06-10
leistung:
{leistung}
positionen:
{positionen}
"""

SONSTIGE = "  taetigkeit: Teilnahme als Panelist\n  einordnung: sonstige"

EINE_POSITION = """\
  - beschreibung: Teilnahme als Panelist
    menge: 1
    einheit: pauschal
    einzelpreis: 1000.00
"""


@pytest.fixture
def gewerbe(tmp_path, monkeypatch):
    """Leerer Gewerbe-Ordner mit den Beispiel-Stammdaten."""
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path))
    shutil.copytree(config.BEISPIEL_STAMMDATEN, tmp_path / "stammdaten")
    (tmp_path / "rechnung-ausgang").mkdir()
    (tmp_path / "steuerberater").mkdir()
    return tmp_path


def cfg(**env) -> config.Config:
    return config.laden(env={**{k: v for k, v in env.items()}}, pfad=config.REPO / "fehlt.toml")


def lege_an(gewerbe, kunde="sample-ltd", positionen=EINE_POSITION, leistung=SONSTIGE, **extra) -> str:
    c = config.laden()
    ordner, nummer = r.neu(c, kunde, date(2026, 6, 10), date(2026, 9, 22))
    text = RECHNUNG.format(kunde=kunde, positionen=positionen, leistung=leistung)
    for schluessel, wert in extra.items():
        text += f"{schluessel}: {wert}\n"
    (ordner / r.INPUT_DATEI).write_text(text, encoding="utf-8")
    return nummer


# ---------------------------------------------------------------- Stammdaten und Kunden

def test_beispiel_stammdaten_sind_gueltig(gewerbe):
    c = config.laden()
    stammdaten = r.lade_stammdaten(c)
    assert stammdaten.ustid == "DE123456789"
    assert stammdaten.bank.iban == "DE89370400440532013000"  # ohne Leerzeichen


@pytest.mark.parametrize(
    "kuerzel, ergebnis",
    [("muster-gmbh", "inland"), ("privat-de", "inland"), ("exemple-sarl", "reverse_charge"),
     ("sample-ltd", "nicht_steuerbar"), ("sample-inc", "nicht_steuerbar"), ("privat-ch", "inland")],
)
def test_jeder_beispielkunde_ergibt_sein_ergebnis(gewerbe, kuerzel, ergebnis):
    from rechnung import rules
    from rechnung.models import Leistung
    c = config.laden()
    kunde = r.lade_kunde(c, kuerzel)
    leistung = Leistung(taetigkeit="Beratung", einordnung="sonstige")
    assert rules.entscheide(kunde, leistung, r.lade_stammdaten(c)).ergebnis == ergebnis
    assert kunde.kuerzel == kuerzel


def test_unbekannter_kunde_listet_die_vorhandenen(gewerbe):
    with pytest.raises(r.ResolveFehler, match="sample-ltd"):
        r.lade_kunde(config.laden(), "gibtsnicht")


def test_fehlende_stammdaten_nennen_den_weg(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path))
    config.init(config.laden())
    with pytest.raises(r.ResolveFehler, match="init --stammdaten"):
        r.lade_stammdaten(config.laden())


def test_unbekanntes_feld_wird_abgelehnt(gewerbe):
    datei = gewerbe / "stammdaten" / "kunden" / "kaputt.yaml"
    datei.write_text("firma: X\nadresse: {strasse: a, plz: '1', ort: b}\nland: DE\ntippfehler: 1\n",
                     encoding="utf-8")
    with pytest.raises(r.ResolveFehler, match="tippfehler"):
        r.lade_kunde(config.laden(), "kaputt")


# ---------------------------------------------------------------- Nummernvergabe

def test_nummer_im_leeren_jahr(gewerbe):
    assert r.neue_nummer(config.laden(), 2026) == "2026-0001"


def test_nummer_zaehlt_weiter(gewerbe, monkeypatch):
    monkeypatch.setenv("RECHNUNG_NUMMER_FORMAT", "MM-{jahr}-{lfd:04d}")
    c = config.laden()
    assert r.neue_nummer(c, 2026) == "MM-2026-0001"
    r.neu(c, "sample-ltd", date(2026, 6, 10), date(2026, 9, 22))
    assert r.neue_nummer(c, 2026) == "MM-2026-0002"


def test_neu_legt_ordner_und_geruest_an(gewerbe):
    c = config.laden()
    ordner, nummer = r.neu(c, "sample-inc", date(2026, 6, 10), date(2026, 9, 22),
                           taetigkeit="Panel: Zukunft der Arbeit", einordnung="unterrichtend", ort="GB")
    assert ordner == gewerbe / "rechnung-ausgang" / "2026" / nummer
    assert (ordner / "belege").is_dir()
    text = (ordner / r.INPUT_DATEI).read_text(encoding="utf-8")
    assert "kunde: sample-inc" in text
    assert "einheit: pauschal" in text       # vorbelegt, aber sichtbar in der Datei
    assert "leistungsdatum: 2026-06-10" in text
    eingabe = Input.model_validate(__import__("yaml").safe_load(text))
    assert eingabe.positionen[0].einheit == "pauschal"
    assert eingabe.leistung.taetigkeit == "Panel: Zukunft der Arbeit"
    assert eingabe.leistung.ort == "GB"


def test_neu_ohne_leistung_laesst_sie_leer_und_listet_die_begriffe(gewerbe):
    """Die Einordnung ist eine Wertung – sie wird nicht geraten, die Liste steht in der Datei."""
    from rechnung import rules
    ordner, _ = r.neu(config.laden(), "muster-gmbh", date(2026, 6, 10), date(2026, 9, 22))
    text = (ordner / r.INPUT_DATEI).read_text(encoding="utf-8")
    assert r.TAETIGKEIT_PFLICHT in text and r.EINORDNUNG_PFLICHT in text
    for wort in rules.EINORDNUNGEN:
        assert wort in text
    assert "Nr. 6" in text and "Nr. 11–13" in text   # was fehlt, steht ausdrücklich da


# ---------------------------------------------------------------- Rechnen

def test_nicht_steuerbar_null_prozent_und_hinweis(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    ergebnis, ziel = r.resolve(config.laden(), nummer)
    assert ergebnis.ergebnis == "nicht_steuerbar"
    assert ergebnis.leistungsort == "GB"
    assert ergebnis.leistung.einordnung == "sonstige"
    assert ergebnis.regeln == ["R1", "R2", "R3", "R9", "R31", "R12", "R32", "R33"]   # R35
    assert ergebnis.netto == Decimal("1000.00")
    assert ergebnis.ust_betrag == Decimal("0.00")
    assert ergebnis.brutto == Decimal("1000.00")
    assert "United Kingdom" in ergebnis.hinweis["en"]
    assert ziel.is_file()


def test_inland_neunzehn_prozent(gewerbe):
    nummer = lege_an(gewerbe, "muster-gmbh")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.ergebnis == "inland"
    assert ergebnis.ust_betrag == Decimal("190.00")
    assert ergebnis.brutto == Decimal("1190.00")
    assert ergebnis.hinweis is None


def test_gemischte_saetze_werden_getrennt(gewerbe):
    positionen = EINE_POSITION + """\
  - beschreibung: Buch
    menge: 2
    einheit: stueck
    einzelpreis: 10.00
    steuersatz: 7
"""
    nummer = lege_an(gewerbe, "muster-gmbh", positionen)
    ergebnis, _ = r.resolve(config.laden(), nummer)
    saetze = {g.satz: (g.netto, g.betrag) for g in ergebnis.steuergruppen}
    assert saetze[Decimal(19)] == (Decimal("1000.00"), Decimal("190.00"))
    assert saetze[Decimal(7)] == (Decimal("20.00"), Decimal("1.40"))
    assert ergebnis.netto == Decimal("1020.00")
    assert ergebnis.brutto == Decimal("1211.40")


def test_rundung_je_zeile_und_summe(gewerbe):
    positionen = """\
  - beschreibung: Beratung
    menge: 3
    einheit: stunde
    einzelpreis: 33.335
  - beschreibung: Fahrt
    menge: 12.5
    einheit: kilometer
    einzelpreis: 0.42
"""
    nummer = lege_an(gewerbe, "muster-gmbh", positionen)
    ergebnis, _ = r.resolve(config.laden(), nummer)
    zeilen = [p.zeilensumme for p in ergebnis.positionen]
    assert zeilen == [Decimal("100.01"), Decimal("5.25")]   # 100.005 -> 100.01 (kaufmännisch)
    assert ergebnis.netto == Decimal("105.26")
    assert ergebnis.ust_betrag == Decimal("20.00")          # 105.26 * 0.19 = 20.0 (gerundet)


def test_privatperson_drittland_vortrag_ist_nicht_steuerbar(gewerbe):
    """Früher Fall D mit 19 %: ein Vortrag in Zürich für eine Privatperson (§ 3a Abs. 3 Nr. 3)."""
    leistung = "  taetigkeit: Vortrag\n  einordnung: unterrichtend\n  ort: CH"
    nummer = lege_an(gewerbe, "privat-ch", leistung=leistung)
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.ergebnis == "nicht_steuerbar"
    assert ergebnis.leistungsort == "CH"
    assert ergebnis.ust_betrag == Decimal("0.00")
    assert "§ 3a Abs. 3 Nr. 3 UStG" in ergebnis.hinweis["de"]


def test_privatperson_drittland_sonstige_ist_inland(gewerbe):
    nummer = lege_an(gewerbe, "privat-ch")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.ergebnis == "inland"
    assert ergebnis.ust_betrag == Decimal("190.00")


def test_leistung_fehlt_nennt_den_weg(gewerbe):
    c = config.laden()
    ordner, nummer = r.neu(c, "muster-gmbh", date(2026, 6, 10), date(2026, 9, 22))
    with pytest.raises(r.ResolveFehler, match="taetigkeit fehlt"):
        r.resolve(c, nummer)


def test_ort_fehlt_bei_taetigkeit(gewerbe):
    nummer = lege_an(gewerbe, "privat-ch", leistung="  taetigkeit: Vortrag\n  einordnung: unterrichtend")
    with pytest.raises(r.ResolveFehler, match="ort fehlt"):
        r.resolve(config.laden(), nummer)


def test_alter_steuerfall_wird_erklaert(gewerbe):
    nummer = lege_an(gewerbe, "privat-ch", steuerfall="D", begruendung="Privatkunde")
    with pytest.raises(r.ResolveFehler, match="gibt es nicht mehr"):
        r.resolve(config.laden(), nummer)


def test_leistungsort_festgelegt_mit_begruendung(gewerbe):
    nummer = lege_an(gewerbe, "exemple-sarl", leistungsort="CH",
                     begruendung="Leistung an die Niederlassung in Zürich")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.leistungsort == "CH"
    assert ergebnis.leistungsort_manuell is True
    assert ergebnis.ergebnis == "nicht_steuerbar"


def test_leistungsort_ohne_begruendung_schlaegt_fehl(gewerbe):
    nummer = lege_an(gewerbe, "privat-ch", leistungsort="DE")
    with pytest.raises(r.ResolveFehler, match="begruendung"):
        r.resolve(config.laden(), nummer)


def test_begruendung_ohne_leistungsort_schlaegt_fehl(gewerbe):
    nummer = lege_an(gewerbe, "muster-gmbh", begruendung="einfach so")
    with pytest.raises(r.ResolveFehler, match="leistungsort"):
        r.resolve(config.laden(), nummer)


def test_reverse_charge_fristwarnung(gewerbe):
    """Leistung im Juni, Rechnung im September: nach dem 15. Juli, also eine Warnung (R30)."""
    nummer = lege_an(gewerbe, "exemple-sarl")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.ergebnis == "reverse_charge"
    assert len(ergebnis.warnungen) == 1 and "14a Abs. 1 Satz 2" in ergebnis.warnungen[0]


def kleinunternehmer(gewerbe):
    ich = gewerbe / "stammdaten" / "ich.yaml"
    ich.write_text(ich.read_text(encoding="utf-8") + "kleinunternehmer: true\n", encoding="utf-8")


def test_kleinunternehmer_inland_ohne_steuer(gewerbe):
    kleinunternehmer(gewerbe)
    nummer = lege_an(gewerbe, "muster-gmbh")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.ergebnis == "kleinunternehmer"
    assert ergebnis.ust_betrag == Decimal("0.00") and ergebnis.brutto == Decimal("1000.00")
    assert ergebnis.hinweis == {"de": "Steuerfrei als Leistung eines Kleinunternehmers (§ 19 Abs. 1 UStG)."}


def test_kleinunternehmer_mit_positionssatz_bricht_ab(gewerbe):
    kleinunternehmer(gewerbe)
    positionen = EINE_POSITION.replace("einzelpreis: 1000.00", "einzelpreis: 1000.00\n    steuersatz: 7")
    nummer = lege_an(gewerbe, "muster-gmbh", positionen)
    with pytest.raises(r.ResolveFehler, match="kleinunternehmer"):
        r.resolve(config.laden(), nummer)


def test_reverse_charge_ohne_eigene_ustid_bricht_ab(gewerbe):
    from rechnung import rules
    ich = gewerbe / "stammdaten" / "ich.yaml"
    ich.write_text(ich.read_text(encoding="utf-8").replace("ustid: DE123456789\n", ""), encoding="utf-8")
    nummer = lege_an(gewerbe, "exemple-sarl")
    with pytest.raises(rules.RegelFehler, match="Eigene USt-IdNr."):
        r.resolve(config.laden(), nummer)


def test_fremdwaehrung_mit_ust_bricht_ab(gewerbe):
    from rechnung import rules
    nummer = lege_an(gewerbe, "muster-gmbh", waehrung="USD")
    with pytest.raises(rules.RegelFehler, match="Euro"):
        r.resolve(config.laden(), nummer)


def test_fremdwaehrung_ohne_ust_laeuft(gewerbe):
    nummer = lege_an(gewerbe, "sample-inc")     # Delaware, Währung USD aus der Kundendatei
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.waehrung == "USD"
    assert ergebnis.ergebnis == "nicht_steuerbar"
    assert "United States" in ergebnis.hinweis["en"]


def test_positions_steuersatz_bei_null_prozent_bricht_ab(gewerbe):
    positionen = EINE_POSITION.replace("einzelpreis: 1000.00", "einzelpreis: 1000.00\n    steuersatz: 19")
    nummer = lege_an(gewerbe, "sample-ltd", positionen)
    with pytest.raises(r.ResolveFehler, match="nicht_steuerbar"):
        r.resolve(config.laden(), nummer)


def test_sprache_kommt_vom_kunden_dann_von_der_config(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")     # Kundendatei sagt en
    assert r.resolve(config.laden(), nummer)[0].sprache == "en"
    nummer = lege_an(gewerbe, "muster-gmbh")    # Kundendatei sagt de
    assert r.resolve(config.laden(), nummer)[0].sprache == "de"


def test_faelligkeit_aus_der_config(gewerbe, monkeypatch):
    nummer = lege_an(gewerbe, "sample-ltd")
    assert r.resolve(config.laden(), nummer)[0].faelligkeit == date(2026, 10, 6)
    monkeypatch.setenv("RECHNUNG_ZAHLUNGSZIEL_TAGE", "30")
    assert r.resolve(config.laden(), nummer)[0].faelligkeit == date(2026, 10, 22)


def test_zahlungsziel_je_rechnung_gewinnt(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd", zahlungsziel_tage=7)
    assert r.resolve(config.laden(), nummer)[0].faelligkeit == date(2026, 9, 29)


# ---------------------------------------------------------------- Eingefrorenes Ergebnis

def test_resolved_json_ist_lesbar_und_vollstaendig(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    ergebnis, ziel = r.resolve(config.laden(), nummer)
    daten = json.loads(ziel.read_text(encoding="utf-8"))

    assert daten["nummer"] == nummer
    assert daten["netto"] == "1000.00"          # Decimal als Text, nicht als Fließkomma
    assert daten["aussteller"]["steuernummer"] == "143/123/12345"
    assert daten["kunde"]["firma"] == "Sample Ltd"
    assert daten["kunde"]["register"]["name"] == "Companies House"
    assert daten["positionen"][0]["einheit_code"] == "LS"
    assert daten["positionen"][0]["einzelpreis"] == "1000.00"
    assert len(daten["input_hash"]) == 64
    assert daten["vorlage_version"]


def test_input_hash_haengt_am_yaml(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    erster = r.resolve(config.laden(), nummer)[0].input_hash
    ordner = r.finde_ordner(config.laden(), nummer)
    datei = ordner / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8") + "referenz: Panel 2026\n", encoding="utf-8")
    assert r.resolve(config.laden(), nummer)[0].input_hash != erster


def test_resolve_ohne_schreiben(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    _, ziel = r.resolve(config.laden(), nummer, schreiben=False)
    assert not ziel.exists()


def test_finde_ordner_akzeptiert_das_nummernende(gewerbe, monkeypatch):
    monkeypatch.setenv("RECHNUNG_NUMMER_FORMAT", "MM-{jahr}-{lfd:04d}")
    nummer = lege_an(gewerbe, "sample-ltd")
    assert nummer == "MM-2026-0001"
    assert r.finde_ordner(config.laden(), "2026-0001").name == nummer


# ---------------------------------------------------------------- YAML-Syntaxfehler

@pytest.mark.parametrize(
    "text, erklaerung",
    [
        ("kunde: sample-ltd\neinleitung: Panel: Zukunft der Arbeit\n", "Anführungszeichen"),
        ("kunde: sample-ltd\nreferenz: \"PO 4711\n", "nicht geschlossen"),
        ("kunde: sample-ltd\npositionen:\n  - beschreibung: a\n    menge: 1\n   einheit: pauschal\n",
         "Einrückung"),
        ("kunde: sample-ltd\n# belege:\n  - flug.pdf\n", "auskommentiert"),
    ],
)
def test_yaml_syntaxfehler_ohne_traceback(gewerbe, text, erklaerung):
    nummer = lege_an(gewerbe)
    ordner = r.finde_ordner(config.laden(), nummer)
    (ordner / r.INPUT_DATEI).write_text(text, encoding="utf-8")
    with pytest.raises(r.ResolveFehler) as info:
        r.resolve(config.laden(), nummer)
    meldung = str(info.value)
    assert "rechnung.yaml, Zeile " in meldung and "Spalte " in meldung
    assert erklaerung in meldung
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_yaml_syntaxfehler_in_der_kundendatei(gewerbe):
    (gewerbe / "stammdaten" / "kunden" / "kaputt.yaml").write_text(
        "firma: Kaputt: Ltd\n", encoding="utf-8")
    with pytest.raises(r.ResolveFehler, match=r"kaputt\.yaml, Zeile 1, Spalte 14"):
        r.lade_kunde(config.laden(), "kaputt")


# ---------------------------------------------------------------- Werte in Fehlermeldungen, Platzhalter

def test_klammer_um_den_betrag_zeigt_wert_und_hinweis(gewerbe):
    pos = EINE_POSITION.replace("einzelpreis: 1000.00", "einzelpreis: {354.82}")
    nummer = lege_an(gewerbe, positionen=pos)
    with pytest.raises(r.ResolveFehler) as info:
        r.resolve(config.laden(), nummer)
    meldung = str(info.value)
    assert "positionen.0.einzelpreis" in meldung
    assert "(Wert: {354.82})" in meldung
    assert "Geschweifte Klammern entfernen" in meldung


def test_falscher_wert_wird_gezeigt(gewerbe):
    pos = EINE_POSITION.replace("einheit: pauschal", "einheit: stunden")
    nummer = lege_an(gewerbe, positionen=pos)
    with pytest.raises(r.ResolveFehler, match="„stunden“"):
        r.resolve(config.laden(), nummer)


@pytest.mark.parametrize(
    "feld, text",
    [("einleitung", "Für meine Teilnahme bei {Event} berechne ich:"),
     ("referenz", "PO {Nummer}")],
)
def test_platzhalter_im_text_bricht_ab(gewerbe, feld, text):
    nummer = lege_an(gewerbe, **{feld: f'"{text}"'})
    with pytest.raises(r.ResolveFehler, match=rf"{feld}: enthält den Platzhalter \{{"):
        r.resolve(config.laden(), nummer)


def test_platzhalter_in_der_beschreibung_bricht_ab(gewerbe):
    pos = EINE_POSITION.replace("Teilnahme als Panelist", "Teilnahme als Panelist, {Event}, London")
    nummer = lege_an(gewerbe, positionen=pos)
    with pytest.raises(r.ResolveFehler, match=r"beschreibung: enthält den Platzhalter \{Event\}"):
        r.resolve(config.laden(), nummer)


def test_platzhalter_in_der_kundendatei_bricht_ab(gewerbe):
    (gewerbe / "stammdaten" / "kunden" / "halb.yaml").write_text(
        "firma: '{Startup Ltd}'\nadresse: {strasse: a, plz: '1', ort: b}\nland: GB\n", encoding="utf-8")
    with pytest.raises(r.ResolveFehler, match=r"firma: enthält den Platzhalter"):
        r.lade_kunde(config.laden(), "halb")


# ---------------------------------------------------------------- Leistungsdatum ist Pflicht

def test_neu_ohne_leistungsdatum_laesst_das_feld_leer(gewerbe):
    c = config.laden()
    ordner, nummer = r.neu(c, "sample-ltd", None, date(2026, 9, 22))
    text = (ordner / r.INPUT_DATEI).read_text(encoding="utf-8")
    zeile = next(z for z in text.splitlines() if z.startswith("leistungsdatum:"))
    assert "2026-09-22" not in zeile                       # nicht still das Rechnungsdatum
    assert "# PFLICHT: Tag der Leistung, JJJJ-MM-TT" in zeile
    with pytest.raises(r.ResolveFehler) as info:
        r.resolve(c, nummer)
    meldung = str(info.value)
    assert "leistungsdatum fehlt" in meldung and "JJJJ-MM-TT" in meldung
    assert "Wert:" not in meldung and "Wurzel" not in meldung


def test_neu_mit_leistungsdatum_traegt_es_ein(gewerbe):
    c = config.laden()
    ordner, nummer = r.neu(c, "sample-ltd", date(2026, 6, 10), date(2026, 9, 22),
                           taetigkeit="Panel", einordnung="sonstige")
    assert "leistungsdatum: 2026-06-10\n" in (ordner / r.INPUT_DATEI).read_text(encoding="utf-8")
    ergebnis, _ = r.resolve(c, nummer)
    assert ergebnis.leistungsdatum == date(2026, 6, 10)


def test_cli_neu_ohne_leistungsdatum_sagt_es(gewerbe):
    from typer.testing import CliRunner

    from rechnung.cli import app

    aus = CliRunner().invoke(app, ["neu", "--kunde", "sample-ltd"])
    assert aus.exit_code == 0, aus.output
    assert "leistungsdatum ist noch leer" in aus.output
