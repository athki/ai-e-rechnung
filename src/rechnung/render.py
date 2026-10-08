"""Aus rechnung.resolved.json wird rechnung.pdf.

Hier wird nichts entschieden und nichts gerechnet – das ist in resolve.py passiert. Diese Datei
formatiert (Datum, Zahlen, Einheiten je Sprache), maskiert Nutzertext für LaTeX und baut.

Gebaut wird in einem Temp-Verzeichnis: dorthin kommen die Vorlage (Standard, darüber ein
eigener Vorlagen-Ordner, siehe vorlage.py), die zur Laufzeit erzeugte
include/issuer.tex mit den echten Ausstellerdaten und die Belege. Zurück in den Rechnungsordner
wandert nur die fertige PDF. Kein .aux, .log oder .tex landet dort, nie.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined

from rechnung import rules, vorlage
from rechnung.models import Resolved

VORLAGE = vorlage.STANDARD
PDF_DATEI = "rechnung.pdf"

# Unsere Einheiten in die Wörterbuchschlüssel der Vorlage (Singular/Plural).
EINHEIT_LATEX: dict[str, tuple[str, str]] = {
    "pauschal": ("flat", "flat"),
    "stunde": ("hour", "hours"),
    "tag": ("day", "days"),
    "stueck": ("each", "each"),
    "kilometer": ("km", "km"),
}

SPRACHE_LATEX = {"de": "ngerman", "en": "english"}

MONATE_EN = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]

# Zeichen, die LaTeX anders liest, als der Nutzer sie meint.
ESCAPE = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


class RenderFehler(Exception):
    pass


def escape(text: str) -> str:
    """Maskiert Nutzertext für LaTeX. Jede Beschreibung läuft hier durch."""
    return "".join(ESCAPE.get(z, z) for z in str(text))


def datum(wert, sprache: str) -> str:
    """23.09.2026 (de) bzw. 23 September 2026 (en)."""
    if sprache == "de":
        return f"{wert.day:02d}.{wert.month:02d}.{wert.year}"
    return f"{wert.day} {MONATE_EN[wert.month - 1]} {wert.year}"


def zahl(wert: Decimal) -> str:
    """Punkt als Dezimaltrenner, keine Gruppierung – die Vorlage formatiert sprachabhängig."""
    text = format(wert, "f")
    return text


def einheit(name: str, menge: Decimal) -> str:
    singular, plural = EINHEIT_LATEX[name]
    return singular if menge == 1 else plural


def _umgebung(eigene: Path | None = None) -> Environment:
    """Jinja sucht zuerst im eigenen Vorlagen-Ordner, dann in der Standardvorlage."""
    ordner = [eigene, VORLAGE] if eigene is not None else [VORLAGE]
    return Environment(
        loader=ChoiceLoader([FileSystemLoader(str(o)) for o in ordner]),
        block_start_string=r"\BLOCK{", block_end_string="}",
        variable_start_string=r"\VAR{", variable_end_string="}",
        comment_start_string=r"\#{", comment_end_string="}",
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
        autoescape=False, undefined=StrictUndefined,
    )


def kontext(r: Resolved) -> dict:
    """Alles, was die Vorlage braucht – fertig formatiert und maskiert."""
    sprache = r.sprache

    empfaenger = [escape(r.kunde.firma)]
    if r.kunde.ansprechpartner:
        empfaenger.append(escape(r.kunde.ansprechpartner))
    empfaenger.append(escape(r.kunde.adresse.strasse))
    if r.kunde.adresse.zusatz:
        empfaenger.append(escape(r.kunde.adresse.zusatz))
    if r.kunde.land == "DE":
        empfaenger.append(escape(f"{r.kunde.adresse.plz} {r.kunde.adresse.ort}"))
    else:
        empfaenger.append(escape(f"{r.kunde.adresse.ort} {r.kunde.adresse.plz}".strip()))
        empfaenger.append(escape(rules.land_name(r.kunde.land, sprache)))
    # USt-IdNr. und Registereintrag des Kunden stehen nicht in der Anschrift, sondern im
    # Metadatenblock unter dem Strich: die Anschrift bleibt rein postalisch.
    register = r.kunde.registereintrag

    positionen = [
        {
            "pos": p.pos,
            "beschreibung": escape(p.beschreibung),
            "menge": zahl(p.menge),
            "einheit": einheit(p.einheit, p.menge),
            "einzelpreis": zahl(p.einzelpreis),
            "steuersatz": zahl(p.steuersatz),
            "zeilensumme": zahl(p.zeilensumme),
        }
        for p in r.positionen
    ]

    return {
        "sprache": sprache,
        "sprache_latex": SPRACHE_LATEX[sprache],
        "nummer": escape(r.nummer),
        "datum": datum(r.datum, sprache),
        "leistungsdatum": datum(r.leistungsdatum, sprache),
        "leistungsdatum_bis": datum(r.leistungsdatum_bis, sprache) if r.leistungsdatum_bis else None,
        "faelligkeit": datum(r.faelligkeit, sprache),
        "waehrung": r.waehrung,
        "referenz": escape(r.referenz) if r.referenz else None,
        "einleitung": escape(r.einleitung) if r.einleitung else None,
        "empfaenger": empfaenger,
        "kunde_ustid": escape(r.kunde.ustid) if r.kunde.ustid else None,
        # Nummer zuerst, sie gehört zum Label; das Register erklärt sie in Klammern.
        "kunde_register": escape(f"{register.nummer} ({register.name})") if register else None,
        "kunde": r.kunde,
        "aussteller": r.aussteller,
        "positionen": positionen,
        "steuergruppen": [
            {"satz": zahl(g.satz), "netto": zahl(g.netto), "betrag": zahl(g.betrag)}
            for g in r.steuergruppen
        ],
        "gemischte_saetze": len(r.steuergruppen) > 1,
        "netto": zahl(r.netto),
        "ust_betrag": zahl(r.ust_betrag),
        "brutto": zahl(r.brutto),
        "hinweis": escape(r.hinweis[sprache]) if r.hinweis else None,
        "belege": [{"datei": b.datei, "text": escape(b.text or b.datei)} for b in r.belege],
    }


def kontext_aussteller(r: Resolved) -> dict:
    a = r.aussteller
    punkt = r" \textperiodcentered\ "
    return {
        "aussteller": a,
        "name_zeile": escape(a.geschaeftsbezeichnung or a.name),
        "adresse_zeile": punkt.join([escape(a.adresse.strasse), escape(f"{a.adresse.plz} {a.adresse.ort}")]),
        "land_de": "" if a.land == "DE" else escape(rules.land_name(a.land, "de")),
        "land_en": escape(rules.land_name(a.land, "en")),
        "telefon": escape(a.telefon or ""),
        "website": escape(a.website or ""),
        # Rücksendeangabe: Name, Straße, Ort – mehr sieht das Fenster des Umschlags nicht.
        "ruecksendeangabe": punkt.join([
            escape(a.name), escape(a.adresse.strasse), escape(f"{a.adresse.plz} {a.adresse.ort}")]),
        "steuernummer": escape(a.steuernummer or ""),
        "ustid": escape(a.ustid or ""),
        "iban": escape(_iban_gruppiert(a.bank.iban)),
        "bic": escape(a.bank.bic or ""),
        "bank": escape(a.bank.name or ""),
    }


def _iban_gruppiert(iban: str) -> str:
    """DE89370400440532013000 -> DE89 3704 0044 0532 0130 00 (lesbar auf der Rechnung)."""
    kompakt = "".join(iban.split())
    return " ".join(kompakt[i:i + 4] for i in range(0, len(kompakt), 4))


def baue_verzeichnis(r: Resolved, ziel: Path, belege_quelle: Path | None = None,
                     eigene: Path | None = None) -> Path:
    """Legt im Zielverzeichnis eine vollständige, für sich kompilierbare Rechnung an.

    Erst die Standardvorlage, dann der eigene Vorlagen-Ordner darüber (gleiche Namen ersetzt er),
    zuletzt die erzeugten Dateien.
    """
    env = _umgebung(eigene)
    (ziel / "style").mkdir(parents=True, exist_ok=True)
    (ziel / "include").mkdir(exist_ok=True)
    (ziel / "attachments").mkdir(exist_ok=True)
    for rel in vorlage.standard_dateien(VORLAGE):
        if not rel.endswith(".j2"):
            shutil.copy2(VORLAGE / rel, ziel / rel)
    if eigene is not None:
        for rel in vorlage.eigene_dateien(eigene):
            if rel.endswith(".j2"):
                continue
            (ziel / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(eigene / rel, ziel / rel)

    (ziel / "include" / "issuer.tex").write_text(
        env.get_template("issuer.tex.j2").render(**kontext_aussteller(r)), encoding="utf-8")
    (ziel / "rechnung.tex").write_text(
        env.get_template("rechnung.tex.j2").render(**kontext(r)), encoding="utf-8")

    for beleg in r.belege:
        if belege_quelle is None:
            continue
        quelle = belege_quelle / beleg.datei
        if not quelle.is_file():
            raise RenderFehler(
                f"Beleg fehlt: {quelle}\nEntweder die Datei nach belege/ legen oder den Eintrag "
                f"aus rechnung.yaml entfernen."
            )
        shutil.copy2(quelle, ziel / "attachments" / beleg.datei)
    return ziel / "rechnung.tex"


def baue_pdf(r: Resolved, ziel_ordner: Path, engine: str = "pdflatex",
             belege_quelle: Path | None = None, eigene: Path | None = None) -> Path:
    """Baut die PDF in einem Temp-Verzeichnis und legt nur sie in den Zielordner."""
    if vorlage.nachweis(eigene) != r.vorlage_eigen:
        raise RenderFehler(
            "Der eigene Vorlagen-Ordner hat sich seit dem Auflösen geändert – erst neu auflösen, "
            "damit resolved.json festhält, womit gebaut wird."
        )
    with tempfile.TemporaryDirectory(prefix="rechnung-build-") as tmp:
        tmp_pfad = Path(tmp)
        tex = baue_verzeichnis(r, tmp_pfad, belege_quelle, eigene)
        cmd = [
            "latexmk", {"pdflatex": "-pdf", "lualatex": "-lualatex", "xelatex": "-xelatex"}[engine],
            "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
            f"-outdir={tmp_pfad}", tex.name,
        ]
        try:
            aus = subprocess.run(cmd, cwd=tmp_pfad, capture_output=True, text=True, timeout=600)
        except FileNotFoundError as e:
            raise RenderFehler("latexmk nicht gefunden – `rechnung doctor` sagt, was fehlt.") from e
        except subprocess.TimeoutExpired as e:
            raise RenderFehler("latexmk hat zu lange gebraucht (600 s).") from e

        pdf = tmp_pfad / "rechnung.pdf"
        if aus.returncode != 0 or not pdf.is_file():
            raise RenderFehler(_fehlermeldung(aus.stdout, tmp_pfad))

        ziel_ordner.mkdir(parents=True, exist_ok=True)
        ziel = ziel_ordner / PDF_DATEI
        if ziel.exists() and not _beschreibbar(ziel):
            raise RenderFehler(f"{ziel} ist schreibgeschützt – festgeschriebene Rechnungen werden nicht neu gebaut.")
        shutil.copy2(pdf, ziel)
    return ziel


def _beschreibbar(pfad: Path) -> bool:
    import os
    return os.access(pfad, os.W_OK)


def _fehlermeldung(ausgabe: str, tmp: Path) -> str:
    """Die LaTeX-Fehlerzeilen herausziehen – der Rest des Logs hilft niemandem."""
    zeilen = [z for z in ausgabe.splitlines() if z.startswith("!") or z.startswith("l.")]
    kern = "\n".join(zeilen[:10]) or "kein LaTeX-Fehler im Protokoll gefunden"
    return f"LaTeX-Bau fehlgeschlagen:\n{kern}"
