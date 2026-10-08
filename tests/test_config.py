from pathlib import Path

import pytest

from rechnung import config


def schreibe(pfad: Path, text: str) -> Path:
    pfad.write_text(text, encoding="utf-8")
    return pfad


def test_ohne_config_ist_demo(tmp_path):
    cfg = config.laden(env={}, pfad=tmp_path / "fehlt.toml")
    assert cfg.demo
    assert cfg.quelle is None
    assert cfg.engine == "pdflatex"
    assert cfg.zahlungsziel_tage == 14
    assert cfg.ausgang == "rechnung-ausgang"


def test_config_datei_wird_gelesen(tmp_path):
    datei = schreibe(tmp_path / "c.toml", f'gewerbe = "{tmp_path}"\nausgang = "Rechnungen - Ausgang"\nzahlungsziel_tage = 30\n')
    cfg = config.laden(env={}, pfad=datei)
    assert cfg.gewerbe == tmp_path
    assert cfg.ausgang == "Rechnungen - Ausgang"
    assert cfg.zahlungsziel_tage == 30
    assert cfg.quelle == datei
    assert cfg.ordner("ausgang") == tmp_path / "Rechnungen - Ausgang"


def test_env_gewinnt_ueber_datei(tmp_path):
    datei = schreibe(tmp_path / "c.toml", 'gewerbe = "/datei"\nengine = "lualatex"\nzahlungsziel_tage = 30\n')
    env = {"RECHNUNG_GEWERBE": "/gewerbe", "RECHNUNG_ENGINE": "xelatex", "RECHNUNG_ZAHLUNGSZIEL_TAGE": "7"}
    cfg = config.laden(env=env, pfad=datei)
    assert cfg.gewerbe == Path("/gewerbe")
    assert cfg.engine == "xelatex"
    assert cfg.zahlungsziel_tage == 7
    assert cfg.aus_env == {"gewerbe", "engine", "zahlungsziel_tage"}


def test_jede_option_hat_eine_env_variable(tmp_path):
    env = {
        "RECHNUNG_GEWERBE": "/g",
        "RECHNUNG_STAMMDATEN": "sd",
        "RECHNUNG_KUNDEN": "sd/k",
        "RECHNUNG_AUSGANG": "aus",
        "RECHNUNG_STEUERBERATER": "stb",
        "RECHNUNG_ENGINE": "xelatex",
        "RECHNUNG_NUMMER_FORMAT": "X-{jahr}-{lfd:04d}",
        "RECHNUNG_ZAHLUNGSZIEL_TAGE": "21",
        "RECHNUNG_SPRACHE": "en",
        "RECHNUNG_WAEHRUNG": "GBP",
        "RECHNUNG_VORLAGE": "/v",
    }
    assert {k.removeprefix("RECHNUNG_").lower() for k in env} == set(config.DEFAULTS)
    cfg = config.laden(env=env, pfad=tmp_path / "fehlt.toml")
    assert (cfg.stammdaten, cfg.kunden, cfg.ausgang, cfg.steuerberater) == ("sd", "sd/k", "aus", "stb")
    assert cfg.sprache == "en"
    assert cfg.waehrung == "GBP"
    assert cfg.nummer_format == "X-{jahr}-{lfd:04d}"
    assert cfg.vorlage == Path("/v")


def test_config_pfad_aus_env(tmp_path):
    assert config.config_pfad({"RECHNUNG_CONFIG": str(tmp_path / "x.toml")}) == tmp_path / "x.toml"
    assert config.config_pfad({"XDG_CONFIG_HOME": "/xdg"}) == Path("/xdg/rechnung/config.toml")


@pytest.mark.parametrize(
    "inhalt",
    ['engine = "pdftex"\n', 'waehrung = "CHF"\n', 'nummer_format = "{jahr}"\n', 'sprache = "fr"\n', 'sprache = "de+en"\n', 'zahlungsziel_tage = "bald"\n', 'unbekannt = 1\n', "kaputt ="],
)
def test_ungueltige_config(tmp_path, inhalt):
    with pytest.raises(config.ConfigFehler):
        config.laden(env={}, pfad=schreibe(tmp_path / "c.toml", inhalt))


def test_beispiel_config_ist_gueltig():
    cfg = config.laden(env={}, pfad=config.REPO / "config.toml.example")
    assert set(config.DEFAULTS) <= set(vars(cfg))


def test_init_legt_nur_die_vier_ordner_an(tmp_path):
    fremd = tmp_path / "Gewerbeanmeldung"
    fremd.mkdir()
    (fremd / "notiz.txt").write_text("bleibt", encoding="utf-8")
    cfg = config.laden(env={"RECHNUNG_GEWERBE": str(tmp_path), "RECHNUNG_AUSGANG": "Rechnungen - Ausgang"},
                       pfad=tmp_path / "fehlt.toml")

    ergebnis = config.init(cfg)

    assert all(neu for _, neu in ergebnis)
    alles = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert alles == [
        "Gewerbeanmeldung",
        "Gewerbeanmeldung/notiz.txt",
        "Rechnungen - Ausgang",
        "stammdaten",
        "stammdaten/kunden",
        "steuerberater",
    ]
    assert (fremd / "notiz.txt").read_text(encoding="utf-8") == "bleibt"


def test_init_ist_idempotent(tmp_path):
    cfg = config.laden(env={"RECHNUNG_GEWERBE": str(tmp_path)}, pfad=tmp_path / "fehlt.toml")
    config.init(cfg)
    (tmp_path / "stammdaten" / "kunden" / "x.yaml").write_text("firma: X\n", encoding="utf-8")
    assert not any(neu for _, neu in config.init(cfg))
    assert (tmp_path / "stammdaten" / "kunden" / "x.yaml").exists()


def test_init_ohne_gewerbe_oder_mit_fehlender_wurzel(tmp_path):
    with pytest.raises(config.ConfigFehler):
        config.init(config.laden(env={}, pfad=tmp_path / "fehlt.toml"))
    with pytest.raises(config.ConfigFehler):
        config.init(config.laden(env={"RECHNUNG_GEWERBE": str(tmp_path / "gibtsnicht")}, pfad=tmp_path / "fehlt.toml"))
    assert not (tmp_path / "gibtsnicht").exists()
