"""Datenmodell. Alle Modelle verbieten unbekannte Felder (`extra="forbid"`).

Drei Ebenen:
  Stammdaten, Kunde  – aus dem Gewerbe-Ordner (bzw. stammdaten.example/)
  Input              – rechnung.yaml, die einzige Datei, die Menschen und AI schreiben
  Resolved           – rechnung.resolved.json, abgeleitet und eingefroren

Beträge sind `Decimal`. YAML-Fließkommazahlen werden über ihre Textform eingelesen,
damit 1234.10 nicht als 1234.0999999 ankommt.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Sprache = Literal["de", "en"]  # eine Sprache je Rechnung; die Vorlage setzt keine zweisprachigen Labels
Waehrung = Literal["EUR", "USD", "GBP"]
Steuerfall = Literal["A", "B", "C", "D"]

# Mengeneinheiten. Der Code ist UN/ECE Recommendation 20, den EN 16931 in BT-130 verlangt.
EINHEITEN: dict[str, str] = {
    "pauschal": "LS",    # lump sum – Panelteilnahme, Vortrag, Auslagen
    "stunde": "HUR",
    "tag": "DAY",
    "stueck": "C62",
    "kilometer": "KMT",
}
Einheit = Literal["pauschal", "stunde", "tag", "stueck", "kilometer"]

Land = Annotated[str, Field(pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2")]


def _dezimal(wert: object) -> object:
    """Zahlen als Decimal, Fließkomma über die Textform (YAML liefert float)."""
    if isinstance(wert, float):
        return Decimal(str(wert))
    if isinstance(wert, int):
        return Decimal(wert)
    return wert


# Ein stehen gelassener Platzhalter aus Vorlage oder Anleitung, z. B. „Panel bei {Event}“.
# Er wäre sonst still ins PDF gedruckt worden.
PLATZHALTER = re.compile(r"\{[^{}\n]*\}")


class Basis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def _kein_platzhalter(cls, v: object) -> object:
        if isinstance(v, str) and (treffer := PLATZHALTER.search(v)):
            raise ValueError(
                f"enthält den Platzhalter {treffer.group()} – durch den echten Wert ersetzen"
            )
        return v


class Adresse(Basis):
    strasse: str
    zusatz: str | None = None
    plz: str
    ort: str


class Bank(Basis):
    kontoinhaber: str
    iban: str
    bic: str | None = None
    name: str | None = None

    @field_validator("iban", mode="before")
    @classmethod
    def _iban_ohne_leerzeichen(cls, v: object) -> object:
        return "".join(str(v).split()) if isinstance(v, str) else v


class Register(Basis):
    """Handelsregister o. Ä. des Kunden – EN 16931 BT-47.

    Beispiele: Companies House / 01234567, Delaware File Number / 1234567, EIN / 12-3456789.
    """

    name: str
    nummer: str


class Stammdaten(Basis):
    """Aussteller. Im Gewerbe-Ordner unter stammdaten/ich.yaml; pflegt nur der Nutzer."""

    name: str
    geschaeftsbezeichnung: str | None = None
    adresse: Adresse
    land: Land = "DE"
    email: str
    telefon: str | None = None
    website: str | None = None
    steuernummer: str | None = None
    ustid: str | None = None
    bank: Bank

    @model_validator(mode="after")
    def _steuernummer_oder_ustid(self) -> Stammdaten:
        if not self.steuernummer and not self.ustid:
            raise ValueError("Pflichtangabe fehlt: steuernummer oder ustid (§ 14 Abs. 4 Nr. 2 UStG)")
        return self


class Kunde(Basis):
    """Ein Kunde je Datei unter stammdaten/kunden/<kuerzel>.yaml.

    `land`, `ustid` und `unternehmer` bestimmen den Steuerfall – deshalb bestätigt der Nutzer
    jede Kundendatei, die die AI vorschlägt.
    """

    kuerzel: str | None = None  # aus dem Dateinamen, nicht aus der Datei
    firma: str
    ansprechpartner: str | None = None
    adresse: Adresse
    land: Land
    ustid: str | None = None
    # YAML- und JSON-Schlüssel ist `register`; der Feldname weicht ab, weil `register` einen
    # internen Namen von pydantic überdeckt.
    registereintrag: Register | None = Field(default=None, alias="register", serialization_alias="register")
    referenz: str | None = None
    unternehmer: bool | None = None
    sprache: Sprache | None = None
    waehrung: Waehrung | None = None


class Position(Basis):
    """Eine Zeile der Rechnung. `menge` und `einheit` sind Pflicht: sie sind der 'Umfang der
    Leistung' nach § 14 Abs. 4 Nr. 5 UStG und BT-129/BT-130 in EN 16931. `rechnung neu` füllt
    beide vor, geraten wird hier nichts."""

    beschreibung: str
    menge: Decimal
    einheit: Einheit
    einzelpreis: Decimal
    steuersatz: Decimal | None = None  # nur im Inland (Fall A) sinnvoll: 19 oder 7

    _zahlen = field_validator("menge", "einzelpreis", "steuersatz", mode="before")(_dezimal)

    @field_validator("steuersatz")
    @classmethod
    def _satz_erlaubt(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v not in (Decimal(0), Decimal(7), Decimal(19)):
            raise ValueError("steuersatz muss 0, 7 oder 19 sein")
        return v


class Beleg(Basis):
    """Ein Beleg in belege/, der ans PDF angehängt wird.

    Kurzform im YAML ist der bloße Dateiname; mit `text:` steht neben der Anlage eine Erklärung:
        belege:
          - flug.pdf
          - datei: hotel.pdf
            text: Hotelrechnung, Position 3
    """

    datei: str
    text: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _kurzform(cls, wert: object) -> object:
        return {"datei": wert} if isinstance(wert, str) else wert


class Input(Basis):
    """rechnung.yaml – die einzige Datei, die Menschen und AI schreiben."""

    kunde: str
    datum: date | None = None          # Rechnungsdatum, Default: heute
    leistungsdatum: date
    leistungsdatum_bis: date | None = None
    sprache: Sprache | None = None
    waehrung: Waehrung | None = None
    zahlungsziel_tage: int | None = None
    referenz: str | None = None
    einleitung: str | None = None
    steuerfall: Steuerfall | None = None
    begruendung: str | None = None
    positionen: list[Position] = Field(min_length=1)
    belege: list[Beleg] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _leistungsdatum_pflicht(cls, daten: object) -> object:
        # `rechnung neu` lässt das Feld ohne --leistungsdatum leer; geraten wird es nie.
        if isinstance(daten, dict) and daten.get("leistungsdatum") in (None, ""):
            raise ValueError(
                "leistungsdatum fehlt: den Tag der Leistung als JJJJ-MM-TT eintragen "
                "(Pflichtangabe, § 14 Abs. 4 Nr. 6 UStG)"
            )
        return daten

    @model_validator(mode="after")
    def _override_braucht_begruendung(self) -> Input:
        if self.steuerfall and not self.begruendung:
            raise ValueError(
                f"steuerfall: {self.steuerfall} ist manuell gesetzt und braucht eine begruendung:"
            )
        if self.begruendung and not self.steuerfall:
            raise ValueError("begruendung: ohne steuerfall: – entweder beides oder keins")
        if self.leistungsdatum_bis and self.leistungsdatum_bis < self.leistungsdatum:
            raise ValueError("leistungsdatum_bis liegt vor leistungsdatum")
        return self


class ResolvedPosition(Basis):
    pos: int
    beschreibung: str
    menge: Decimal
    einheit: Einheit
    einheit_code: str
    einzelpreis: Decimal
    steuersatz: Decimal
    zeilensumme: Decimal


class Steuergruppe(Basis):
    """Ein Nettobetrag je Steuersatz – § 14 Abs. 4 Nr. 8 UStG verlangt die Trennung."""

    satz: Decimal
    netto: Decimal
    betrag: Decimal


class Resolved(Basis):
    """rechnung.resolved.json – abgeleitet, eingefroren, Grundlage für PDF und später ZUGFeRD."""

    nummer: str
    datum: date
    leistungsdatum: date
    leistungsdatum_bis: date | None = None
    faelligkeit: date
    sprache: Sprache
    waehrung: Waehrung
    aussteller: Stammdaten
    kunde: Kunde
    steuerfall: Steuerfall
    steuerfall_manuell: bool = False
    begruendung: str | None = None
    hinweis: dict[str, str] | None = None   # {"de": ..., "en": ...}, nur wenn kein USt-Ausweis
    referenz: str | None = None
    einleitung: str | None = None
    positionen: list[ResolvedPosition]
    steuergruppen: list[Steuergruppe]
    netto: Decimal
    ust_betrag: Decimal
    brutto: Decimal
    belege: list[Beleg] = Field(default_factory=list)
    vorlage_version: str
    vorlage_eigen: dict[str, str] | None = None   # eigene Vorlagen-Dateien: {Pfad: sha256}
    input_hash: str
    erzeugt_am: datetime
