# Vorlage

Die LaTeX-Vorlage der Rechnung. Sie enthält **keine Steuerlogik**: Welches Ergebnis gilt, welcher
Satz, welcher Hinweis, wie die Summen sich aufteilen – all das entscheidet `resolve.py`. Die Vorlage
druckt, was sie bekommt. Das macht sie prüfbar: Was auf dem Blatt steht, stand in den Daten.

```
rechnung.tex.j2     die eigentliche Vorlage: dieselbe Rechnung mit Platzhaltern, gefüllt von render.py
issuer.tex.j2       der Aussteller, ebenfalls zur Laufzeit gefüllt – echte Daten nie im Repo
beispiel.tex        dieselbe Rechnung mit festen Werten – kompiliert in Sekunden, für Designrunden
beispiel.pdf        das gebaute Ergebnis
style/defaults.sty  ALLE Stilentscheidungen: Schrift, Farben, Linien, Positionen, Größen, Schalter
style/invoice.sty   Mechanik der Elemente und die beiden Sprachwörterbücher (nicht für Stil anfassen)
include/issuer.tex  Aussteller für beispiel.tex – nur Musterdaten; echte Rechnungen erzeugen ihn zur Laufzeit
include/currency.tex Geld- und Zahlenformate, sprachabhängig
attachments/        Beleg-PDFs, die ans Dokument angehängt werden (Beispielbeleg)
fonts/              Platz für eigene, offen lizenzierte Fonts; genutzt werden XCharter und Fira Sans
```

## Bauen

```sh
make beispiel        # das statische Beispiel, schnell, für Designrunden
make beispiel-neu    # vollständig, inklusive Beleg; nach Änderungen in style/ nötig
rechnung demo        # sechs echte Rechnungen, je Ergebnis mindestens eine, durch die Jinja-Vorlage
```

Wer am Design arbeitet, ändert `beispiel.tex` und `style/` – und zieht die Änderung danach in
`rechnung.tex.j2` nach. Beide sollen dieselbe Rechnung ergeben.

## Eigene Vorlage

Wer anders aussehen will, kopiert nicht die ganze Vorlage, sondern legt einen eigenen Ordner an und
trägt ihn als `vorlage` in die Config ein (oder `RECHNUNG_VORLAGE`). Darin liegen nur die Dateien,
die anders sein sollen, unter demselben Pfad wie hier:

```
meine-vorlage/
  style/defaults.sty    eigene Farben, Schrift, Maße – der übliche Fall
  include/logo.pdf      zusätzliche Dateien kommen einfach dazu
```

Beim Bauen kommt erst diese Standardvorlage ins Temp-Verzeichnis, dann der eigene Ordner darüber;
gleiche Namen ersetzt er. Auch `rechnung.tex.j2` und `issuer.tex.j2` lassen sich so ersetzen.
Verbesserungen an allem, was man nicht ersetzt hat, kommen mit jedem Update automatisch an.
`resolved.json` hält im Feld `vorlage_eigen` fest, welche eigenen Dateien mit welchem Hash beteiligt
waren.

Kommt in `defaults.sty` eine neue Stellschraube dazu, bekommt sie in `invoice.sty` einen
Standardwert. Eine ältere eigene `defaults.sty` baut deshalb weiter. `rechnung doctor` nennt die
Stellschrauben, die ihr fehlen.

## Entscheidungen, die im Layout stecken

- **DIN 5008 Form B**: Das Anschriftfeld beginnt 45 mm von der Oberkante, passend für Fensterumschläge.
  Im Fenster erscheinen nur die Empfängeranschrift und die kleine Rücksendeangabe darüber.
- **Kontaktdaten oben rechts** im Briefkopf, nicht in der Fußzeile und nicht im Anschriftfeld.
- **Fußzeile dreispaltig**: Bank, Steuernummern, Seitenzahl. Die Seitenzahl erscheint nur, wenn die
  Rechnung mehr als eine Seite hat.
- **Die USt-Zeile fehlt nie**, auch bei 0 % nicht; sie verweist dann auf den Hinweis darunter.
  Einzige Ausnahme ist der Kleinunternehmer (§ 19 UStG): Entgelt in einer Summe, ohne Steuerzeile.
- **Belegarten** über `\InvoiceKind`: `invoice`, `creditnote`, `cancellation`, `quote`, `proforma`. Die
  Pro forma trägt auf jeder Seite die Kopfzeile „PRO FORMA – KEINE RECHNUNG“ (`\InvoiceBannerTop`,
  `\InvoiceBannerSize`, Farbe `BannerInk`, Standard: die Akzentfarbe), „(keine Rechnung)“ im Betreff,
  vorläufige Labels und die Bitte um Prüfung statt der Zahlungsaufforderung. Die Texte stehen in den
  Wörterbüchern von `invoice.sty`.
- **Eine Sprache je Rechnung** (`english` oder `ngerman`), gesetzt in Zeile 2 des Dokuments.
- **PDF/A-tauglich gebaut**: eingebettete Schriften, keine Bitmap-Fonts. Der Schalter selbst kommt mit
  ZUGFeRD (geplant).

Alle Maße, Farben und Schalter stehen in `style/defaults.sty`; dort ändern, nicht in `invoice.sty`.

## Lizenz

Die Vorlage steht wie das übrige Repo unter MIT; die Ausstellerdaten hier sind erfunden.
