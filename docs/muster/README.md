# Muster

Sechs Rechnungen, je Ergebnis mindestens eine, gebaut aus `stammdaten.example/` mit erfundenen Daten.
Sie liegen hier als visuelle Referenz: Wer die Vorlage ändert, sieht im Diff der neu gebauten
PDFs, was sich verschoben hat. Neu erzeugt werden sie mit

```sh
rechnung demo --pruefen
```

und danach aus `demo-output/<name>/` hierher kopiert, die Rechnung als `<name>.pdf`. Die Muster zeigen die
Standardvorlage: Wer einen eigenen Vorlagen-Ordner konfiguriert hat, baut sie ohne Config,
`RECHNUNG_CONFIG=/dev/null rechnung demo --pruefen`. Die `.yaml` daneben ist jeweils die Eingabe, aus
der die PDF entstanden ist.

| Datei | Kunde | Einordnung | Sprache | Ergebnis |
| --- | --- | --- | --- | --- |
| `inland-muster-gmbh` | Unternehmen im Inland | `beratung` | de | 1.200,00 netto + 19 % = 1.428,00 EUR |
| `reverse-charge-exemple-sarl` | Unternehmen in der EU mit USt-IdNr. | `beratung` | en | 2.400,00 EUR, 0 %, Reverse Charge, beide USt-IdNrn. |
| `nicht-steuerbar-sample-ltd` | Unternehmen im Drittland | `unterrichtend`, GB | en | 2 Std. × 200,00 + Flug 287,30 = 687,30 EUR, 0 %, § 3a Abs. 2 UStG, Flugbeleg angehängt |
| `nicht-steuerbar-privat-ch` | Privatperson im Drittland | `unterrichtend`, CH | de | Vortrag in Zürich: 900,00 EUR, 0 %, § 3a Abs. 3 Nr. 3 UStG |
| `inland-privat-de` | Privatperson im Inland | `beratung` | de | 180,00 netto + 19 % = 214,20 EUR |
| `kleinunternehmer-muster-gmbh` | Unternehmen im Inland | `beratung` | de | 480,00 EUR, steuerfrei nach § 19 UStG, keine Steuerzeile |

Für die letzte setzt die Demo im Beispiel-Aussteller `kleinunternehmer: true`; die Eingabe selbst
sieht aus wie jede andere.

`nicht-steuerbar-sample-ltd` geht vorher durch zwei Pro-forma-Revisionen (die zweite ergänzt die
Referenz „PO 4711“); die Demo legt sie in `demo-output/nicht-steuerbar-sample-ltd/pro-forma/1/` und
`…/2/` ab. Als Muster liegt hier die zweite: `nicht-steuerbar-sample-ltd.pro-forma.pdf`.

Alle sechs bestehen `rechnung pruefen`, also den Nachweis der Pflichtangaben im PDF-Text.
