"""Eigener Vorlagen-Ordner: Überlagerung beim Build, Nachweis in resolved.json, doctor-Hinweise."""

import json
import re
import shutil
from datetime import date

import pytest

from rechnung import config, doctor, render, resolve as r, vorlage

BRAUCHT_LATEX = pytest.mark.skipif(
    shutil.which("latexmk") is None or shutil.which("pdflatex") is None,
    reason="latexmk oder pdflatex fehlt",
)

# Die Stellschrauben, die es gab, als der Vorlagen-Ordner kam. Jede spätere braucht einen
# Standardwert in invoice.sty – sonst bricht eine ältere eigene defaults.sty den Build.
GRUNDBESTAND = {
    "Farbe Accent", "Farbe InkMain", "Farbe InkSoft", "Farbe PaperBg", "Farbe RuleGrey",
    r"\CurrencyCodeFont", r"\CurrencyLocale", r"\CurrencyStyle",
    r"\InvoiceAmountFormat", r"\InvoiceFont", r"\InvoiceFootSkip", r"\InvoiceFooterSize",
    r"\InvoiceFrameTop", r"\InvoiceHeadingSize", r"\InvoiceItemSep", r"\InvoiceLabelSize",
    r"\InvoiceLetterheadLinesTop", r"\InvoiceLetterheadSize", r"\InvoiceLetterheadTop",
    r"\InvoiceListIndent", r"\InvoiceMarginBottom", r"\InvoiceMarginLeft", r"\InvoiceMarginRight",
    r"\InvoiceMarginTop", r"\InvoiceMetaSepSkip", r"\InvoiceMetaWidth", r"\InvoiceParSkip",
    r"\InvoiceQtyFormat", r"\InvoiceRecipientTop", r"\InvoiceRecipientWidth", r"\InvoiceRuleHair",
    r"\InvoiceRuleHeavy", r"\InvoiceRuleLight", r"\InvoiceRunningSize", r"\InvoiceSenderLineSize",
    r"\InvoiceSenderLineSkip", r"\InvoiceSmallSize", r"\InvoiceTabColSep", r"\InvoiceTableHeadSize",
    r"\InvoiceTableSize", r"\InvoiceTableStretch", r"\TemplateName", r"\TemplateVersion",
    r"\ifInvoiceAttachmentStamp", r"\ifInvoiceClosing", r"\ifInvoiceNoSignatureLine",
}

RECHNUNG = """\
kunde: sample-ltd
datum: 2026-09-23
leistungsdatum: 2026-06-10
leistung:
  taetigkeit: Teilnahme als Panelist
  einordnung: sonstige
positionen:
  - beschreibung: Teilnahme als Panelist
    menge: 1
    einheit: pauschal
    einzelpreis: 1000.00
"""


@pytest.fixture
def gewerbe(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHNUNG_CONFIG", str(tmp_path / "fehlt.toml"))
    monkeypatch.setenv("RECHNUNG_GEWERBE", str(tmp_path / "gewerbe"))
    monkeypatch.delenv("RECHNUNG_VORLAGE", raising=False)
    shutil.copytree(config.BEISPIEL_STAMMDATEN, tmp_path / "gewerbe" / "stammdaten")
    config.init(config.laden())
    return tmp_path / "gewerbe"


@pytest.fixture
def eigene(tmp_path, monkeypatch):
    """Ein eigener Vorlagen-Ordner mit einer Kopie der Standard-defaults.sty."""
    ordner = tmp_path / "meine-vorlage"
    (ordner / "style").mkdir(parents=True)
    shutil.copy2(vorlage.STANDARD / "style" / "defaults.sty", ordner / "style" / "defaults.sty")
    monkeypatch.setenv("RECHNUNG_VORLAGE", str(ordner))
    return ordner


def lege_an() -> str:
    cfg = config.laden()
    ordner, nummer = r.neu(cfg, "sample-ltd", date(2026, 6, 10), date(2026, 9, 23))
    (ordner / r.INPUT_DATEI).write_text(RECHNUNG, encoding="utf-8")
    return nummer


def akzent_rot(ordner):
    datei = ordner / "style" / "defaults.sty"
    datei.write_text(
        datei.read_text(encoding="utf-8").replace("{Accent}{HTML}{000000}", "{Accent}{HTML}{C00000}"),
        encoding="utf-8")


# ---------------------------------------------------------------- Stellschrauben

def test_stellschrauben_ignoriert_kommentare():
    text = "\\newcommand{\\A}{1}  % \\newcommand{\\B}{2}\n% \\definecolor{C}{HTML}{000000}\n\\newif\\ifD\n"
    assert vorlage.stellschrauben(text) == {r"\A", r"\ifD"}


def test_jede_neue_stellschraube_hat_einen_standardwert_in_invoice_sty():
    standard = vorlage.stellschrauben((vorlage.STANDARD / "style" / "defaults.sty").read_text(encoding="utf-8"))
    mechanik = (vorlage.STANDARD / "style" / "invoice.sty").read_text(encoding="utf-8")
    ohne = []
    for name in sorted(standard - GRUNDBESTAND):
        if name.startswith("Farbe "):
            muster = r"\\@ifundefinedcolor\{" + re.escape(name[6:]) + r"\}"
        elif name.startswith(r"\if"):
            muster = r"\\ifdefined" + re.escape(name)
        else:
            muster = r"\\providecommand\*?\{" + re.escape(name) + r"\}"
        if not re.search(muster, mechanik):
            ohne.append(name)
    assert not ohne, f"Standardwert in invoice.sty fehlt für: {ohne}"


def test_fehlende_stellschrauben(eigene):
    datei = eigene / "style" / "defaults.sty"
    datei.write_text(
        "\n".join(z for z in datei.read_text(encoding="utf-8").splitlines() if "InvoiceTabColSep" not in z),
        encoding="utf-8")
    assert vorlage.fehlende_stellschrauben(eigene) == [r"\InvoiceTabColSep"]


# ---------------------------------------------------------------- Config und Dateien

def test_config_vorlage_aus_env_und_toml(tmp_path, monkeypatch):
    monkeypatch.delenv("RECHNUNG_VORLAGE", raising=False)
    toml = tmp_path / "config.toml"
    toml.write_text('vorlage = "~/meine-vorlage"\n', encoding="utf-8")
    cfg = config.laden(env={}, pfad=toml)
    assert cfg.vorlage == config.Path("~/meine-vorlage").expanduser()
    cfg = config.laden(env={"RECHNUNG_VORLAGE": str(tmp_path)}, pfad=toml)
    assert cfg.vorlage == tmp_path
    assert config.laden(env={}, pfad=tmp_path / "fehlt.toml").vorlage is None


def test_eigene_dateien_ohne_versteckte(eigene):
    (eigene / ".DS_Store").write_text("x")
    (eigene / ".git").mkdir()
    (eigene / ".git" / "HEAD").write_text("x")
    (eigene / "include").mkdir()
    (eigene / "include" / "logo.pdf").write_bytes(b"%PDF")
    assert vorlage.eigene_dateien(eigene) == ["include/logo.pdf", "style/defaults.sty"]


def test_fehlender_ordner_ist_ein_fehler(tmp_path):
    with pytest.raises(vorlage.VorlageFehler, match="existiert nicht"):
        vorlage.eigene_dateien(tmp_path / "gibt-es-nicht")


# ---------------------------------------------------------------- Build

def test_eigene_dateien_ersetzen_und_ergaenzen(gewerbe, eigene, tmp_path):
    akzent_rot(eigene)
    (eigene / "include").mkdir()
    (eigene / "include" / "logo.pdf").write_bytes(b"%PDF")
    nummer = lege_an()
    ergebnis, _ = r.resolve(config.laden(), nummer)
    bau = tmp_path / "bau"
    render.baue_verzeichnis(ergebnis, bau, eigene=eigene)
    assert "C00000" in (bau / "style" / "defaults.sty").read_text(encoding="utf-8")
    assert (bau / "include" / "logo.pdf").read_bytes() == b"%PDF"
    # Alles andere kommt weiter aus der Standardvorlage.
    assert (bau / "style" / "invoice.sty").read_bytes() == (vorlage.STANDARD / "style" / "invoice.sty").read_bytes()
    assert (bau / "include" / "currency.tex").is_file()


def test_eigene_jinja_vorlage_gewinnt(gewerbe, eigene, tmp_path):
    text = (vorlage.STANDARD / "rechnung.tex.j2").read_text(encoding="utf-8")
    (eigene / "rechnung.tex.j2").write_text("% EIGENES GERUEST\n" + text, encoding="utf-8")
    nummer = lege_an()
    ergebnis, _ = r.resolve(config.laden(), nummer)
    tex = render.baue_verzeichnis(ergebnis, tmp_path / "bau", eigene=eigene)
    assert tex.read_text(encoding="utf-8").startswith("% EIGENES GERUEST")
    assert not (tmp_path / "bau" / "rechnung.tex.j2").exists()


def test_ohne_eigenen_ordner_wie_bisher(gewerbe, tmp_path):
    nummer = lege_an()
    ergebnis, ziel = r.resolve(config.laden(), nummer)
    assert json.loads(ziel.read_text(encoding="utf-8"))["vorlage_eigen"] is None
    bau = tmp_path / "bau"
    render.baue_verzeichnis(ergebnis, bau)
    assert (bau / "style" / "defaults.sty").read_bytes() == (vorlage.STANDARD / "style" / "defaults.sty").read_bytes()


# ---------------------------------------------------------------- Nachweis

def test_resolved_json_haelt_eigene_dateien_fest(gewerbe, eigene):
    nummer = lege_an()
    _, ziel = r.resolve(config.laden(), nummer)
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert list(daten["vorlage_eigen"]) == ["style/defaults.sty"]
    assert re.fullmatch(r"[0-9a-f]{64}", daten["vorlage_eigen"]["style/defaults.sty"])


def test_bau_verweigert_geaenderte_vorlage_nach_resolve(gewerbe, eigene):
    nummer = lege_an()
    ergebnis, ziel = r.resolve(config.laden(), nummer)
    akzent_rot(eigene)
    with pytest.raises(render.RenderFehler, match="seit dem Auflösen geändert"):
        render.baue_pdf(ergebnis, ziel.parent, eigene=eigene)


@BRAUCHT_LATEX
def test_pdf_mit_eigener_vorlage(gewerbe, eigene):
    akzent_rot(eigene)
    nummer = lege_an()
    cfg = config.laden()
    ergebnis, ziel = r.resolve(cfg, nummer)
    pdf = render.baue_pdf(ergebnis, ziel.parent, cfg.engine, eigene=cfg.vorlage)
    assert pdf.is_file()
    assert ergebnis.vorlage_eigen is not None
    # Nur PDF und resolved.json kommen zurück, nichts aus dem eigenen Ordner.
    assert not list(ziel.parent.glob("*.sty"))


# ---------------------------------------------------------------- doctor

def test_doctor_standardvorlage(tmp_path):
    cfg = config.laden(env={}, pfad=tmp_path / "fehlt.toml")
    [p] = doctor.pruefe_vorlage(cfg)
    assert (p.status, p.detail) == (doctor.OK, "Standardvorlage")


def test_doctor_fehlender_ordner(tmp_path):
    cfg = config.laden(env={"RECHNUNG_VORLAGE": str(tmp_path / "weg")}, pfad=tmp_path / "fehlt.toml")
    [p] = doctor.pruefe_vorlage(cfg)
    assert p.status == doctor.FEHLER


def test_doctor_meldet_ersetzt_zusaetzlich_wirkungslos_und_fehlende(eigene, tmp_path):
    (eigene / "include").mkdir()
    (eigene / "include" / "logo.pdf").write_bytes(b"%PDF")
    (eigene / "include" / "issuer.tex").write_text("x")
    datei = eigene / "style" / "defaults.sty"
    datei.write_text(
        "\n".join(z for z in datei.read_text(encoding="utf-8").splitlines() if "InvoiceItemSep" not in z),
        encoding="utf-8")
    cfg = config.laden(env={"RECHNUNG_VORLAGE": str(eigene)}, pfad=tmp_path / "fehlt.toml")
    uebersicht, wirkungslos, defaults = doctor.pruefe_vorlage(cfg)
    assert uebersicht.status == doctor.OK
    assert "ersetzt: style/defaults.sty" in uebersicht.detail
    assert "zusätzlich: include/logo.pdf" in uebersicht.detail
    assert wirkungslos.status == doctor.WARNUNG and "include/issuer.tex" in wirkungslos.detail
    assert defaults.status == doctor.WARNUNG and r"\InvoiceItemSep" in defaults.detail


def test_doctor_aktuelle_defaults(eigene, tmp_path):
    cfg = config.laden(env={"RECHNUNG_VORLAGE": str(eigene)}, pfad=tmp_path / "fehlt.toml")
    _, defaults = doctor.pruefe_vorlage(cfg)
    assert defaults.status == doctor.OK
