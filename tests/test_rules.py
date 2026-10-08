"""Jede Regel aus rules.py hat hier einen Test."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from rechnung import rules
from rechnung.models import Adresse, Kunde


def kunde(land: str, ustid: str | None = None, unternehmer: bool | None = None) -> Kunde:
    return Kunde(
        kuerzel="test",
        firma="Test",
        adresse=Adresse(strasse="Weg 1", plz="1", ort="Ort"),
        land=land,
        ustid=ustid,
        unternehmer=unternehmer,
    )


# ---------------------------------------------------------------- Steuerfall

@pytest.mark.parametrize(
    "land, ustid, unternehmer, erwartet",
    [
        ("DE", "DE123", True, "A"),      # Inland, Unternehmen
        ("DE", None, False, "A"),        # Inland, Privatperson
        ("FR", "FR123", True, "B"),      # EU mit USt-IdNr.
        ("AT", "ATU123", None, "B"),     # USt-IdNr. genügt
        ("FR", None, True, "D"),         # EU ohne USt-IdNr. -> nicht B
        ("GB", None, True, "C"),         # Drittland, Unternehmer
        ("US", None, True, "C"),         # Delaware C-Corp
        ("CH", None, False, "D"),        # Drittland, Privatperson
        ("CH", None, None, "D"),         # Unternehmereigenschaft unbekannt
    ],
)
def test_steuerfall(land, ustid, unternehmer, erwartet):
    assert rules.steuerfall(kunde(land, ustid, unternehmer)) == erwartet


def test_gb_ist_drittland():
    assert "GB" not in rules.EU_LAENDER


def test_steuersatz_folgt_aus_dem_fall():
    assert rules.steuersatz("A") == Decimal(19)
    assert rules.steuersatz("B") == Decimal(0)
    assert rules.steuersatz("C") == Decimal(0)
    assert rules.steuersatz("D") == Decimal(19)


def test_fall_d_erklaerung_nennt_den_weg_heraus():
    eu = rules.fall_d_erklaerung(kunde("FR", None, True))
    assert "ustid" in eu and "Fall B" in eu
    drittland = rules.fall_d_erklaerung(kunde("CH", None, False))
    assert "unternehmer: true" in drittland and "Fall C" in drittland
    assert "begruendung" in drittland


# ---------------------------------------------------------------- Hinweistexte

def test_hinweis_a_und_d_haben_keinen_text():
    assert rules.hinweis("A", "DE", "de") is None
    assert rules.hinweis("D", "CH", "de") is None


def test_hinweis_b_reverse_charge():
    de = rules.hinweis("B", "FR", "de")["de"]
    assert "Steuerschuldnerschaft des Leistungsempfängers" in de   # Wortlaut nach § 14a Abs. 5 UStG
    assert "Art. 196" in de
    en = rules.hinweis("B", "FR", "en")["en"]
    assert "Reverse charge" in en and "Art. 196" in en


def test_hinweis_c_nennt_den_leistungsort():
    de = rules.hinweis("C", "GB", "de")["de"]
    assert "Leistungsort: Vereinigtes Königreich" in de
    assert "§ 3a Abs. 2 UStG" in de
    assert "Place of supply: United Kingdom" in rules.hinweis("C", "GB", "en")["en"]
    assert "Vereinigte Staaten" in rules.hinweis("C", "US", "de")["de"]
    assert "United States" in rules.hinweis("C", "US", "en")["en"]


def test_hinweis_hat_genau_eine_sprache():
    """Eine Sprache je Rechnung – die Vorlage setzt keine zweisprachigen Labels."""
    assert set(rules.hinweis("C", "US", "de")) == {"de"}
    assert set(rules.hinweis("C", "US", "en")) == {"en"}


def test_unbekanntes_land_sagt_was_zu_tun_ist():
    with pytest.raises(rules.RegelFehler, match="LAENDER"):
        rules.hinweis("C", "XX", "de")


def test_jedes_eu_land_hat_einen_namen():
    assert rules.EU_LAENDER <= set(rules.LAENDER)


# ---------------------------------------------------------------- Fälligkeit, Rundung

def test_faelligkeit():
    assert rules.faelligkeit(date(2026, 9, 22), 14) == date(2026, 10, 6)
    assert rules.faelligkeit(date(2026, 12, 28), 14) == date(2027, 1, 11)
    with pytest.raises(rules.RegelFehler):
        rules.faelligkeit(date(2026, 9, 22), -1)


@pytest.mark.parametrize(
    "roh, erwartet",
    [("1.005", "1.01"), ("1.004", "1.00"), ("2.675", "2.68"), ("-1.005", "-1.01"), ("0.005", "0.01")],
)
def test_runden_ist_kaufmaennisch(roh, erwartet):
    assert rules.runde(Decimal(roh)) == Decimal(erwartet)


# ---------------------------------------------------------------- Nummer

@pytest.mark.parametrize(
    "roh, erwartet",
    [("0", "0.00"), ("0.0", "0.00"), ("287.30", "287.30"), ("33.335", "33.335"), ("1500", "1500.00")],
)
def test_mindestens_zwei_nachkommastellen(roh, erwartet):
    assert str(rules.mindestens_zwei(Decimal(roh))) == erwartet


def test_nummer_format():
    assert rules.nummer("{jahr}-{lfd:04d}", 2026, 1) == "2026-0001"
    assert rules.nummer("MM-{jahr}-{lfd:04d}", 2026, 42) == "MM-2026-0042"


def test_nummer_format_kaputt():
    with rules_fehler():
        rules.nummer("{unbekannt}-{lfd:04d}", 2026, 1)


def rules_fehler():
    return pytest.raises(rules.RegelFehler)


def test_naechste_lfd_bei_leerem_jahr(tmp_path: Path):
    assert rules.naechste_lfd(tmp_path / "2026") == 1
    (tmp_path / "2026").mkdir()
    assert rules.naechste_lfd(tmp_path / "2026") == 1


def test_naechste_lfd_zaehlt_hoechste_weiter(tmp_path: Path):
    jahr = tmp_path / "2026"
    for name in ["2026-0001", "2026-0002", "2026-0007"]:
        (jahr / name).mkdir(parents=True)
    (jahr / "notiz.txt").write_text("keine Rechnung", encoding="utf-8")
    assert rules.naechste_lfd(jahr) == 8


def test_naechste_lfd_ignoriert_das_praefix(tmp_path: Path):
    """Formatwechsel mitten im Jahr zählt weiter, statt wieder bei 1 zu beginnen."""
    jahr = tmp_path / "2026"
    (jahr / "2026-0003").mkdir(parents=True)
    (jahr / "MM-2026-0004").mkdir()
    assert rules.naechste_lfd(jahr) == 5


# ---------------------------------------------------------------- Währung

def test_fremdwaehrung_ohne_ust_ist_erlaubt():
    rules.waehrung_erlaubt("USD", [Decimal(0), Decimal(0)])
    rules.waehrung_erlaubt("EUR", [Decimal(19)])


def test_fremdwaehrung_mit_ust_bricht_ab():
    with pytest.raises(rules.RegelFehler, match="Euro"):
        rules.waehrung_erlaubt("USD", [Decimal(19)])
