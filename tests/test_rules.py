"""Jede Regel aus rules.py hat hier einen Test."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from rechnung import rules
from rechnung.models import Adresse, Bank, Kunde, Leistung, Stammdaten


def kunde(land: str, ustid: str | None = None, unternehmer: bool | None = None) -> Kunde:
    return Kunde(
        kuerzel="test",
        firma="Test",
        adresse=Adresse(strasse="Weg 1", plz="1", ort="Ort"),
        land=land,
        ustid=ustid,
        unternehmer=unternehmer,
    )


# ---------------------------------------------------------------- Einordnung (RULES.md Teil 4)

def test_einordnungen_passen_zum_modell():
    from typing import get_args
    from rechnung.models import TAETIGKEITEN, Einordnung
    assert set(rules.EINORDNUNGEN) == set(get_args(Einordnung))
    assert {w for w, (g, _) in rules.EINORDNUNGEN.items() if g == rules.TAETIGKEIT} == set(TAETIGKEITEN)


def test_einordnungen_stehen_in_rules_md():
    text = (Path(__file__).parent.parent / "RULES.md").read_text(encoding="utf-8")
    for wort in rules.EINORDNUNGEN:
        assert f"| `{wort}` |" in text, wort


def test_katalog_nr_6_und_11_bis_13_fehlen_bewusst():
    nummern = {f.rsplit("Nr. ", 1)[1].split()[0] for _, f in rules.EINORDNUNGEN.values() if "Abs. 4" in f}
    assert nummern == {"1", "2", "3", "4", "5", "7", "8", "9", "10", "14"}


# ---------------------------------------------------------------- Leistungsort und Ergebnis

def ich(ustid: str | None = "DE123456789") -> Stammdaten:
    return Stammdaten(
        name="Max Mustermann", adresse=Adresse(strasse="Weg 1", plz="1", ort="Ort"), email="a@b.c",
        steuernummer="1/2/3", ustid=ustid, bank=Bank(kontoinhaber="M", iban="DE89370400440532013000"),
    )


def leistung(einordnung: str = "sonstige", ort: str | None = None) -> Leistung:
    return Leistung(taetigkeit="Test", einordnung=einordnung, ort=ort)


@pytest.mark.parametrize(
    "land, ustid, unternehmer, einordnung, ort, erwartet_ort, ergebnis, regel",
    [
        # Unternehmer: immer Sitz des Kunden (R3), gleich welche Einordnung
        ("DE", "DE1", True, "beratung", None, "DE", "inland", "R3"),
        ("FR", "FR1", True, "unterrichtend", "DE", "FR", "reverse_charge", "R3"),
        ("AT", "ATU1", True, "sonstige", None, "AT", "reverse_charge", "R3"),
        ("GB", None, True, "sonstige", None, "GB", "nicht_steuerbar", "R3"),
        ("US", None, True, "beratung", None, "US", "nicht_steuerbar", "R3"),
        # Privatperson, Grundregel (R4)
        ("DE", None, False, "sonstige", None, "DE", "inland", "R4"),
        ("FR", None, False, "sonstige", None, "DE", "inland", "R4"),
        ("CH", None, False, "sonstige", None, "DE", "inland", "R4"),
        # Privatperson, Katalog: Drittland -> Wohnsitz (R7), sonst Inland (R8)
        ("CH", None, False, "beratung", None, "CH", "nicht_steuerbar", "R7"),
        ("US", None, False, "datenverarbeitung", None, "US", "nicht_steuerbar", "R7"),
        ("FR", None, False, "beratung", None, "DE", "inland", "R8"),
        ("DE", None, False, "werbung", None, "DE", "inland", "R8"),
        # Privatperson, Tätigkeit: Ort der Tätigkeit (R5), online Wohnsitz (R6)
        ("DE", None, False, "unterrichtend", "DE", "DE", "inland", "R5"),
        ("DE", None, False, "unterrichtend", "CH", "CH", "nicht_steuerbar", "R5"),
        ("CH", None, False, "kuenstlerisch", "DE", "DE", "inland", "R5"),
        ("CH", None, False, "unterrichtend", "online", "CH", "nicht_steuerbar", "R6"),
        ("DE", None, False, "unterhaltend", "online", "DE", "inland", "R6"),
    ],
)
def test_entscheidungstabelle(land, ustid, unternehmer, einordnung, ort, erwartet_ort, ergebnis, regel):
    e = rules.entscheide(kunde(land, ustid, unternehmer), leistung(einordnung, ort), ich())
    assert (e.ort.land, e.ergebnis) == (erwartet_ort, ergebnis)
    assert regel in e.regeln
    assert e.satz == (Decimal(19) if ergebnis == "inland" else Decimal(0))


@pytest.mark.parametrize(
    "land, ustid, unternehmer, einordnung, ort, meldung",
    [
        ("CH", None, None, "sonstige", None, "unternehmer"),           # R19
        ("DE", None, None, "beratung", None, "unternehmer"),           # R19 auch im Inland
        ("AT", "ATU1", None, "sonstige", None, "unternehmer"),         # USt-IdNr. ersetzt die Angabe nicht
        ("FR", None, None, "sonstige", None, "ustid"),                 # R19, Hinweis auf USt-IdNr.
        ("DE", None, None, "unterrichtend", "CH", "unternehmer"),      # Tätigkeit braucht den Status
        ("FR", None, True, "sonstige", None, "ustid"),                 # R29: EU-Unternehmer ohne USt-IdNr.
        ("DE", None, False, "unterrichtend", "FR", "R18"),             # Workshop in Paris für Privatleute
        ("FR", None, False, "unterrichtend", "online", "R18"),
    ],
)
def test_abbruch_statt_falscher_entscheidung(land, ustid, unternehmer, einordnung, ort, meldung):
    with pytest.raises(rules.RegelFehler, match=meldung):
        rules.entscheide(kunde(land, ustid, unternehmer), leistung(einordnung, ort), ich())


def test_reverse_charge_braucht_die_eigene_ustid():
    with pytest.raises(rules.RegelFehler, match="Eigene USt-IdNr."):
        rules.entscheide(kunde("FR", "FR1", True), leistung(), ich(ustid=None))


def test_festgelegter_leistungsort_geht_durch_dieselben_regeln():
    e = rules.entscheide(kunde("FR", "FR1", True), leistung(), ich(), festgelegt="CH")
    assert (e.ort.land, e.ergebnis, e.ort.regeln) == ("CH", "nicht_steuerbar", ("R37",))
    with pytest.raises(rules.RegelFehler, match="R18"):
        rules.entscheide(kunde("CH", None, False), leistung(), ich(), festgelegt="FR")
    # Status unbekannt: als Unternehmer wäre es Reverse Charge, also fehlt eine Angabe (R19), nicht R18.
    with pytest.raises(rules.RegelFehler, match="unternehmer"):
        rules.entscheide(kunde("CH", None, None), leistung(), ich(), festgelegt="FR")


def test_aussteller_ausserhalb_deutschlands_bricht_ab():
    at = ich().model_copy(update={"land": "AT"})
    with pytest.raises(rules.RegelFehler, match="R4"):
        rules.entscheide(kunde("DE", None, False), leistung(), at)


@pytest.mark.parametrize(
    "land, ustid, unternehmer, einordnung, ort, ergebnis, regeln",
    [
        ("DE", "DE1", True, "beratung", None, "kleinunternehmer", {"R13", "R14", "R16"}),
        ("CH", None, False, "sonstige", None, "kleinunternehmer", {"R4", "R13", "R14", "R16"}),
        ("FR", None, True, "beratung", None, "reverse_charge", {"R14", "R15", "R28"}),   # ohne USt-IdNr.
        ("FR", "FR1", True, "beratung", None, "reverse_charge", {"R14", "R15", "R28"}),
        ("US", None, True, "beratung", None, "nicht_steuerbar", {"R14", "R17", "R31"}),
        ("DE", None, False, "unterrichtend", "CH", "nicht_steuerbar", {"R5", "R14", "R17", "R31"}),
    ],
)
def test_kleinunternehmer(land, ustid, unternehmer, einordnung, ort, ergebnis, regeln):
    ku = ich(ustid=None).model_copy(update={"kleinunternehmer": True})   # oft ohne USt-IdNr.
    e = rules.entscheide(kunde(land, ustid, unternehmer), leistung(einordnung, ort), ku)
    assert e.ergebnis == ergebnis
    assert e.satz == Decimal(0)                       # R14: nie ein Steuerausweis
    assert regeln <= set(e.regeln)
    assert "R10" not in e.regeln and "R29" not in e.regeln


def test_kleinunternehmer_hinweis():
    ku = ich().model_copy(update={"kleinunternehmer": True})
    e = rules.entscheide(kunde("DE", None, False), leistung(), ku)
    assert rules.hinweis(e, "de") == {"de": "Steuerfrei als Leistung eines Kleinunternehmers (§ 19 Abs. 1 UStG)."}
    assert "small business exemption" in rules.hinweis(e, "en")["en"]


def test_kleinunternehmer_auch_mit_festgelegtem_leistungsort_ohne_steuer():
    ku = ich().model_copy(update={"kleinunternehmer": True})
    e = rules.entscheide(kunde("FR", "FR1", True), leistung(), ku, festgelegt="DE")
    assert (e.ergebnis, e.satz) == ("kleinunternehmer", Decimal(0))


def test_gb_ist_drittland():
    assert "GB" not in rules.EU_LAENDER
    assert rules.kategorie("GB") == rules.DRITTLAND
    assert rules.kategorie("FR") == rules.EU
    assert rules.kategorie("DE") == rules.INLAND


# Prüfliste der EU-Mitgliedstaaten, Stand 2026-10-10, unabhängig von rules.EU_LAENDER abgetippt.
# Ändert sich die EU, beide nachziehen. Griechenland: ISO-Code GR (EL ist nur das USt-IdNr.-Präfix).
EU_2026 = set("AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split())


def test_laendercodes_bilden_gebiete():
    """R1: Die Lean-Aussagen gelten für jede Länderzuordnung mit genau einer Kategorie je Land und
    genau einem Inland (`Gebiete`, inland_eindeutig). rules.py ist eine solche Zuordnung."""
    kategorien = {land: rules.kategorie(land) for land in rules.LAENDER}
    assert set(kategorien.values()) <= set(KATEGORIEN)
    assert [land for land, k in kategorien.items() if k == rules.INLAND] == ["DE"]


def test_eu_liste():
    """R1: genau die 27 Mitgliedstaaten; nur sie sind EU (außer DE, dem Inland)."""
    assert rules.EU_LAENDER == EU_2026 and len(EU_2026) == 27
    assert "EL" not in rules.EU_LAENDER
    for land in rules.LAENDER:
        assert (rules.kategorie(land) == rules.EU) == (land in EU_2026 - {"DE"}), land


@pytest.mark.parametrize("land", ["GB", "CH", "NO", "IS", "LI", "TR"])
def test_bekannte_fallen_sind_drittland(land):
    """Vereinigtes Königreich seit 2021; EWR und EFTA sind nicht Gemeinschaftsgebiet."""
    assert rules.kategorie(land) == rules.DRITTLAND


@pytest.mark.parametrize(
    "leistung_bis, frist",
    [(date(2026, 6, 10), date(2026, 7, 15)), (date(2026, 12, 31), date(2027, 1, 15))],
)
def test_frist_reverse_charge(leistung_bis, frist):
    assert rules.frist_reverse_charge(leistung_bis) == frist


# ---------------------------------------------------------------- Hinweistexte

def hinweis(land, ustid, unternehmer, einordnung="sonstige", ort=None, sprache="de"):
    e = rules.entscheide(kunde(land, ustid, unternehmer), leistung(einordnung, ort), ich())
    return rules.hinweis(e, sprache)


def test_hinweis_inland_hat_keinen_text():
    assert hinweis("DE", None, True) is None
    assert hinweis("CH", None, False) is None


def test_hinweis_reverse_charge():
    de = hinweis("FR", "FR1", True)["de"]
    assert "Steuerschuldnerschaft des Leistungsempfängers" in de   # Wortlaut nach § 14a Abs. 1 UStG
    assert "§ 14a Abs. 1 UStG" in de and "Art. 196" in de
    en = hinweis("FR", "FR1", True, sprache="en")["en"]
    assert "Reverse charge" in en and "Art. 196" in en and "§ 14a (1)" in en


def test_hinweis_nicht_steuerbar_nennt_den_leistungsort():
    de = hinweis("GB", None, True)["de"]
    assert de == ("Leistungsort: Vereinigtes Königreich. Die Leistung ist in Deutschland nicht "
                  "steuerbar (§ 3a Abs. 2 UStG).")
    # Die englische Fassung bleibt wörtlich gleich.
    assert hinweis("GB", None, True, sprache="en")["en"] == (
        "Place of supply: United Kingdom. Not subject to German VAT; the reverse charge may apply "
        "in the recipient's country.")
    assert "Vereinigte Staaten" in hinweis("US", None, True)["de"]


def test_hinweis_privatperson_ohne_reverse_charge_nachsatz():
    en = hinweis("CH", None, False, "unterrichtend", "CH", sprache="en")["en"]
    assert en == "Place of supply: Switzerland. Not subject to German VAT."
    de = hinweis("CH", None, False, "beratung")["de"]
    assert "Leistungsort: Schweiz" in de and "(§ 3a Abs. 4 UStG)" in de
    assert "(§ 3a Abs. 3 Nr. 3 UStG)" in hinweis("DE", None, False, "unterrichtend", "CH")["de"]


def test_hinweis_hat_genau_eine_sprache():
    """Eine Sprache je Rechnung – die Vorlage setzt keine zweisprachigen Labels."""
    assert set(hinweis("US", None, True)) == {"de"}
    assert set(hinweis("US", None, True, sprache="en")) == {"en"}


def test_unbekanntes_land_sagt_was_zu_tun_ist():
    with pytest.raises(rules.RegelFehler, match="LAENDER"):
        hinweis("XX", None, True)


@pytest.mark.parametrize("land", ["EL", "XX", "UK"])
def test_unbekannter_laendercode_wird_nicht_als_drittland_geraten(land):
    """R1: Ein Code außerhalb von LAENDER bricht ab – auch wo das Ergebnis nicht vom Land abhinge
    (Privatperson, Grundregel: Leistungsort Inland) und wo er nur Ort oder Festlegung ist."""
    with pytest.raises(rules.RegelFehler, match="LAENDER"):
        rules.kategorie(land)
    with pytest.raises(rules.RegelFehler, match="LAENDER"):
        rules.entscheide(kunde(land, None, False), leistung(), ich())
    with pytest.raises(rules.RegelFehler, match="LAENDER"):
        rules.entscheide(kunde("DE", None, False), leistung("unterrichtend", land), ich())
    with pytest.raises(rules.RegelFehler, match="LAENDER"):
        rules.entscheide(kunde("DE", None, True), leistung(), ich(), festgelegt=land)


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


# ---------------------------------------------------------------- Entscheidungskern, vollständig
#
# Die Menge aller Merkmale ist endlich. Diese Tests laufen über jede Kombination und prüfen
# Eigenschaften, die RULES.md verspricht. Die Garantie kommt aus dem Abgleich mit dem bewiesenen
# Lean-Modell (tests/test_abgleich.py); diese Tests sind eine zweite, von Lean unabhängige Sicht und
# sagen bei einer Änderung an rules.py, welche Regel verletzt ist. `ALLE` nutzt auch der Abgleich.

import itertools
import re

KATEGORIEN = (rules.INLAND, rules.EU, rules.DRITTLAND)
RULES_MD = (Path(__file__).parent.parent / "RULES.md").read_text(encoding="utf-8")
AKTIVE_REGELN = {
    m.group(1) for m in re.finditer(r"^#### (R\d+) – (?!\(entfallen\))", RULES_MD, flags=re.M)
}


def alle_merkmale():
    for kunde, unternehmer, kunde_ustid, gruppe, ku, eigene, inland, festgelegt in itertools.product(
        KATEGORIEN, (True, False, None), (True, False), (rules.TAETIGKEIT, rules.KATALOG, rules.GRUNDREGEL),
        (True, False), (True, False), (True, False), (None, *KATEGORIEN),
    ):
        orte = (*KATEGORIEN, "online") if gruppe == rules.TAETIGKEIT else (None,)
        for ort in orte:
            yield rules.Merkmale(kunde, unternehmer, kunde_ustid, gruppe, ort, ku, eigene, inland, festgelegt)


ALLE = list(alle_merkmale())


def test_kern_ist_total():
    """Jede Kombination ergibt genau eine Entscheidung oder einen begründeten Abbruch."""
    assert len(ALLE) == 3 * 3 * 2 * (4 + 1 + 1) * 2 * 2 * 2 * 4 == 3456
    for m in ALLE:
        k = rules.kern(m)
        assert isinstance(k, (rules.KernErgebnis, rules.Abbruch)), m
        if isinstance(k, rules.Abbruch):
            assert k.regel in {"R4", "R18", "R19", "R29"}, m


def test_kern_aussteller_im_ausland_bricht_immer_ab():
    """R4: genau dann, wenn der Aussteller nicht im Inland sitzt."""
    for m in ALLE:
        k = rules.kern(m)
        assert (isinstance(k, rules.Abbruch) and k.regel == "R4") == (not m.aussteller_inland), m


def test_kern_r19_genau_wenn_unternehmer_fehlt():
    """R19: `unternehmer` ist Pflicht; das Werkzeug rät den Status nie."""
    for m in ALLE:
        if m.aussteller_inland:
            k = rules.kern(m)
            assert (isinstance(k, rules.Abbruch) and k.regel == "R19") == (m.unternehmer is None), m


def test_kern_r18_nur_bei_privatpersonen():
    """R18 heißt: Privatperson. Ist der Status unbekannt, ist der Grund R19 – auch bei Festlegung."""
    for m in ALLE:
        k = rules.kern(m)
        if isinstance(k, rules.Abbruch) and k.regel == "R18":
            assert m.unternehmer is False, m


@pytest.mark.parametrize(
    "satz, ku, ermaessigt, erwartet",
    [(19, False, False, 19), (19, False, True, 7), (0, False, False, 0), (0, True, False, 0),
     (0, False, True, "R12"), (0, True, True, "R14")],
)
def test_satz_position(satz, ku, ermaessigt, erwartet):
    s = rules.satz_position(satz, ku, ermaessigt)
    assert (s.regel if isinstance(s, rules.Abbruch) else s) == erwartet


def test_kern_satz_und_ergebnis_passen_zum_leistungsort():
    for m in ALLE:
        k = rules.kern(m)
        if isinstance(k, rules.Abbruch):
            continue
        erwartet = {
            rules.INLAND: "kleinunternehmer" if m.kleinunternehmer else "inland",
            rules.EU: "reverse_charge",
            rules.DRITTLAND: "nicht_steuerbar",
        }[k.ort]
        assert k.ergebnis == erwartet, m                              # R2, R10, R11, R13
        assert (k.satz == 19) == (k.ergebnis == "inland"), m          # R12, R14
        if m.festgelegt is not None:
            assert k.ort == m.festgelegt and k.ort_quelle == rules.ORT_FESTGELEGT, m   # R37


def test_kern_unternehmer_immer_sitz_des_kunden():
    """R3: bei Unternehmern ist die Einordnung gleichgültig."""
    for m in ALLE:
        if m.unternehmer and m.festgelegt is None:
            k = rules.kern(m)
            if isinstance(k, rules.KernErgebnis):
                assert (k.ort, k.ort_quelle) == (m.kunde, rules.ORT_KUNDE), m


def test_kern_kleinunternehmer_weist_nie_steuer_aus():
    """R14, auch bei festgelegtem Leistungsort."""
    for m in ALLE:
        k = rules.kern(m)
        if m.kleinunternehmer and isinstance(k, rules.KernErgebnis):
            assert k.satz == 0 and "R14" in k.regeln, m


def test_kern_nennt_nur_regeln_aus_rules_md():
    for m in ALLE:
        k = rules.kern(m)
        regeln = (k.regel,) if isinstance(k, rules.Abbruch) else k.regeln
        assert set(regeln) <= AKTIVE_REGELN, (m, set(regeln) - AKTIVE_REGELN)


def test_jede_regel_id_im_code_steht_in_rules_md():
    """Der Code verweist nur auf Regeln, die es in RULES.md gibt und die nicht entfallen sind."""
    quelle = Path(rules.__file__).parent
    for datei in ("rules.py", "resolve.py", "models.py"):
        ids = set(re.findall(r"\bR(\d+)\b", (quelle / datei).read_text(encoding="utf-8")))
        fehlend = {f"R{i}" for i in ids} - AKTIVE_REGELN
        assert not fehlend, (datei, fehlend)
