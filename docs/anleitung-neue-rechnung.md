# Eine neue Rechnung schreiben

Ablauf und Nachschlagewerk für `ai-e-rechnung`. Die Anleitung steht absichtlich für sich: Sie lässt
sich auch außerhalb des Repos lesen, zum Beispiel in einer Notizsammlung.

Ist `rechnung` nicht installiert, laufen alle Befehle mit `uv run` aus dem Repo-Verzeichnis – oder
von überall mit `uv --directory`. Wo der Befehl gestartet wird, ist egal: Das Werkzeug schreibt nur
in den Gewerbe-Ordner aus der Config.

```sh
cd ~/Code/rechnung
uv run rechnung <kommando>
# oder von überall:
uv --directory ~/Code/rechnung run rechnung <kommando>
```

> Prototyp, noch nicht rechtlich oder steuerlich geprüft. Das Werkzeug kann noch nicht: Lieferungen von Waren, Steuerbefreiungen außer § 19 UStG, durchlaufende Posten, nicht steuerbare Zahlungen (z. B. Schadenersatz, Zuschüsse). Vollständige Liste: RULES.md, Teil 1.

Es rechnet nur sonstige Leistungen ab (§ 3 Abs. 9 UStG). Ware erkennt es an `art: lieferung` in der
Preisliste und bricht dann ab; eine Ware, die nur im Freitext steht, erkennt es nicht.

---

## Kurzfassung

```sh
uv run rechnung neu --kunde <kuerzel>
# rechnung.yaml ausfüllen (leistungsdatum, leistung: und Positionen mit Kürzel sind Pflicht),
# Belege nach belege/ legen
uv run rechnung resolve       MM-2026-0001     # Leistungsort, Ergebnis; übernimmt die Listenpreise, schreibt
                                               # mit Summen rechnung.resolved.json
uv run rechnung preise        MM-2026-0001     # bei Bedarf: Auslagen, eigene Preise, Referenz – dann resolve
uv run rechnung bauen         MM-2026-0001 --pro-forma   # optional: Pro forma an den Kunden, dann
uv run rechnung pro-forma     MM-2026-0001 --gesendet-am 2026-06-12   # festhalten, was raus ist
uv run rechnung bauen         MM-2026-0001     # erzeugt die PDF
uv run rechnung pruefen       MM-2026-0001     # weist die Pflichtangaben im PDF nach
uv run rechnung anschreiben   MM-2026-0001     # optional: Text aus anschreiben.md mit eingesetzten Werten
# PDF selbst per Mail verschicken
uv run rechnung festschreiben MM-2026-0001 --gesendet-am 2026-06-18
```

Zwischen `neu` und `festschreiben` darf beliebig oft gebaut und geprüft werden. Eingefroren wird
ausschließlich durch `festschreiben`.

Jederzeit nützlich:

```sh
uv run rechnung offen                      # alle Rechnungen, die noch nicht festgeschrieben sind, und was fehlt
uv run rechnung begruendung MM-2026-0001   # warum dieser Leistungsort und diese Steuer – für Prüfer
uv run rechnung preisliste                 # Kürzel, Einheiten, Preise; Waren mit Vermerk
uv run rechnung doctor                     # Config, Ordner, LaTeX, Commit-Wächter
uv run rechnung demo --pruefen             # sechs Beispielrechnungen aus erfundenen Daten nach ./demo-output/
```

---

## Vorbereitung, einmalig

| Was | Wo | Prüfen mit |
| --- | --- | --- |
| Config | `~/.config/rechnung/config.toml` | `rechnung doctor`, Zeile „Config“ |
| Eigene Stammdaten | `<gewerbe>/stammdaten/ich.yaml` | `rechnung doctor`, dann `rechnung resolve` meldet Lücken |
| Preisliste | `<gewerbe>/stammdaten/preise.yaml` | `rechnung preisliste` |
| Ordnerstruktur | `<gewerbe>/` | `rechnung init` legt die vier Ordner an; `--stammdaten` dazu leere, kommentierte `ich.yaml` und `preise.yaml`; `--beispiel` stattdessen die erfundenen Beispiel-Stammdaten zum Ausprobieren. Überschreibt nie |
| LaTeX, pdftotext | System | `rechnung doctor` muss grün sein |

`<gewerbe>` ist die Wurzel aus `config.toml`. Darunter gehören dem Werkzeug genau vier Ordner:
`stammdaten/`, `stammdaten/kunden/`, der Ausgangsordner und `steuerberater/`. Alles andere dort
fasst es nicht an.

---

## Schritt für Schritt

### 1. Kunde prüfen oder anlegen

Jeder Kunde ist eine Datei: `<gewerbe>/stammdaten/kunden/<kuerzel>.yaml`. Das Kürzel ist der
Dateiname ohne Endung und zugleich der Wert, der später in `rechnung.yaml` steht.

**Drei Felder bestimmen zusammen mit der Einordnung der Leistung den Leistungsort**, deshalb hier
genau hinsehen:

| Feld | Wirkung |
| --- | --- |
| `land` | ISO-Code, z. B. `DE`, `FR`, `GB`, `US`. Bestimmt Inland, EU oder Drittland |
| `unternehmer` | `true`/`false`. Bei Unternehmern ist der Leistungsort ihr Sitz; bei Privatpersonen hängt er von der Einordnung ab. Pflicht für jeden Kunden; fehlt sie, bricht `resolve` ab |
| `ustid` | USt-IdNr. Bei EU-Unternehmern Pflicht (Reverse Charge, § 14a Abs. 1 UStG); ein EU-Kunde mit `ustid` gilt als Unternehmer |

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
ustid: GB123456789                   # bei EU-Unternehmern Pflicht; erscheint als "Ihre USt-IdNr."
register:                            # optional, belegt die Unternehmereigenschaft; "Ihre Register-Nr."
  name: Companies House
  nummer: "01234567"
referenz: Sample Panel 2026          # optional, erscheint als "Ihre Referenz"
anrede: Dear Jane Sample             # optional, wörtlich; sonst "Sehr geehrte Damen und Herren" / "Dear Madam or Sir"
unternehmer: true                    # true | false – bestimmt mit der Einordnung den Leistungsort
sprache: en                          # de | en, Default aus der Config
waehrung: EUR                        # EUR | USD | GBP, Default aus der Config
```

### 1a. Preisliste

Die Preise stehen nicht in der Rechnung, sondern in `<gewerbe>/stammdaten/preise.yaml`. In
`rechnung.yaml` steht je Position nur ein Kürzel und die Menge. So kann eine AI die Rechnung
schreiben, ohne einen Preis zu sehen. `rechnung init --stammdaten` legt die Datei mit Erklärung an
(zusammen mit einer leeren `ich.yaml`), ein vollständiges Beispiel liegt in
`stammdaten.example/preise.yaml`:

```yaml
vortrag:                              # das Kürzel
  bezeichnung: { de: Vortrag, en: Talk }   # oder ein Text für beide Sprachen
  einheit: stunde                     # pauschal | stunde | tag | stueck | kilometer
  preis: 450.00                       # in EUR, je Einheit
nutzungsrecht:
  bezeichnung: { de: Einräumung von Nutzungsrechten an einem Text, en: Licence to use a text }
  einheit: pauschal
  preis: 300.00
  steuersatz: 7                       # nur als Vorschlag (§ 12 Abs. 2 Nr. 7 c UStG); ob 7 % gilt, entscheidet das Werkzeug
bahnticket:
  bezeichnung: { de: Bahnticket, en: Train ticket }
  einheit: pauschal
  art: auslage                        # kein fester Preis: Betrag je Rechnung vom Beleg
buch:
  bezeichnung: { de: Buch, en: Book }
  einheit: stueck
  preis: 24.00
  art: lieferung                      # Ware: eine Rechnung damit bricht ab (RULES.md R39)
```

`art` ist `leistung` (Default), `auslage` oder `lieferung`. Eine Position mit `art: lieferung` lässt
`resolve` als Erstes abbrechen (`Abbruch (ausserhalb)`), vor jeder Steuerentscheidung und auch im
Inland – Lieferungen von Waren kann das Werkzeug noch nicht. Solche Einträge dürfen in der Liste
stehen; die Rechnung dafür schreibst du außerhalb des Werkzeugs.

`rechnung preisliste` zeigt die Liste, Waren mit Vermerk (unter `RECHNUNG_GESCHWAERZT` ohne Preise).

### 2. Rechnung anlegen

```sh
uv run rechnung neu --kunde sample-ltd
```

Optional: `--datum` (Rechnungsdatum, Default heute), `--sprache`, `--waehrung`,
`--leistungsdatum`, `--taetigkeit`, `--einordnung`, `--ort` (füllen die Felder vor; gedacht für
Skripte und AI).

Ohne `--leistungsdatum` bleibt das Feld in `rechnung.yaml` **leer**:

```yaml
leistungsdatum:             # PFLICHT: Tag der Leistung, JJJJ-MM-TT
```

Das Werkzeug setzt hier nie still das Rechnungsdatum ein – das Leistungsdatum ist eine
Pflichtangabe, und `resolve` bricht ab, solange es fehlt. Genauso bleibt der Block `leistung:` leer,
mit der Liste der erlaubten Begriffe als Kommentar darunter (siehe Schritt 3).

Das Werkzeug vergibt die Nummer selbst, aus dem höchsten vorhandenen Ordner des Jahres plus eins,
und legt an:

```
<gewerbe>/<ausgang>/2026/MM-2026-0001/
  rechnung.yaml      vorbefüllt, mit Kommentaren
  belege/            leer
```

Das Kürzel der ersten Position bleibt ebenfalls leer und markiert.

### 3. `rechnung.yaml` ausfüllen

Die einzige Datei, die von Hand (oder von einer AI) geschrieben wird. Sie sagt, was geleistet wurde
und wie viel davon – nie, was es kostet.

```yaml
kunde: sample-ltd                    # Pflicht, Kürzel der Kundendatei
datum: 2026-06-17                    # Rechnungsdatum
leistungsdatum: 2026-06-10           # Pflicht
leistungsdatum_bis:                  # nur bei einem Zeitraum
leistung:                            # Pflicht – daraus folgt der Leistungsort
  taetigkeit: Teilnahme als Panelist  # was du tatsächlich leistest, in eigenen Worten
  einordnung: unterrichtend          # ein Begriff aus § 3a UStG, Liste unten
  ort: GB                            # nur bei Tätigkeitsleistungen: Land oder online
sprache: en                          # überschreibt Kunde und Config
waehrung: EUR                        # überschreibt Kunde und Config
zahlungsziel_tage: 14                # überschreibt die Config
einleitung: >                        # der Satz über der Tabelle, nach der Anrede; ohne Angabe bleibt die Stelle leer
  for my participation as a panelist …

positionen:                          # mindestens eine
  - kuerzel: panel                   # Pflicht, aus der Preisliste
    menge: 2
    einheit: stunde                  # Pflicht, wie in der Preisliste
    beschreibung: Panel participation, Sample Policy Forum, London   # optional, sonst die Bezeichnung
  - kuerzel: flug
    menge: 1
    einheit: pauschal
    beschreibung: "Travel: flight FRA–LON–FRA, receipt attached"

belege:                              # optional
  - datei: flug.pdf
    text: Flugbeleg FRA-LON-FRA (Position 2)
  - hotel.pdf                        # Kurzform: nur der Dateiname

leistungsort: CH                     # nur im Ausnahmefall: Leistungsort festlegen
begruendung: …                       # dann Pflicht
```

**Die Einordnung** ist der Begriff aus dem Gesetz, der deine Leistung am besten beschreibt. Maßgeblich
ist die Hauptleistung; Nebenleistungen wie Reisekosten folgen ihr. Die vollständige Liste steht als
Kommentar in jeder neuen `rechnung.yaml` und in `RULES.md`, Teil 4:

| Gruppe | Begriffe | Leistungsort bei Privatpersonen |
| --- | --- | --- |
| Tätigkeit (§ 3a Abs. 3 Nr. 3) | `kulturell`, `kuenstlerisch`, `wissenschaftlich`, `unterrichtend`, `sportlich`, `unterhaltend` | wo die Leistung erbracht wird (`ort:`); online: Wohnsitz des Kunden |
| Katalog (§ 3a Abs. 4) | `rechte`, `werbung`, `beratung`, `datenverarbeitung`, `informationen`, `personal`, `verzicht-recht`, `verzicht-taetigkeit`, `vermietung`, `energienetze` | im Drittland: Wohnsitz des Kunden; sonst Inland |
| Grundregel (§ 3a Abs. 1) | `sonstige` | Inland |

Bei Unternehmern als Kunden ist der Leistungsort immer ihr Sitz; die Einordnung wird trotzdem
festgehalten. Katalog Nr. 6 (Finanz- und Versicherungsumsätze) und elektronische Dienstleistungen
an Privatpersonen in der EU deckt das Werkzeug nicht ab.

Die Reihenfolge, in der Angaben gewinnen: **Rechnung schlägt Kunde schlägt Config.** Für die
Referenz: `rechnung.privat.yaml` schlägt die Kundendatei.

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
(„Ihre …“): `referenz` (aus `rechnung.privat.yaml` oder der Kundendatei), `ustid` und `register`
aus der Kundendatei. Beim Register steht
die Nummer vorn, das Register in Klammern dahinter. Fehlen alle drei Kundenangaben, entfällt der
untere Abschnitt samt Strich. Lange Werte brechen in ihrer Spalte um.

### 4. Belege ablegen

Jede Datei, die unter `belege:` steht, muss im Unterordner `belege/` der Rechnung liegen. Sie wird
als zusätzliche Seite ans PDF gehängt und mit „Anlage 1 zu Rechnung Nr. …“ gestempelt.

### 5. Auflösen und kontrollieren

```sh
uv run rechnung resolve MM-2026-0001
```

Fehlende Preise übernimmt es aus der Preisliste (je Position, die neu oder geändert ist; Quelle
`liste` in `rechnung.privat.yaml`). Fehlt ein Preis, den die Liste nicht hat – eine Auslage oder eine
Rechnung in Fremdwährung –, zeigt es nur Leistungsort, Ergebnis und Positionen und sagt „Preise
fehlen“; es schreibt noch nichts. Mit vollständigen Preisen zeigt es dazu Sätze, Summen, Fälligkeit und den
Hinweistext und schreibt `rechnung.resolved.json`. **Hier schaust du genau hin**, besonders auf
Leistungsort und Ergebnis: Sie folgen aus Kundendatei und Einordnung, nicht aus deiner Absicht.

### 5a. Preise eintragen oder ändern

```sh
uv run rechnung preise MM-2026-0001
```

Im eigenen Terminal, nicht über eine AI: Unter `RECHNUNG_GESCHWAERZT` verweigert der Befehl. Er zeigt
jede Position mit dem Preis aus der Liste als Vorschlag; Enter übernimmt ihn, eine Zahl ersetzt ihn
(`287,30` oder `287.30`). Auslagen sind leer. Wo das Werkzeug 7 % erlaubt (Inland, nicht als
Kleinunternehmer), fragt es je Position danach. Dann die Referenz des Kunden für diese Rechnung (ohne
Angabe die der Kundendatei), die Summen zur Kontrolle und „Bestätigen?“.

Nötig ist das für Auslagen, für Rechnungen in Fremdwährung und wenn ein Preis von der Liste abweichen
soll; sonst übernimmt `resolve` die Liste selbst. Festgehalten wird in `rechnung.privat.yaml`: die
Preise als Schnappschuss (eine spätere Änderung der Preisliste wirkt nicht zurück), der 7-%-Schalter,
die Referenz, ein Hash der Positionen und je Position die Quelle (`mensch` oder `liste`). Änderst du
danach eine Position in `rechnung.yaml` – Kürzel, Menge, Einheit oder Beschreibung – oder die
Währung, sind die Preise **veraltet**: `resolve` füllt geänderte Positionen aus der Liste, deine
Preise für unveränderte bleiben; eine geänderte Auslage trägst du neu ein, sonst baut `bauen` nichts. Die Einleitung
oder das Datum zu ändern, lässt die Preise gültig. `--aus-liste` übernimmt die Liste ohne Rückfrage
(für Skripte; verweigert bei Auslagen), `--referenz "PO 4711"` setzt die Referenz.

### 6. Bauen

```sh
uv run rechnung bauen MM-2026-0001
```

Ruft `resolve` selbst noch einmal auf und erzeugt die PDF; ohne gültig bestätigte Preise bricht es
ab. Gebaut wird in einem Temp-Verzeichnis;
im Rechnungsordner landen nur die PDF (`rechnung_MM-2026-0001.pdf`, englisch `invoice_…`) und
`rechnung.resolved.json`. Beliebig oft wiederholbar.

### 6a. Pro forma (optional)

Eine Pro forma geht an den Kunden, damit er alles prüfen kann, bevor die Rechnung mit ihren
Rechtsfolgen ausgestellt wird. Sie entsteht aus derselben `rechnung.yaml` nach denselben Regeln:

```sh
uv run rechnung bauen     MM-2026-0001 --pro-forma    # rechnung-pro-forma_MM-2026-0001.pdf, beliebig oft
uv run rechnung pruefen   MM-2026-0001 --pro-forma    # Pflichtangaben plus Kennzeichnung
# PDF selbst an den Kunden schicken
uv run rechnung pro-forma MM-2026-0001 --gesendet-am 2026-06-12
```

Jede Seite trägt „PRO FORMA – KEINE RECHNUNG“, der Betreff „(keine Rechnung)“, Nummer, Datum und
Fälligkeit sind als vorläufig markiert („Re.-Nr. (vorl.)“, „Re.-Datum (vorl.)“, „Fällig (vorl.)“), und statt der Zahlungsaufforderung steht die Bitte um Prüfung.
`rechnung pro-forma` hält fest, was du verschickt hast: `pro-forma/1/` mit der PDF und Kopien von
`rechnung.yaml`, `rechnung.privat.yaml` und `rechnung.resolved.json`, schreibgeschützt, dazu ein
Eintrag in `status.yaml`. Will der Kunde etwas geändert haben: `rechnung.yaml` anpassen oder mit
`rechnung preise` Preise bzw. Referenz ändern, neu bauen, wieder senden – das wird `pro-forma/2/`. Ist alles bestätigt, das Rechnungsdatum in `rechnung.yaml` auf den Tag der echten
Rechnung setzen und normal weiter mit Schritt 6.

Wichtig: Der Name allein macht ein Dokument nicht zur Nicht-Rechnung (§ 14 Abs. 1 UStG). Folgt auf
eine Pro forma nie eine Rechnung, ist das zu erklären (RULES.md R38).

### 7. Prüfen

```sh
uv run rechnung pruefen MM-2026-0001
```

Zieht den Text aus der fertigen PDF und weist jede Pflichtangabe nach. Rot heißt: nicht verschicken.

### 8. Verschicken

Macht das Werkzeug **nicht**. Die PDF liegt im Rechnungsordner; verschick sie per Mail, wie du magst.

Für den Begleittext kann eine AI `anschreiben.md` im Rechnungsordner entwerfen, mit Platzhaltern statt
Namen und Beträgen: `[anrede]`, `[nummer]`, `[datum]`, `[leistungsdatum]`, `[faelligkeit]`, `[netto]`,
`[brutto]`, `[firma]`, `[referenz]`, `[name]`. `uv run rechnung anschreiben MM-2026-0001` setzt die
Werte aus der gebauten Rechnung ein und gibt den Text aus; ein unbekannter Platzhalter oder ein
Platzhalter ohne Wert ist ein Abbruch.

### 9. Festschreiben

```sh
uv run rechnung festschreiben MM-2026-0001 --gesendet-am 2026-06-18
```

Danach ist die Rechnung unveränderbar: Status, Schreibschutz auf PDF, `resolved.json` und
`rechnung.privat.yaml`, Hashes in `status.yaml`. Festgeschrieben wird nur, was zu `rechnung.yaml` und
den Preisen passt. `bauen` verweigert den Neubau. `--gesendet-am` ist Pflicht und darf nicht in der
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
| `kuerzel fehlt` / `kuerzel „…“ steht nicht in der Preisliste` | Position ohne oder mit unbekanntem Kürzel | Kürzel aus `rechnung preisliste` eintragen oder die Liste ergänzen |
| `einheit „stunde“, die Preisliste führt … in „pauschal“` | Einheit passt nicht zur Liste | Einheit der Liste nehmen, Menge darin angeben |
| `positionen.0.menge: … (Wert: {2})` | Platzhalter-Klammern stehen gelassen | Klammern entfernen: `menge: 2` |
| `Abbruch (preise): Preise … sind noch nicht bestätigt` / `… veraltet` | ein Preis, den die Liste nicht hat (Auslage, Fremdwährung) | `rechnung preise <nr>` im eigenen Terminal |
| `Position … hat keinen Preis in der Liste – Auslage oder Fremdwährung` | `rechnung preise --aus-liste` bei einer Auslage oder in Fremdwährung | ohne `--aus-liste` aufrufen und den Betrag eingeben |
| `Position … (buch): Lieferung von Waren (art: lieferung …)` | Kürzel ist in der Preisliste als Ware markiert | kann das Werkzeug noch nicht (RULES.md R39); Rechnung außerhalb schreiben |
| `referenz: steht nicht in rechnung.yaml` | Referenz aus einer alten Rechnungsdatei | mit `rechnung preise` eintragen |
| `einleitung: enthält den Platzhalter {Event} …` | `{…}` aus einer Vorlage nicht ersetzt | echten Text einsetzen |
| `leistungdatum: Extra inputs are not permitted` | Feldname vertippt | Tippfehler korrigieren |
| `leistung: taetigkeit fehlt …` / `einordnung fehlt …` | Block nach `rechnung neu` noch leer | Tätigkeit und Begriff aus der Liste eintragen |
| `ort fehlt: bei „unterrichtend“ …` | Tätigkeitsleistung ohne Ort | `ort:` mit Ländercode oder `online` |
| `` `unternehmer` ist nicht gesetzt `` | Kundendatei sagt nicht, ob Unternehmer oder Privatperson | `unternehmer: true` oder `false` in der Kundendatei |
| `` `ustid` fehlt `` / `Eigene USt-IdNr. fehlt` | Reverse Charge braucht beide USt-IdNrn. | in Kunden- bzw. eigener Stammdatei ergänzen |
| `Leistungsort … ist ein anderer EU-Staat …` | Privatperson, Leistung in einem anderen EU-Land | nicht abgedeckt (RULES.md R18) |
| `steuerfall: gibt es nicht mehr` | alte Rechnungsdatei | `leistung:` eintragen; Sonderfall über `leistungsort:` + `begruendung:` |
| `Währung USD mit Umsatzsteuerausweis …` | Fremdwährung mit deutscher USt | In EUR fakturieren; Umrechnung ist noch nicht gebaut |
| `Beleg fehlt: …` | Datei steht im YAML, liegt aber nicht in `belege/` | Datei hinlegen oder Eintrag löschen |
| `Rechnung … ist festgeschrieben` | Neubau einer eingefrorenen Rechnung | Storno und neue Rechnung |
| `… passt nicht mehr zu rechnung.yaml oder den Preisen` | `rechnung pro-forma` oder `festschreiben` nach einer Änderung ohne neuen Bau | neu bauen, ansehen, dann festhalten |
| `Land XX ist in rules.LAENDER nicht hinterlegt` | Neues Land | In `src/rechnung/rules.py` eintragen |

### YAML-Fallen

Aus dem ersten echten Testlauf. Die Faustregel: **Text mit Satzzeichen in Anführungszeichen setzen.**

| Falle | Was passiert | So geht es richtig |
| --- | --- | --- |
| ` #` mitten im Wert, z. B. `beschreibung: Workshop #3` | Alles ab ` #` ist ein Kommentar; „#3“ verschwindet still | `beschreibung: "Workshop #3"` |
| `{…}` am Wertanfang, z. B. `menge: {2}` | YAML liest ein Dictionary; `resolve` meldet den Wert und rät, die Klammern zu entfernen | `menge: 2` |
| `: ` mitten im Text, z. B. `einleitung: Panel: Zukunft der Arbeit` | Syntaxfehler „Doppelpunkt mit Leerzeichen mitten im Wert“ | `einleitung: "Panel: Zukunft der Arbeit"` |
| Block nur halb auskommentiert: `# belege:` über `  - flug.pdf` | Syntaxfehler „Listeneintrag ohne Schlüssel darüber“ | beide Zeilen aus- oder beide einkommentieren |
| `??` als Platzhalter, z. B. `beschreibung: ??` | Wird als Text gedruckt; nur in Zahlenfeldern fällt es auf | Platzhalter vor dem Bauen ersetzen; im PDF nach `??` suchen |

---

## Wo welche Einstellung steht

### Steuerliche Logik — `RULES.md` und `src/rechnung/rules.py`

`RULES.md` beschreibt die Regeln mit Gesetzeswortlaut, Status und Grenzen; `rules.py` ist der einzige
Ort, an dem über Steuern entschieden wird. Die Vorlage druckt nur.

| Thema | Fundstelle in `rules.py` | Inhalt |
| --- | --- | --- |
| Entscheidungskern | `kern()` | Entscheidungstabelle aus RULES.md Teil 4 über abstrakte Merkmale |
| Übersetzung | `entscheide()` | Kunde, Leistung, Aussteller → Merkmale → Leistungsort, Ergebnis, Satz, Regeln |
| Einordnung | `EINORDNUNGEN` | Begriffe aus § 3a UStG mit Gruppe und Fundstelle |
| EU-Länder | `EU_LAENDER`, `kategorie()` | Liste mit Stand-Datum; UK ist Drittland |
| Ländernamen | `LAENDER` | deutscher und englischer Name, für den Hinweistext |
| Hinweistexte | `hinweis()` | Wortlaut je Ergebnis und Sprache |
| Frist Reverse Charge | `frist_reverse_charge()` | 15. des Folgemonats, Warnung bei `resolve` |
| Fälligkeit | `faelligkeit()` | Rechnungsdatum plus Zahlungsziel |
| Rundung | `runde()` | kaufmännisch, zwei Stellen, je Zeile und je Steuersatz |
| Nummernvergabe | `nummer()`, `naechste_lfd()` | Format aus der Config, laufende Nummer aus den Ordnern |
| Währungsregel | `waehrung_erlaubt()` | Fremdwährung nur ohne deutschen USt-Ausweis |

| Ergebnis | Wann | Satz | Text auf der Rechnung |
| --- | --- | --- | --- |
| `inland` | Leistungsort Inland | 19 % (7 % je Position möglich) | kein Hinweis |
| `reverse_charge` | Leistungsort anderer EU-Staat, Kunde Unternehmer | 0 % | „Steuerschuldnerschaft des Leistungsempfängers (§ 14a Abs. 1 UStG, Art. 196 MwStSystRL).“ |
| `nicht_steuerbar` | Leistungsort Drittland | 0 % | „Leistungsort: {Land}. Die Leistung ist in Deutschland nicht steuerbar ({Fundstelle}).“ |
| `kleinunternehmer` | Leistungsort Inland, `kleinunternehmer: true` in `ich.yaml` | 0 % | „Steuerfrei als Leistung eines Kleinunternehmers (§ 19 Abs. 1 UStG).“, keine Steuerzeile |

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
| `vorlage` | – | eigener Vorlagen-Ordner; seine Dateien ersetzen die gleichnamigen der Standardvorlage |
| `demo` | `false` | Demo-Betrieb für Ausprobierer: nur die erfundenen Stammdaten aus `stammdaten.example/`, ein Gewerbe-Ordner mit eigener `ich.yaml` wird verweigert |

### Eigene Stammdaten — `<gewerbe>/stammdaten/ich.yaml`

Pflegt nur der Mensch. Weder das Werkzeug noch eine AI schreiben diese Datei.

| Feld | Pflicht | Erscheint |
| --- | --- | --- |
| `name` | ja | Briefkopf, Gruß, Rücksendeangabe, Kontoinhaber |
| `geschaeftsbezeichnung` | nein | fette Zeile im Briefkopf statt des Namens |
| `adresse.strasse`, `adresse.plz`, `adresse.ort` | ja | Briefkopf und Rücksendeangabe |
| `land` | nein (Default `DE`) | Briefkopf bei englischen Rechnungen; ein anderes Land als `DE` lässt `resolve` abbrechen (RULES.md R4) |
| `email`, `telefon`, `website` | E-Mail ja | Briefkopf oben rechts |
| `steuernummer` **oder** `ustid` | eines von beiden | Metadatenblock und Fußzeile |
| `kleinunternehmer` | nein (`false`) | `true`: § 19 UStG, keine Umsatzsteuer; die Umsatzgrenzen prüfst du selbst |
| `bank.kontoinhaber`, `bank.iban` | ja | Zahlungssatz und Fußzeile |
| `bank.bic`, `bank.name` | nein | Zahlungssatz und Fußzeile |

### Aussehen — `vorlage/style/defaults.sty`

Schriften, Farben (Akzent Schwarz `#000000`, Grau `#C8C8C8`), Linienstärken, Ränder, Position des
Anschriftfelds (45 mm, DIN 5008 Form B), Schriftgrößen, Schalter für Schlussformel und
Anlagenstempel. Nie in `invoice.sty` ändern — dort steckt die Mechanik.

Für ein eigenes Aussehen nicht die Datei im Repo ändern, sondern eine Kopie in einen eigenen
Vorlagen-Ordner legen und ihn als `vorlage` in die Config eintragen (siehe `vorlage/README.md`).

### Pflichtangaben — `src/rechnung/pruefen.py`

Welche Angaben `pruefen` im PDF-Text nachweist und mit welcher Fundstelle im UStG.

---

## Mit einer AI: Skill und MCP-Server

Eine AI kann die Rechnung schreiben, ohne zu sehen, wer beteiligt ist und was es kostet. Zwei Wege:

- **MCP-Server** (`uv run rechnung mcp`, stdio; im Container `docker run -i --rm -v <gewerbe>:/gewerbe
  rechnung mcp`). Die AI bekommt nur seine Werkzeuge – `neu`, `preisliste`, `lesen`, `schreiben`,
  `resolve`, `begruendung`, `offen`, `bauen`, `pruefen`, `anschreiben_schreiben`, `anschreiben_pruefen` –
  und nur geschwärzte Antworten: keine Namen, Anschriften, Beträge, nicht einmal das Kürzel des Kunden.
  Jede Antwort zu einer Rechnung nennt in `naechster_schritt`, was als Nächstes kommt. Den Kunden
  wählt der Mensch (`--kunde` beim Start, ein Formular im Client oder er nennt der AI das Kürzel).
  `preise`, `pro-forma` und `festschreiben` sind keine Werkzeuge; `--preise-im-client` bietet die
  Preisbestätigung als Formular an. `--demo` (oder `RECHNUNG_DEMO=1`) nimmt nur die erfundenen
  Stammdaten und gibt der AI zusätzlich das Werkzeug `kunden` mit den Testkunden. Hier ist die Grenze
  echt: Die AI hat nur diese Werkzeuge.
- **Skill in Claude Code** (`.claude/skills/rechnung/SKILL.md`) mit `RECHNUNG_GESCHWAERZT=1`: die
  Befehle geben dann nur geschwärzte Ausgaben, ein Hook sperrt das Lesen im Gewerbe-Ordner. Lesen
  über Bash ist damit nicht ganz gesperrt – echte Durchsetzung bietet der MCP-Server.

In beiden Fällen gilt derselbe Vertrag wie für einen Menschen. Er steht ausführlich in `CLAUDE.md`,
hier das Wesentliche:

**Eine AI darf:** `rechnung.yaml` und `anschreiben.md` anlegen und ändern, Kundendateien als Vorschlag anlegen (der Mensch
bestätigt, weil `land`, `ustid` und `unternehmer` den Leistungsort bestimmen), Code und Vorlage ändern.

**Eine AI darf nicht:** `rechnung.resolved.json`, PDFs, `status.yaml`, `pro-forma/`, `rechnung.privat.yaml`,
`ich.yaml` oder `preise.yaml` schreiben, Preise bestätigen, Rechnungsnummern vergeben, Beträge ausrechnen, festgeschriebene Rechnungen anfassen. Das ist
zusätzlich technisch erzwungen, über einen PreToolUse-Hook und Deny-Regeln.

**Gut automatisierbar**, weil deterministisch und mit klaren Exit-Codes: `neu`, `resolve`, `bauen`,
`pruefen`, `offen`, `begruendung`, `doctor`. Jeder Fehler ist eine Meldung, die sagt, was zu tun ist;
unter dem Schalter beginnt sie mit `Abbruch (<art>):` – `eingabe`, `frage`, `stammdaten`,
`ausserhalb` oder `preise`.

**Nicht automatisieren:** `preise`, `festschreiben` und `pro-forma`. `preise`, weil die Beträge an der
AI vorbeigehen sollen. `festschreiben` und `pro-forma`, weil sie wissen müssen, wann das Dokument
tatsächlich beim Kunden war, und unumkehrbar sind.

**Ablauf für einen Assistenten:** `neu` → `preisliste` → `rechnung.yaml` füllen → `resolve` ausführen
und dem Menschen **zeigen**, was herauskommt (vor allem Einordnung, Leistungsort und Ergebnis) →
Bestätigung abwarten → Listenpreise übernimmt `resolve` selbst; Auslagen trägt der Mensch im eigenen
Terminal ein → `bauen` → `pruefen` → dem Menschen die PDF geben. Das Festschreiben macht der Mensch
nach dem Versand.
