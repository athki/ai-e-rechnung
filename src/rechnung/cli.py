"""Kommandozeile `rechnung`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer

from rechnung import (
    config,
    doctor as doctor_mod,
    festschreiben as festschreiben_mod,
    pruefen as pruefen_mod,
    render as render_mod,
    resolve as resolve_mod,
    rules,
)
from rechnung.models import Resolved

app = typer.Typer(help="Rechnungen aus YAML, gesetzt mit LaTeX.", no_args_is_help=True, add_completion=False)

SYMBOL = {
    doctor_mod.OK: typer.style("✓", fg=typer.colors.GREEN, bold=True),
    doctor_mod.WARNUNG: typer.style("!", fg=typer.colors.YELLOW, bold=True),
    doctor_mod.FEHLER: typer.style("✗", fg=typer.colors.RED, bold=True),
}


def _config() -> config.Config:
    try:
        return config.laden()
    except config.ConfigFehler as e:
        typer.secho(f"Fehler in der Config: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e


def _abbruch(e: Exception) -> typer.Exit:
    typer.secho(str(e), fg=typer.colors.RED, err=True)
    return typer.Exit(1)


def _geld(betrag: Decimal, waehrung: str) -> str:
    text = f"{betrag:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"{text} {waehrung}"


@app.command()
def doctor() -> None:
    """Prüft Python, LaTeX, pdftotext, Fonts, Config, Gewerbe-Ordner und Docker."""
    pruefungen = doctor_mod.alle()
    breite = max(len(p.name) for p in pruefungen)
    for p in pruefungen:
        typer.echo(f" {SYMBOL[p.status]} {p.name.ljust(breite)}  {p.detail}")
    fehler = sum(p.status == doctor_mod.FEHLER for p in pruefungen)
    warnungen = sum(p.status == doctor_mod.WARNUNG for p in pruefungen)
    typer.echo()
    if fehler:
        typer.secho(f"rot: {fehler} Fehler, {warnungen} Warnung(en)", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    typer.secho(f"grün ({warnungen} Warnung(en))", fg=typer.colors.GREEN, bold=True)


@app.command()
def init(
    stammdaten: Annotated[bool, typer.Option("--stammdaten", help="Zusätzlich ein leeres ich.yaml anlegen.")] = False,
) -> None:
    """Legt unter der Gewerbe-Wurzel die Ordner an, die das Werkzeug besitzt. Rührt sonst nichts an."""
    cfg = _config()
    try:
        ergebnis = config.init(cfg)
    except config.ConfigFehler as e:
        raise _abbruch(e) from e
    assert cfg.gewerbe is not None
    typer.echo(f"Gewerbe-Wurzel: {cfg.gewerbe}")
    for pfad, neu_angelegt in ergebnis:
        typer.echo(f"  {'angelegt ' if neu_angelegt else 'vorhanden'}  {pfad.relative_to(cfg.gewerbe)}/")
    if stammdaten:
        try:
            ziel, neu_angelegt = config.stammdaten_geruest(cfg)
        except config.ConfigFehler as e:
            raise _abbruch(e) from e
        typer.echo(f"  {'angelegt ' if neu_angelegt else 'vorhanden'}  {ziel.relative_to(cfg.gewerbe)}")
        if neu_angelegt:
            typer.echo("\nJetzt ausfüllen; `rechnung resolve` sagt dir, wenn etwas fehlt.")


@app.command()
def neu(
    kunde: Annotated[str, typer.Option("--kunde", help="Kürzel der Datei in stammdaten/kunden/")],
    leistungsdatum: Annotated[str, typer.Option(
        help="JJJJ-MM-TT. Ohne Angabe bleibt das Feld in rechnung.yaml leer und ist dort auszufüllen.")] = "",
    datum: Annotated[str, typer.Option(help="Rechnungsdatum JJJJ-MM-TT, Default: heute")] = "",
    sprache: Annotated[str, typer.Option(help="de | en")] = "",
    waehrung: Annotated[str, typer.Option(help="EUR | USD | GBP")] = "",
    taetigkeit: Annotated[str, typer.Option(help="Was geleistet wird, in eigenen Worten.")] = "",
    einordnung: Annotated[str, typer.Option(
        help="Begriff aus § 3a UStG, z. B. beratung, unterrichtend, sonstige (Liste: RULES.md Teil 4). "
             "Ohne Angabe bleibt das Feld in rechnung.yaml leer und ist dort auszufüllen.")] = "",
    ort: Annotated[str, typer.Option(help="Nur bei Tätigkeitsleistungen: Land (z. B. GB) oder online.")] = "",
) -> None:
    """Legt Ordner und vorbefülltes rechnung.yaml für eine neue Rechnung an."""
    cfg = _config()
    try:
        rechnungsdatum = date.fromisoformat(datum) if datum else date.today()
        leistung = date.fromisoformat(leistungsdatum) if leistungsdatum else None
    except ValueError as e:
        raise _abbruch(ValueError(f"Datum muss JJJJ-MM-TT sein: {e}")) from e
    if sprache and sprache not in config.SPRACHEN:
        raise _abbruch(ValueError(f"sprache muss eine von {config.SPRACHEN} sein"))
    if waehrung and waehrung not in config.WAEHRUNGEN:
        raise _abbruch(ValueError(f"waehrung muss eine von {config.WAEHRUNGEN} sein"))
    if einordnung and einordnung not in rules.EINORDNUNGEN:
        raise _abbruch(ValueError(f"einordnung muss eine von {', '.join(rules.EINORDNUNGEN)} sein"))
    try:
        ordner, nummer = resolve_mod.neu(
            cfg, kunde, leistung, rechnungsdatum, sprache or None, waehrung or None,
            taetigkeit or None, einordnung or None, ort or None,
        )
    except (resolve_mod.ResolveFehler, config.ConfigFehler, rules.RegelFehler) as e:
        raise _abbruch(e) from e
    typer.secho(f"Rechnung {nummer} angelegt", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  {ordner / resolve_mod.INPUT_DATEI}")
    if leistung is None:
        typer.secho("  leistungsdatum ist noch leer – Pflicht, in rechnung.yaml eintragen.",
                    fg=typer.colors.YELLOW)
    if not (taetigkeit and einordnung):
        typer.secho("  leistung: ist noch unvollständig – Pflicht, in rechnung.yaml eintragen.",
                    fg=typer.colors.YELLOW)
    typer.echo(f"\nAusfüllen, dann: rechnung resolve {nummer}")


def _zeige(r: Resolved, ziel: Path) -> None:
    typer.secho(f"Rechnung {r.nummer}", bold=True)
    typer.echo(f"  Kunde           {r.kunde.firma} ({r.kunde.land})")
    typer.echo(f"  Datum           {r.datum}  ·  Leistung {r.leistungsdatum}"
               + (f" bis {r.leistungsdatum_bis}" if r.leistungsdatum_bis else ""))
    typer.echo(f"  Fällig          {r.faelligkeit}")
    typer.echo(f"  Sprache         {r.sprache}")
    typer.echo(f"  Leistung        {r.leistung.taetigkeit}")
    typer.echo(f"                  {r.leistung.einordnung}"
               + (f", erbracht: {r.leistung.ort}" if r.leistung.ort else ""))
    ort = f"{r.leistungsort}{' (manuell festgelegt)' if r.leistungsort_manuell else ''}"
    typer.echo(f"  Leistungsort    {ort}")
    typer.echo(f"  Ergebnis        {r.ergebnis}")
    typer.echo()
    for p in r.positionen:
        typer.echo(f"  {p.pos}  {p.beschreibung}")
        typer.echo(f"     {p.menge} {p.einheit} × {_geld(p.einzelpreis, r.waehrung)}"
                   f"  =  {_geld(p.zeilensumme, r.waehrung)}   ({p.steuersatz} %)")
    typer.echo()
    typer.echo(f"  Netto           {_geld(r.netto, r.waehrung)}")
    for g in r.steuergruppen:
        typer.echo(f"  USt {g.satz} %{'':<9}{_geld(g.betrag, r.waehrung)}")
    typer.secho(f"  Brutto          {_geld(r.brutto, r.waehrung)}", bold=True)
    if r.hinweis:
        typer.echo()
        for text in r.hinweis.values():
            typer.echo(f"  {text}")
    for warnung in r.warnungen:
        typer.secho(f"\n  Achtung: {warnung}", fg=typer.colors.YELLOW)
    typer.echo(f"\n  geschrieben: {ziel}")


@app.command()
def resolve(nummer: Annotated[str, typer.Argument(help="Rechnungsnummer, z. B. 2026-0001")]) -> None:
    """Löst rechnung.yaml auf: Leistungsort, Ergebnis, Summen, Fälligkeit; schreibt rechnung.resolved.json."""
    cfg = _config()
    try:
        ergebnis, ziel = resolve_mod.resolve(cfg, nummer)
    except (resolve_mod.ResolveFehler, config.ConfigFehler, rules.RegelFehler) as e:
        raise _abbruch(e) from e
    _zeige(ergebnis, ziel)


@app.command()
def bauen(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer, z. B. 2026-0001")],
    still: Annotated[bool, typer.Option("--still", help="Nur den Pfad der PDF ausgeben.")] = False,
) -> None:
    """Löst die Rechnung auf und baut daraus die PDF. Gebaut wird in einem Temp-Verzeichnis."""
    cfg = _config()
    try:
        ordner_vorab = resolve_mod.finde_ordner(cfg, nummer)
        if festschreiben_mod.ist_festgeschrieben(ordner_vorab):
            raise festschreiben_mod.FestschreibFehler(
                f"Rechnung {ordner_vorab.name} ist festgeschrieben und wird nicht neu gebaut.\n"
                f"Für eine Korrektur: Stornorechnung und neue Rechnung."
            )
        ergebnis, json_ziel = resolve_mod.resolve(cfg, nummer)
        ordner = json_ziel.parent
        pdf = render_mod.baue_pdf(ergebnis, ordner, cfg.engine, belege_quelle=ordner / "belege",
                                  eigene=cfg.vorlage)
    except (resolve_mod.ResolveFehler, render_mod.RenderFehler, config.ConfigFehler,
            rules.RegelFehler, festschreiben_mod.FestschreibFehler) as e:
        raise _abbruch(e) from e
    if still:
        typer.echo(str(pdf))
        return
    _zeige(ergebnis, json_ziel)
    typer.secho(f"\n  PDF: {pdf}", fg=typer.colors.GREEN, bold=True)


def _ordner_oder_nummer(cfg: config.Config, wert: str) -> Path:
    """Akzeptiert eine Rechnungsnummer oder direkt den Pfad eines Rechnungsordners."""
    kandidat = Path(wert)
    if kandidat.is_dir() and (kandidat / resolve_mod.RESOLVED_DATEI).is_file():
        return kandidat
    return resolve_mod.finde_ordner(cfg, wert)


@app.command()
def pruefen(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer oder Pfad eines Rechnungsordners")],
) -> None:
    """Weist im Text der fertigen PDF nach, dass alle Pflichtangaben enthalten sind."""
    import json

    from rechnung.models import Resolved

    cfg = _config()
    try:
        ordner = _ordner_oder_nummer(cfg, nummer)
        ergebnis = Resolved.model_validate(
            json.loads((ordner / resolve_mod.RESOLVED_DATEI).read_text(encoding="utf-8")))
        liste = pruefen_mod.pruefe(ergebnis, ordner / pruefen_mod.PDF_DATEI)
    except (resolve_mod.ResolveFehler, pruefen_mod.PruefFehler, config.ConfigFehler, OSError) as e:
        raise _abbruch(e) from e

    breite = max(len(b.angabe) for b in liste)
    for b in liste:
        zeichen = SYMBOL[doctor_mod.OK if b.gefunden else doctor_mod.FEHLER]
        zusatz = "" if b.gefunden else f"   gesucht: {b.gesucht!r}  ({b.paragraf} UStG)"
        typer.echo(f" {zeichen} {b.angabe.ljust(breite)}{zusatz}")

    fehlend = [b for b in liste if not b.gefunden]
    abweichungen = festschreiben_mod.pruefe_unveraendert(ordner)
    for a in abweichungen:
        typer.secho(f" {SYMBOL[doctor_mod.FEHLER]} {a}", fg=typer.colors.RED)
    typer.echo()
    if fehlend or abweichungen:
        typer.secho(f"rot: {len(fehlend) + len(abweichungen)} Mangel/Mängel in {ordner.name}",
                    fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    typer.secho(f"grün: {len(liste)} Pflichtangaben nachgewiesen in {ordner.name}",
                fg=typer.colors.GREEN, bold=True)


@app.command()
def festschreiben(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer, z. B. 2026-0001")],
    gesendet_am: Annotated[str, typer.Option(
        "--gesendet-am",
        help="Tag, an dem die Rechnung an den Kunden ging (JJJJ-MM-TT). Pflicht.")],
) -> None:
    """Macht die Rechnung unveränderbar: Status, Schreibschutz auf PDF und resolved.json, Hashes.

    Das Werkzeug verschickt nichts – es hält fest, dass du verschickt hast. Vorher darf beliebig
    oft gebaut und geprüft werden. Danach verweigert `bauen` den Neubau.
    """
    cfg = _config()
    try:
        gesendet = date.fromisoformat(gesendet_am)
    except ValueError as e:
        raise _abbruch(ValueError(f"--gesendet-am muss JJJJ-MM-TT sein: {e}")) from e
    if gesendet > date.today():
        raise _abbruch(ValueError(
            f"--gesendet-am liegt in der Zukunft ({gesendet}). Festgeschrieben wird, was raus ist."))
    try:
        ordner = resolve_mod.finde_ordner(cfg, nummer)
        daten = festschreiben_mod.festschreiben(ordner, gesendet)
    except (resolve_mod.ResolveFehler, festschreiben_mod.FestschreibFehler, config.ConfigFehler) as e:
        raise _abbruch(e) from e
    typer.secho(f"Rechnung {ordner.name} festgeschrieben", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  gesendet am        {daten['gesendet_am']}")
    typer.echo(f"  festgeschrieben am {daten['festgeschrieben_am']}")
    typer.echo("  PDF und resolved.json sind jetzt schreibgeschützt, die Hashes stehen in status.yaml.")
    typer.echo("  `rechnung bauen` verweigert ab jetzt den Neubau dieser Rechnung.")


# Die Demo baut je Ergebnis mindestens eine Rechnung aus stammdaten.example/.
DEMO: list[dict] = [
    {"kuerzel": "muster-gmbh", "sprache": "de",
     "leistung": ("Beratung zum Marktzugang mit Workshop", "beratung", None),
     "beschreibung": "Beratung Marktzugang, Workshop in Berlin",
     "menge": "8", "einheit": "stunde", "einzelpreis": "150.00"},
    {"kuerzel": "exemple-sarl", "sprache": "en",
     "leistung": ("Policy briefing for the management team", "beratung", None),
     "beschreibung": "Policy briefing, Paris",
     "menge": "1", "einheit": "pauschal", "einzelpreis": "2400.00"},
    {"kuerzel": "sample-ltd", "sprache": "en",
     "leistung": ("Panel participation at a policy forum", "unterrichtend", "GB"),
     "beschreibung": "Panel participation, Sample Policy Forum, London",
     "menge": "2", "einheit": "stunde", "einzelpreis": "200.00",
     "zweite": ("Travel: flight FRA--LON--FRA, receipt attached", "1", "pauschal", "287.30")},
    {"kuerzel": "privat-ch", "sprache": "de",
     "leistung": ("Vortrag vor Publikum", "unterrichtend", "CH"),
     "beschreibung": "Vortrag, Zürich",
     "menge": "1", "einheit": "pauschal", "einzelpreis": "900.00"},
]


@app.command()
def demo(
    ziel: Annotated[str, typer.Option(help="Zielordner")] = "demo-output",
    pruefe: Annotated[bool, typer.Option("--pruefen", help="Jede gebaute Rechnung gleich pruefen.")] = False,
) -> None:
    """Baut Beispielrechnungen, je Ergebnis mindestens eine, aus stammdaten.example/ in einen Ordner."""
    import shutil
    import tempfile
    from datetime import date

    ziel_pfad = Path(ziel).resolve()
    ziel_pfad.mkdir(parents=True, exist_ok=True)
    cfg = _config()

    with tempfile.TemporaryDirectory(prefix="rechnung-demo-") as tmp:
        gewerbe = Path(tmp)
        shutil.copytree(config.BEISPIEL_STAMMDATEN, gewerbe / "stammdaten")
        demo_cfg = config.laden(
            env={"RECHNUNG_GEWERBE": str(gewerbe), "RECHNUNG_CONFIG": str(gewerbe / "keine.toml"),
                 "RECHNUNG_NUMMER_FORMAT": "DEMO-{jahr}-{lfd:04d}",
                 # Die Demo zeigt das eigene Aussehen, wenn eines konfiguriert ist.
                 "RECHNUNG_VORLAGE": str(cfg.vorlage or "")},
            pfad=gewerbe / "keine.toml",
        )
        config.init(demo_cfg)
        for eintrag in DEMO:
            ordner, nummer = resolve_mod.neu(
                demo_cfg, eintrag["kuerzel"], date(2026, 6, 10), date(2026, 6, 17), eintrag["sprache"]
            )
            (ordner / resolve_mod.INPUT_DATEI).write_text(
                _demo_yaml(eintrag), encoding="utf-8")
            if "zweite" in eintrag:
                shutil.copy2(config.REPO / "vorlage" / "attachments" / "sample-receipt.pdf",
                             ordner / "belege" / "flug.pdf")
            try:
                ergebnis, json_ziel = resolve_mod.resolve(demo_cfg, nummer)
                pdf = render_mod.baue_pdf(ergebnis, ordner, cfg.engine, belege_quelle=ordner / "belege",
                                          eigene=demo_cfg.vorlage)
            except (resolve_mod.ResolveFehler, render_mod.RenderFehler, rules.RegelFehler,
                    config.ConfigFehler) as e:
                raise _abbruch(e) from e
            # Der ganze Rechnungsordner wandert ins Ziel, nicht nur die PDF: damit kann
            # `rechnung pruefen <ordner>` die Demo-Rechnungen nachträglich prüfen.
            name = f"{ergebnis.ergebnis.replace('_', '-')}-{eintrag['kuerzel']}"
            zielordner = ziel_pfad / name
            if zielordner.exists():
                shutil.rmtree(zielordner)
            shutil.copytree(ordner, zielordner)
            typer.echo(f" {SYMBOL[doctor_mod.OK]} {name}/rechnung.pdf"
                       f"  ({ergebnis.waehrung} {ergebnis.brutto})")
            if pruefe:
                befunde = pruefen_mod.pruefe(ergebnis, zielordner / pruefen_mod.PDF_DATEI)
                fehlend = [b for b in befunde if not b.gefunden]
                zeichen = SYMBOL[doctor_mod.FEHLER if fehlend else doctor_mod.OK]
                typer.echo(f"   {zeichen} pruefen: {len(befunde) - len(fehlend)}/{len(befunde)} Pflichtangaben"
                           + ("" if not fehlend else "  fehlt: " + ", ".join(b.angabe for b in fehlend)))
                if fehlend:
                    raise typer.Exit(1)
    typer.secho(f"\n{len(DEMO)} Rechnungen in {ziel_pfad}", fg=typer.colors.GREEN, bold=True)


def _demo_yaml(eintrag: dict) -> str:
    import json

    def t(wert: str) -> str:
        """Doppelte Anfuehrungszeichen: Beschreibungen enthalten Doppelpunkte und Kommas."""
        return json.dumps(wert, ensure_ascii=False)

    zeilen = [
        f"kunde: {eintrag['kuerzel']}",
        "datum: 2026-06-17",
        "leistungsdatum: 2026-06-10",
        f"sprache: {eintrag['sprache']}",
    ]
    taetigkeit, einordnung, ort = eintrag["leistung"]
    zeilen += ["leistung:", f"  taetigkeit: {t(taetigkeit)}", f"  einordnung: {einordnung}"]
    if ort:
        zeilen.append(f"  ort: {ort}")
    zeilen += [
        "positionen:",
        f"  - beschreibung: {t(eintrag['beschreibung'])}",
        f"    menge: {eintrag['menge']}",
        f"    einheit: {eintrag['einheit']}",
        f"    einzelpreis: {eintrag['einzelpreis']}",
    ]
    if "zweite" in eintrag:
        beschreibung, menge, einheit, preis = eintrag["zweite"]
        zeilen += [
            f"  - beschreibung: {t(beschreibung)}",
            f"    menge: {menge}",
            f"    einheit: {einheit}",
            f"    einzelpreis: {preis}",
            "belege:",
            "  - datei: flug.pdf",
            f"    text: {t('Flight receipt FRA-LON-FRA (position 2)')}",
        ]
    return "\n".join(zeilen) + "\n"


if __name__ == "__main__":
    app()
