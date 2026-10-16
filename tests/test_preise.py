"""Preise an der AI vorbei: Preisliste, Bestätigung, Stand, rechnung.privat.yaml, Anrede, Anschreiben, `offen`."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from rechnung import anschreiben, config, meldung, preise, resolve as r
from rechnung.cli import app
from rechnung.models import PreisEintrag

from hilfen import bestaetige
from test_resolve import EINE_POSITION, gewerbe, lege_an  # noqa: F401 – Fixture

# ---------------------------------------------------------------- Preisliste


def test_beispiel_preisliste_ist_gueltig(gewerbe):
    liste = r.lade_preisliste(config.laden())
    assert liste["vortrag"].preis == Decimal("450.00") and liste["vortrag"].einheit == "stunde"
    assert liste["bahnticket"].art == "auslage" and liste["bahnticket"].preis == Decimal("89.90")   # nur Demo
    assert liste["nutzungsrecht"].steuersatz == Decimal(7)
    assert liste["buch"].art == "lieferung"
    assert liste["flug"].bezeichnung == {"de": "Reisekosten Flug", "en": "Travel: flight"}


@pytest.mark.parametrize(("eintrag", "meldung_"), [
    ({"bezeichnung": "Vortrag", "einheit": "pauschal"}, "preis fehlt"),
    ({"bezeichnung": "Buch", "einheit": "stueck", "preis": 10, "steuersatz": 19}, "nur 7"),
    ({"bezeichnung": "", "einheit": "stueck", "preis": 10}, "bezeichnung fehlt"),
    ({"bezeichnung": "Kiste", "einheit": "kiste", "preis": 10}, "einheit"),
])
def test_ungueltige_eintraege(eintrag, meldung_):
    with pytest.raises(ValueError, match=meldung_):
        PreisEintrag.model_validate(eintrag)


def test_bezeichnung_als_text_gilt_fuer_beide_sprachen():
    assert PreisEintrag.model_validate({"bezeichnung": "Workshop", "einheit": "tag", "preis": 1}).bezeichnung == {
        "de": "Workshop", "en": "Workshop"}


def test_fehler_in_der_preisliste_zeigt_geschwaerzt_keinen_preis(gewerbe):
    datei = gewerbe / "stammdaten" / "preise.yaml"
    datei.write_text(datei.read_text(encoding="utf-8") + "teuer:\n  bezeichnung: X\n  einheit: tag\n  preis: 4711x\n",
                     encoding="utf-8")
    with pytest.raises(r.ResolveFehler) as info:
        r.lade_preisliste(config.laden())
    assert info.value.art == meldung.STAMMDATEN
    assert "4711x" in str(info.value) and "4711" not in info.value.geschwaerzt
    assert info.value.geschwaerzt.startswith("Preisliste preise.yaml:")


def test_kuerzel_der_liste_nur_klein(gewerbe):
    datei = gewerbe / "stammdaten" / "preise.yaml"
    datei.write_text(datei.read_text(encoding="utf-8") + "Gross:\n  bezeichnung: X\n  einheit: tag\n  preis: 1\n",
                     encoding="utf-8")
    with pytest.raises(r.ResolveFehler, match="Kleinbuchstaben"):
        r.lade_preisliste(config.laden())


def test_fehlende_preisliste_ist_sache_der_stammdaten(gewerbe):
    (gewerbe / "stammdaten" / "preise.yaml").unlink()
    nummer = lege_an(gewerbe, preise_=None)
    with pytest.raises(r.ResolveFehler) as info:
        r.entwurf(config.laden(), nummer)
    assert info.value.art == meldung.STAMMDATEN
    assert info.value.geschwaerzt == "Preisliste preise.yaml fehlt. Der Mensch legt sie an."


# ---------------------------------------------------------------- Positionen gegen die Liste


def test_unbekanntes_kuerzel_nennt_die_vorhandenen(gewerbe):
    nummer = lege_an(gewerbe, positionen=EINE_POSITION.replace("kuerzel: vortrag", "kuerzel: keynote"))
    with pytest.raises(r.ResolveFehler) as info:
        r.entwurf(config.laden(), nummer)
    assert info.value.art == meldung.EINGABE
    assert "„keynote“ steht nicht in der Preisliste" in info.value.geschwaerzt
    assert "vortrag" in info.value.geschwaerzt and "450" not in info.value.geschwaerzt


def test_einheit_muss_zur_liste_passen(gewerbe):
    nummer = lege_an(gewerbe, positionen=EINE_POSITION.replace("einheit: stunde", "einheit: pauschal"))
    with pytest.raises(r.ResolveFehler, match="die Preisliste führt vortrag in „stunde“") as info:
        r.entwurf(config.laden(), nummer)
    assert info.value.art == meldung.EINGABE


def test_ohne_beschreibung_die_bezeichnung_in_der_sprache_der_rechnung(gewerbe):
    ohne = EINE_POSITION.replace("    beschreibung: Teilnahme als Panelist\n", "")
    assert r.entwurf(config.laden(), lege_an(gewerbe, "sample-ltd", ohne)).positionen[0].beschreibung == "Talk"
    assert r.entwurf(config.laden(), lege_an(gewerbe, "muster-gmbh", ohne)).positionen[0].beschreibung == "Vortrag"


def test_preis_nur_in_der_waehrung_der_liste_vorgeschlagen(gewerbe):
    assert r.entwurf(config.laden(), lege_an(gewerbe, "sample-ltd")).positionen[0].vorschlag == Decimal("450.00")
    assert r.entwurf(config.laden(), lege_an(gewerbe, "sample-inc", waehrung="USD")).positionen[0].vorschlag is None


def test_sieben_prozent_nur_wo_erlaubt(gewerbe):
    recht = "  - kuerzel: nutzungsrecht\n    menge: 1\n    einheit: pauschal\n"
    inland = r.entwurf(config.laden(), lege_an(gewerbe, "muster-gmbh", recht))
    assert inland.positionen[0].sieben_erlaubt and inland.positionen[0].vorschlag_sieben
    ausland = r.entwurf(config.laden(), lege_an(gewerbe, "sample-ltd", recht))
    assert not ausland.positionen[0].sieben_erlaubt and not ausland.positionen[0].vorschlag_sieben


# ---------------------------------------------------------------- Stand der Bestätigung


AUSLAGE = "  - kuerzel: bahnticket\n    menge: 1\n    einheit: pauschal\n"


def test_ohne_bestaetigung_fehlen_die_preise(gewerbe):
    nummer = lege_an(gewerbe, positionen=EINE_POSITION + AUSLAGE, preise_=None)
    assert r.entwurf(config.laden(), nummer).preise == preise.FEHLEN
    with pytest.raises(r.ResolveFehler) as info:
        r.resolve(config.laden(), nummer)
    assert info.value.art == meldung.PREISE
    assert f"`rechnung preise {nummer}`" in info.value.geschwaerzt


@pytest.mark.parametrize(("alt", "neu", "listenpreis"), [
    ("menge: 1\n    einheit: stunde", "menge: 2\n    einheit: stunde", "450.00"),
    ("beschreibung: Teilnahme als Panelist", "beschreibung: Teilnahme als Moderator", "450.00"),   # streng
    ("kuerzel: vortrag\n    menge: 1\n    einheit: stunde",
     "kuerzel: briefing\n    menge: 1\n    einheit: pauschal", "2400.00"),
])
def test_geaenderte_position_macht_die_preise_veraltet(gewerbe, alt, neu, listenpreis):
    """Veraltet ist die ganze Bestätigung; resolve füllt die geänderte Position aus der Liste, die
    unveränderte Auslage behält ihren bestätigten Preis (entscheidungen 2026-10-16)."""
    nummer = lege_an(gewerbe, positionen=EINE_POSITION + AUSLAGE, preise_=("1000.00", "50.00"))
    assert r.entwurf(config.laden(), nummer).preise == preise.BESTAETIGT
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8").replace(alt, neu), encoding="utf-8")
    assert r.entwurf(config.laden(), nummer).preise == preise.VERALTET
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert [p.einzelpreis for p in ergebnis.positionen] == [Decimal(listenpreis), Decimal("50.00")]


def test_geaenderte_auslage_bleibt_veraltet(gewerbe):
    nummer = lege_an(gewerbe, positionen=EINE_POSITION + AUSLAGE, preise_=("1000.00", "50.00"))
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8").replace("kuerzel: bahnticket\n    menge: 1",
                                                               "kuerzel: bahnticket\n    menge: 2"), encoding="utf-8")
    with pytest.raises(r.ResolveFehler, match="veraltet") as info:
        r.resolve(config.laden(), nummer)
    assert info.value.art == meldung.PREISE


def test_menge_in_anderer_schreibweise_bleibt_bestaetigt(gewerbe):
    nummer = lege_an(gewerbe)
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8").replace("menge: 1\n", "menge: 1.0\n"), encoding="utf-8")
    assert r.entwurf(config.laden(), nummer).preise == preise.BESTAETIGT


def test_andere_waehrung_macht_die_preise_veraltet(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8") + "waehrung: GBP\n", encoding="utf-8")
    assert r.entwurf(config.laden(), nummer).preise == preise.VERALTET


def test_einleitung_aendert_die_bestaetigung_nicht(gewerbe):
    nummer = lege_an(gewerbe)
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8") + "einleitung: Für den Vortrag\n", encoding="utf-8")
    assert r.entwurf(config.laden(), nummer).preise == preise.BESTAETIGT


def test_privat_datei_ist_ein_schnappschuss(gewerbe):
    """Spätere Änderungen der Preisliste wirken nicht auf bestätigte Rechnungen."""
    nummer = lege_an(gewerbe, preise_=())   # Preise aus der Liste
    liste = gewerbe / "stammdaten" / "preise.yaml"
    liste.write_text(liste.read_text(encoding="utf-8").replace("preis: 450.00", "preis: 1500.00"), encoding="utf-8")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.positionen[0].einzelpreis == Decimal("450.00")
    text = (r.finde_ordner(config.laden(), nummer) / preise.PRIVAT_DATEI).read_text(encoding="utf-8")
    assert "einzelpreis: 450.00" in text and "positionen_hash:" in text


def test_falsche_anzahl_preise(gewerbe):
    nummer = lege_an(gewerbe, preise_=None)
    with pytest.raises(preise.PreisFehler, match="1 Positionen, aber 2 Preise"):
        bestaetige(nummer, "1", "2")


def test_kaputte_privat_datei_ist_art_preise_ohne_wert(gewerbe):
    nummer = lege_an(gewerbe)
    ordner = r.finde_ordner(config.laden(), nummer)
    datei = ordner / preise.PRIVAT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8").replace("1000.00", "10x0"), encoding="utf-8")
    with pytest.raises(r.ResolveFehler) as info:
        r.entwurf(config.laden(), nummer)
    assert info.value.art == meldung.PREISE and "10x0" not in info.value.geschwaerzt


# ---------------------------------------------------------------- Referenz und Anrede


def test_referenz_aus_der_privat_datei_gewinnt_vor_der_kundendatei(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    assert r.resolve(config.laden(), nummer)[0].referenz == "Sample Panel 2026"   # Kundendatei
    preise.referenz_setzen(r.entwurf(config.laden(), nummer), "PO 4711")
    assert r.entwurf(config.laden(), nummer).preise == preise.BESTAETIGT          # bleibt bestätigt
    assert r.resolve(config.laden(), nummer)[0].referenz == "PO 4711"


def test_referenz_in_rechnung_yaml_wird_abgelehnt(gewerbe):
    nummer = lege_an(gewerbe, referenz="PO 4711")
    with pytest.raises(r.ResolveFehler, match="rechnung preise") as info:
        r.resolve(config.laden(), nummer)
    assert "4711" not in info.value.geschwaerzt


def test_anrede_aus_der_kundendatei_sonst_standard(gewerbe):
    assert r.resolve(config.laden(), lege_an(gewerbe, "sample-ltd"))[0].anrede == "Dear Jane Sample"
    assert r.resolve(config.laden(), lege_an(gewerbe, "exemple-sarl"))[0].anrede == "Dear Madam or Sir"
    assert r.resolve(config.laden(), lege_an(gewerbe, "muster-gmbh"))[0].anrede == "Sehr geehrte Damen und Herren"


# ---------------------------------------------------------------- CLI `rechnung preise` (ohne Schalter)


def test_preise_interaktiv_mit_vorschlag_und_eigenem_preis(gewerbe):
    zwei = EINE_POSITION + "  - kuerzel: bahnticket\n    menge: 1\n    einheit: pauschal\n"
    nummer = lege_an(gewerbe, "muster-gmbh", zwei, preise_=None)
    # Vortrag: Enter übernimmt 450.00, 7 % nein (Enter); Bahnticket: leer, 87,40, 7 % nein; Referenz; bestätigen.
    aus = CliRunner().invoke(app, ["preise", nummer], input="\n\n87,40\nn\nPO 12\nj\n")
    assert aus.exit_code == 0, aus.output
    assert "Einzelpreis [450.00]" in aus.output
    assert "Brutto     639,51 EUR" in aus.output                   # (450 + 87.40) * 1.19
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert [p.einzelpreis for p in ergebnis.positionen] == [Decimal("450.00"), Decimal("87.40")]
    assert ergebnis.referenz == "PO 12"


def test_preise_ohne_bestaetigung_aendert_nichts(gewerbe):
    nummer = lege_an(gewerbe, preise_=None)
    aus = CliRunner().invoke(app, ["preise", nummer], input="\n\nn\n")    # Preis, Referenz, nein
    assert aus.exit_code == 1 and "Nichts geändert" in aus.output
    assert r.entwurf(config.laden(), nummer).preise == preise.FEHLEN


def test_preise_fragt_sieben_prozent_nur_wo_erlaubt(gewerbe):
    recht = "  - kuerzel: nutzungsrecht\n    menge: 2\n    einheit: pauschal\n"
    inland = lege_an(gewerbe, "muster-gmbh", recht, preise_=None)
    aus = CliRunner().invoke(app, ["preise", inland], input="\n\n\nj\n")   # Preis, 7 % (Vorschlag ja), Referenz
    assert "7 % (ermäßigt" in aus.output, aus.output
    assert r.resolve(config.laden(), inland)[0].positionen[0].steuersatz == Decimal(7)
    ausland = lege_an(gewerbe, "sample-ltd", recht, preise_=None)
    aus = CliRunner().invoke(app, ["preise", ausland], input="\n\nj\n")
    assert "7 %" not in aus.output and aus.exit_code == 0, aus.output


def test_preise_aus_liste_verweigert_bei_auslagen(gewerbe):
    nummer = lege_an(gewerbe, positionen="  - kuerzel: flug\n    menge: 1\n    einheit: pauschal\n", preise_=None)
    aus = CliRunner().invoke(app, ["preise", nummer, "--aus-liste"])
    assert aus.exit_code == 1 and "Auslage" in aus.output
    nummer = lege_an(gewerbe, preise_=None)
    aus = CliRunner().invoke(app, ["preise", nummer, "--aus-liste", "--referenz", "PO 9"])
    assert aus.exit_code == 0, aus.output
    assert r.resolve(config.laden(), nummer)[0].referenz == "PO 9"


def test_resolve_ohne_preise_zeigt_den_entwurf(gewerbe):
    nummer = lege_an(gewerbe, positionen=EINE_POSITION + AUSLAGE, preise_=None)
    aus = CliRunner().invoke(app, ["resolve", nummer])
    assert aus.exit_code == 0, aus.output
    assert "Sample Ltd" in aus.output and f"rechnung preise {nummer}" in aus.output
    assert not (r.finde_ordner(config.laden(), nummer) / r.RESOLVED_DATEI).exists()


# ---------------------------------------------------------------- Anschreiben


def test_anschreiben_setzt_die_werte_ein(gewerbe):
    nummer = lege_an(gewerbe, "muster-gmbh")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    text = "[anrede],\nanbei Rechnung [nummer] über [brutto], zahlbar bis [faelligkeit].\n[name]\n"
    assert anschreiben.einsetzen(text, ergebnis) == (
        "Sehr geehrte Damen und Herren,\nanbei Rechnung 2026-0001 über 1.190,00 EUR, zahlbar bis 06.10.2026.\n"
        "Max Mustermann\n")


def test_anschreiben_englisch_und_mit_referenz(gewerbe):
    nummer = lege_an(gewerbe, "sample-ltd")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert anschreiben.einsetzen("[brutto] · [referenz] · [leistungsdatum] · [firma]", ergebnis) == (
        "EUR 1,000.00 · Sample Panel 2026 · 10 June 2026 · Sample Ltd")


def test_anschreiben_unbekannter_platzhalter_bricht_ab(gewerbe):
    with pytest.raises(anschreiben.AnschreibenFehler, match=r"\[iban\]"):
        anschreiben.platzhalter("Bitte auf [iban] überweisen")


def test_anschreiben_ohne_wert_bricht_ab(gewerbe):
    nummer = lege_an(gewerbe, "muster-gmbh")   # ohne Referenz in Kunden- und Privatdatei
    ergebnis, _ = r.resolve(config.laden(), nummer)
    with pytest.raises(anschreiben.AnschreibenFehler, match=r"Kein Wert für \[referenz\]"):
        anschreiben.einsetzen("Ihre Referenz: [referenz]", ergebnis)


def test_cli_anschreiben_verlangt_einen_aktuellen_bau(gewerbe):
    nummer = lege_an(gewerbe, "muster-gmbh")
    ordner = r.finde_ordner(config.laden(), nummer)
    (ordner / anschreiben.DATEI).write_text("Rechnung [nummer] über [brutto]\n", encoding="utf-8")
    aus = CliRunner().invoke(app, ["anschreiben", nummer])
    assert aus.exit_code == 1 and "erst `rechnung bauen" in aus.output
    r.resolve(config.laden(), nummer)
    aus = CliRunner().invoke(app, ["anschreiben", nummer])
    assert aus.exit_code == 0 and aus.output == f"Rechnung {nummer} über 1.190,00 EUR\n"
    bestaetige(nummer, "2000")                                    # Preise geändert, nicht neu gebaut
    assert CliRunner().invoke(app, ["anschreiben", nummer]).exit_code == 1


# ---------------------------------------------------------------- offen


def test_offen_listet_was_fehlt(gewerbe):
    fertig = lege_an(gewerbe)
    ohne_preise = lege_an(gewerbe, preise_=None)
    c = config.laden()
    ohne_datum, _ = r.neu(c, "sample-ltd", None, date(2026, 9, 22))
    aus = CliRunner().invoke(app, ["offen"])
    assert aus.exit_code == 0, aus.output
    assert f"{fertig}  bereit" in aus.output
    assert f"{ohne_preise}  Preise fehlen" in aus.output
    assert f"{ohne_datum.name}" in aus.output and "leistungsdatum fehlt" in aus.output


def test_resolved_json_traegt_kuerzel_und_privat_hash(gewerbe):
    nummer = lege_an(gewerbe)
    _, ziel = r.resolve(config.laden(), nummer)
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["positionen"][0]["kuerzel"] == "vortrag"
    assert daten["privat_hash"] == r.privat_hash(ziel.parent)
    assert daten["anrede"] == "Dear Jane Sample"
