"""Listenpreise ohne den Menschen (entscheidungen 2026-10-16), Demo-Betrieb, nächster Schritt.

- `resolve` und `bauen` füllen fehlende oder veraltete Preise aus der Liste, je Position: was der
  Mensch für eine unveränderte Position bestätigt hat, bleibt; Auslagen und Fremdwährung nicht.
- Jede Position trägt ihre Quelle; `festschreiben` weist auf übernommene hin.
- RECHNUNG_DEMO: nur stammdaten.example/, Beispielpreise für Auslagen, nie ein Ordner mit eigenen Stammdaten.
- `schritt.befehl()` je Startart, `schritt.naechster()` je Stand der Rechnung.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from typer.testing import CliRunner

from rechnung import config, meldung, preise, resolve as r, schritt
from rechnung.cli import app

from hilfen import bestaetige
from test_resolve import EINE_POSITION, gewerbe, lege_an  # noqa: F401 – Fixture

ZWEI = EINE_POSITION + "  - kuerzel: reisezeit\n    menge: 3\n    einheit: stunde\n"
AUSLAGE = EINE_POSITION + "  - kuerzel: bahnticket\n    menge: 1\n    einheit: pauschal\n"


def _privat(nummer: str):
    return r.lade_privat(r.finde_ordner(config.laden(), nummer))


def _ersetze(nummer: str, alt: str, neu: str) -> None:
    datei = r.finde_ordner(config.laden(), nummer) / r.INPUT_DATEI
    datei.write_text(datei.read_text(encoding="utf-8").replace(alt, neu), encoding="utf-8")


# ---------------------------------------------------------------- Übernahme


def test_resolve_uebernimmt_listenpreise_mit_quelle(gewerbe):
    nummer = lege_an(gewerbe, positionen=ZWEI, preise_=None)
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert [p.einzelpreis for p in ergebnis.positionen] == [Decimal("450.00"), Decimal("60.00")]
    privat = _privat(nummer)
    assert [p.quelle for p in privat.positionen] == [preise.LISTE, preise.LISTE]
    assert all(p.position for p in privat.positionen)
    text = (r.finde_ordner(config.laden(), nummer) / preise.PRIVAT_DATEI).read_text(encoding="utf-8")
    assert "quelle: liste" in text
    assert preise.stand_text(preise.BESTAETIGT, privat) == "aus der Preisliste übernommen (nicht einzeln bestätigt)"


def test_bestaetigter_preis_einer_unveraenderten_position_bleibt(gewerbe):
    nummer = lege_an(gewerbe, positionen=ZWEI, preise_=("999.00", "70.00"))
    _ersetze(nummer, "menge: 3", "menge: 4")          # nur die Reisezeit ändert sich
    assert r.entwurf(config.laden(), nummer).preise == preise.VERALTET
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert [p.einzelpreis for p in ergebnis.positionen] == [Decimal("999.00"), Decimal("60.00")]
    privat = _privat(nummer)
    assert [p.quelle for p in privat.positionen] == [preise.MENSCH, preise.LISTE]
    assert preise.stand_text(preise.BESTAETIGT, privat) == "bestätigt, 1 von 2 Positionen aus der Preisliste übernommen"


def test_bestaetigte_preise_bleiben_unangetastet(gewerbe):
    nummer = lege_an(gewerbe, preise_=("1000.00",))
    r.resolve(config.laden(), nummer)
    assert _privat(nummer).positionen[0].einzelpreis == Decimal("1000.00")
    assert _privat(nummer).positionen[0].quelle == preise.MENSCH


def test_auslage_bleibt_beim_menschen(gewerbe):
    nummer = lege_an(gewerbe, positionen=AUSLAGE, preise_=None)
    e = r.mit_listenpreisen(config.laden(), nummer)
    assert e.preise == preise.FEHLEN and not preise.liste_reicht(e)
    assert not (r.finde_ordner(config.laden(), nummer) / preise.PRIVAT_DATEI).exists()
    with pytest.raises(r.ResolveFehler) as info:
        r.resolve(config.laden(), nummer)
    assert info.value.art == meldung.PREISE


def test_fremdwaehrung_bleibt_beim_menschen(gewerbe):
    nummer = lege_an(gewerbe, "sample-inc", preise_=None)      # USD
    assert r.mit_listenpreisen(config.laden(), nummer).preise == preise.FEHLEN


def test_sieben_prozent_wie_die_liste_vorschlaegt(gewerbe):
    recht = "  - kuerzel: nutzungsrecht\n    menge: 1\n    einheit: pauschal\n"
    inland = lege_an(gewerbe, "muster-gmbh", recht, preise_=None)
    assert r.resolve(config.laden(), inland)[0].positionen[0].steuersatz == Decimal(7)
    ausland = lege_an(gewerbe, "sample-ltd", recht, preise_=None)
    assert r.resolve(config.laden(), ausland)[0].positionen[0].steuersatz == Decimal(0)


def test_festgeschriebene_rechnung_wird_nicht_gefuellt(gewerbe, monkeypatch):
    nummer = lege_an(gewerbe, preise_=None)
    monkeypatch.setattr(r.festschreiben, "ist_festgeschrieben", lambda ordner: True)
    assert r.mit_listenpreisen(config.laden(), nummer).preise == preise.FEHLEN


def test_cli_resolve_uebernimmt_und_sagt_es(gewerbe):
    nummer = lege_an(gewerbe, preise_=None)
    aus = CliRunner().invoke(app, ["resolve", nummer])
    assert aus.exit_code == 0, aus.output
    assert "aus der Preisliste übernommen" in aus.output and "450,00" in aus.output


def test_cli_preise_aus_liste_ist_quelle_liste_interaktiv_mensch(gewerbe):
    nummer = lege_an(gewerbe, preise_=None)
    assert CliRunner().invoke(app, ["preise", nummer, "--aus-liste"]).exit_code == 0
    assert _privat(nummer).positionen[0].quelle == preise.LISTE
    aus = CliRunner().invoke(app, ["preise", nummer], input="\n\nj\n")
    assert aus.exit_code == 0, aus.output
    assert _privat(nummer).positionen[0].quelle == preise.MENSCH


def test_alte_privat_datei_ohne_quelle_gilt_als_mensch(gewerbe):
    nummer = lege_an(gewerbe)
    datei = r.finde_ordner(config.laden(), nummer) / preise.PRIVAT_DATEI
    text = "\n".join(z for z in datei.read_text(encoding="utf-8").splitlines()
                     if "quelle:" not in z and "position:" not in z) + "\n"
    datei.write_text(text, encoding="utf-8")
    privat = _privat(nummer)
    assert privat.positionen[0].quelle == preise.MENSCH and r.entwurf(config.laden(), nummer).preise == preise.BESTAETIGT


# ---------------------------------------------------------------- Demo-Betrieb


def test_demo_nimmt_beispielpreis_fuer_auslagen(gewerbe, monkeypatch):
    nummer = lege_an(gewerbe, positionen=AUSLAGE, preise_=None)
    monkeypatch.setenv("RECHNUNG_DEMO", "1")
    ergebnis, _ = r.resolve(config.laden(), nummer)
    assert ergebnis.positionen[1].einzelpreis == Decimal("89.90")


def test_demo_nimmt_die_beispiel_stammdaten(gewerbe, monkeypatch):
    monkeypatch.setenv("RECHNUNG_DEMO", "1")
    cfg = config.laden()
    assert r.stammdaten_ordner(cfg) == config.BEISPIEL_STAMMDATEN
    assert r.kunden_ordner(cfg) == config.BEISPIEL_STAMMDATEN / "kunden"


def test_demo_verweigert_eigene_stammdaten(gewerbe, monkeypatch):
    ich = gewerbe / "stammdaten" / "ich.yaml"
    ich.write_text(ich.read_text(encoding="utf-8") + "# eigene Änderung\n", encoding="utf-8")
    monkeypatch.setenv("RECHNUNG_DEMO", "1")
    with pytest.raises(r.ResolveFehler) as info:
        r.lade_stammdaten(config.laden())
    assert info.value.art == meldung.STAMMDATEN and str(gewerbe) not in info.value.geschwaerzt


def test_demo_in_leerem_gewerbe_ordner(gewerbe, monkeypatch):
    (gewerbe / "stammdaten" / "ich.yaml").unlink()
    monkeypatch.setenv("RECHNUNG_DEMO", "1")
    assert r.lade_stammdaten(config.laden())


def test_ohne_demo_bleibt_der_beispielpreis_der_auslage_unbeachtet(gewerbe):
    nummer = lege_an(gewerbe, positionen=AUSLAGE, preise_=None)
    assert r.entwurf(config.laden(), nummer).positionen[1].vorschlag is None


# ---------------------------------------------------------------- Befehl je Startart


def test_befehl_im_container():
    text = schritt.befehl("preise 2026-0001", {"RECHNUNG_IM_CONTAINER": "1", "RECHNUNG_GEWERBE": "/gewerbe"})
    assert text == "docker run -it --rm -v <dein Gewerbe-Ordner>:/gewerbe rechnung preise 2026-0001"
    assert "/gewerbe rechnung" in text and "RECHNUNG_GEWERBE" not in text


def test_befehl_im_container_im_demo_betrieb():
    text = schritt.befehl("preise X", {"RECHNUNG_IM_CONTAINER": "1", "RECHNUNG_DEMO": "1"})
    assert "-e RECHNUNG_DEMO=1" in text


def test_befehl_auf_dem_host_ohne_echten_pfad(monkeypatch, tmp_path):
    monkeypatch.setattr(schritt, "_installiert", lambda: True)
    env = {"RECHNUNG_GEWERBE": str(tmp_path), "RECHNUNG_CONFIG": str(tmp_path / "c.toml")}
    text = schritt.befehl("preise X", env)
    assert str(tmp_path) not in text
    assert text == "RECHNUNG_CONFIG=<deine config.toml> RECHNUNG_GEWERBE=<dein Gewerbe-Ordner> rechnung preise X"
    assert schritt.befehl("preise X", {}) == "rechnung preise X"


def test_befehl_ohne_installiertes_rechnung(monkeypatch):
    monkeypatch.setattr(schritt, "_installiert", lambda: False)
    assert schritt.befehl("preise X", {}) == "uv --directory <repo> run rechnung preise X"


# ---------------------------------------------------------------- nächster Schritt


def test_naechster_schritt_je_stand(gewerbe, monkeypatch):
    from datetime import date

    monkeypatch.setattr(schritt, "_installiert", lambda: True)
    cfg = config.laden()
    ohne_datum, _ = r.neu(cfg, "sample-ltd", None, date(2026, 9, 22))
    assert schritt.naechster(cfg, ohne_datum) in (schritt.ABBRUCH[meldung.FRAGE], schritt.ABBRUCH[meldung.EINGABE])

    liste = lege_an(gewerbe, preise_=None)
    ordner = r.finde_ordner(cfg, liste)
    assert schritt.naechster(cfg, ordner).startswith(f"resolve({liste})")

    auslage = lege_an(gewerbe, positionen=AUSLAGE, preise_=None)
    text = schritt.naechster(cfg, r.finde_ordner(cfg, auslage))
    assert "Auslage" in text and f"rechnung preise {auslage}" in text
    assert "Formular" in schritt.naechster(cfg, r.finde_ordner(cfg, auslage), "Formular")

    r.resolve(cfg, liste)
    assert schritt.naechster(cfg, ordner).endswith(f"bauen({liste}).")
    (ordner / "invoice_" f"{liste}.pdf").write_bytes(b"%PDF")
    text = schritt.naechster(cfg, ordner)
    assert text.startswith(f"pruefen({liste})") and f"rechnung festschreiben {liste} --gesendet-am" in text

    monkeypatch.setattr(schritt.festschreiben, "ist_festgeschrieben", lambda o: True)
    assert schritt.naechster(cfg, ordner).startswith("Festgeschrieben")


def test_naechster_schritt_nennt_keinen_betrag_und_keinen_kunden(gewerbe):
    cfg = config.laden()
    nummer = lege_an(gewerbe, preise_=("1234.56",))
    text = schritt.naechster(cfg, r.finde_ordner(cfg, nummer))
    assert "1234" not in text and "Sample" not in text and "sample-ltd" not in text


def test_festschreiben_weist_auf_listenpreise_hin(gewerbe, monkeypatch):
    from rechnung import festschreiben

    nummer = lege_an(gewerbe, preise_=None)
    r.resolve(config.laden(), nummer)
    monkeypatch.setattr(festschreiben, "festschreiben",
                        lambda ordner, gesendet: {"gesendet_am": "2026-09-22", "festgeschrieben_am": "2026-09-22"})
    aus = CliRunner().invoke(app, ["festschreiben", nummer, "--gesendet-am", "2026-09-22"])
    assert aus.exit_code == 0, aus.output
    assert "1 von 1 Position(en) mit Preis aus der Preisliste" in aus.output


def test_hilfe_bestaetigt_als_mensch(gewerbe):
    nummer = lege_an(gewerbe, preise_=None)
    bestaetige(nummer)
    assert _privat(nummer).positionen[0].quelle == preise.MENSCH
