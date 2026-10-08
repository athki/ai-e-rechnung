# Eine neue Rechnung schreiben

Ablauf und Nachschlagewerk für `ai-e-rechnung`. Die Anleitung steht absichtlich für sich: Sie lässt
sich auch außerhalb des Repos lesen, zum Beispiel in einer Notizsammlung.

Alle Befehle laufen aus dem Repo-Verzeichnis, mit `uv run` davor:

```sh
cd ~/Code/rechnung
uv run rechnung <kommando>
```

---

## Kurzfassung

```sh
uv run rechnung neu --kunde <kuerzel>
# rechnung.yaml ausfüllen (leistungsdatum ist Pflicht), Belege nach belege/ legen
uv run rechnung resolve       MM-2026-0001     # zeigt Steuerfall und Summen, schreibt rechnung.resolved.json
uv run rechnung bauen         MM-2026-0001     # erzeugt die PDF
uv run rechnung pruefen       MM-2026-0001     # weist die Pflichtangaben im PDF nach
# PDF selbst per Mail verschicken
uv run rechnung festschreiben MM-2026-0001 --gesendet-am 2026-06-18
```

Zwischen `neu` und `festschreiben` darf beliebig oft gebaut und geprüft werden. Eingefroren wird
ausschließlich durch `festschreiben`.

---

## Vorbereitung, einmalig

| Was | Wo | Prüfen mit |
| --- | --- | --- |
| Config | `~/.config/rechnung/config.toml` | `rechnung doctor`, Zeile „Config“ |
| Eigene Stammdaten | `<gewerbe>/stammdaten/ich.yaml` | `rechnung doctor`, dann `rechnung resolve` meldet Lücken |
| Ordnerstruktur | `<gewerbe>/` | `rechnung init` legt die vier Ordner an |
| LaTeX, pdftotext | System | `rechnung doctor` muss grün sein |

`<gewerbe>` ist die Wurzel aus `config.toml`. Darunter gehören dem Werkzeug genau vier Ordner:
`stammdaten/`, `stammdaten/kunden/`, der Ausgangsordner und `steuerberater/`. Alles andere dort
fasst es nicht an.

---

## Schritt für Schritt

### 1. Kunde prüfen oder anlegen

Jeder Kunde ist eine Datei: `<gewerbe>/stammdaten/kunden/<kuerzel>.yaml`. Das Kürzel ist der
Dateiname ohne Endung und zugleich der Wert, der später in `rechnung.yaml` steht.

**Drei Felder entscheiden über die Umsatzsteuer**, deshalb hier genau hinsehen:

| Feld | Wirkung |
| --- | --- |
| `land` | ISO-Code, z. B. `DE`, `FR`, `GB`, `US`. Bestimmt Inland, EU oder Drittland |
| `ustid` | USt-IdNr. Bei EU-Kunden entscheidet sie über Reverse Charge |
| `unternehmer` | `true`/`false`. Bei Drittlandskunden entscheidet sie über Steuerbarkeit |

Vollständige Kundendatei:

```yaml
firma: Sample Ltd                    # Pflicht, juristische Person, nicht der Ansprechpartner
ansprechpartner: Jane Sample         # optional
adresse:
  strasse: 1 Sample Street
  zusatz:                            # optional, z. B. "2nd floor"
  plz: EC1A 1AA
  ort: London
land: GB                             # Pflicht
ustid: GB123456789                   # bei EU-Kunden für Fall B nötig; erscheint als "Ihre USt-IdNr."
register:                            # optional, belegt die Unternehmereigenschaft; "Ihre Register-Nr."
  name: Companies House
  nummer: "01234567"
referenz: Sample Panel 2026          # optional, erscheint als "Ihre Referenz"
unternehmer: true                    # bei Drittlandskunden wichtig
sprache: en                          # de | en, Default aus der Config
waehrung: EUR                        # EUR | USD | GBP, Default aus der Config
```

### 2. Rechnung anlegen

```sh
uv run rechnung neu --kunde sample-ltd
```

Optional: `--datum` (Rechnungsdatum, Default heute), `--sprache`, `--waehrung`,
`--leistungsdatum` (füllt das Feld vor; gedacht für Skripte und AI).

Ohne `--leistungsdatum` bleibt das Feld in `rechnung.yaml` **leer**:

```yaml
leistungsdatum:             # PFLICHT: Tag der Leistung, JJJJ-MM-TT
```

Das Werkzeug setzt hier nie still das Rechnungsdatum ein – das Leistungsdatum ist eine
Pflichtangabe, und `resolve` bricht ab, solange es fehlt.

Das Werkzeug vergibt die Nummer selbst, aus dem höchsten vorhandenen Ordner des Jahres plus eins,
und legt an:

```
<gewerbe>/<ausgang>/2026/MM-2026-0001/
  rechnung.yaml      vorbefüllt, mit Kommentaren
  belege/            leer
```

### 3. `rechnung.yaml` ausfüllen

Die einzige Datei, die von Hand geschrieben wird.

```yaml
kunde: sample-ltd                    # Pflicht, Kürzel der Kundendatei
datum: 2026-06-17                    # Rechnungsdatum
leistungsdatum: 2026-06-10           # Pflicht
leistungsdatum_bis:                  # nur bei einem Zeitraum
sprache: en                          # überschreibt Kunde und Config
waehrung: EUR                        # überschreibt Kunde und Config
zahlungsziel_tage: 14                # überschreibt die Config
referenz: Sample Panel 2026          # überschreibt die Kundendatei
einleitung: >                        # der Satz über der Tabelle; ohne Angabe bleibt die Stelle leer
  For my participation as a panelist …

positionen:                          # mindestens eine
  - beschreibung: Teilnahme als Panelist, Sample Policy Forum, London
    menge: 1
    einheit: pauschal                # pauschal | stunde | tag | stueck | kilometer — Pflicht
    einzelpreis: 0.00
    steuersatz: 7                    # nur im Inland, wenn abweichend von 19

belege:                              # optional
  - datei: flug.pdf
    text: Flugbeleg FRA-LON-FRA (Position 2)
  - hotel.pdf                        # Kurzform: nur der Dateiname

steuerfall: D                        # nur im Ausnahmefall, siehe unten
begruendung: …                       # dann Pflicht
```

Die Reihenfolge, in der Angaben gewinnen: **Rechnung schlägt Kunde schlägt Config.**

Platzhalter aus Vorlagen oder Notizen (`{Event}`, `{354.82}`) vollständig ersetzen, Klammern
eingeschlossen. Bleibt ein `{…}` in einem Text stehen, bricht `resolve` ab, statt ihn ins PDF zu
drucken. Wann Anführungszeichen nötig sind, steht unten unter „YAML-Fallen“.

### So sieht der Kopf der Rechnung aus

Links steht nur die Postanschrift des Kunden, so, wie sie im Fensterumschlag erscheint. Rechts
steht der Metadatenblock in drei Abschnitten, getrennt durch dünne graue Striche:

```
Sample Ltd                   Invoice no.         MM-2026-0001
Jane Sample                  Invoice date        17 June 2026
1 Sample Street              Date of service     10 June 2026
London EC1A 1AA              Due date            1 July 2026
United Kingdom               ────────────────────────────────────
                             Our tax no.         143/123/12345
                             Our VAT ID          DE123456789
                             ────────────────────────────────────
                             Your reference      Sample Panel 2026
                             Your VAT no.        GB123456789
                             Your company no.    01234567 (Companies
                                                 House)
```

Oben die Rechnung selbst, in der Mitte deine Steuerdaten („Unsere …“), unten die des Kunden
(„Ihre …“): `referenz`, `ustid` und `register` aus Kunden- oder Rechnungsdatei. Beim Register steht
die Nummer vorn, das Register in Klammern dahinter. Fehlen alle drei Kundenangaben, entfällt der
untere Abschnitt samt Strich. Lange Werte brechen in ihrer Spalte um.

### 4. Belege ablegen

Jede Datei, die unter `belege:` steht, muss im Unterordner `belege/` der Rechnung liegen. Sie wird
als zusätzliche Seite ans PDF gehängt und mit „Anlage 1 zu Rechnung Nr. …“ gestempelt.

### 5. Auflösen und kontrollieren

```sh
uv run rechnung resolve MM-2026-0001
```

Zeigt Steuerfall, Sätze, Summen, Fälligkeit und den Hinweistext. **Hier schaust du genau hin**,
besonders auf den Steuerfall: Er folgt aus der Kundendatei, nicht aus deiner Absicht.

### 6. Bauen

```sh
uv run rechnung bauen MM-2026-0001
```

Ruft `resolve` selbst noch einmal auf und erzeugt die PDF. Gebaut wird in einem Temp-Verzeichnis;
im Rechnungsordner landen nur `rechnung.pdf` und `rechnung.resolved.json`. Beliebig oft wiederholbar.

### 7. Prüfen

```sh
uv run rechnung pruefen MM-2026-0001
```

Zieht den Text aus der fertigen PDF und weist jede Pflichtangabe nach. Rot heißt: nicht verschicken.

### 8. Verschicken

Macht das Werkzeug **nicht**. Die PDF liegt im Rechnungsordner; verschick sie per Mail, wie du magst.

### 9. Festschreiben

```sh
uv run rechnung festschreiben MM-2026-0001 --gesendet-am 2026-06-18
```

Danach ist die Rechnung unveränderbar: Status, Schreibschutz auf PDF und `resolved.json`, Hashes in
`status.yaml`. `bauen` verweigert den Neubau. `--gesendet-am` ist Pflicht und darf nicht in der
Zukunft liegen.

**Korrektur nach dem Festschreiben:** niemals am Original. Stornorechnung plus neue Rechnung — im
Werkzeug noch nicht gebaut (geplant).

---

## Wenn etwas schiefgeht

| Meldung | Ursache | Lösung |
| --- | --- | --- |
| `rechnung.yaml, Zeile 7, Spalte 18: …` | YAML-Syntaxfehler; die Meldung zeigt die Zeile und markiert die Stelle | siehe „YAML-Fallen“ unten |
| `leistungsdatum fehlt: …` | Feld ist nach `rechnung neu` noch leer | Tag der Leistung als `JJJJ-MM-TT` eintragen |
| `positionen.0.einheit: Field required` | Pflichtfeld fehlt | Feld ergänzen; Einheit wird nie geraten |
| `positionen.0.einzelpreis: … (Wert: {354.82})` | Platzhalter-Klammern stehen gelassen | Klammern entfernen: `einzelpreis: 354.82` |
| `einleitung: enthält den Platzhalter {Event} …` | `{…}` aus einer Vorlage nicht ersetzt | echten Text einsetzen |
| `leistungdatum: Extra inputs are not permitted` | Feldname vertippt | Tippfehler korrigieren |
| `Steuerfall D erkannt …` | Bei Drittlandskunden fehlt `unternehmer: true`, bei EU-Kunden die `ustid` | Kundendatei ergänzen, oder D mit `begruendung:` bestätigen |
| `Währung USD mit Umsatzsteuerausweis …` | Fremdwährung mit deutscher USt | In EUR fakturieren; Umrechnung ist noch nicht gebaut |
| `Beleg fehlt: …` | Datei steht im YAML, liegt aber nicht in `belege/` | Datei hinlegen oder Eintrag löschen |
| `Rechnung … ist festgeschrieben` | Neubau einer eingefrorenen Rechnung | Storno und neue Rechnung |
| `Land XX ist in rules.LAENDER nicht hinterlegt` | Neues Land | In `src/rechnung/rules.py` eintragen |

### YAML-Fallen

Aus dem ersten echten Testlauf. Die Faustregel: **Text mit Satzzeichen in Anführungszeichen setzen.**

| Falle | Was passiert | So geht es richtig |
| --- | --- | --- |
| ` #` mitten im Wert, z. B. `referenz: PO #594` | Alles ab ` #` ist ein Kommentar; „#594“ verschwindet still | `referenz: "PO #594"` |
| `{…}` am Wertanfang, z. B. `einzelpreis: {354.82}` | YAML liest ein Dictionary; `resolve` meldet den Wert und rät, die Klammern zu entfernen | `einzelpreis: 354.82` |
| `: ` mitten im Text, z. B. `einleitung: Panel: Zukunft der Arbeit` | Syntaxfehler „Doppelpunkt mit Leerzeichen mitten im Wert“ | `einleitung: "Panel: Zukunft der Arbeit"` |
| Block nur halb auskommentiert: `# belege:` über `  - flug.pdf` | Syntaxfehler „Listeneintrag ohne Schlüssel darüber“ | beide Zeilen aus- oder beide einkommentieren |
| `??` als Platzhalter, z. B. `beschreibung: ??` | Wird als Text gedruckt; nur in Zahlenfeldern fällt es auf | Platzhalter vor dem Bauen ersetzen; im PDF nach `??` suchen |

---

## Wo welche Einstellung steht

### Steuerliche Logik — `src/rechnung/rules.py`

Das ist der einzige Ort, an dem über Steuern entschieden wird. Die Vorlage druckt nur.

| Thema | Fundstelle in `rules.py` | Inhalt |
| --- | --- | --- |
| Steuerfall | `steuerfall()` | A Inland · B EU mit USt-IdNr. · C Drittland-Unternehmen · D sonst |
| EU-Länder | `EU_LAENDER` | Liste mit Stand-Datum; UK ist Drittland |
| Ländernamen | `LAENDER` | deutscher und englischer Name, für den Hinweistext |
| Steuersatz | `steuersatz()` | 0 % bei B und C, sonst 19 %; 7 % nur je Position im Inland |
| Hinweistexte | `hinweis()` | Wortlaut für Fall B und C, je Sprache |
| Fälligkeit | `faelligkeit()` | Rechnungsdatum plus Zahlungsziel |
| Rundung | `runde()` | kaufmännisch, zwei Stellen, je Zeile und je Steuersatz |
| Nummernvergabe | `nummer()`, `naechste_lfd()` | Format aus der Config, laufende Nummer aus den Ordnern |
| Währungsregel | `waehrung_erlaubt()` | Fremdwährung nur ohne deutschen USt-Ausweis |

| Fall | Bedingung | Satz | Text auf der Rechnung |
| --- | --- | --- | --- |
| A | Kunde in Deutschland | 19 % (7 % je Position möglich) | kein Hinweis |
| B | EU-Land **und** `ustid` gesetzt | 0 % | „Steuerschuldnerschaft des Leistungsempfängers (§ 14a Abs. 5 UStG, Art. 196 MwStSystRL).“ |
| C | Drittland **und** `unternehmer: true` | 0 % | „Leistungsort: {Land}. Die Leistung ist in Deutschland nicht steuerbar (§ 3a Abs. 2 UStG).“ |
| D | alles andere | 19 % | kein Hinweis; `resolve` bricht ab, bis du D mit `begruendung:` bestätigst |

Die Kleinunternehmerregelung (§ 19 UStG) wird bewusst nicht unterstützt.

### Betriebseinstellungen — `~/.config/rechnung/config.toml`

Jede Option gibt es auch als Umgebungsvariable `RECHNUNG_<OPTION>`; die Umgebung gewinnt.

| Option | Default | Bedeutung |
| --- | --- | --- |
| `gewerbe` | – | Wurzel des Gewerbe-Ordners |
| `stammdaten` | `stammdaten` | Unterordner der eigenen Stammdaten |
| `kunden` | `stammdaten/kunden` | Unterordner der Kundendateien |
| `ausgang` | `rechnung-ausgang` | Unterordner der Ausgangsrechnungen |
| `steuerberater` | `steuerberater` | Ziel des Jahresexports |
| `engine` | `pdflatex` | LaTeX-Engine |
| `nummer_format` | `{jahr}-{lfd:04d}` | ganzes Nummernformat, z. B. `MM-{jahr}-{lfd:04d}` |
| `zahlungsziel_tage` | `14` | Tage bis zur Fälligkeit |
| `sprache` | `de` | `de` oder `en` |
| `waehrung` | `EUR` | `EUR`, `USD` oder `GBP` |

### Eigene Stammdaten — `<gewerbe>/stammdaten/ich.yaml`

Pflegt nur der Mensch. Weder das Werkzeug noch eine AI schreiben diese Datei.

| Feld | Pflicht | Erscheint |
| --- | --- | --- |
| `name` | ja | Briefkopf, Gruß, Rücksendeangabe, Kontoinhaber |
| `geschaeftsbezeichnung` | nein | fette Zeile im Briefkopf statt des Namens |
| `adresse.strasse`, `adresse.plz`, `adresse.ort` | ja | Briefkopf und Rücksendeangabe |
| `land` | ja (`DE`) | Briefkopf bei englischen Rechnungen |
| `email`, `telefon`, `website` | E-Mail ja | Briefkopf oben rechts |
| `steuernummer` **oder** `ustid` | eines von beiden | Metadatenblock und Fußzeile |
| `bank.kontoinhaber`, `bank.iban`, `bank.bic`, `bank.name` | für die Zahlung | Zahlungssatz und Fußzeile |

### Aussehen — `vorlage/style/defaults.sty`

Schriften, Farben (Akzent Schwarz `#000000`, Grau `#C8C8C8`), Linienstärken, Ränder, Position des
Anschriftfelds (45 mm, DIN 5008 Form B), Schriftgrößen, Schalter für Schlussformel und
Anlagenstempel. Nie in `invoice.sty` ändern — dort steckt die Mechanik.

Für ein eigenes Aussehen nicht die Datei im Repo ändern, sondern eine Kopie in einen eigenen
Vorlagen-Ordner legen und ihn als `vorlage` in die Config eintragen (siehe `vorlage/README.md`).

### Pflichtangaben — `src/rechnung/pruefen.py`

Welche Angaben `pruefen` im PDF-Text nachweist und mit welcher Fundstelle im UStG.

---

## Für später: Automatisierung und MCP-Server

Wenn dieses Werkzeug einmal über einen MCP-Server oder direkt aus Claude bedient wird, gilt derselbe
Vertrag wie für einen Menschen. Er steht ausführlich in `CLAUDE.md`, hier das Wesentliche:

**Eine AI darf:** `rechnung.yaml` anlegen und ändern, Kundendateien als Vorschlag anlegen (der Mensch
bestätigt, weil `land` und `ustid` den Steuerfall bestimmen), Code und Vorlage ändern.

**Eine AI darf nicht:** `rechnung.resolved.json`, PDFs, `status.yaml` oder `ich.yaml` schreiben,
Rechnungsnummern vergeben, Beträge ausrechnen, festgeschriebene Rechnungen anfassen. Das ist
zusätzlich technisch erzwungen, über einen PreToolUse-Hook und Deny-Regeln.

**Gut automatisierbar**, weil deterministisch und mit klaren Exit-Codes: `neu`, `resolve`, `bauen`,
`pruefen`, `doctor`. Jeder Fehler ist eine Meldung, die sagt, was zu tun ist.

**Nicht automatisieren:** `festschreiben`. Es verlangt zu wissen, wann die Rechnung tatsächlich beim
Kunden war, und es ist unumkehrbar.

**Sinnvoller Ablauf für einen Assistenten:** `neu` → `rechnung.yaml` füllen → `resolve` ausführen und
dem Menschen **zeigen**, was herauskommt (vor allem den Steuerfall) → Bestätigung abwarten → `bauen`
→ `pruefen` → dem Menschen die PDF geben. Das Festschreiben macht der Mensch nach dem Versand.
