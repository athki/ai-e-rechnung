"""Kommandozeile `rechnung`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer

from rechnung import (
    anschreiben as anschreiben_mod,
    begruendung as begruendung_mod,
    config,
    doctor as doctor_mod,
    festschreiben as festschreiben_mod,
    meldung,
    preise as preise_mod,
    pruefen as pruefen_mod,
    render as render_mod,
    resolve as resolve_mod,
    rules,
    sicht,
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
    typer.secho(sicht.abbruch(e) if sicht.aktiv() else str(e), fg=typer.colors.RED, err=True)
    return typer.Exit(1)


def _eingabe(text: str) -> meldung.Fehler:
    """Fehler in einem Argument, das die AI selbst übergibt: Art `eingabe`, die Meldung bleibt ganz."""
    return meldung.Fehler(text, art=meldung.EINGABE, geschwaerzt=text)


def _pfad(p: Path, cfg: config.Config | None = None) -> str:
    """Pfad für die Ausgabe; unter dem Schalter ohne den Namen der Gewerbe-Wurzel."""
    return sicht.pfad(p, cfg) if sicht.aktiv() else str(p)


def _geld(betrag: Decimal, waehrung: str) -> str:
    text = f"{betrag:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"{text} {waehrung}"


@app.command()
def mcp(
    kunde: Annotated[str, typer.Option(
        "--kunde", envvar="RECHNUNG_MCP_KUNDE",
        help="Kunde fest wählen (Kürzel); `neu` fragt dann nicht. Für eine Demo mit einem Profil.")] = "",
    preise_im_client: Annotated[bool, typer.Option(
        "--preise-im-client", envvar="RECHNUNG_MCP_PREISE_IM_CLIENT",
        help="Preise per Formular im Client bestätigen (Elicitation), nicht nur im Terminal.")] = False,
) -> None:
    """MCP-Server über stdio: das Werkzeug für eine AI, immer geschwärzt. Braucht das Extra `mcp`."""
    try:
        from rechnung import mcp_server
    except ImportError as e:
        typer.secho("Der MCP-Server braucht das Extra `mcp`: uv sync --extra mcp "
                    "bzw. pip install 'ai-e-rechnung[mcp]'", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    mcp_server.starten(mcp_server.Einstellungen(kunde=kunde or None, preise_im_client=preise_im_client))


@app.command()
def doctor() -> None:
    """Prüft Python, LaTeX, pdftotext, Fonts, Config, Gewerbe-Ordner und Docker."""
    pruefungen = doctor_mod.alle()
    breite = max(len(p.name) for p in pruefungen)
    for p in pruefungen:
        detail = sicht.kurz(p.detail) if sicht.aktiv() else p.detail
        typer.echo(f" {SYMBOL[p.status]} {p.name.ljust(breite)}  {detail}")
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
    beispiel: Annotated[bool, typer.Option(
        "--beispiel", help="Zusätzlich die erfundenen Beispiel-Stammdaten (Aussteller, sechs Kunden, Preisliste) "
                           "kopieren – zum Ausprobieren. Überschreibt nichts.")] = False,
) -> None:
    """Legt unter der Gewerbe-Wurzel die Ordner an, die das Werkzeug besitzt. Rührt sonst nichts an."""
    cfg = _config()
    try:
        ergebnis = config.init(cfg)
    except config.ConfigFehler as e:
        raise _abbruch(e) from e
    assert cfg.gewerbe is not None
    typer.echo(f"Gewerbe-Wurzel: {_pfad(cfg.gewerbe, cfg)}")
    for pfad, neu_angelegt in ergebnis:
        typer.echo(f"  {'angelegt ' if neu_angelegt else 'vorhanden'}  {pfad.relative_to(cfg.gewerbe)}/")
    if stammdaten or beispiel:
        try:
            dateien = config.beispiel_stammdaten(cfg) if beispiel else config.stammdaten_geruest(cfg)
        except config.ConfigFehler as e:
            raise _abbruch(e) from e
        for ziel, neu_angelegt in dateien:
            typer.echo(f"  {'angelegt ' if neu_angelegt else 'vorhanden'}  {ziel.relative_to(cfg.gewerbe)}")
        if beispiel:
            typer.echo("\nErfundene Beispieldaten zum Ausprobieren, z. B. mit `rechnung mcp`.")
        elif any(neu_angelegt for _, neu_angelegt in dateien):
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
        raise _abbruch(_eingabe(f"Datum muss JJJJ-MM-TT sein: {e}")) from e
    if sprache and sprache not in config.SPRACHEN:
        raise _abbruch(_eingabe(f"sprache muss eine von {config.SPRACHEN} sein"))
    if waehrung and waehrung not in config.WAEHRUNGEN:
        raise _abbruch(_eingabe(f"waehrung muss eine von {config.WAEHRUNGEN} sein"))
    if einordnung and einordnung not in rules.EINORDNUNGEN:
        raise _abbruch(_eingabe(f"einordnung muss eine von {', '.join(rules.EINORDNUNGEN)} sein"))
    try:
        ordner, nummer = resolve_mod.neu(
            cfg, kunde, leistung, rechnungsdatum, sprache or None, waehrung or None,
            taetigkeit or None, einordnung or None, ort or None,
        )
    except (resolve_mod.ResolveFehler, config.ConfigFehler, rules.RegelFehler) as e:
        raise _abbruch(e) from e
    typer.secho(f"Rechnung {nummer} angelegt", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  {_pfad(ordner / resolve_mod.INPUT_DATEI, cfg)}")
    if leistung is None:
        typer.secho("  leistungsdatum ist noch leer – Pflicht, in rechnung.yaml eintragen.",
                    fg=typer.colors.YELLOW)
    if not (taetigkeit and einordnung):
        typer.secho("  leistung: ist noch unvollständig – Pflicht, in rechnung.yaml eintragen.",
                    fg=typer.colors.YELLOW)
    typer.echo(f"\nAusfüllen, dann: rechnung resolve {nummer}")


PREISE_TEXT = {
    preise_mod.BESTAETIGT: "bestätigt",
    preise_mod.FEHLEN: "fehlen – der Mensch bestätigt sie im eigenen Terminal: rechnung preise {nr}",
    preise_mod.VERALTET: "veraltet (Positionen oder Währung geändert) – der Mensch bestätigt sie neu: "
                         "rechnung preise {nr}",
}


def _zeige_geschwaerzt(s: dict, ziel: Path | None, cfg: config.Config) -> None:
    """Was die AI vom Ergebnis sieht (sicht.ergebnis, sicht.entwurf): kein Name, kein Land des Kunden,
    kein Betrag."""
    typer.secho(f"Rechnung {s['nummer']}  (geschwärzt)", bold=True)
    typer.echo(f"  Kunde           {s['kunde']}")
    typer.echo(f"  Datum           {s['datum']}  ·  Leistung {s['leistungsdatum']}"
               + (f" bis {s['leistungsdatum_bis']}" if s["leistungsdatum_bis"] else ""))
    typer.echo(f"  Sprache         {s['sprache']}")
    typer.echo(f"  Leistung        {s['leistung']['taetigkeit']}")
    typer.echo(f"                  {s['leistung']['einordnung']}"
               + (f", erbracht: {s['leistung']['ort']}" if s["leistung"]["ort"] else ""))
    typer.echo(f"  Leistungsort    {s['leistungsort']}{' (manuell festgelegt)' if s['leistungsort_manuell'] else ''}")
    typer.echo(f"  Ergebnis        {s['ergebnis']}")
    typer.echo(f"  Regeln          {' '.join(s['regeln'])}  (RULES.md)")
    typer.echo()
    for p in s["positionen"]:
        typer.echo(f"  {p['pos']}  {p['beschreibung']}  [{p['kuerzel']}]")
        typer.echo(f"     {p['menge']} {p['einheit']}   ({p['steuersatz']} %)")
    for beleg in s["belege"]:
        typer.echo(f"  Beleg: {beleg}")
    _zeige_preise(s["preise"], s["nummer"])
    typer.echo("  Preise und Beträge sind geschwärzt.")
    for warnung in s["warnungen"]:
        typer.secho(f"\n  Achtung: {warnung}", fg=typer.colors.YELLOW)
    if ziel is not None:
        typer.echo(f"\n  geschrieben: {sicht.pfad(ziel, cfg)}")


def _zeige_preise(stand: str, nummer: str) -> None:
    farbe = typer.colors.GREEN if stand == preise_mod.BESTAETIGT else typer.colors.YELLOW
    typer.secho(f"\n  Preise          {PREISE_TEXT[stand].format(nr=nummer)}", fg=farbe)


def _zeige_entwurf(e: resolve_mod.Entwurf, cfg: config.Config) -> None:
    """Vor der Bestätigung der Preise: was feststeht, ohne Beträge; resolved.json wird nicht geschrieben."""
    if sicht.aktiv():
        _zeige_geschwaerzt(sicht.entwurf(e), None, cfg)
        return
    typer.secho(f"Rechnung {e.nummer}", bold=True)
    typer.echo(f"  Kunde           {e.kunde.firma} ({e.kunde.land})")
    typer.echo(f"  Datum           {e.datum}  ·  Leistung {e.eingabe.leistungsdatum}"
               + (f" bis {e.eingabe.leistungsdatum_bis}" if e.eingabe.leistungsdatum_bis else ""))
    typer.echo(f"  Leistung        {e.eingabe.leistung.taetigkeit}")
    typer.echo(f"  Leistungsort    {e.entscheidung.ort.land}")
    typer.echo(f"  Ergebnis        {e.entscheidung.ergebnis}")
    typer.echo()
    for p in e.positionen:
        typer.echo(f"  {p.pos}  {p.beschreibung}  [{p.kuerzel}]")
        typer.echo(f"     {p.menge} {p.einheit}")
    _zeige_preise(e.preise, e.nummer)
    for warnung in e.warnungen:
        typer.secho(f"\n  Achtung: {warnung}", fg=typer.colors.YELLOW)


def _zeige(r: Resolved, ziel: Path, cfg: config.Config) -> None:
    if sicht.aktiv():
        _zeige_geschwaerzt(sicht.ergebnis(r), ziel, cfg)
        return
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
    typer.echo(f"  Regeln          {' '.join(r.regeln)}  (RULES.md)")
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
    """Löst rechnung.yaml auf: Leistungsort, Ergebnis, Stand der Preise; mit bestätigten Preisen auch
    Summen und Fälligkeit, dann schreibt es rechnung.resolved.json."""
    cfg = _config()
    try:
        entwurf = resolve_mod.entwurf(cfg, nummer)
        if entwurf.preise != preise_mod.BESTAETIGT:
            _zeige_entwurf(entwurf, cfg)
            return
        ergebnis, ziel = resolve_mod.resolve(cfg, nummer)
    except (resolve_mod.ResolveFehler, config.ConfigFehler, rules.RegelFehler) as e:
        raise _abbruch(e) from e
    _zeige(ergebnis, ziel, cfg)


@app.command()
def bauen(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer, z. B. 2026-0001")],
    still: Annotated[bool, typer.Option("--still", help="Nur den Pfad der PDF ausgeben.")] = False,
    pro_forma: Annotated[bool, typer.Option(
        "--pro-forma", help="Pro forma statt Rechnung bauen (Arbeitskopie, wird überschrieben).")] = False,
) -> None:
    """Löst die Rechnung auf und baut daraus die PDF. Gebaut wird in einem Temp-Verzeichnis."""
    cfg = _config()
    try:
        ordner_vorab = resolve_mod.finde_ordner(cfg, nummer)
        if festschreiben_mod.ist_festgeschrieben(ordner_vorab):
            raise festschreiben_mod.FestschreibFehler(
                f"Rechnung {ordner_vorab.name} ist festgeschrieben und wird nicht neu gebaut.\n"
                f"Für eine Korrektur: Stornorechnung und neue Rechnung.",
                art=meldung.AUSSERHALB,
                geschwaerzt=f"Rechnung {ordner_vorab.name} ist festgeschrieben und wird nicht neu gebaut.",
            )
        ergebnis, json_ziel = resolve_mod.resolve(cfg, nummer)
        ordner = json_ziel.parent
        pdf = render_mod.baue_pdf(ergebnis, ordner, cfg.engine, belege_quelle=ordner / "belege",
                                  eigene=cfg.vorlage, pro_forma=pro_forma)
    except (resolve_mod.ResolveFehler, render_mod.RenderFehler, config.ConfigFehler,
            rules.RegelFehler, festschreiben_mod.FestschreibFehler) as e:
        raise _abbruch(e) from e
    if still:
        typer.echo(_pfad(pdf, cfg))
        return
    _zeige(ergebnis, json_ziel, cfg)
    typer.secho(f"\n  {'Pro forma' if pro_forma else 'PDF'}: {_pfad(pdf, cfg)}", fg=typer.colors.GREEN, bold=True)
    if pro_forma:
        typer.echo(f"  Nach dem Versand: rechnung pro-forma {ordner.name} --gesendet-am JJJJ-MM-TT")


def _ordner_oder_nummer(cfg: config.Config, wert: str) -> Path:
    """Akzeptiert eine Rechnungsnummer oder direkt den Pfad eines Rechnungsordners."""
    kandidat = Path(wert)
    if kandidat.is_dir() and (kandidat / resolve_mod.RESOLVED_DATEI).is_file():
        return kandidat
    return resolve_mod.finde_ordner(cfg, wert)


@app.command()
def pruefen(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer oder Pfad eines Rechnungsordners")],
    pro_forma: Annotated[bool, typer.Option(
        "--pro-forma", help="Die Arbeitskopie der Pro forma prüfen statt der Rechnung.")] = False,
) -> None:
    """Weist im Text der fertigen PDF nach, dass alle Pflichtangaben enthalten sind."""
    import json

    from rechnung.models import Resolved

    cfg = _config()
    try:
        ordner = _ordner_oder_nummer(cfg, nummer)
        ergebnis = Resolved.model_validate(
            json.loads((ordner / resolve_mod.RESOLVED_DATEI).read_text(encoding="utf-8")))
        liste = pruefen_mod.pruefe(ergebnis, pruefen_mod.pdf_pfad(ordner, ergebnis, pro_forma), pro_forma)
    except (resolve_mod.ResolveFehler, pruefen_mod.PruefFehler, config.ConfigFehler, OSError) as e:
        raise _abbruch(e) from e

    breite = max(len(b.angabe) for b in liste)
    for b in liste:
        zeichen = SYMBOL[doctor_mod.OK if b.gefunden else doctor_mod.FEHLER]
        if b.gefunden:
            zusatz = ""
        elif sicht.aktiv():
            zusatz = f"   ({b.paragraf} UStG; der gesuchte Text ist geschwärzt)"
        else:
            zusatz = f"   gesucht: {b.gesucht!r}  ({b.paragraf} UStG)"
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
def begruendung(
    nummer: Annotated[str, typer.Argument(
        help="Rechnungsnummer oder Pfad eines Rechnungsordners, auch einer Pro-forma-Revision (pro-forma/<n>)")],
) -> None:
    """Begründung der Steuerentscheidung für Prüfer, als Markdown: Fakten, Regeln der Spur mit Status und
    Nachweis, was bewiesen, getestet und angenommen ist.

    Entscheidet nichts; liest rechnung.resolved.json und RULES.md. Rot (Exit 1), wenn die Spur in der
    Datei nicht zu dem passt, was das Werkzeug heute auf denselben Fakten entscheidet.
    """
    cfg = _config()
    try:
        ordner = _ordner_oder_nummer(cfg, nummer)
        text, spur_passt = begruendung_mod.begruende(ordner, geschwaerzt=sicht.aktiv())
    except (resolve_mod.ResolveFehler, begruendung_mod.BegruendungFehler, config.ConfigFehler, OSError) as e:
        raise _abbruch(e) from e
    typer.echo(text, nl=False)
    if not spur_passt:
        raise typer.Exit(1)


def _ja(text: str, standard: bool) -> bool:
    """Ja/Nein auf Deutsch: j, ja, n, nein (y und yes gehen auch); Enter nimmt den Standard."""
    while True:
        eingabe = typer.prompt(f"{text} [{'J/n' if standard else 'j/N'}]", default="", show_default=False)
        wert = eingabe.strip().lower()
        if not wert:
            return standard
        if wert in ("j", "ja", "y", "yes"):
            return True
        if wert in ("n", "nein", "no"):
            return False
        typer.secho("    j oder n", fg=typer.colors.YELLOW)


def _frage_preis(text: str, vorschlag: Decimal | None) -> Decimal:
    while True:
        eingabe = typer.prompt(text, default=str(rules.mindestens_zwei(vorschlag)) if vorschlag is not None else None)
        wert = preise_mod.betrag(str(eingabe))
        if wert is not None:
            return wert
        typer.secho("    Ein Betrag, z. B. 900 oder 287,30.", fg=typer.colors.YELLOW)


@app.command()
def preise(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer, z. B. 2026-0001")],
    aus_liste: Annotated[bool, typer.Option(
        "--aus-liste", help="Ohne Rückfrage die Preise der Liste übernehmen (für Skripte). Verweigert bei "
                            "Auslagen und in Fremdwährung.")] = False,
    referenz: Annotated[str | None, typer.Option(
        help="Referenz des Kunden für diese Rechnung (Bestellnummer); '-' entfernt sie.")] = None,
) -> None:
    """Preise bestätigen – nur der Mensch, im eigenen Terminal.

    Zeigt jede Position mit dem Preis aus der Liste als Vorschlag; Enter übernimmt ihn, eine Zahl
    ersetzt ihn. Auslagen sind leer. 7 % wird nur angeboten, wo das Werkzeug es für diese Rechnung
    erlaubt. Hält die Preise in rechnung.privat.yaml fest; ändert sich danach eine Position, sind sie
    veraltet, und `bauen` baut nichts.
    """
    if sicht.aktiv():
        text = (f"`rechnung preise` läuft nur ohne RECHNUNG_GESCHWAERZT, im eigenen Terminal des Menschen – "
                f"sonst stünden die Preise im Chat. Der Mensch ruft auf: rechnung preise {nummer}")
        raise _abbruch(meldung.Fehler(text, art=meldung.PREISE, geschwaerzt=text))
    cfg = _config()
    try:
        entwurf = resolve_mod.entwurf(cfg, nummer)
        if festschreiben_mod.ist_festgeschrieben(entwurf.ordner):
            raise festschreiben_mod.FestschreibFehler(
                f"Rechnung {entwurf.nummer} ist festgeschrieben; ihre Preise ändern sich nicht mehr.",
                art=meldung.AUSSERHALB)
    except (resolve_mod.ResolveFehler, config.ConfigFehler, rules.RegelFehler,
            festschreiben_mod.FestschreibFehler) as e:
        raise _abbruch(e) from e

    typer.secho(f"Preise für Rechnung {entwurf.nummer}", bold=True)
    typer.echo(f"  Kunde      {entwurf.kunde.firma} ({entwurf.kunde.land})")
    typer.echo(f"  Ergebnis   {entwurf.entscheidung.ergebnis}, Satz {entwurf.entscheidung.satz} %")
    typer.echo(f"  Währung    {entwurf.waehrung}"
               + ("" if entwurf.waehrung == preise_mod.LISTENWAEHRUNG else
                  f"  – die Liste gilt in {preise_mod.LISTENWAEHRUNG}, nichts vorgeschlagen"))
    typer.echo(f"  Stand      {PREISE_TEXT[entwurf.preise].format(nr=entwurf.nummer)}\n")

    # Wer neu bestätigt, sieht zuerst, was er zuletzt für dieselbe Position bestätigt hat.
    alt = {i: p for i, p in enumerate(entwurf.privat.positionen)}
    einzelpreise: list[Decimal] = []
    ermaessigt: list[bool] = []
    for i, p in enumerate(entwurf.positionen):
        vorher = alt.get(i) if alt.get(i) and alt[i].kuerzel == p.kuerzel else None
        vorschlag = vorher.einzelpreis if vorher else p.vorschlag
        art = ", Auslage" if p.art == "auslage" else ""
        typer.echo(f"  {p.pos}  {p.beschreibung}  ({p.menge} {p.einheit}, {p.kuerzel}{art})")
        if aus_liste:
            if p.vorschlag is None:
                text = (f"Position {p.pos} ({p.kuerzel}) hat keinen Preis in der Liste – Auslage oder Fremdwährung. "
                        f"Ohne --aus-liste eingeben.")
                raise _abbruch(meldung.Fehler(text, art=meldung.PREISE, geschwaerzt=text))
            preis = p.vorschlag
            typer.echo(f"     Einzelpreis {preis}")
        else:
            preis = _frage_preis("     Einzelpreis", vorschlag)
        sieben = False
        if p.sieben_erlaubt:
            standard = (vorher.steuersatz is not None) if vorher else p.vorschlag_sieben
            sieben = standard if aus_liste else _ja("     7 % (ermäßigt, § 12 Abs. 2 UStG)?", standard)
        einzelpreise.append(preis)
        ermaessigt.append(sieben)

    neue_referenz: str | None
    if referenz is not None:
        neue_referenz = None if referenz.strip() in ("", "-") else referenz.strip()
    elif aus_liste:
        neue_referenz = entwurf.privat.referenz
    else:
        standard = entwurf.kunde.referenz
        hinweis = f" (Enter: keine eigene, es gilt die der Kundendatei: {standard})" if standard else " (Enter: keine)"
        eingabe = typer.prompt(f"\n  Referenz des Kunden für diese Rechnung{hinweis}; '-' entfernt sie",
                               default=entwurf.privat.referenz or "", show_default=bool(entwurf.privat.referenz))
        neue_referenz = None if eingabe.strip() in ("", "-") else eingabe.strip()

    # Zur Kontrolle rechnet das Werkzeug mit den Preisen, bevor es sie festhält.
    from dataclasses import replace
    from rechnung.models import Privat, PrivatPosition
    kandidat = Privat(
        referenz=neue_referenz, waehrung=entwurf.waehrung, positionen_hash=entwurf.positionen_hash,
        positionen=[PrivatPosition(kuerzel=p.kuerzel, einzelpreis=preis, steuersatz=Decimal(7) if sieben else None)
                    for p, preis, sieben in zip(entwurf.positionen, einzelpreise, ermaessigt)],
    )
    try:
        probe = resolve_mod.rechne(replace(entwurf, privat=kandidat, preise=preise_mod.BESTAETIGT))
    except (resolve_mod.ResolveFehler, rules.RegelFehler) as e:
        raise _abbruch(e) from e
    typer.echo()
    for rp in probe.positionen:
        typer.echo(f"  {rp.pos}  {rp.menge} × {_geld(rp.einzelpreis, probe.waehrung)}"
                   f"  =  {_geld(rp.zeilensumme, probe.waehrung)}   ({rp.steuersatz} %)")
    typer.echo(f"  Netto      {_geld(probe.netto, probe.waehrung)}")
    for g in probe.steuergruppen:
        typer.echo(f"  USt {g.satz} %{'':<4}{_geld(g.betrag, probe.waehrung)}")
    typer.secho(f"  Brutto     {_geld(probe.brutto, probe.waehrung)}", bold=True)
    if probe.referenz:
        typer.echo(f"  Referenz   {probe.referenz}")

    if not aus_liste and not _ja("\n  Bestätigen?", False):
        typer.echo("  Nichts geändert.")
        raise typer.Exit(1)
    try:
        preise_mod.bestaetigen(entwurf, einzelpreise, ermaessigt, referenz=neue_referenz)
    except preise_mod.PreisFehler as e:
        raise _abbruch(e) from e
    typer.secho(f"\n  Preise bestätigt: {preise_mod.PRIVAT_DATEI}", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  Weiter: rechnung bauen {entwurf.nummer}")


@app.command()
def preisliste() -> None:
    """Zeigt die Preisliste: Kürzel, Einheit, Art, Bezeichnung – unter dem Schalter ohne Preise."""
    cfg = _config()
    try:
        liste = resolve_mod.lade_preisliste(cfg)
    except (resolve_mod.ResolveFehler, config.ConfigFehler) as e:
        raise _abbruch(e) from e
    geschwaerzt = sicht.aktiv()
    breite = max((len(k) for k in liste), default=6)
    for kuerzel, e in liste.items():
        bezeichnung = " / ".join(dict.fromkeys(e.bezeichnung.values()))
        preis = "" if geschwaerzt or e.preis is None else f"  {_geld(e.preis, preise_mod.LISTENWAEHRUNG)}"
        sieben = "  7 % vorgeschlagen" if e.steuersatz is not None else ""
        typer.echo(f"  {kuerzel.ljust(breite)}  {e.einheit:<9}  {e.art:<8}  {bezeichnung}{preis}{sieben}")
    if geschwaerzt:
        typer.echo("\n  Preise sind geschwärzt.")


@app.command()
def offen() -> None:
    """Listet alle Rechnungen, die noch nicht festgeschrieben sind, und was ihnen fehlt."""
    cfg = _config()
    try:
        wurzel = cfg.ordner("ausgang")
    except config.ConfigFehler as e:
        raise _abbruch(e) from e
    ordner_liste = [o for o in sorted(wurzel.glob("*/*")) if (o / resolve_mod.INPUT_DATEI).is_file()
                    and not festschreiben_mod.ist_festgeschrieben(o)]
    if not ordner_liste:
        typer.echo("Keine offenen Rechnungen.")
        return
    for ordner in ordner_liste:
        try:
            e = resolve_mod.entwurf_aus(cfg, ordner)
        except (resolve_mod.ResolveFehler, rules.RegelFehler, config.ConfigFehler) as f:
            text = sicht.abbruch(f) if sicht.aktiv() else str(f)
            typer.echo(f" {SYMBOL[doctor_mod.FEHLER]} {ordner.name}")
            for zeile in text.splitlines():
                typer.echo(f"     {zeile}")
            continue
        if e.preise != preise_mod.BESTAETIGT:
            typer.echo(f" {SYMBOL[doctor_mod.WARNUNG]} {ordner.name}  Preise {e.preise}: rechnung preise {ordner.name}")
        else:
            typer.echo(f" {SYMBOL[doctor_mod.OK]} {ordner.name}  bereit: rechnung bauen {ordner.name}")


@app.command()
def anschreiben(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer, z. B. 2026-0001")],
) -> None:
    """Setzt die Werte in anschreiben.md ein und gibt den Text aus; verschickt nichts.

    Den Entwurf mit Platzhaltern ([nummer], [brutto], [anrede] …) schreibt die AI in den Rechnungsordner.
    Unter RECHNUNG_GESCHWAERZT prüft der Befehl nur die Platzhalter; eingesetzt wird im eigenen Terminal.
    """
    import json

    cfg = _config()
    try:
        ordner = resolve_mod.finde_ordner(cfg, nummer)
        text = anschreiben_mod.lesen(ordner)
        namen = anschreiben_mod.platzhalter(text)
        if sicht.aktiv():
            typer.secho(f"{anschreiben_mod.DATEI} ist gültig.", fg=typer.colors.GREEN, bold=True)
            typer.echo(f"  Platzhalter: {', '.join(f'[{n}]' for n in namen) or '(keine)'}")
            typer.echo(f"  Eingesetzt wird im eigenen Terminal des Menschen: rechnung anschreiben {ordner.name}")
            return
        resolved = ordner / resolve_mod.RESOLVED_DATEI
        r = Resolved.model_validate(json.loads(resolved.read_text(encoding="utf-8"))) if resolved.is_file() else None
        if (r is None or r.input_hash != resolve_mod.input_hash(ordner)
                or r.privat_hash != resolve_mod.privat_hash(ordner)):
            raise anschreiben_mod.AnschreibenFehler(
                f"Rechnung {ordner.name} ist nicht auf dem Stand von rechnung.yaml und den Preisen – "
                f"erst `rechnung bauen {ordner.name}`.")
        typer.echo(anschreiben_mod.einsetzen(text, r), nl=False)
    except (resolve_mod.ResolveFehler, anschreiben_mod.AnschreibenFehler, config.ConfigFehler) as e:
        raise _abbruch(e) from e


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
        raise _abbruch(_eingabe(f"--gesendet-am muss JJJJ-MM-TT sein: {e}")) from e
    if gesendet > date.today():
        raise _abbruch(_eingabe(
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


@app.command("pro-forma")
def pro_forma(
    nummer: Annotated[str, typer.Argument(help="Rechnungsnummer, z. B. 2026-0001")],
    gesendet_am: Annotated[str, typer.Option(
        "--gesendet-am",
        help="Tag, an dem die Pro forma an den Kunden ging (JJJJ-MM-TT). Pflicht.")],
) -> None:
    """Friert die zuletzt gebaute Pro forma als nächste Revision ein (pro-forma/<n>/).

    Die Pro forma ist keine Rechnung: Sie geht an den Kunden zur Prüfung. Das Werkzeug verschickt
    nichts – es hält fest, was du verschickt hast, mit PDF und den Daten, aus denen sie entstand.
    """
    cfg = _config()
    try:
        gesendet = date.fromisoformat(gesendet_am)
    except ValueError as e:
        raise _abbruch(_eingabe(f"--gesendet-am muss JJJJ-MM-TT sein: {e}")) from e
    if gesendet > date.today():
        raise _abbruch(_eingabe(f"--gesendet-am liegt in der Zukunft ({gesendet})."))
    try:
        ordner = resolve_mod.finde_ordner(cfg, nummer)
        eintrag = festschreiben_mod.pro_forma_festhalten(ordner, gesendet)
    except (resolve_mod.ResolveFehler, festschreiben_mod.FestschreibFehler, config.ConfigFehler) as e:
        raise _abbruch(e) from e
    typer.secho(f"Pro forma {ordner.name}, Revision {eintrag['revision']} festgehalten",
                fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  gesendet am  {eintrag['gesendet_am']}")
    for datei in eintrag["hash"]:
        typer.echo(f"  {datei}")
    typer.echo("  Schreibgeschützt; die Hashes stehen in status.yaml, `rechnung pruefen` vergleicht sie.")


# Die Demo baut je Ergebnis mindestens eine Rechnung aus stammdaten.example/. Positionen tragen Kürzel
# aus stammdaten.example/preise.yaml; die Demo bestätigt die Preise selbst, wie es ein Mensch mit
# `rechnung preise` täte – mit dem Listenpreis, wo `preise` nichts anderes sagt.
DEMO: list[dict] = [
    {"kuerzel": "muster-gmbh", "sprache": "de",
     "leistung": ("Beratung zum Marktzugang mit Workshop", "beratung", None),
     "positionen": [("beratung", "8", "stunde", "Beratung Marktzugang, Workshop in Berlin")]},
    {"kuerzel": "exemple-sarl", "sprache": "en",
     "leistung": ("Policy briefing for the management team", "beratung", None),
     "positionen": [("briefing", "1", "pauschal", "Policy briefing, Paris")]},
    {"kuerzel": "sample-ltd", "sprache": "en",
     "leistung": ("Panel participation at a policy forum", "unterrichtend", "GB"),
     "positionen": [("panel", "2", "stunde", "Panel participation, Sample Policy Forum, London"),
                    ("flug", "1", "pauschal", "Travel: flight FRA--LON--FRA, receipt attached")],
     "preise": {"flug": "287.30"},
     "beleg": ("flug.pdf", "Flight receipt FRA-LON-FRA (position 2)"),
     # Vorher zwei Pro-forma-Revisionen; die zweite ergänzt die Referenz, die der Kunde nachgereicht hat.
     "pro_forma": [("2026-06-11", None), ("2026-06-15", "PO 4711")]},
    {"kuerzel": "privat-ch", "sprache": "de",
     "leistung": ("Vortrag vor Publikum", "unterrichtend", "CH"),
     "positionen": [("vortrag", "2", "stunde", "Vortrag, Zürich")]},
    {"kuerzel": "privat-de", "sprache": "de",
     "leistung": ("Bewerbungscoaching", "beratung", None),
     "positionen": [("coaching", "2", "stunde", "Bewerbungscoaching, zwei Sitzungen")]},
    # Derselbe Aussteller als Kleinunternehmer (§ 19 UStG): die Demo setzt es nur für diese Rechnung.
    {"kuerzel": "muster-gmbh", "sprache": "de", "kleinunternehmer": True,
     "leistung": ("Beratung zum Marktzugang", "beratung", None),
     "positionen": [("beratung", "4", "stunde", "Beratung Marktzugang")],
     "preise": {"beratung": "120.00"}},
]


def _demo_preise(demo_cfg: config.Config, nummer: str, eintrag: dict) -> None:
    """Bestätigt die Preise der Demo-Rechnung: Listenpreis oder der Wert aus `preise`."""
    entwurf = resolve_mod.entwurf(demo_cfg, nummer)
    eigene = eintrag.get("preise", {})
    einzelpreise = [Decimal(eigene[p.kuerzel]) if p.kuerzel in eigene else p.vorschlag for p in entwurf.positionen]
    assert all(preis is not None for preis in einzelpreise), "Demo: Auslage ohne Preis"
    preise_mod.bestaetigen(entwurf, einzelpreise, [p.vorschlag_sieben for p in entwurf.positionen])  # type: ignore[arg-type]


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
        ich = gewerbe / "stammdaten" / "ich.yaml"
        ich_text = ich.read_text(encoding="utf-8")
        for eintrag in DEMO:
            ich.write_text(ich_text + ("kleinunternehmer: true\n" if eintrag.get("kleinunternehmer") else ""),
                           encoding="utf-8")
            try:
                ordner, nummer = resolve_mod.neu(
                    demo_cfg, eintrag["kuerzel"], date(2026, 6, 10), date(2026, 6, 17), eintrag["sprache"]
                )
                (ordner / resolve_mod.INPUT_DATEI).write_text(_demo_yaml(eintrag), encoding="utf-8")
                if "beleg" in eintrag:
                    shutil.copy2(config.REPO / "vorlage" / "attachments" / "sample-receipt.pdf",
                                 ordner / "belege" / eintrag["beleg"][0])
                _demo_preise(demo_cfg, nummer, eintrag)
                for gesendet, referenz in eintrag.get("pro_forma", []):
                    if referenz:
                        preise_mod.referenz_setzen(resolve_mod.entwurf(demo_cfg, nummer), referenz)
                    ergebnis, _ = resolve_mod.resolve(demo_cfg, nummer)
                    render_mod.baue_pdf(ergebnis, ordner, cfg.engine, belege_quelle=ordner / "belege",
                                        eigene=demo_cfg.vorlage, pro_forma=True)
                    festschreiben_mod.pro_forma_festhalten(ordner, date.fromisoformat(gesendet))
                ergebnis, json_ziel = resolve_mod.resolve(demo_cfg, nummer)
                pdf = render_mod.baue_pdf(ergebnis, ordner, cfg.engine, belege_quelle=ordner / "belege",
                                          eigene=demo_cfg.vorlage)
            except (resolve_mod.ResolveFehler, render_mod.RenderFehler, rules.RegelFehler,
                    config.ConfigFehler, festschreiben_mod.FestschreibFehler, preise_mod.PreisFehler) as e:
                raise _abbruch(e) from e
            # Der ganze Rechnungsordner wandert ins Ziel, nicht nur die PDF: damit kann
            # `rechnung pruefen <ordner>` die Demo-Rechnungen nachträglich prüfen.
            name = f"{ergebnis.ergebnis.replace('_', '-')}-{eintrag['kuerzel']}"
            zielordner = ziel_pfad / name
            if zielordner.exists():
                festschreiben_mod.schreibbar_machen(zielordner)
                shutil.rmtree(zielordner)
            shutil.copytree(ordner, zielordner)
            betrag = "" if sicht.aktiv() else f"  ({ergebnis.waehrung} {ergebnis.brutto})"
            typer.echo(f" {SYMBOL[doctor_mod.OK]} {name}/{pdf.name}{betrag}")
            if pruefe:
                befunde = pruefen_mod.pruefe(ergebnis, zielordner / pdf.name)
                fehlend = [b for b in befunde if not b.gefunden]
                zeichen = SYMBOL[doctor_mod.FEHLER if fehlend else doctor_mod.OK]
                typer.echo(f"   {zeichen} pruefen: {len(befunde) - len(fehlend)}/{len(befunde)} Pflichtangaben"
                           + ("" if not fehlend else "  fehlt: " + ", ".join(b.angabe for b in fehlend)))
                if fehlend:
                    raise typer.Exit(1)
    typer.secho(f"\n{len(DEMO)} Rechnungen in {_pfad(ziel_pfad)}", fg=typer.colors.GREEN, bold=True)


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
    zeilen.append("positionen:")
    for kuerzel, menge, einheit, beschreibung in eintrag["positionen"]:
        zeilen += [
            f"  - kuerzel: {kuerzel}",
            f"    menge: {menge}",
            f"    einheit: {einheit}",
            f"    beschreibung: {t(beschreibung)}",
        ]
    if "beleg" in eintrag:
        datei, text = eintrag["beleg"]
        zeilen += ["belege:", f"  - datei: {datei}", f"    text: {t(text)}"]
    return "\n".join(zeilen) + "\n"


if __name__ == "__main__":
    app()
