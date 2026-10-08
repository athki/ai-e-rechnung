"""`rechnung pruefen`: weist die Pflichtangaben im fertigen PDF nach.

Nicht im Datenmodell, nicht in der Vorlage – im **Text der PDF**, extrahiert mit `pdftotext`.
Das ist der Unterschied zwischen „die Daten waren vollständig“ und „es steht auf dem Blatt“:
Ein vergessenes Feld in der Vorlage, ein Umbruch, der etwas verschluckt, eine Schrift ohne
Unicode-Zuordnung – all das fällt nur hier auf.

Liste der Pflichtangaben: § 14 Abs. 4 UStG.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from rechnung import render
from rechnung.models import Resolved

PDF_DATEI = "rechnung.pdf"


class PruefFehler(Exception):
    pass


@dataclass
class Befund:
    angabe: str          # was geprüft wurde
    gesucht: str         # der Text, der im PDF stehen muss
    gefunden: bool
    paragraf: str = ""   # Fundstelle im Gesetz, für die Meldung


def pdf_text(pdf: Path) -> str:
    if not shutil.which("pdftotext"):
        raise PruefFehler("pdftotext fehlt – `rechnung doctor` sagt, wie es dazukommt.")
    if not pdf.is_file():
        raise PruefFehler(f"PDF fehlt: {pdf}\nErst `rechnung bauen` ausführen.")
    aus = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
    if aus.returncode != 0:
        raise PruefFehler(f"pdftotext scheiterte an {pdf}: {aus.stderr.strip()}")
    return aus.stdout


def normalisiere(text: str) -> str:
    """Zeilenumbrüche, Trennstriche und Mehrfach-Leerzeichen raus.

    LaTeX bricht Wörter um und setzt Gedankenstriche; ohne Normalisierung meldet die Prüfung
    Fehlalarme, und eine Prüfung mit Fehlalarmen schaltet man ab.
    """
    text = text.replace("­", "")               # weiches Trennzeichen
    text = re.sub(r"-\s*\n\s*", "", text)           # am Zeilenende getrenntes Wort
    text = text.replace("–", "-").replace("—", "-").replace("’", "'")
    text = text.replace(" ", " ")
    # LaTeX setzt -- als Gedankenstrich; im PDF steht dann ein Zeichen, im YAML zwei.
    text = re.sub(r"-{2,}", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def enthaelt(text: str, gesucht: str) -> bool:
    return normalisiere(gesucht) in text


def geld(betrag: Decimal, waehrung: str, sprache: str) -> str:
    """So, wie die Vorlage es setzt: 1.428,00 EUR (de) bzw. EUR 1,428.00 (en)."""
    zahl = f"{betrag:,.2f}"
    if sprache == "de":
        zahl = zahl.replace(",", "#").replace(".", ",").replace("#", ".")
        return f"{zahl} {waehrung}"
    return f"{waehrung} {zahl}"


def befunde(r: Resolved, text: str) -> list[Befund]:
    """Jede Pflichtangabe als einzelner Befund – die Meldung soll sagen, was genau fehlt."""
    n = normalisiere(text)
    a, k = r.aussteller, r.kunde

    liste: list[Befund] = [
        Befund("Rechnungsnummer", r.nummer, enthaelt(n, r.nummer), "§ 14 Abs. 4 Nr. 4"),
        Befund("Rechnungsdatum", render.datum(r.datum, r.sprache),
               enthaelt(n, render.datum(r.datum, r.sprache)), "§ 14 Abs. 4 Nr. 3"),
        Befund("Leistungsdatum", render.datum(r.leistungsdatum, r.sprache),
               enthaelt(n, render.datum(r.leistungsdatum, r.sprache)), "§ 14 Abs. 4 Nr. 6"),
        Befund("Name des Ausstellers", a.name, enthaelt(n, a.name), "§ 14 Abs. 4 Nr. 1"),
        Befund("Anschrift des Ausstellers", f"{a.adresse.strasse}",
               enthaelt(n, a.adresse.strasse) and enthaelt(n, a.adresse.ort), "§ 14 Abs. 4 Nr. 1"),
        Befund("Name des Kunden", k.firma, enthaelt(n, k.firma), "§ 14 Abs. 4 Nr. 1"),
        Befund("Anschrift des Kunden", k.adresse.strasse,
               enthaelt(n, k.adresse.strasse) and enthaelt(n, k.adresse.ort), "§ 14 Abs. 4 Nr. 1"),
        Befund("Steuernummer oder USt-IdNr.", a.steuernummer or a.ustid or "",
               enthaelt(n, a.steuernummer or "") or enthaelt(n, a.ustid or ""), "§ 14 Abs. 4 Nr. 2"),
    ]

    for p in r.positionen:
        liste.append(Befund(f"Position {p.pos}: Beschreibung", p.beschreibung,
                            enthaelt(n, p.beschreibung), "§ 14 Abs. 4 Nr. 5"))

    liste.append(Befund("Nettobetrag", geld(r.netto, r.waehrung, r.sprache),
                        enthaelt(n, geld(r.netto, r.waehrung, r.sprache)), "§ 14 Abs. 4 Nr. 7"))
    liste.append(Befund("Rechnungsbetrag", geld(r.brutto, r.waehrung, r.sprache),
                        enthaelt(n, geld(r.brutto, r.waehrung, r.sprache)), "§ 14 Abs. 4 Nr. 8"))

    if r.ust_betrag > 0:
        for g in r.steuergruppen:
            satz = f"{g.satz:f}".rstrip("0").rstrip(".") or "0"
            liste.append(Befund(f"Steuerbetrag {satz} %", geld(g.betrag, r.waehrung, r.sprache),
                                enthaelt(n, geld(g.betrag, r.waehrung, r.sprache)), "§ 14 Abs. 4 Nr. 8"))
            liste.append(Befund(f"Steuersatz {satz} %", f"{satz} %",
                                enthaelt(n, f"{satz} %") or enthaelt(n, f"{satz}%"), "§ 14 Abs. 4 Nr. 8"))
    else:
        hinweis = r.hinweis[r.sprache] if r.hinweis else ""
        if r.ergebnis != "kleinunternehmer":   # dort gibt es keine Steuerzeile (§ 34a UStDV)
            liste.append(Befund("Steuerbetrag 0,00", geld(Decimal("0.00"), r.waehrung, r.sprache),
                                enthaelt(n, geld(Decimal("0.00"), r.waehrung, r.sprache)), "§ 14 Abs. 4 Nr. 8"))
        if hinweis:
            liste.append(Befund("Hinweis auf Steuerbefreiung / Nichtsteuerbarkeit", hinweis,
                                enthaelt(n, hinweis), "§ 14 Abs. 4 Nr. 8"))

    # Ein Kleinunternehmer muss die USt-IdNrn. nicht angeben (§ 19 Abs. 1 Satz 2 UStG, RULES.md R15).
    if r.ergebnis == "reverse_charge" and not a.kleinunternehmer:
        liste.append(Befund("USt-IdNr. des Kunden (Reverse Charge)", k.ustid or "",
                            enthaelt(n, k.ustid or ""), "§ 14a Abs. 1"))
        liste.append(Befund("USt-IdNr. des Ausstellers (Reverse Charge)", a.ustid or "",
                            enthaelt(n, a.ustid or ""), "§ 14a Abs. 1"))

    return liste


def pruefe(r: Resolved, pdf: Path) -> list[Befund]:
    return befunde(r, pdf_text(pdf))
