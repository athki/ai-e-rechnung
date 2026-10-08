# ai-e-rechnung – Rechnungswerkzeug für ein deutsches Kleingewerbe

CLI und Python-Bibliothek, die aus einem kurzen YAML eine vollständige Rechnung als PDF erzeugt (LaTeX).
Deterministischer Kern, AI nur als Schicht darüber.

## Zwei Orte, strikt getrennt

**Repo (Code)** – dieses Verzeichnis. Enthält Bibliothek, CLI, LaTeX-Vorlage, Tests und vollständige
Beispiel-Stammdaten. Enthält NIE echte Stammdaten, echte Kunden oder echte Rechnungen.

**Gewerbe-Ordner (Daten)** – der Ordner für das Gewerbe, z. B. `~/Gewerbe`, außerhalb des
Repos. Ob er in Dropbox, iCloud oder nirgends synchronisiert liegt, ist dem Werkzeug egal. Das Werkzeug kennt
eine Wurzel (`gewerbe` in `~/.config/rechnung/config.toml` oder `RECHNUNG_GEWERBE`; Env gewinnt) und
darunter benannte Unterordner mit umbenennbaren Defaults (`stammdaten`, `kunden`, `ausgang`,
`steuerberater`). Nur diese fasst es an; alles andere im Gewerbe-Ordner gehört nicht dem Werkzeug. Enthält NIE
Code oder Build-Artefakte.

```
<gewerbe>/
  stammdaten/
    ich.yaml                 # Aussteller, einmal
    kunden/<kuerzel>.yaml    # ein Kunde pro Datei (Kundenstammdaten)
  rechnung-ausgang/JJJJ/<nummer>/
    rechnung.yaml            # Input (einzige Datei, die Menschen und AI schreiben)
    rechnung.resolved.json   # abgeleitet, eingefroren
    rechnung.pdf             # abgeleitet
    status.yaml              # nach dem Festschreiben: Status, Datum, Hashes
    belege/
  steuerberater/JJJJ/        # Export-Ziel
  rechnung-eingang/, bank/, vertraege/ …   # nicht Sache des Werkzeugs
```

Builds laufen in einem temporären Verzeichnis (`tempfile.mkdtemp()`); nur `rechnung.pdf` und
`rechnung.resolved.json` werden in den Rechnungsordner kopiert. Kein `.aux`, `.log`, `.tex` dort, nie.

Ohne Gewerbe-Wurzel läuft alles gegen `stammdaten.example/` im Repo (Demo-Modus).
`rechnung demo` baut daraus vier Beispielrechnungen (Steuerfall A–D) nach `./demo-output/` (gitignored).

## Pipeline

```
rechnung.yaml ──resolve()──▶ rechnung.resolved.json ──render()──▶ rechnung.pdf
```

- Alle Logik in `resolve.py` und `rules.py`. Das Template druckt nur Felder; keine Entscheidungen in LaTeX.
- Beträge als `Decimal`, Rundung `ROUND_HALF_UP` auf 2 Stellen, Währung Default EUR.
- Rechnungsnummer aus `nummer_format` in der Config (eine Option, das ganze Format, Default
  `{jahr}-{lfd:04d}`, z. B. auch `MM-{jahr}-{lfd:04d}`). Die laufende Nummer ist die höchste Ziffernfolge
  am Ende der Ordnernamen im Jahresordner plus eins – ein Formatwechsel zählt weiter. Kein Zähler-File.
  Der Ordnername ist die vollständige Rechnungsnummer.
- Währung `EUR`, `USD` oder `GBP`; Fremdwährung nur, wenn keine deutsche USt ausgewiesen wird (sonst
  wäre der Steuerbetrag zusätzlich in Euro anzugeben, § 16 Abs. 6 UStG – nicht gebaut, `resolve` bricht ab).
- Mengeneinheit je Position ist Pflicht (`pauschal`, `stunde`, `tag`, `stueck`, `kilometer`, gemappt auf
  UN/ECE Rec. 20). Kein Default im Modell; `rechnung neu` füllt `pauschal` sichtbar in die Datei vor.
- Leistungsdatum ist Pflicht und wird nie geraten. `rechnung neu --kunde <kuerzel>` lässt es in
  `rechnung.yaml` leer (`# PFLICHT: Tag der Leistung, JJJJ-MM-TT`), `resolve` bricht ab, bis es dasteht;
  `--leistungsdatum JJJJ-MM-TT` füllt es vor (für Skripte und AI).
- `resolved.json` enthält `vorlage_version` (Git-Short-Hash des Repos beim Build) und einen Hash des Inputs.
- `rechnung festschreiben <nr> --gesendet-am JJJJ-MM-TT` macht die Rechnung unveränderbar: Status
  `festgeschrieben`, PDF und resolved.json read-only, Hashes von yaml, resolved.json und PDF in
  `status.yaml`. `--gesendet-am` ist Pflicht – unveränderbar wird eine Rechnung, weil sie ausgestellt
  ist (§ 14 UStG), und das Werkzeug verschickt nichts, es hält nur fest, wann du verschickt hast.
  Vorher darf beliebig oft gebaut und geprüft werden. Danach verweigert `bauen` den Neubau, und
  `pruefen` meldet jede nachträgliche Änderung an den eingefrorenen Dateien.
- `rechnung pruefen <nr>` nimmt auch den Pfad eines Rechnungsordners – so prüft der Container die
  Demo-Rechnungen. `rechnung demo --pruefen` baut und prüft in einem Zug.

## Steuerfälle (`rules.py`) – Regelbesteuerung

| Fall | Bedingung | Satz | Hinweis |
| --- | --- | --- | --- |
| A | `kunde.land == "DE"` | 19 % (7 % je Position möglich) | keiner |
| B | Land in EU und `kunde.ustid` gesetzt | 0 % | „Steuerschuldnerschaft des Leistungsempfängers (§ 14a Abs. 5 UStG, Art. 196 MwStSystRL).“ bzw. die englische Fassung – beide USt-IdNrn. auf der Rechnung |
| C | Land nicht in EU und `kunde.unternehmer == true` | 0 % | „Leistungsort: {Land}. Die Leistung ist in Deutschland nicht steuerbar (§ 3a Abs. 2 UStG). / Place of supply: {Country}. Not subject to German VAT; the reverse charge may apply in the recipient's country.“ |
| D | sonst | 19 % | keiner; `resolve` **bricht ab** und nennt, was fehlt (meist `ustid` oder `unternehmer`), weil D fast immer ein Datenfehler ist. Freigabe nur über `steuerfall: D` plus `begruendung:` |

- Manueller Override `steuerfall:` im Input nur zusammen mit `begruendung:`; sonst Validierungsfehler.
- Kleinunternehmerregelung (§ 19 UStG) wird bewusst nicht unterstützt.
- EU-Länderliste als Konstante in `rules.py`, mit Kommentar und Datum.

## Vorlage (`vorlage/`)

LaTeX, pdflatex, neutral in Schwarz. Sie enthält keine Steuerlogik und druckt nur, was `resolve.py` liefert.

- `style/defaults.sty` – **alle** Stilentscheidungen: Schrift, Farben (Akzent Schwarz `#000000`, Grau `#C8C8C8`),
  Linienstärken, Positionen, Größen, Schalter. Änderungen am Aussehen gehören hierher, nie in `invoice.sty`.
- `style/invoice.sty` – Mechanik der neun Blöcke und die Sprachwörterbücher (`english`, `ngerman`).
- Eigener Vorlagen-Ordner (`vorlage` / `RECHNUNG_VORLAGE`, `vorlage.py`): seine Dateien ersetzen beim
  Build die gleichnamigen der Standardvorlage, `resolved.json` hält sie in `vorlage_eigen` fest. Jede
  neue Stellschraube in `defaults.sty` bekommt in `invoice.sty` einen Standardwert (`tests/test_vorlage.py`).
- `include/issuer.tex` – Aussteller für `beispiel.tex`, nur Musterdaten; echte Rechnungen erzeugen ihn zur Laufzeit
  aus `issuer.tex.j2`.
- `rechnung.tex.j2` / `issuer.tex.j2` – die Vorlage, die `render.py` füllt. `beispiel.tex` ist dieselbe
  Rechnung mit festen Werten (`make beispiel`); beide zusammen ändern, sonst driften sie auseinander.
- Belege: Kurzform ist der bloße Dateiname, lang mit `datei:` und `text:`; die Datei liegt im
  Unterordner belege der Rechnung und wird als gestempelte Seite angehängt.
- Layout: DIN 5008 Form B (Anschriftfeld ab 45 mm), Kontaktdaten oben rechts, Rücksendeangabe klein über
  dem Empfänger, Fußzeile Bank · Steuernummern · Seitenzahl (nur bei mehrseitigen Rechnungen).
- PDF/A-tauglich gebaut (eingebettete Schriften); der Schalter kommt mit ZUGFeRD (geplant).

## Pflichtangaben – müssen im PDF-Text nachweisbar sein

`rechnung pruefen <nr>` extrahiert den Text (`pdftotext`) und prüft, dass enthalten sind: Rechnungsnummer,
Rechnungsdatum, Leistungsdatum, Name und Anschrift des Ausstellers, Name und Anschrift des Kunden,
Steuernummer oder USt-IdNr., jede Positionsbeschreibung, Netto, USt-Betrag, Brutto, und bei Satz 0 der
Steuerhinweis-Text. Die vollständige Liste mit Paragraphen steht in `pruefen.py`.

## Was die AI darf und was nicht

Darf: `rechnung.yaml` anlegen und ändern; `stammdaten/kunden/*.yaml` als Vorschlag anlegen (der Mensch bestätigt,
weil `land` und `ustid` den Steuerfall bestimmen); Code, Tests und Vorlage im Repo ändern.

Darf nicht: `resolved.json`, PDFs, `status.yaml` oder `stammdaten/ich.yaml` schreiben; Rechnungsnummern vergeben;
Beträge ausrechnen; festgeschriebene Rechnungen anfassen; echte Daten in Tests, Fixtures oder Commits.

Diese Regeln werden zusätzlich technisch erzwungen (PreToolUse-Hook und Deny-Regeln in
`.claude/settings.json`, Pydantic-Schema, Freeze). Sie stehen hier, damit es gar nicht erst versucht wird.

## Technik

- Python ≥ 3.12, `uv`, src-Layout: `src/rechnung/{config,models,rules,resolve,render,vorlage,pruefen,festschreiben,doctor,cli}.py`
- `pydantic` v2 mit `extra="forbid"` auf allen Modellen; `typer` für die CLI; `pyyaml`
- `jinja2` mit LaTeX-Delimitern (`\VAR{ }`, `\BLOCK{ }`, `\#{ }`) und `StrictUndefined`
- LaTeX: `latexmk -interaction=nonstopmode -no-shell-escape -outdir=<tmp>`; Engine `pdflatex`,
  XCharter + Fira Sans als TeX-Pakete;
  lualatex und xelatex in `config.toml` wählbar
- Tests: `pytest`; jede Regel in `rules.py` hat einen Test; End-to-End-Tests bauen A–D aus
  `stammdaten.example/`; Tests laufen ohne Config und ohne Gewerbe-Ordner (Temp-Verzeichnis)
- Feldnamen und CLI-Kommandos auf Deutsch (`kunde`, `positionen`, `leistungsdatum`, `netto`, `brutto`,
  `neu`, `resolve`, `bauen`, `pruefen`, `festschreiben`, `demo`, `doctor`)
- Sprache der Rechnung: `de` oder `en`, eine je Rechnung (die Vorlage setzt jedes feste Label einsprachig);
  Datums-, Zahlen- und Währungsformat folgen der Sprache
- Commit-Wächter: `make hooks` schaltet `.githooks/` ein; jeder Commit und jede Commit-Message wird gegen
  die Sperrliste neben der Config geprüft (`sperrliste.txt` oder `RECHNUNG_SPERRLISTE`), auch Text und
  Metadaten von PDFs. Ohne Sperrliste still. `make test` und `make schatten` schalten ihn mit ein;
  `rechnung doctor` ist rot, wenn eine Sperrliste da ist und der Wächter aus ist.
- Kein Netzwerkzugriff im Kern. Künftige AI-Funktionen kommen in ein eigenes, optional importierbares Modul.

## Schattencontainer – Muss

Das Werkzeug wird lokal benutzt, muss aber jederzeit im Container laufen. Der Container ist das
`Dockerfile`, wird über `make schatten` gebaut und geprüft, und ist im Alltag nicht in Gebrauch.
Eine Änderung ist erst fertig, wenn `make schatten` grün ist. Er baut immer mit der Standardvorlage.

Der Vertrag:
- Keine Host-Annahmen: jede Option auch als Umgebungsvariable `RECHNUNG_<OPTION>` (Env gewinnt); kein
  Code verlässt sich auf `$HOME`, `~/.config` oder absolute Pfade. Im Container liegt der Gewerbe-Ordner unter `/gewerbe`.
- Alle Abhängigkeiten deklariert: Python in `uv.lock`, TeX-Pakete in `docs/tex-pakete.txt` (kein „TeX Live
  full“), Fonts offen lizenziert (XCharter, Fira Sans; als TeX-Pakete, bei Bedarf Dateien in `vorlage/fonts/`). Systemfonts sind nie Default.
- Der Gewerbe-Ordner ist der einzige Mount-Punkt; mehr sieht der Container nicht. Der Kern braucht kein Netzwerk.
- Definition von „läuft“: `rechnung demo` und `rechnung pruefen` auf allen vier Demo-Rechnungen im Container.
- Bewusste Abstriche: Container läuft als root, kein User-Mapping, keine Secrets, kein Netzwerk-Setup.
  Aufruf ist `docker run --rm -v <gewerbe>:/gewerbe rechnung <kommando>`, nicht mehr.
- `rechnung doctor` prüft auf dem Host gegen dieselbe Paketliste, die das Dockerfile installiert.
