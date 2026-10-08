# Muster

Vier Rechnungen, eine je Steuerfall, gebaut aus `stammdaten.example/` mit erfundenen Daten.
Sie liegen hier als visuelle Referenz: Wer die Vorlage ändert, sieht im Diff der neu gebauten
PDFs, was sich verschoben hat. Neu erzeugt werden sie mit

```sh
rechnung demo --pruefen
```

und danach aus `demo-output/<fall>/` hierher kopiert. Die Muster zeigen die Standardvorlage: Wer
einen eigenen Vorlagen-Ordner konfiguriert hat, baut sie ohne Config,
`RECHNUNG_CONFIG=/dev/null rechnung demo --pruefen`. Die `.yaml` daneben ist jeweils die
Eingabe, aus der die PDF entstanden ist.

| Datei | Fall | Kunde | Sprache | Ergebnis |
| --- | --- | --- | --- | --- |
| `fall-a-muster-gmbh` | A | Unternehmen im Inland | de | 1.200,00 netto + 19 % = 1.428,00 EUR |
| `fall-b-exemple-sarl` | B | Unternehmen in der EU mit USt-IdNr. | en | 2.400,00 EUR, 0 %, Reverse Charge, beide USt-IdNrn. |
| `fall-c-sample-ltd` | C | Unternehmen im Drittland | en | 2 Std. × 200,00 + Flug 287,30 = 687,30 EUR, 0 %, § 3a Abs. 2 UStG, Flugbeleg angehängt |
| `fall-d-privat-ch` | D | Privatperson im Drittland | de | 900,00 netto + 19 % = 1.071,00 EUR, nur mit Begründung im YAML |

Alle vier bestehen `rechnung pruefen`, also den Nachweis der Pflichtangaben im PDF-Text.
