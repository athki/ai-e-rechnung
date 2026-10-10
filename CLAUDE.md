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
    rechnung_<nummer>.pdf    # abgeleitet; englisch invoice_<nummer>.pdf
    rechnung-pro-forma_<nummer>.pdf   # Arbeitskopie der Pro forma, bei jedem Bau überschrieben
    pro-forma/<n>/           # gesendete Pro-forma-Revision: PDF, rechnung.yaml, resolved.json, schreibgeschützt
    status.yaml              # ab der ersten gesendeten Pro forma bzw. dem Festschreiben: Status, Daten, Hashes
    belege/
  steuerberater/JJJJ/        # Export-Ziel
  rechnung-eingang/, bank/, vertraege/ …   # nicht Sache des Werkzeugs
```

Builds laufen in einem temporären Verzeichnis (`tempfile.mkdtemp()`); nur die PDF und
`rechnung.resolved.json` werden in den Rechnungsordner kopiert. Kein `.aux`, `.log`, `.tex` dort, nie.

Ohne Gewerbe-Wurzel läuft alles gegen `stammdaten.example/` im Repo (Demo-Modus).
`rechnung demo` baut daraus sechs Beispielrechnungen, je Ergebnis mindestens eine, nach `./demo-output/` (gitignored).

## Pipeline

```
rechnung.yaml ──resolve()──▶ rechnung.resolved.json ──render()──▶ rechnung_<nummer>.pdf
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
- `leistung:` ist Pflicht und wird nie geraten: `taetigkeit` (in eigenen Worten), `einordnung` (ein Begriff
  aus § 3a UStG, Liste in RULES.md Teil 4 und als Kommentar in jeder neuen `rechnung.yaml`), `ort` bei
  Tätigkeitsleistungen (Land oder `online`). `rechnung neu` lässt den Block leer; `--taetigkeit`,
  `--einordnung`, `--ort` füllen ihn vor.
- Leistungsdatum ist Pflicht und wird nie geraten. `rechnung neu --kunde <kuerzel>` lässt es in
  `rechnung.yaml` leer (`# PFLICHT: Tag der Leistung, JJJJ-MM-TT`), `resolve` bricht ab, bis es dasteht;
  `--leistungsdatum JJJJ-MM-TT` füllt es vor (für Skripte und AI).
- `resolved.json` enthält Leistungsort, Ergebnis und die angewandten Regel-IDs (`regeln`), dazu `vorlage_version` (Git-Short-Hash des Repos beim Build) und einen Hash des Inputs.
- `rechnung festschreiben <nr> --gesendet-am JJJJ-MM-TT` macht die Rechnung unveränderbar: Status
  `festgeschrieben`, PDF und resolved.json read-only, Hashes von yaml, resolved.json und PDF in
  `status.yaml`. `--gesendet-am` ist Pflicht – unveränderbar wird eine Rechnung, weil sie ausgestellt
  ist (§ 14 UStG), und das Werkzeug verschickt nichts, es hält nur fest, wann du verschickt hast.
  Vorher darf beliebig oft gebaut und geprüft werden. Danach verweigert `bauen` den Neubau, und
  `pruefen` meldet jede nachträgliche Änderung an den eingefrorenen Dateien.
- Pro forma (RULES.md R38): `rechnung bauen <nr> --pro-forma` baut aus denselben Daten eine Pro forma
  (Belegart `proforma`: Kopfzeile „PRO FORMA – KEINE RECHNUNG“, „(keine Rechnung)“ im Betreff, Labels
  „Re.-Nr. (vorl.)“ usw., Bitte um Prüfung statt Zahlungsaufforderung) und überschreibt die Arbeitskopie.
  `rechnung pro-forma <nr> --gesendet-am JJJJ-MM-TT` friert sie als nächste Revision in `pro-forma/<n>/`
  ein (PDF plus Kopien von yaml und resolved.json, Hashes in `status.yaml`). `festschreiben` friert nur
  die echte Rechnung ein; danach gibt es keine Pro forma mehr. Das Datum der Rechnung stellt der Mensch
  vor dem echten Bau in `rechnung.yaml` um.
- Dateinamen der PDFs tragen die Nummer, das Präfix folgt der Sprache (`rechnung_…` / `invoice_…`);
  ein Sprachwechsel räumt die Datei mit dem anderen Präfix weg.
- `rechnung pruefen <nr>` nimmt auch den Pfad eines Rechnungsordners – so prüft der Container die
  Demo-Rechnungen. `rechnung demo --pruefen` baut und prüft in einem Zug.

## Steuerregeln (`RULES.md`, `rules.py`)

`RULES.md` ist die Spezifikation: Gesetzeswortlaut, Regeln R1…Rn mit Status, Entscheidungstabelle,
Geltungsbereich. `rules.py` setzt sie um; Regel-IDs im Code verweisen dorthin. Grundsatz: Das Werkzeug
darf strenger sein als das Gesetz (abbrechen), aber nie anders entscheiden.

- Leistungsort aus Status des Kunden (`unternehmer`, bei EU-Kunden genügt `ustid`), Gruppe der
  Einordnung (Tätigkeit / Katalog / Grundregel) und Ort; daraus das Ergebnis:

| Ergebnis | Leistungsort | Satz | Hinweis |
| --- | --- | --- | --- |
| `inland` | Inland | 19 % (7 % je Position möglich) | keiner |
| `reverse_charge` | anderer EU-Staat, Kunde Unternehmer | 0 % | „Steuerschuldnerschaft des Leistungsempfängers (§ 14a Abs. 1 UStG, Art. 196 MwStSystRL).“ bzw. englisch – beide USt-IdNrn. auf der Rechnung; Warnung nach dem 15. des Folgemonats |
| `nicht_steuerbar` | Drittland | 0 % | „Leistungsort: {Land}. Die Leistung ist in Deutschland nicht steuerbar ({Fundstelle}).“ bzw. englisch, mit Reverse-Charge-Nachsatz nur bei Unternehmern |
| `kleinunternehmer` | Inland, Aussteller mit `kleinunternehmer: true` (§ 19 UStG) | 0 % | „Steuerfrei als Leistung eines Kleinunternehmers (§ 19 Abs. 1 UStG).“; keine Steuerzeile |

- Abbruch statt Entscheidung, wenn Daten fehlen (`unternehmer`, USt-IdNrn. bei `reverse_charge`) oder
  der Leistungsort bei einer Privatperson ein anderer EU-Staat wäre; ebenso, wenn der Aussteller laut
  Stammdaten nicht in Deutschland sitzt (R4).
- `rules.kern()` ist der Entscheidungskern als reine Funktion über abstrakte Merkmale (3456 Kombinationen,
  Tests laufen über alle); `rules.entscheide()` übersetzt Daten hin und zurück. `steuersatz` je Position
  nimmt nur `7` (§ 12 Abs. 2); `rules.satz_position()` entscheidet, wo das geht. Später prüft ein
  Lean-Modell (`lean/`) den Kern vollständig.
- Manuelle Festlegung nur des Leistungsorts: `leistungsort:` mit `begruendung:`, sonst Validierungsfehler.
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
Steuernummer oder USt-IdNr., jede Positionsbeschreibung, Netto, USt-Betrag (beim Kleinunternehmer
entfällt die Steuerzeile), Brutto, bei Satz 0 der Steuerhinweis-Text und bei `reverse_charge` beide USt-IdNrn.; an der Pro forma zusätzlich die
Kennzeichnung, an der Rechnung ihr Fehlen (`pruefen --pro-forma` prüft die Arbeitskopie). Die vollständige Liste mit Paragraphen steht in `pruefen.py`.

## Was die AI darf und was nicht

Darf: `rechnung.yaml` anlegen und ändern; `stammdaten/kunden/*.yaml` als Vorschlag anlegen (der Mensch bestätigt,
weil `land`, `ustid` und `unternehmer` den Leistungsort bestimmen); Code, Tests und Vorlage im Repo ändern.

Darf nicht: `resolved.json`, PDFs, `status.yaml`, `pro-forma/` oder `stammdaten/ich.yaml` schreiben; Rechnungsnummern vergeben;
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
- Tests: `pytest`; jede Regel in `rules.py` hat einen Test; End-to-End-Tests bauen die Ergebnisse aus
  `stammdaten.example/`; Tests laufen ohne Config und ohne Gewerbe-Ordner (Temp-Verzeichnis)
- Feldnamen und CLI-Kommandos auf Deutsch (`kunde`, `positionen`, `leistungsdatum`, `netto`, `brutto`,
  `neu`, `resolve`, `bauen`, `pruefen`, `pro-forma`, `festschreiben`, `demo`, `doctor`)
- Sprache der Rechnung: `de` oder `en`, eine je Rechnung (die Vorlage setzt jedes feste Label einsprachig);
  Datums-, Zahlen- und Währungsformat folgen der Sprache
- Commit-Wächter: `make hooks` schaltet `.githooks/` ein. Gegen die Sperrliste neben der Config
  (`sperrliste.txt` oder `RECHNUNG_SPERRLISTE`) prüft er jeden Commit und jede Commit-Message, vor jedem
  Push noch einmal jeden Commit, der hochgeht, samt Autor; bei PDFs auch Text und Metadaten. Ohne
  Sperrliste still. `make test` und `make schatten` schalten ihn mit ein;
  `rechnung doctor` ist rot, wenn eine Sperrliste da ist und der Wächter aus ist.
- Kein Netzwerkzugriff im Kern. Künftige AI-Funktionen kommen in ein eigenes, optional importierbares Modul.
- Lean (`lean/`, README englisch): Beweise über die Steuerregeln, außerhalb des Werkzeugs. Version fest in
  `lean/lean-toolchain`, keine Abhängigkeiten (kein Mathlib), `lakefile.toml`. Namen spiegeln `rules.py`
  und RULES.md (Felder in `snake_case`, Theoreme mit Regel-ID, z. B. `R14_…`). Zwei Ebenen: `Gesetz/`
  (Sachverhalt, § 3a je Absatz, Folgen) und `Werkzeug/` (genauer Spiegel von `kern()`, `satz_position()`,
  `merkmale()`); `Bruecke.lean` (`Passt`) ist die vollständige Liste der Annahmen. Je Regel eine
  `Aussage.R…` in `Aussagen.lean`, bewiesen durch ein Theorem gleichen Namens. `lean/pruefen.sh` baut,
  gibt die Entscheidungstabelle aus (`Tabelle.lean`) und prüft (`Pruefung.lean`): jede Aussage hat ein
  Theorem genau dieses Typs (in 8.4 noch offen erlaubt), jede Warnung ist ein Fehler (`sorry`), nur Leans
  Standardaxiome (kein `native_decide`). `make lean` auf dem Host (braucht elan, `doctor` warnt nur),
  `make beweise` im Container.

## Schattencontainer – Muss

Das Werkzeug wird lokal benutzt, muss aber jederzeit im Container laufen. Es gibt zwei Container, beide
werden über `make schatten` gebaut und geprüft, beide sind im Alltag nicht in Gebrauch:

- **Rechnungs-Container** (`Dockerfile`, Image `rechnung`): das Werkzeug, für Ausprobierer. Baut immer mit
  der Standardvorlage. Ohne Lean (`lean/` steht in `.dockerignore`).
- **Beweis-Container** (`Dockerfile.beweise`, Image `rechnung-beweise`, `make beweise`): `FROM rechnung`
  plus elan und die Lean-Version aus `lean/lean-toolchain`. Jeder Lauf baut die Beweise neu und prüft die
  Axiome (`lean/pruefen.sh`). Kein Mount, kein Netzwerk. Eigene Ignore-Datei
  `Dockerfile.beweise.dockerignore`: nur `lean/` ohne `.lake/`.

Eine Änderung ist erst fertig, wenn `make schatten` grün ist – beide Container. Am Ende räumt es die alten,
unbenannten Images dieses Projekts weg (Kennzeichnung `ai-e-rechnung=schatten` im `Dockerfile`), sonst nichts.

Der Vertrag:
- Keine Host-Annahmen: jede Option auch als Umgebungsvariable `RECHNUNG_<OPTION>` (Env gewinnt); kein
  Code verlässt sich auf `$HOME`, `~/.config` oder absolute Pfade. Im Container liegt der Gewerbe-Ordner unter `/gewerbe`.
- Alle Abhängigkeiten deklariert: Python in `uv.lock`, TeX-Pakete in `docs/tex-pakete.txt` (kein „TeX Live
  full“), Fonts offen lizenziert (XCharter, Fira Sans; als TeX-Pakete, bei Bedarf Dateien in `vorlage/fonts/`). Systemfonts sind nie Default.
- Der Gewerbe-Ordner ist der einzige Mount-Punkt; mehr sieht der Container nicht. Der Kern braucht kein
  Netzwerk. Der Beweis-Container braucht keinen Mount.
- Definition von „läuft“: `rechnung demo` und `rechnung pruefen` auf allen Demo-Rechnungen im
  Rechnungs-Container, `make beweise` grün im Beweis-Container.
- Bewusste Abstriche: Container läuft als root, kein User-Mapping, keine Secrets, kein Netzwerk-Setup.
  Aufruf ist `docker run --rm -v <gewerbe>:/gewerbe rechnung <kommando>`, nicht mehr.
- `rechnung doctor` prüft auf dem Host gegen dieselbe Paketliste, die das Dockerfile installiert.
