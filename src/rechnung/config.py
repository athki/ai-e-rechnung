"""Konfiguration: config.toml plus Umgebungsvariablen RECHNUNG_<OPTION> (Env gewinnt).

Ohne Gewerbe-Wurzel (weder Config noch RECHNUNG_GEWERBE) läuft das Werkzeug im Demo-Modus
gegen stammdaten.example/ im Repo.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BEISPIEL_STAMMDATEN = REPO / "stammdaten.example"

ENGINES = ("pdflatex", "lualatex", "xelatex")
SPRACHEN = ("de", "en")
WAEHRUNGEN = ("EUR", "USD", "GBP")

# Option -> Default. Jede Option ist auch als RECHNUNG_<OPTION> setzbar.
DEFAULTS: dict[str, object] = {
    "gewerbe": None,
    "stammdaten": "stammdaten",
    "kunden": "stammdaten/kunden",
    "ausgang": "rechnung-ausgang",
    "steuerberater": "steuerberater",
    "engine": "pdflatex",
    "nummer_format": "{jahr}-{lfd:04d}",
    "zahlungsziel_tage": 14,
    "sprache": "de",
    "waehrung": "EUR",
    "vorlage": None,
}

# Die Unterordner, die dem Werkzeug gehören. Nur diese legt `init` an.
UNTERORDNER = ("stammdaten", "kunden", "ausgang", "steuerberater")


class ConfigFehler(Exception):
    pass


def config_pfad(env: dict[str, str] | None = None) -> Path:
    """RECHNUNG_CONFIG, sonst $XDG_CONFIG_HOME/rechnung/config.toml, sonst ~/.config/…"""
    env = os.environ if env is None else env
    if env.get("RECHNUNG_CONFIG"):
        return Path(env["RECHNUNG_CONFIG"]).expanduser()
    basis = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else Path.home() / ".config"
    return basis / "rechnung" / "config.toml"


def sperrliste_pfad(env: dict[str, str] | None = None) -> Path:
    """Sperrliste des Commit-Wächters: RECHNUNG_SPERRLISTE, sonst sperrliste.txt neben der Config.

    Dieselbe Regel steht in .githooks/sperrliste.py, das ohne dieses Paket laufen muss;
    tests/test_sperrliste.py hält beide gleich.
    """
    env = os.environ if env is None else env
    if env.get("RECHNUNG_SPERRLISTE"):
        return Path(env["RECHNUNG_SPERRLISTE"]).expanduser()
    return config_pfad(env).parent / "sperrliste.txt"


@dataclass(frozen=True)
class Config:
    gewerbe: Path | None
    stammdaten: str
    kunden: str
    ausgang: str
    steuerberater: str
    engine: str
    nummer_format: str
    zahlungsziel_tage: int
    sprache: str
    waehrung: str
    vorlage: Path | None = None  # eigener Vorlagen-Ordner; None = nur die Standardvorlage
    quelle: Path | None = None  # geladene config.toml, falls vorhanden
    aus_env: frozenset[str] = field(default_factory=frozenset)

    @property
    def demo(self) -> bool:
        return self.gewerbe is None

    def ordner(self, name: str) -> Path:
        """Absoluter Pfad eines Werkzeug-Unterordners unter der Gewerbe-Wurzel."""
        if name not in UNTERORDNER:
            raise KeyError(name)
        if self.gewerbe is None:
            raise ConfigFehler("Keine Gewerbe-Wurzel konfiguriert (Demo-Modus).")
        return self.gewerbe / getattr(self, name)


def laden(env: dict[str, str] | None = None, pfad: Path | None = None) -> Config:
    env = os.environ if env is None else env
    pfad = pfad or config_pfad(env)

    werte = dict(DEFAULTS)
    quelle = None
    if pfad.is_file():
        try:
            daten = tomllib.loads(pfad.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise ConfigFehler(f"{pfad}: {e}") from e
        unbekannt = set(daten) - set(DEFAULTS)
        if unbekannt:
            raise ConfigFehler(f"{pfad}: unbekannte Option(en): {', '.join(sorted(unbekannt))}")
        werte.update(daten)
        quelle = pfad

    aus_env = set()
    for option in DEFAULTS:
        wert = env.get(f"RECHNUNG_{option.upper()}")
        if wert is not None and wert != "":
            werte[option] = wert
            aus_env.add(option)

    try:
        tage = int(werte["zahlungsziel_tage"])
    except (TypeError, ValueError) as e:
        raise ConfigFehler(f"zahlungsziel_tage muss eine ganze Zahl sein, ist {werte['zahlungsziel_tage']!r}") from e
    if werte["engine"] not in ENGINES:
        raise ConfigFehler(f"engine muss eine von {ENGINES} sein, ist {werte['engine']!r}")
    if werte["sprache"] not in SPRACHEN:
        raise ConfigFehler(f"sprache muss eine von {SPRACHEN} sein, ist {werte['sprache']!r}")
    if werte["waehrung"] not in WAEHRUNGEN:
        raise ConfigFehler(f"waehrung muss eine von {WAEHRUNGEN} sein, ist {werte['waehrung']!r}")
    format_ = str(werte["nummer_format"])
    if "{lfd" not in format_ or "{jahr" not in format_:
        raise ConfigFehler(
            f"nummer_format braucht die Platzhalter {{jahr}} und {{lfd}}, ist {format_!r}"
        )

    gewerbe = Path(str(werte["gewerbe"])).expanduser() if werte["gewerbe"] else None
    vorlage = Path(str(werte["vorlage"])).expanduser() if werte["vorlage"] else None
    return Config(
        gewerbe=gewerbe,
        stammdaten=str(werte["stammdaten"]),
        kunden=str(werte["kunden"]),
        ausgang=str(werte["ausgang"]),
        steuerberater=str(werte["steuerberater"]),
        engine=str(werte["engine"]),
        nummer_format=format_,
        zahlungsziel_tage=tage,
        sprache=str(werte["sprache"]),
        waehrung=str(werte["waehrung"]),
        vorlage=vorlage,
        quelle=quelle,
        aus_env=frozenset(aus_env),
    )


def init(cfg: Config) -> list[tuple[Path, bool]]:
    """Legt die Werkzeug-Unterordner an, falls sie fehlen. Rührt sonst nichts an.

    Gibt (Pfad, neu_angelegt) je Ordner zurück.
    """
    if cfg.gewerbe is None:
        raise ConfigFehler("Keine Gewerbe-Wurzel konfiguriert: `gewerbe` in config.toml oder RECHNUNG_GEWERBE setzen.")
    if not cfg.gewerbe.is_dir():
        raise ConfigFehler(f"Gewerbe-Wurzel existiert nicht: {cfg.gewerbe}")
    ergebnis = []
    for name in UNTERORDNER:
        ziel = cfg.ordner(name)
        neu = not ziel.exists()
        if neu:
            ziel.mkdir(parents=True)
        elif not ziel.is_dir():
            raise ConfigFehler(f"{ziel} existiert, ist aber kein Ordner.")
        ergebnis.append((ziel, neu))
    return ergebnis


STAMMDATEN_GERUEST = """\
# Aussteller – deine Stammdaten. Diese Datei pflegst nur du; das Werkzeug und die AI
# fassen sie nie an. Sie verlässt den Gewerbe-Ordner nicht.
#
# Pflicht nach § 14 Abs. 4 UStG: voller Name und Anschrift sowie steuernummer ODER ustid.
# Bei EU-Kunden mit Reverse Charge wird die ustid gebraucht (außer als Kleinunternehmer).

name:                     # voller Name der natürlichen Person, nicht nur die Geschäftsbezeichnung
geschaeftsbezeichnung:    # optional, z. B. "Mustermann Beratung"
adresse:
  strasse:
  zusatz:                 # optional
  plz: ""
  ort:
land: DE

email:
telefon:                  # optional
website:                  # optional

steuernummer:             # z. B. 143/123/12345
ustid:                    # z. B. DE123456789
# kleinunternehmer: true   # § 19 UStG: keine Umsatzsteuer; Umsatzgrenzen prüfst du selbst

bank:
  kontoinhaber:
  iban:
  bic:
  name:                   # Name der Bank
"""


def stammdaten_geruest(cfg: Config) -> tuple[Path, bool]:
    """Legt ein leeres, kommentiertes ich.yaml im Gewerbe-Ordner an. Überschreibt nie.

    Gibt (Pfad, neu_angelegt) zurück.
    """
    ordner = cfg.ordner("stammdaten")
    if not ordner.is_dir():
        raise ConfigFehler(f"{ordner} fehlt – erst `rechnung init` ausführen.")
    ziel = ordner / "ich.yaml"
    if ziel.exists():
        return ziel, False
    ziel.write_text(STAMMDATEN_GERUEST, encoding="utf-8")
    return ziel, True
