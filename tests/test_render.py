"""render: Formatierung, Maskierung, und der Bau selbst.

Die Bau-Tests brauchen LaTeX. Fehlt es, werden sie übersprungen statt rot – die reinen
Formatierungstests laufen überall.
"""

import shutil
from datetime import date
from decimal import Decimal

import pytest

from rechnung import config, render, resolve as r

BRAUCHT_LATEX = pytest.mark.skipif(
    shutil.which("latexmk") is None or shutil.which("pdflatex") is None,
    reason="latexmk oder pdflatex fehlt",
)

RECHNUNG = """\
kunde: {kunde}
datum: 2026-09-23
leistungsdatum: 2026-06-10
positionen:
{positionen}
"""

EINE_POSITION = """\
  - beschreibung: Teilnahme als Panelist
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


def lege_an(kunde="sample-ltd", positionen=EINE_POSITION, **extra) -> str:
    cfg = config.laden()
    ordner, nummer = r.neu(cfg, kunde, date(2026, 6, 10), date(2026, 9, 23))
    text = RECHNUNG.format(kunde=kunde, positionen=positionen)
    for schluessel, wert in extra.items():
        text += f"{schluessel}: {wert}\n"
    (ordner / r.INPUT_DATEI).write_text(text, encoding="utf-8")
    return nummer


# ---------------------------------------------------------------- Formatierung

@pytest.mark.parametrize(
    "roh, erwartet",
    [
        ("Beratung & Analyse", r"Beratung \& Analyse"),
        ("100 % Einsatz", r"100 \% Einsatz"),
        ("Datei_name", r"Datei\_name"),
        ("Rabatt #3", r"Rabatt \#3"),
        ("Kosten $ und {Klammern}", r"Kosten \$ und \{Klammern\}"),
        ("a\\b", r"a\textbackslash{}b"),
        ("Panel ~ London", r"Panel \textasciitilde{} London"),
        ("Umlaute äöü bleiben", "Umlaute äöü bleiben"),
    ],
)
def test_escape(roh, erwartet):
    assert render.escape(roh) == erwartet


def test_datum_je_sprache():
    assert render.datum(date(2026, 9, 23), "de") == "23.09.2026"
    assert render.datum(date(2026, 9, 23), "en") == "23 September 2026"
    assert render.datum(date(2026, 1, 5), "de") == "05.01.2026"


def test_zahl_hat_punkt_als_trenner():
    """Die Vorlage formatiert sprachabhängig – sie bekommt immer Punktnotation."""
    assert render.zahl(Decimal("1234.50")) == "1234.50"
    assert render.zahl(Decimal("0.00")) == "0.00"
    assert render.zahl(Decimal("19")) == "19"


@pytest.mark.parametrize(
    "einheit, menge, erwartet",
    [("pauschal", Decimal(1), "flat"), ("stunde", Decimal(1), "hour"), ("stunde", Decimal(8), "hours"),
     ("tag", Decimal("2.5"), "days"), ("stueck", Decimal(3), "each"), ("kilometer", Decimal(120), "km")],
)
def test_einheit_singular_und_plural(einheit, menge, erwartet):
    assert render.einheit(einheit, menge) == erwartet


def test_iban_wird_lesbar_gruppiert():
    assert render._iban_gruppiert("DE89370400440532013000") == "DE89 3704 0044 0532 0130 00"


# ---------------------------------------------------------------- Vorlage füllen

def test_kontext_enthaelt_alles_wichtige(gewerbe):
    nummer = lege_an("sample-ltd")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    k = render.kontext(ergebnis)
    assert k["sprache_latex"] == "english"
    assert k["empfaenger"][0] == "Sample Ltd"
    assert "United Kingdom" in k["empfaenger"]
    assert k["kunde_ustid"] == "GB123456789"
    assert k["kunde_register"] == "01234567 (Companies House)"
    assert k["positionen"][0]["einheit"] == "flat"
    assert k["netto"] == "1000.00"
    assert "Place of supply" in k["hinweis"]


def test_anschrift_ist_rein_postalisch(gewerbe):
    nummer = lege_an("sample-ltd")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    empfaenger = render.kontext(ergebnis)["empfaenger"]
    assert empfaenger == ["Sample Ltd", "Jane Sample", "1 Sample Street", "London EC1A 1AA",
                          "United Kingdom"]


def test_kunde_ohne_ustid_zeigt_den_registereintrag(gewerbe):
    nummer = lege_an("sample-inc")     # Delaware C-Corp, keine USt-IdNr.
    ergebnis, _ = r.resolve(config.laden(), nummer)
    k = render.kontext(ergebnis)
    assert k["kunde_ustid"] is None
    assert k["kunde_register"] == "1234567 (Delaware File Number)"
    assert not any("1234567" in z for z in k["empfaenger"])


def test_metadaten_in_drei_abschnitten(gewerbe, tmp_path):
    nummer = lege_an("sample-ltd", referenz="PO-4711")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    tex = render.baue_verzeichnis(ergebnis, tmp_path / "bau").read_text(encoding="utf-8")
    rechnung, unsere, ihre = tex.split("\\metasep")
    assert "\\InvStrNumberLabel" in rechnung and "\\InvStrDue" in rechnung
    assert "\\metarow{\\InvStrOurTaxNo}" in unsere and "\\metarow{\\InvStrOurVatId}" in unsere
    for zeile in ("\\metarow{\\InvStrReference}{PO-4711}",
                  "\\metarow{\\InvStrCustomerVatId}{GB123456789}",
                  "\\metarow{\\InvStrCustomerRegister}{01234567 (Companies House)}"):
        assert zeile in ihre


def test_ohne_kundendaten_kein_zweiter_strich(gewerbe, tmp_path):
    nummer = lege_an("privat-de")      # Privatperson: keine Referenz, USt-IdNr., Register
    ergebnis, _ = r.resolve(config.laden(), nummer)
    tex = render.baue_verzeichnis(ergebnis, tmp_path / "bau").read_text(encoding="utf-8")
    assert tex.count("\\metasep") == 1


@BRAUCHT_LATEX
def test_labels_sagen_wessen_daten_es_sind(gewerbe):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext fehlt")
    import subprocess

    nummer = lege_an("muster-gmbh")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    pdf = render.baue_pdf(ergebnis, r.finde_ordner(config.laden(), nummer))
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    for label in ("Unsere St.-Nr.", "Unsere USt-IdNr.", "Ihre USt-IdNr.", "Ihre Register-Nr."):
        assert label in text, f"fehlt im PDF: {label}"
    # Nummer zuerst, das Register in Klammern dahinter (darf umbrechen)
    assert text.index("HRB 123456") < text.index("(Handelsregister")


def test_tex_wird_vollstaendig_gefuellt(gewerbe, tmp_path):
    nummer = lege_an("muster-gmbh")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    bau = tmp_path / "bau"
    tex = render.baue_verzeichnis(ergebnis, bau)

    inhalt = tex.read_text(encoding="utf-8")
    assert r"\VAR{" not in inhalt and r"\BLOCK{" not in inhalt
    assert r"\InvoiceLanguage}{ngerman" in inhalt
    assert (bau / "style" / "invoice.sty").is_file()

    issuer = (bau / "include" / "issuer.tex").read_text(encoding="utf-8")
    assert "Max Mustermann" in issuer
    assert "DE89 3704 0044 0532 0130 00" in issuer   # gruppiert, nicht am Stück


def test_fehlender_beleg_sagt_was_zu_tun_ist(gewerbe, tmp_path):
    nummer = lege_an("sample-ltd", belege="[flug.pdf]")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    ordner = r.finde_ordner(config.laden(), nummer)
    with pytest.raises(render.RenderFehler, match="Beleg fehlt"):
        render.baue_verzeichnis(ergebnis, tmp_path / "bau", belege_quelle=ordner / "belege")


# ---------------------------------------------------------------- Bauen

@BRAUCHT_LATEX
def test_bauen_erzeugt_pdf_und_sonst_nichts(gewerbe):
    nummer = lege_an("sample-ltd")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    ordner = r.finde_ordner(config.laden(), nummer)

    pdf = render.baue_pdf(ergebnis, ordner)

    assert pdf.is_file() and pdf.stat().st_size > 10_000
    # Im Rechnungsordner liegen nur yaml, resolved.json, pdf und belege/ – kein .tex, .aux, .log.
    inhalt = sorted(p.name for p in ordner.iterdir())
    assert inhalt == ["belege", "rechnung.pdf", "rechnung.resolved.json", "rechnung.yaml"]


@BRAUCHT_LATEX
def test_pdf_enthaelt_die_pflichtangaben(gewerbe):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext fehlt")
    import subprocess

    nummer = lege_an("sample-ltd")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    ordner = r.finde_ordner(config.laden(), nummer)
    pdf = render.baue_pdf(ergebnis, ordner)
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout

    for pflicht in [nummer, "Max Mustermann", "Musterstraße 1", "Sample Ltd", "1 Sample Street",
                    "143/123/12345", "Teilnahme als Panelist", "1,000.00", "Place of supply"]:
        assert pflicht in text, f"fehlt im PDF: {pflicht}"


@BRAUCHT_LATEX
def test_deutsche_rechnung_mit_umsatzsteuer(gewerbe):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext fehlt")
    import subprocess

    nummer = lege_an("muster-gmbh")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    ordner = r.finde_ordner(config.laden(), nummer)
    pdf = render.baue_pdf(ergebnis, ordner)
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout

    assert "Rechnung Nr." in text
    assert "Umsatzsteuer 19" in text
    assert "1.190,00 EUR" in text      # deutsche Zahlenschreibweise
    assert "Seite" not in text          # einseitig: keine Seitenzahl


@BRAUCHT_LATEX
def test_lange_referenz_bricht_um_statt_aus_der_seite_zu_laufen(gewerbe):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext fehlt")
    import re
    import subprocess

    lang = "Sample Policy Forum 2026, Panel Future of Work, Purchase Order PO-2026-000123-LONDON"
    nummer = lege_an("sample-ltd", referenz=f'"{lang}"')
    ergebnis, _ = r.resolve(config.laden(), nummer)
    pdf = render.baue_pdf(ergebnis, r.finde_ordner(config.laden(), nummer))
    bbox = subprocess.run(["pdftotext", "-bbox", "-f", "1", "-l", "1", str(pdf), "-"],
                          capture_output=True, text=True).stdout
    breite = float(re.search(r'<page width="([\d.]+)"', bbox).group(1))
    rand = breite - 25 / 25.4 * 72            # rechter Satzspiegelrand: 25 mm
    woerter = re.findall(r'xMax="([\d.]+)"[^>]*>([^<]+)</word>', bbox)
    assert any("LONDON" in w for _, w in woerter), "Referenz fehlt im PDF"
    # 3 pt Toleranz: microtype lässt Satzzeichen bewusst ein wenig in den Rand hängen.
    zu_weit = [(w, float(x)) for x, w in woerter if float(x) > rand + 3]
    assert not zu_weit, f"läuft über den rechten Rand ({rand:.1f} pt): {zu_weit}"
