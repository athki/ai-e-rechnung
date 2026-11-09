---
name: rechnung
description: Eine Rechnung mit dem Werkzeug `rechnung` erstellen – von `rechnung neu` über rechnung.yaml bis `bauen` und `pruefen`, mit geschwärzter Sicht (die AI sieht keine Kundendaten, Preise oder Beträge; die Preise kommen aus der Preisliste oder vom Menschen selbst). Greift, wenn jemand eine Rechnung schreiben, auflösen, bauen oder prüfen lassen will, oder bei /rechnung. Nicht für Arbeit am Code, an Tests oder an der Vorlage.
---

# Rechnung erstellen

Du bedienst das Werkzeug `rechnung` für den Menschen. Er sagt dir, was er geleistet hat; das Werkzeug
entscheidet Leistungsort und Steuer (`rules.py`) und setzt Namen, Anschriften und Beträge selbst ein.

**Die Grenze:** Du weißt, was geleistet wurde und wie viel davon – nie, wer beteiligt ist und was es
kostet. Du liest keine Kundendaten, keine Ausstellerdaten, keine Preisliste, keine `rechnung.privat.yaml`,
keine `rechnung.resolved.json`, keine PDFs, keine `status.yaml`, nichts unter `pro-forma/`,
`belege/` oder `unterlagen/`. Was du vom Werkzeug brauchst, gibt es dir geschwärzt aus.

**Geltungsbereich**, sag es dem Menschen einmal vor der ersten Rechnung:

> Prototyp, noch nicht rechtlich oder steuerlich geprüft. Das Werkzeug kann noch nicht: Lieferungen
> von Waren, Steuerbefreiungen außer § 19 UStG, durchlaufende Posten, nicht steuerbare Zahlungen
> (z. B. Schadenersatz, Zuschüsse). Vollständige Liste: RULES.md, Teil 1.

Klingt das, was er geleistet hat, nach einem dieser Fälle (er verkauft Bücher, rechnet Gebühren ab, die
er für den Kunden bezahlt hat, gibt steuerfreien Unterricht), sag es, bevor du etwas anlegst.

Jeder Abschnitt unten entspricht einem Werkzeug des MCP-Servers (`rechnung mcp`, README). Stehen
dir dessen Werkzeuge zur Verfügung (`neu`, `schreiben`, `resolve` …), nimm sie statt der Befehle
hier: Sie schwärzen immer, und `neu` fragt den Kunden selbst beim Menschen ab. Jede ihrer Antworten
nennt in `naechster_schritt`, was als Nächstes kommt; halte dich daran. Im Demo-Betrieb
(`RECHNUNG_DEMO`, nur erfundene Daten) zeigt das Werkzeug `kunden` die Testkunden – zeig sie dem
Menschen und lass ihn wählen. Sonst gibt es `kunden` nicht, und du fragst nach dem Kürzel.

## 1. Wurzel feststellen

Bevor du etwas anlegst, nenne dem Menschen die aktive Gewerbe-Wurzel:

```
printenv RECHNUNG_GEWERBE
printenv RECHNUNG_GESCHWAERZT
```

- `RECHNUNG_GEWERBE` leer: Das Werkzeug arbeitet im echten Gewerbe-Ordner aus der Config. **Vor
  `rechnung neu` fragen**, ob wirklich dort – jede Rechnung verbraucht eine echte Nummer.
- `RECHNUNG_GESCHWAERZT` leer oder `0`: Die Ausgabe ist nicht geschwärzt. Anhalten und dem Menschen
  sagen, dass der Schalter fehlt (`.claude/settings.local.json`, `env`). Nicht selbst setzen.

In Ausgaben steht `<gewerbe>` für diese Wurzel. Für Read und Edit auf `rechnung.yaml` setzt du den
Pfad aus `RECHNUNG_GEWERBE` zusammen.

## 2. Rechnung anlegen – `rechnung neu`

Den Kunden wählt der Mensch. Entweder legt er die Rechnung selbst an und nennt dir die Nummer, oder
er nennt dir das Kürzel, und du rufst auf:

```
rechnung neu --kunde <kürzel> [--leistungsdatum JJJJ-MM-TT] [--taetigkeit "…"] [--einordnung <wort>] [--ort <LAND|online>]
```

Rate nie ein Kürzel, und lies nicht in `stammdaten/`, um eins zu finden. Füll die Optionen nur mit
dem, was der Mensch gesagt hat. Die Rechnungsnummer vergibt das Werkzeug.

## 3. `rechnung.yaml` füllen

Das ist die einzige Datei, die du schreibst. Sie enthält nur, was du sehen darfst: was geleistet wurde
und wie viel davon, nie einen Preis.

- `leistungsdatum`: nur, was der Mensch sagt. Nie raten, nie das Rechnungsdatum einsetzen.
- `leistung:` wird nie geraten.
  - `taetigkeit`: in den Worten des Menschen.
  - `einordnung`: ein Wort aus der Liste in der Datei (RULES.md Teil 4). Schlag eins vor, wenn es
    sich aus der Tätigkeit ergibt, und lass es dir bestätigen.
  - `ort`: nur bei Tätigkeitsleistungen (kulturell … unterhaltend); wo erbracht, Land oder `online`.
    Immer fragen.
- `positionen`: je Position `kuerzel` aus der Preisliste, `menge` und `einheit`; die Einheit muss zur
  Liste passen. `beschreibung` nur, wenn die Bezeichnung der Liste nicht reicht (z. B. „Vortrag,
  Konferenz X, Paris“). Die Liste zeigt dir `rechnung preisliste`: Kürzel, Einheit, Art, Bezeichnung,
  ohne Preise. Passt kein Kürzel, frag den Menschen; erfinde keins, und schreib nie einen Preis, einen
  Steuersatz oder eine Referenz in die Datei. Du rechnest nie einen Betrag aus.
- Auslagen (`art: auslage`, z. B. Bahnticket) bekommen eine eigene Position; den Betrag trägt der
  Mensch bei `rechnung preise` vom Beleg ein (im Demo-Betrieb nimmt das Werkzeug einen Beispielbetrag).
- Lieferungen (`art: lieferung`, eine Ware wie `buch`) kann das Werkzeug noch nicht; `resolve` bricht
  ab (RULES.md R39). Nimm so ein Kürzel nicht, sag es dem Menschen. Beschreib eine Ware auch nicht als
  Leistung um, damit sie durchgeht.
- `einleitung:` darfst du entwerfen: ein Satz in der Sprache der Rechnung, ohne Beträge und ohne
  Namen. Er steht nach der Anrede („Sehr geehrte Damen und Herren,“), auf Deutsch also klein weiter.
- `belege:` Dateinamen wählt der Mensch. Rate zu neutralen Namen (`beleg-1.pdf`, nicht
  `hotel-<name>.pdf`).
- Nie `leistungsort:` setzen. Das ist eine Festlegung des Menschen mit `begruendung:` (RULES.md R37).

## 4. Auflösen – `rechnung resolve <nr>`

Zeig dem Menschen die geschwärzte Ausgabe: Leistung, Positionen, Leistungsort, Ergebnis, Regeln,
Warnungen und den Stand der Preise. Hat jede Position einen Preis in der Liste, übernimmt `resolve`
ihn selbst („aus der Preisliste übernommen“) und schreibt das Ergebnis. Erklär das Ergebnis mit
`rechnung begruendung <nr>`, wenn er fragt (erst, wenn `resolve` das Ergebnis geschrieben hat). Weiter
erst, wenn er bestätigt.

### Wenn `resolve` abbricht

Die Meldung beginnt mit `Abbruch (<art>):`.

| Art | Was es heißt | Was du tust |
| --- | --- | --- |
| `eingabe` | Fehler in rechnung.yaml (YAML, Feldname, Einheit) | selbst beheben, neu auflösen |
| `frage` | eine Tatsache, die nur der Mensch kennt (Datum, Ort, Tätigkeit), oder eine zurückgehaltene Meldung | fragen, nie raten; bei „Meldung zurückgehalten“ den Menschen bitten, dasselbe Kommando im eigenen Terminal auszuführen |
| `stammdaten` | Kunden- oder Ausstellerdatei bzw. Config unvollständig | dem Menschen sagen, welches Feld in welcher Datei fehlt; **er trägt es selbst ein, nicht über den Chat** |
| `ausserhalb` | bewusst außerhalb des Geltungsbereichs (z. B. Privatperson im EU-Ausland, 7 % wo nicht erlaubt, Lieferung einer Ware) | erklären und anhalten |
| `preise` | Preise fehlen, die die Liste nicht hat (Auslage, Fremdwährung), oder `rechnung.privat.yaml` passt nicht | dem Menschen sagen: `rechnung preise <nr>` im eigenen Terminal; nie nach Beträgen fragen |

Ändere nie `einordnung`, `ort` oder `leistungsort`, um an einem Abbruch vorbeizukommen. Das ist nur
erlaubt, wenn der Mensch sagt, dass die Fakten falsch beschrieben waren.

## 5. Preise – aus der Liste oder beim Menschen

Preise der Liste übernimmt `resolve` (und `bauen`) selbst, je Position, die neu oder geändert ist;
was der Mensch für eine unveränderte Position bestätigt hat, bleibt. Du tust dafür nichts und nennst
keinen Betrag. Steht bei „Preise“ trotzdem `fehlen` oder `veraltet`, fehlt ein Preis, den die Liste
nicht hat (Auslage, Fremdwährung). Dann sag dem Menschen, dass er ihn **im eigenen Terminal** einträgt:
`rechnung preise <nr>`. Will er einen Listenpreis ändern, geht das auf demselben Weg. Nicht über `!` in Claude Code, sonst stehen die Beträge im Chat.
Setzt die Session `RECHNUNG_GEWERBE` (z. B. auf einen Test-Ordner), arbeitet sein Terminal sonst im
Ordner aus der Config: Gib ihm den Aufruf mit derselben Wurzel, `RECHNUNG_GEWERBE=<wurzel> rechnung
preise <nr>`. Der Befehl fragt jeden Einzelpreis ab (Enter übernimmt den Vorschlag), dann die
Referenz, zeigt die Summen und fragt „Bestätigen? [j/N]“.
Ruf `rechnung preise` nie selbst auf; unter dem Schalter verweigert es ohnehin. Frag nie nach Preisen
und bestätige keine Beträge, die er dir in den Chat tippt. Danach `rechnung resolve <nr>` erneut:
„Preise bestätigt“. Änderst du danach eine Position (Kürzel, Menge, Einheit, Beschreibung), füllt
`resolve` sie aus der Liste neu; eine geänderte Auslage trägt er neu ein. `rechnung offen` zeigt,
welchen Rechnungen noch etwas fehlt. Beim Festschreiben weist das Werkzeug ihn auf Preise hin, die nur
aus der Liste kommen.

## 6. Bauen und prüfen – `rechnung bauen <nr>`, `rechnung pruefen <nr>`

`bauen` erzeugt die PDF, `pruefen` weist die Pflichtangaben im PDF-Text nach. Ist `pruefen` rot, sag
dem Menschen, welche Angabe fehlt. Den gesuchten Text siehst du geschwärzt nicht. Die PDF öffnet der
Mensch selbst.

`rechnung bauen <nr> --pro-forma` baut eine Pro forma zur Prüfung durch den Kunden, wenn der Mensch
das will. Fehlt ein Preis, den die Liste nicht hat, baut `bauen` nichts (`Abbruch (preise)`).

## 7. Anschreiben – `anschreiben.md`, `rechnung anschreiben <nr>`

Wenn der Mensch einen Begleittext zur Rechnung will, entwirf ihn in `anschreiben.md` im
Rechnungsordner, in der Sprache der Rechnung. Namen, Beträge und Daten schreibst du nicht aus, sondern
als Platzhalter: `[anrede]`, `[nummer]`, `[datum]`, `[leistungsdatum]`, `[faelligkeit]`, `[netto]`,
`[brutto]`, `[firma]`, `[referenz]`, `[name]`. `[anrede]` ohne Komma, das setzt du dahinter. Andere
Platzhalter gibt es nicht. `rechnung anschreiben <nr>` prüft unter dem Schalter nur die Platzhalter;
eingesetzt wird im eigenen Terminal des Menschen. Das Werkzeug verschickt nichts.

## 8. Was beim Menschen bleibt

- `rechnung preise`: Auslagen, eigene Preise statt der Liste, 7 % und die Referenz des Kunden für
  diese Rechnung.
- `rechnung festschreiben` und `rechnung pro-forma`: Sie halten fest, was er verschickt hat. Du
  rufst sie nicht auf.
- Kundendateien, `ich.yaml` und die Preisliste: Er legt sie an und ändert sie. Eine fehlende Anrede
  (`anrede:` in der Kundendatei) ergänzt er selbst; ohne steht „Sehr geehrte Damen und Herren“.
- Was er dir in den Chat tippt, siehst du – auch Beträge. Bitte ihn, sie dort nicht zu nennen.

## Was du darfst und was nicht

Wie in CLAUDE.md, „Was die AI darf und was nicht“; dieser Skill erweitert keine Rechte. Insbesondere:
keine Rechnungsnummern vergeben, keine Beträge ausrechnen, keine Preise bestätigen (die Liste setzt
das Werkzeug selbst ein), nicht in
`rechnung.privat.yaml` oder die Preisliste schreiben, keine festgeschriebene Rechnung anfassen,
`RECHNUNG_GESCHWAERZT`, `RECHNUNG_GEWERBE` und `RECHNUNG_CONFIG` nicht überschreiben.

## Ehrlich

In Claude Code ist die Grenze so weit erzwungen, wie geschwärzte Ausgabe, Deny-Regeln und der Hook
reichen. Lesen über Bash ist nicht ganz gesperrt: Ein Skript, das Pfade selbst zusammensetzt, sieht der
Hook nicht. Halte dich trotzdem daran; echte Durchsetzung bietet erst der MCP-Server, der nur
geschwärzte Werkzeuge anbietet.
