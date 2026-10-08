"""pruefen: Die Pflichtangaben müssen im Text der fertigen PDF stehen.

Der wichtigste Test ist der rote: Wenn ein Feld aus der Vorlage verschwindet, muss die Prüfung
das merken. Ein Prüfer, der immer grün ist, prüft nichts.
"""

import shutil
from datetime import date
from decimal import Decimal

import pytest

from rechnung import config, pruefen, render, resolve as r

BRAUCHT_LATEX = pytest.mark.skipif(
    shutil.which("latexmk") is None or shutil.which("pdftotext") is None,
    reason="latexmk oder pdftotext fehlt",
)

RECHNUNG = """\
kunde: {kunde}
datum: 2026-09-23
leistungsdatum: 2026-06-10
leistung:
  taetigkeit: Teilnahme als Panelist
  einordnung: sonstige
positionen:
  - beschreibung: {beschreibung}
    menge: 1
    einheit: pauschal
    einzelpreis: 1000.00
"""


@pytest.fixture
def gewerbe(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path))
    shutil.copytree(config.BEISPIEL_STAMMDATEN, tmp_path / "stammdaten")
    config.init(config.laden())
    return tmp_path


def baue(kunde="sample-ltd", beschreibung="Teilnahme als Panelist"):
    cfg = config.laden()
    ordner, nummer = r.neu(cfg, kunde, date(2026, 6, 10), date(2026, 9, 23))
    (ordner / r.INPUT_DATEI).write_text(
        RECHNUNG.format(kunde=kunde, beschreibung=beschreibung), encoding="utf-8")
    ergebnis, _ = r.resolve(cfg, nummer)
    pdf = render.baue_pdf(ergebnis, ordner, cfg.engine)
    return ergebnis, pdf


# ---------------------------------------------------------------- Textvergleich

@pytest.mark.parametrize(
    "roh, gesucht",
    [
        ("Teilnahme als\nPanelist", "Teilnahme als Panelist"),          # Zeilenumbruch
        ("Teilnah-\nme als Panelist", "Teilnahme als Panelist"),        # Silbentrennung
        ("Flug FRA–LON", "Flug FRA--LON"),                              # Gedankenstrich
        ("Betrag  1.234,00   EUR", "Betrag 1.234,00 EUR"),              # Mehrfach-Leerzeichen
        ("Panelist London", "Panelist London"),                    # geschütztes Leerzeichen
    ],
)
def test_normalisierung_verhindert_fehlalarme(roh, gesucht):
    assert pruefen.enthaelt(pruefen.normalisiere(roh), gesucht)


def test_normalisierung_ist_nicht_blind():
    """Sie darf Umbrüche glätten, aber keine fehlenden Angaben durchwinken."""
    text = pruefen.normalisiere("Rechnung 2026-0001 über 100,00 EUR")
    assert not pruefen.enthaelt(text, "2026-0002")
    assert not pruefen.enthaelt(text, "200,00 EUR")


def test_geld_folgt_der_sprache():
    assert pruefen.geld(Decimal("1428.00"), "EUR", "de") == "1.428,00 EUR"
    assert pruefen.geld(Decimal("1428.00"), "EUR", "en") == "EUR 1,428.00"
    assert pruefen.geld(Decimal("0.00"), "USD", "en") == "USD 0.00"


# ---------------------------------------------------------------- Gegen echte PDFs

@BRAUCHT_LATEX
@pytest.mark.parametrize("kunde", ["muster-gmbh", "exemple-sarl", "sample-ltd", "sample-inc"])
def test_jede_rechnung_besteht_die_pruefung(gewerbe, kunde):
    ergebnis, pdf = baue(kunde)
    fehlend = [b.angabe for b in pruefen.pruefe(ergebnis, pdf) if not b.gefunden]
    assert not fehlend


@BRAUCHT_LATEX
def test_reverse_charge_verlangt_beide_ustidnr(gewerbe):
    ergebnis, pdf = baue("exemple-sarl")
    angaben = {b.angabe for b in pruefen.pruefe(ergebnis, pdf)}
    assert "USt-IdNr. des Kunden (Reverse Charge)" in angaben
    assert "USt-IdNr. des Ausstellers (Reverse Charge)" in angaben


@BRAUCHT_LATEX
def test_kleinunternehmer_ohne_steuerzeile_mit_hinweis(gewerbe):
    ich = gewerbe / "stammdaten" / "ich.yaml"
    ich.write_text(ich.read_text(encoding="utf-8") + "kleinunternehmer: true\n", encoding="utf-8")
    ergebnis, pdf = baue("muster-gmbh")
    assert ergebnis.ergebnis == "kleinunternehmer"
    befunde = pruefen.pruefe(ergebnis, pdf)
    assert all(b.gefunden for b in befunde)
    assert "Hinweis auf Steuerbefreiung / Nichtsteuerbarkeit" in {b.angabe for b in befunde}
    text = pruefen.normalisiere(pruefen.pdf_text(pdf))
    assert "Umsatzsteuer" not in text and "Nettobetrag" not in text   # Entgelt in einer Summe


@BRAUCHT_LATEX
def test_fehlende_steuernummer_wird_rot(gewerbe, monkeypatch):
    """Die Steuernummer aus der Vorlage entfernen – die Prüfung muss das melden.

    Dieselbe Probe lässt sich von Hand machen.
    """
    ergebnis, pdf = baue("muster-gmbh")
    assert all(b.gefunden for b in pruefen.pruefe(ergebnis, pdf))

    # Vorlage kopieren und beide Kennungen daraus entfernen. Eine allein zu löschen genügt
    # nicht: § 14 Abs. 4 Nr. 2 UStG verlangt Steuernummer ODER USt-IdNr., und die Prüfung
    # bildet dieses Oder ab.
    kaputt = gewerbe / "kaputte-vorlage"
    shutil.copytree(render.VORLAGE, kaputt)
    issuer = kaputt / "issuer.tex.j2"
    issuer.write_text(
        issuer.read_text(encoding="utf-8")
        .replace(r"\VAR{steuernummer}", "")
        .replace(r"\VAR{ustid}", ""),
        encoding="utf-8")
    monkeypatch.setattr(render, "VORLAGE", kaputt)

    ordner = pdf.parent
    neu_pdf = render.baue_pdf(ergebnis, ordner, config.laden().engine)
    befunde = pruefen.pruefe(ergebnis, neu_pdf)
    fehlend = [b.angabe for b in befunde if not b.gefunden]
    assert fehlend == ["Steuernummer oder USt-IdNr."] or "Steuernummer oder USt-IdNr." in fehlend


@BRAUCHT_LATEX
def test_meldung_nennt_den_gesuchten_text(gewerbe):
    ergebnis, pdf = baue("sample-ltd")
    befunde = pruefen.pruefe(ergebnis, pdf)
    nummer = next(b for b in befunde if b.angabe == "Rechnungsnummer")
    assert nummer.gesucht == ergebnis.nummer
    assert nummer.paragraf.startswith("§ 14")


def test_fehlendes_pdf_sagt_was_zu_tun_ist(tmp_path):
    with pytest.raises(pruefen.PruefFehler, match="rechnung bauen"):
        pruefen.pdf_text(tmp_path / "rechnung.pdf")
