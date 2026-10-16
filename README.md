# ai-e-rechnung

*English: what is proved, what is tested, what is assumed, and how to reproduce it –
[`lean/README.md`](lean/README.md).*

Rechnungen für ein deutsches Kleingewerbe: Aus einem kurzen YAML wird eine formal vollständige
Rechnung als PDF, gesetzt mit LaTeX. Der Kern ist deterministisch. Leistungsort, Steuersatz, Summen
und Rechnungsnummer rechnet das Werkzeug, nicht der Mensch und nicht die AI. Der Befehl heißt `rechnung`.

```
rechnung.yaml          (was und wie viel: Kürzel aus der Preisliste, Menge)  ─┐
rechnung.privat.yaml   (Preise aus der Liste oder vom Menschen, Referenz)    ─┴─resolve──▶
    rechnung.resolved.json ──render──▶ rechnung_<nummer>.pdf
```

**Stand:** PDF heute. ZUGFeRD (E-Rechnung nach EN 16931) ist geplant, die Vorlage ist dafür schon
PDF/A-tauglich gebaut. Sonstige Leistungen an Unternehmer und Privatpersonen im Inland, in der EU
und im Drittland, mit Regelbesteuerung oder als Kleinunternehmer (§ 19 UStG). Welche Regeln das
Werkzeug anwendet, woher sie kommen und was es bewusst nicht kann, steht in [`RULES.md`](RULES.md).

> Prototyp, noch nicht rechtlich oder steuerlich geprüft. Das Werkzeug kann noch nicht: Lieferungen
> von Waren, Steuerbefreiungen außer § 19 UStG, durchlaufende Posten, nicht steuerbare Zahlungen
> (z. B. Schadenersatz, Zuschüsse). Vollständige Liste: RULES.md, Teil 1.

## Ausprobieren ohne Installation (Docker)

Das Image bringt Python, TeX und alle Schriften mit. Es sieht nur den Ordner, den man ihm mitgibt.

```sh
git clone https://github.com/athki/ai-e-rechnung.git && cd ai-e-rechnung
docker build -t rechnung .
mkdir -p probe
docker run --rm -v "$PWD/probe":/gewerbe rechnung demo --pruefen --ziel /gewerbe/demo
```

Danach liegen in `probe/demo/` sechs Beispielrechnungen, je Ergebnis mindestens eine (Inland,
EU mit Reverse Charge, Drittland, Kleinunternehmer), jede mit `rechnung.yaml`,
`rechnung.privat.yaml`, `rechnung.resolved.json` und der PDF; eine davon zusätzlich mit zwei gesendeten
Pro-forma-Revisionen.
`--pruefen` weist in jeder PDF die Pflichtangaben nach
§ 14 Abs. 4 UStG nach. Dieselben liegen als Muster in `docs/muster/`.

## Installation

Voraussetzungen: Python ≥ 3.12 mit [uv](https://docs.astral.sh/uv/), TeX Live mit `latexmk` und
`pdflatex` und den Paketen aus `docs/tex-pakete.txt`, `pdftotext` (poppler).

```sh
uv sync
uv run rechnung doctor   # prüft Python, LaTeX, TeX-Pakete, pdftotext, Config, Gewerbe-Ordner
uv run rechnung demo     # sechs Beispielrechnungen nach ./demo-output/
```

## Ablauf einer Rechnung

```sh
rechnung init --stammdaten            # einmalig: Ordner, ein leeres ich.yaml und eine leere Preisliste
rechnung preisliste                   # Kürzel, Einheit und Bezeichnung aus stammdaten/preise.yaml
rechnung neu --kunde sample-ltd
#   legt <ausgang>/2026/2026-0001/ mit vorbefülltem rechnung.yaml an;
#   leistungsdatum, leistung: (was, Einordnung nach § 3a UStG) und je Position Kürzel und Menge
#   dort eintragen – Pflicht
rechnung resolve 2026-0001            # Leistungsort, Ergebnis, Regeln; übernimmt die Preise der Liste
#   und schreibt mit Summen das Ergebnis daneben. Fehlt ein Preis, den die Liste nicht hat (Auslage,
#   Fremdwährung), zeigt es nur den Entwurf.
rechnung preise  2026-0001            # nur bei Bedarf: Auslagen eintragen, Preise ändern, Referenz
rechnung bauen   2026-0001 --pro-forma   # optional: Pro forma zur Prüfung durch den Kunden
rechnung pro-forma 2026-0001 --gesendet-am 2026-06-12
#   hält die gesendete Pro forma als Revision fest (pro-forma/1/), schreibgeschützt
rechnung bauen   2026-0001            # die Rechnung: rechnung_2026-0001.pdf bzw. invoice_2026-0001.pdf
rechnung pruefen 2026-0001            # weist die Pflichtangaben im PDF-Text nach
rechnung anschreiben 2026-0001        # setzt Nummer, Betrag, Anrede … in anschreiben.md ein (verschickt nichts)
rechnung festschreiben 2026-0001 --gesendet-am 2026-06-18
#   macht die Rechnung unveränderbar: Status, Schreibschutz, Hashes
rechnung begruendung 2026-0001        # für Prüfer: Fakten, angewandte Regeln, Status und Nachweis (Markdown)
rechnung offen                        # alle Rechnungen, die noch nicht festgeschrieben sind, und was fehlt
```

`rechnung.yaml` ist die einzige Datei, die von Hand (oder von einer AI) geschrieben wird. Sie sagt, was
geleistet wurde und wie viel davon, nie, was es kostet. Die Preise kommen aus der Preisliste: `resolve`
und `bauen` übernehmen sie selbst, je Position mit der Quelle `liste`. Was die Liste nicht hat (Auslagen,
Fremdwährung) und was anders sein soll, trägt der Mensch mit `rechnung preise` ein (Quelle `mensch`).
Alles steht als Schnappschuss in `rechnung.privat.yaml`, zusammen mit einem Hash der Positionen, für die
es gilt. Ändert sich eine Position, füllt `resolve` sie neu aus der Liste; die bestätigten Preise der
unveränderten Positionen bleiben. Die Kontrolle bleibt beim Festschreiben: `festschreiben` weist auf
Preise hin, die nur aus der Liste kommen. Leistungsort, Ergebnis, Steuersatz, Hinweistext, Fälligkeit, Summen und Rechnungsnummer
leitet das Werkzeug ab und friert sie in `rechnung.resolved.json` ein. Die ausführliche Anleitung steht in
`docs/anleitung-neue-rechnung.md`.

## Mit einer AI: geschwärzte Sicht

Die AI soll wissen, was geleistet wurde und wie viel davon, nie, wer beteiligt ist und was es kostet.
Deshalb stehen in `rechnung.yaml` keine Preise: Die AI schreibt Kürzel aus der Preisliste und Mengen,
die Beträge setzt das Werkzeug lokal aus der Liste ein; Auslagen trägt der Mensch im eigenen Terminal
ein (`rechnung preise`, später im Web ein Formular).
Mit `RECHNUNG_GESCHWAERZT=1` geben `neu`, `resolve`, `bauen`, `pruefen`, `begruendung`, `preisliste`,
`offen` und `anschreiben` keine Namen, Anschriften, Werte aus Kunden- oder Ausstellerdatei, Beträge oder
absoluten Pfade aus; `rechnung preise` verweigert unter dem Schalter, und `anschreiben` prüft dort nur
die Platzhalter. Abbrüche kommen als `Abbruch (<art>): …` und sagen, wer handeln muss (`eingabe`,
`frage`, `stammdaten`, `ausserhalb`, `preise`). Für Claude Code beschreibt der Skill `.claude/skills/rechnung/SKILL.md` den Ablauf;
den Schalter und die Gewerbe-Wurzel setzt man in `.claude/settings.local.json` (`env`). Unter dem
Schalter sperrt der Hook auch das Lesen von Stammdaten und abgeleiteten Dateien im Gewerbe-Ordner.
Ehrlich: Über Bash ist Lesen in Claude Code damit nicht ganz gesperrt.

## Mit einer AI: MCP-Server

Mit dem MCP-Server ist die Grenze echt. Die AI kommt nur über seine Werkzeuge an das Werkzeug heran
und bekommt nur deren geschwärzte Antworten, unabhängig vom Schalter. Das Kürzel des Kunden sieht sie
dort auch nicht. Jede Antwort zu einer Rechnung nennt in `naechster_schritt`, was als Nächstes kommt –
auch, was der Mensch selbst tun muss, mit dem passenden Befehl.

| Werkzeug | Was es tut | Was die AI zurückbekommt |
| --- | --- | --- |
| `neu` | legt eine Rechnung an; den Kunden wählt der Mensch | Nummer, Sprache, Prototyp-Hinweis |
| `preisliste` | Kürzel, Einheit, Art, Bezeichnung | ohne Preise |
| `lesen` / `schreiben` | `rechnung.yaml`: Daten, `leistung:`, Positionen, Einleitung, Belege | was sie selbst schreiben darf |
| `resolve`, `begruendung`, `offen` | Leistungsort, Ergebnis, Regeln, Stand der Preise; `resolve` übernimmt die Listenpreise | ohne Kunde und Beträge |
| `bauen`, `pruefen` | PDF bauen, Pflichtangaben nachweisen | Dateiname, ✓/✗ je Angabe |
| `anschreiben_schreiben`, `anschreiben_pruefen` | Begleittext mit Platzhaltern | Liste der Platzhalter |
| `kunden` | nur im Demo-Betrieb: die erfundenen Testkunden | Kürzel, Name, Land, Fall |

Preise eintragen, `festschreiben` und `pro-forma` sind keine Werkzeuge; sie bleiben beim Menschen. Den
Kunden fragt `neu` per Auswahl im Client ab (MCP-Elicitation, z. B. Claude Code). Kann der Client das
nicht (Claude Desktop), nennt der Mensch der AI das Kürzel. `rechnung mcp --kunde <kürzel>` legt den
Kunden beim Start fest. `--preise-im-client` bietet zusätzlich `preise_bestaetigen` an: ein Formular im
Client, dessen Werte an den Server gehen, nicht an die AI. Ob ein Client das wirklich so hält, ist je
Client zu prüfen; im Zweifel bleibt `rechnung preise` im Terminal. Was ein Werkzeug zurückgibt, geht an
den Modellanbieter; was der Mensch in den Chat tippt, auch.

### Ausprobieren: Demo-Betrieb mit Claude Desktop

Mit `RECHNUNG_DEMO=1` gibt es nur den erfundenen Aussteller und die sechs erfundenen Testkunden aus
`stammdaten.example/`, auch wenn im Ordner etwas anderes liegt; ein Ordner mit eigener `ich.yaml` wird
verweigert. Weil die Daten erfunden sind, nennt das Werkzeug `kunden` sie der AI, damit man ohne
Terminal wählen kann. Auslagen bekommen einen Beispielpreis aus der Liste, so kommt man von der ersten
Nachricht bis zur PDF, ohne ein Terminal zu öffnen. Jede Antwort trägt den Prototyp-Hinweis.

```sh
docker build -t rechnung .
mkdir -p ~/rechnung-probe          # leer; dort landen die Testrechnungen
```

In `claude_desktop_config.json` (Pfad absolut):

```json
{
  "mcpServers": {
    "rechnung-demo": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "RECHNUNG_DEMO=1",
               "-v", "/Users/<du>/rechnung-probe:/gewerbe", "rechnung", "mcp"]
    }
  }
}
```

Dann im Chat zum Beispiel: „Schreib eine Rechnung: zwei Stunden Beratung am 1. Oktober.“ Die
Testkunden:

| Kürzel | Fall |
| --- | --- |
| `muster-gmbh` | Unternehmen im Inland: `inland`, 19 % |
| `privat-de` | Privatperson im Inland: `inland`, 19 % |
| `exemple-sarl` | Unternehmen in Frankreich mit USt-IdNr.: `reverse_charge`, 0 % |
| `sample-ltd` | Unternehmen im Vereinigten Königreich: `nicht_steuerbar`, 0 % |
| `sample-inc` | Unternehmen in den USA, Rechnung in USD: `nicht_steuerbar`; Preise in USD trägt der Mensch ein |
| `privat-ch` | Privatperson in der Schweiz: Leistungsort hängt von der Einordnung ab |

Die PDFs liegen danach in `~/rechnung-probe/rechnung-ausgang/`. Ohne Docker, in Claude Code:
`claude mcp add rechnung-demo -e RECHNUNG_DEMO=1 -e RECHNUNG_GEWERBE=<leerer Ordner> -- uv --directory <repo> run --extra mcp rechnung mcp`.

### Eigene Rechnungen: lokal, mit eigenem Gewerbe-Ordner

Eigene Daten bleiben bei dir; online läuft nichts. Einmal einrichten:

```sh
docker run --rm -v ~/Gewerbe:/gewerbe rechnung init --stammdaten
# dann in ~/Gewerbe/stammdaten/ ausfüllen: ich.yaml, preise.yaml, kunden/<kürzel>.yaml
```

Im Client wie oben, aber **ohne** `RECHNUNG_DEMO` und mit deinem Ordner
(`"-v", "/Users/<du>/Gewerbe:/gewerbe"`). Die AI kennt deine Kunden dann nicht; du nennst ihr das
Kürzel (den Dateinamen ohne `.yaml`). Was du selbst im Terminal machst, nennt dir die Antwort in
`naechster_schritt` mit dem passenden Befehl, im Container etwa:

```sh
docker run -it --rm -v ~/Gewerbe:/gewerbe rechnung preise <nr>        # Auslagen eintragen, Preise ändern
docker run -it --rm -v ~/Gewerbe:/gewerbe rechnung festschreiben <nr> --gesendet-am JJJJ-MM-TT
```

Ohne Docker, mit installiertem TeX: `RECHNUNG_GEWERBE=~/Gewerbe uv run rechnung …` bzw. in Claude Code
`claude mcp add rechnung -e RECHNUNG_GEWERBE=<gewerbe> -- uv --directory <repo> run --extra mcp rechnung mcp`.

| Variable | Wofür |
| --- | --- |
| `RECHNUNG_GEWERBE` | dein Gewerbe-Ordner (im Container fest `/gewerbe`) |
| `RECHNUNG_CONFIG` | Pfad einer `config.toml`, sonst `~/.config/rechnung/config.toml` |
| `RECHNUNG_DEMO` | `1`: Demo-Betrieb mit den Testdaten; für eigene Rechnungen nicht setzen |
| `RECHNUNG_MCP_KUNDE` | Kunde für den MCP-Server fest wählen |
| `RECHNUNG_MCP_PREISE_IM_CLIENT` | `1`: Preisformular im Client anbieten |
| `RECHNUNG_GESCHWAERZT` | `1`: geschwärzte Ausgabe des CLI (für eine AI in Claude Code) |

## Zwei Orte, strikt getrennt

**Repo (Code):** Bibliothek, CLI, LaTeX-Vorlage, Tests und erfundene Beispiel-Stammdaten in
`stammdaten.example/`. Niemals echte Stammdaten, Kunden oder Rechnungen.

**Gewerbe-Ordner (Daten):** dein Ordner für das Gewerbe, irgendwo außerhalb des Repos. Das Werkzeug
kennt nur die Wurzel und darunter vier Unterordner, die ihm gehören:

| Option | Default | Inhalt |
| --- | --- | --- |
| `stammdaten` | `stammdaten` | `ich.yaml` (Aussteller), `preise.yaml` (Preisliste) |
| `kunden` | `stammdaten/kunden` | `<kuerzel>.yaml`, ein Kunde pro Datei |
| `ausgang` | `rechnung-ausgang` | `JJJJ/<nummer>/` je Rechnung |
| `steuerberater` | `steuerberater` | Export-Ziel |

Alles andere im Gewerbe-Ordner fasst das Werkzeug nicht an. `rechnung init` legt die vier Ordner an,
falls sie fehlen.

## Konfiguration

`~/.config/rechnung/config.toml` (Vorlage: `config.toml.example`). Jede Option gibt es auch als
Umgebungsvariable `RECHNUNG_<OPTION>`, z. B. `RECHNUNG_GEWERBE`; die Umgebung gewinnt. Den Pfad der
Config selbst setzt `RECHNUNG_CONFIG`. Ohne Gewerbe-Wurzel läuft alles im Demo-Modus gegen
`stammdaten.example/`; `RECHNUNG_DEMO=1` (Option `demo`) erzwingt die Beispieldaten auch mit Wurzel.

## Eigenes Aussehen: der Vorlagen-Ordner

Die Standardvorlage ist neutral in Schwarz. Für ein eigenes Aussehen kopiert man nicht die ganze
Vorlage, sondern legt einen Ordner mit den Dateien an, die anders sein sollen – meist nur
`style/defaults.sty` mit Farben, Schrift und Maßen – und trägt ihn als `vorlage` in die Config ein:

```toml
vorlage = "~/meine-vorlage"
```

Beim Bauen ersetzen diese Dateien die gleichnamigen der Standardvorlage; alles andere kommt mit
jedem Update aus dem Repo. `rechnung.resolved.json` hält fest, welche eigenen Dateien beteiligt
waren. `rechnung doctor` zeigt, was ersetzt wird, und nennt neue Stellschrauben, die einer älteren
eigenen `defaults.sty` fehlen. Einzelheiten in `vorlage/README.md`.

## Container

Das Werkzeug läuft jederzeit auch im Container. Der Gewerbe-Ordner ist der einzige Mount, ein
Netzwerk braucht der Kern nicht.

```sh
make schatten                                            # beide Images bauen, Demo und MCP-Server prüfen, Beweise prüfen
docker run --rm -v "<gewerbe>":/gewerbe rechnung doctor  # gegen den eigenen Gewerbe-Ordner
```

Ein zweiter Container prüft die Beweise unter [`lean/`](lean/README.md): das Rechnungs-Image plus Lean,
ohne Mount. Jeder Lauf baut die Beweise neu, scheitert an einem offenen Beweis und prüft, dass die
Antworten des Modells, gegen die `make test` den Python-Code abgleicht, zum Modell passen.

```sh
docker build -t rechnung . && docker build -f Dockerfile.beweise -t rechnung-beweise .
docker run --rm rechnung-beweise                         # oder kurz: make beweise
```

Abhängigkeiten sind vollständig deklariert: Python in `uv.lock`, TeX-Pakete in `docs/tex-pakete.txt`,
Fonts offen lizenziert (XCharter, Fira Sans). Der Container baut immer mit der Standardvorlage.

## Mitentwickeln

```sh
uv run pytest -q    # Tests; die Bau-Tests brauchen LaTeX
make schatten       # Pflicht vor jedem Commit: beide Container bauen und prüfen
make lean           # Lean-Beweise auf dem Host bauen und prüfen (braucht elan)
make hooks          # Commit-Wächter einschalten (test und schatten tun das mit)
```

Der Commit-Wächter prüft jeden Commit samt Commit-Message – und vor jedem Push noch einmal alles, was
hochgeht, samt Autor – gegen eine private Sperrliste
(`sperrliste.txt` neben der Config oder `RECHNUNG_SPERRLISTE`): eigener Name, Anschrift, Steuernummer,
IBAN, Kundennamen. So landen keine echten Daten im Repo, auch nicht im Text einer PDF. Das Format
steht in `.githooks/sperrliste.py`. Ohne Sperrliste ist er still; mit Sperrliste meldet
`rechnung doctor` rot, solange er in diesem Klon aus ist.

## Weiterlesen

- `docs/anleitung-neue-rechnung.md` – Schritt für Schritt eine Rechnung schreiben, plus
  Nachschlagewerk: welche Einstellung in welcher Datei steht
- `vorlage/README.md` – die LaTeX-Vorlage: Aufbau, Stilschalter, eigener Vorlagen-Ordner, `make beispiel`
- `RULES.md` – die Steuerregeln: Gesetzeswortlaut, Regeln mit Status und Nachweis, Entscheidungstabelle,
  Grenzen; `rechnung begruendung <nr>` zeigt daraus die Kette für eine einzelne Rechnung
- `lean/README.md` – die ganze Prüfkette auf Englisch: was bewiesen, abgeglichen, getestet und
  angenommen ist, wie man es nachbaut; danach das Lean-Modell
- `docs/muster/` – sechs Musterrechnungen als visuelle Referenz

## Hinweis

Das Werkzeug ersetzt keine Steuerberatung. Es setzt die Pflichtangaben nach § 14 UStG um und prüft
sie im PDF nach; ob die Einordnung der Leistung und die Kundendaten im Einzelfall stimmen, bleibt deine Verantwortung.
Die Regeln in `RULES.md` sind begründete Annahmen; kein Steuerberater hat sie bisher geprüft.

Lizenz: MIT.
