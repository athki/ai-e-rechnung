# ai-e-rechnung

Rechnungen für ein deutsches Kleingewerbe: Aus einem kurzen YAML wird eine formal vollständige
Rechnung als PDF, gesetzt mit LaTeX. Der Kern ist deterministisch. Steuerfall, Summen und
Rechnungsnummer rechnet das Werkzeug, nicht der Mensch und nicht die AI. Der Befehl heißt `rechnung`.

```
rechnung.yaml ──resolve──▶ rechnung.resolved.json ──render──▶ rechnung.pdf
```

**Stand:** PDF heute. ZUGFeRD (E-Rechnung nach EN 16931) ist geplant, die Vorlage ist dafür schon
PDF/A-tauglich gebaut. Regelbesteuerung mit vier Steuerfällen (Inland, EU mit Reverse Charge,
Drittland-Unternehmen, sonst); die Kleinunternehmerregelung (§ 19 UStG) wird nicht unterstützt.

## Ausprobieren ohne Installation (Docker)

Das Image bringt Python, TeX und alle Schriften mit. Es sieht nur den Ordner, den man ihm mitgibt.

```sh
git clone https://github.com/athki/ai-e-rechnung.git && cd ai-e-rechnung
docker build -t rechnung .
mkdir -p probe
docker run --rm -v "$PWD/probe":/gewerbe rechnung demo --pruefen --ziel /gewerbe/demo
```

Danach liegen in `probe/demo/` vier Beispielrechnungen, eine je Steuerfall, jede mit
`rechnung.yaml`, `rechnung.resolved.json` und `rechnung.pdf`. `--pruefen` weist in jeder PDF die
Pflichtangaben nach § 14 Abs. 4 UStG nach. Dieselben vier liegen als Muster in `docs/muster/`.

## Installation

Voraussetzungen: Python ≥ 3.12 mit [uv](https://docs.astral.sh/uv/), TeX Live mit `latexmk` und
`pdflatex` und den Paketen aus `docs/tex-pakete.txt`, `pdftotext` (poppler).

```sh
uv sync
uv run rechnung doctor   # prüft Python, LaTeX, TeX-Pakete, pdftotext, Config, Gewerbe-Ordner
uv run rechnung demo     # vier Beispielrechnungen nach ./demo-output/
```

## Ablauf einer Rechnung

```sh
rechnung init --stammdaten            # einmalig: Ordner und ein leeres ich.yaml anlegen
rechnung neu --kunde sample-ltd
#   legt <ausgang>/2026/2026-0001/ mit vorbefülltem rechnung.yaml an;
#   leistungsdatum dort eintragen (Pflicht, resolve bricht sonst ab)
rechnung resolve 2026-0001            # Steuerfall, Summen, Fälligkeit – schreibt das Ergebnis daneben
rechnung bauen   2026-0001            # PDF
rechnung pruefen 2026-0001            # weist die Pflichtangaben im PDF-Text nach
rechnung festschreiben 2026-0001 --gesendet-am 2026-06-18
#   macht die Rechnung unveränderbar: Status, Schreibschutz, Hashes
```

`rechnung.yaml` ist die einzige Datei, die von Hand (oder von einer AI) geschrieben wird. Steuerfall,
Steuersatz, Hinweistext, Fälligkeit, Summen und Rechnungsnummer leitet das Werkzeug daraus ab und
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
make schatten                                            # Image bauen, Demo bauen und prüfen
docker run --rm -v "<gewerbe>":/gewerbe rechnung doctor  # gegen den eigenen Gewerbe-Ordner
```

Abhängigkeiten sind vollständig deklariert: Python in `uv.lock`, TeX-Pakete in `docs/tex-pakete.txt`,
Fonts offen lizenziert (XCharter, Fira Sans). Der Container baut immer mit der Standardvorlage.

## Mitentwickeln

```sh
uv run pytest -q    # Tests; die Bau-Tests brauchen LaTeX
make schatten       # Pflicht vor jedem Commit: Image bauen, Demo bauen und prüfen
make hooks          # Commit-Wächter einschalten (test und schatten tun das mit)
```

Der Commit-Wächter prüft jeden Commit samt Commit-Message gegen eine private Sperrliste
(`sperrliste.txt` neben der Config oder `RECHNUNG_SPERRLISTE`): eigener Name, Anschrift, Steuernummer,
IBAN, Kundennamen. So landen keine echten Daten im Repo, auch nicht im Text einer PDF. Das Format
steht in `.githooks/sperrliste.py`. Ohne Sperrliste ist er still; mit Sperrliste meldet
`rechnung doctor` rot, solange er in diesem Klon aus ist.

## Weiterlesen

- `docs/anleitung-neue-rechnung.md` – Schritt für Schritt eine Rechnung schreiben, plus
  Nachschlagewerk: welche Einstellung in welcher Datei steht
- `vorlage/README.md` – die LaTeX-Vorlage: Aufbau, Stilschalter, eigener Vorlagen-Ordner, `make beispiel`
- `docs/muster/` – vier Musterrechnungen (Steuerfall A–D) als visuelle Referenz

## Hinweis

Das Werkzeug ersetzt keine Steuerberatung. Es setzt die Pflichtangaben nach § 14 UStG um und prüft
sie im PDF nach; ob ein Steuerfall im Einzelfall richtig gewählt ist, bleibt deine Verantwortung.

Lizenz: MIT.
