# ai-e-rechnung

Rechnungen für ein deutsches Kleingewerbe: Aus einem kurzen YAML wird eine formal vollständige
Rechnung als PDF, gesetzt mit LaTeX. Der Kern ist deterministisch. Leistungsort, Steuersatz, Summen
und Rechnungsnummer rechnet das Werkzeug, nicht der Mensch und nicht die AI. Der Befehl heißt `rechnung`.

```
rechnung.yaml ──resolve──▶ rechnung.resolved.json ──render──▶ rechnung_<nummer>.pdf
```

**Stand:** PDF heute. ZUGFeRD (E-Rechnung nach EN 16931) ist geplant, die Vorlage ist dafür schon
PDF/A-tauglich gebaut. Sonstige Leistungen an Unternehmer und Privatpersonen im Inland, in der EU
und im Drittland, mit Regelbesteuerung oder als Kleinunternehmer (§ 19 UStG). Welche Regeln das
Werkzeug anwendet, woher sie kommen und was es bewusst nicht kann, steht in [`RULES.md`](RULES.md).

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
`rechnung.resolved.json` und der PDF; eine davon zusätzlich mit zwei gesendeten Pro-forma-Revisionen.
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
rechnung init --stammdaten            # einmalig: Ordner und ein leeres ich.yaml anlegen
rechnung neu --kunde sample-ltd
#   legt <ausgang>/2026/2026-0001/ mit vorbefülltem rechnung.yaml an;
#   leistungsdatum und leistung: (was, Einordnung nach § 3a UStG) dort eintragen – Pflicht
rechnung resolve 2026-0001            # Leistungsort, Ergebnis, Summen, Regeln – schreibt das Ergebnis daneben
rechnung bauen   2026-0001 --pro-forma   # optional: Pro forma zur Prüfung durch den Kunden
rechnung pro-forma 2026-0001 --gesendet-am 2026-06-12
#   hält die gesendete Pro forma als Revision fest (pro-forma/1/), schreibgeschützt
rechnung bauen   2026-0001            # die Rechnung: rechnung_2026-0001.pdf bzw. invoice_2026-0001.pdf
rechnung pruefen 2026-0001            # weist die Pflichtangaben im PDF-Text nach
rechnung festschreiben 2026-0001 --gesendet-am 2026-06-18
#   macht die Rechnung unveränderbar: Status, Schreibschutz, Hashes
```

`rechnung.yaml` ist die einzige Datei, die von Hand (oder von einer AI) geschrieben wird. Leistungsort,
Ergebnis, Steuersatz, Hinweistext, Fälligkeit, Summen und Rechnungsnummer leitet das Werkzeug daraus ab und
friert sie in `rechnung.resolved.json` ein. Die ausführliche Anleitung steht in
`docs/anleitung-neue-rechnung.md`.

## Zwei Orte, strikt getrennt

**Repo (Code):** Bibliothek, CLI, LaTeX-Vorlage, Tests und erfundene Beispiel-Stammdaten in
`stammdaten.example/`. Niemals echte Stammdaten, Kunden oder Rechnungen.

**Gewerbe-Ordner (Daten):** dein Ordner für das Gewerbe, irgendwo außerhalb des Repos. Das Werkzeug
kennt nur die Wurzel und darunter vier Unterordner, die ihm gehören:

| Option | Default | Inhalt |
| --- | --- | --- |
| `stammdaten` | `stammdaten` | `ich.yaml` (Aussteller) |
| `kunden` | `stammdaten/kunden` | `<kuerzel>.yaml`, ein Kunde pro Datei |
| `ausgang` | `rechnung-ausgang` | `JJJJ/<nummer>/` je Rechnung |
| `steuerberater` | `steuerberater` | Export-Ziel |

Alles andere im Gewerbe-Ordner fasst das Werkzeug nicht an. `rechnung init` legt die vier Ordner an,
falls sie fehlen.

## Konfiguration

`~/.config/rechnung/config.toml` (Vorlage: `config.toml.example`). Jede Option gibt es auch als
Umgebungsvariable `RECHNUNG_<OPTION>`, z. B. `RECHNUNG_GEWERBE`; die Umgebung gewinnt. Den Pfad der
Config selbst setzt `RECHNUNG_CONFIG`. Ohne Gewerbe-Wurzel läuft alles im Demo-Modus gegen
`stammdaten.example/`.

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
make schatten                                            # beide Images bauen, Demo bauen und prüfen, Beweise prüfen
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
- `RULES.md` – die Steuerregeln: Gesetzeswortlaut, Regeln mit Status, Entscheidungstabelle, Grenzen
- `lean/README.md` – Beweise über die Steuerregeln (englisch): was bewiesen ist und was nicht
- `docs/muster/` – sechs Musterrechnungen als visuelle Referenz

## Hinweis

Das Werkzeug ersetzt keine Steuerberatung. Es setzt die Pflichtangaben nach § 14 UStG um und prüft
sie im PDF nach; ob die Einordnung der Leistung und die Kundendaten im Einzelfall stimmen, bleibt deine Verantwortung.
Die Regeln in `RULES.md` sind begründete Annahmen; kein Steuerberater hat sie bisher geprüft.

Lizenz: MIT.
