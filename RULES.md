# RULES.md – Die Steuerregeln des Werkzeugs

**Entwurf, Stand 2026-10-08.** Dieses Dokument legt fest, wie das Werkzeug das Umsatzsteuergesetz
auslegt. Es ist für zwei Leser geschrieben: für eine Steuerberaterin oder einen Steuerberater, die
prüfen, ob die Regeln das Gesetz richtig wiedergeben, und für die formale Verifikation, die beweist,
dass der Code die Regeln richtig umsetzt.

Die Kette:

```
Gesetz ──(Prüfung durch Steuerberater, steht aus)──▶ Regeln R1…Rn in dieser Datei
       ──(je Regel ein Theorem, gleiche ID)──▶ Lean-Modell (bewiesen)
       ──(erschöpfender Abgleich)──▶ rules.py
```

Die Aussage am Ende soll lauten: *Der Code setzt die Regeln R1…Rn beweisbar um; R1…Rn geben das
zitierte Recht wieder – soweit der Status einer Regel „bestätigt“ lautet, und unter den genannten
Annahmen.* Solange eine Regel ungeprüft ist, sagt dieses Dokument genau das.

## Grundsatz

**Das Werkzeug darf strenger sein als das Gesetz, aber es entscheidet nie anders.** Strenger heißt:
Es bricht ab und nennt, was fehlt, oder es verlangt eine Angabe, die das Gesetz im konkreten Fall
nicht verlangt. Anders entscheiden hieße: einen falschen Steuersatz, einen falschen Hinweis oder einen
falschen Leistungsort auf die Rechnung zu drucken. Wo eine Situation außerhalb des Geltungsbereichs
liegt, bricht das Werkzeug ab, statt zu raten.

Die Einordnung einer Leistung (welche Art von Leistung, ob der Kunde Unternehmer ist) ist eine
Wertung. Sie trifft der Mensch und schreibt sie in die Rechnungsdaten; das Werkzeug leitet daraus
Leistungsort, Steuersatz und Pflichttexte ab und hält die Einordnung im Ergebnis fest. So bleibt die
Entscheidung im Nachhinein prüfbar.

## Wie man dieses Dokument liest

- **Teil 1 – Geltungsbereich:** wofür das Werkzeug gebaut ist und was es bewusst nicht kann.
- **Teil 2 – Quellen:** die einschlägigen Vorschriften im Wortlaut (Q1…), jeweils mit den Regeln,
  die daraus folgen.
- **Teil 3 – Regeln:** R1…Rn in der Sprache des Gesetzes. Jede Regel nennt ihre Quellen, Annahmen,
  die betroffenen Felder im Werkzeug und ihren Status.
- **Teil 4 – Zuordnung zum Werkzeug:** die Entscheidungstabelle (Merkmale → Leistungsort → Satz und
  Pflichttext) und wie sie sich zu den heutigen Steuerfällen A–D verhält.
- **Teil 5 – Regeln im Code:** wo jede Regel umgesetzt und wie sie geprüft ist, und wo der Code bekannte
  Grenzen hat.
- **Teil 6 – Fragen an den Steuerberater.**

**Status einer Regel:**

| Status | Bedeutung |
| --- | --- |
| bestätigt | Ein Steuerberater hat eine Rechnung gesehen, die genau diese Regel anwendet, und sie für richtig befunden. Datum und Umfang stehen dabei. |
| Annahme – ungeprüft | Begründete Auslegung, kein Steuerberater hat sie gesehen. Die Begründung steht dabei. |

Derzeit hat keine Regel den Status „bestätigt“: Kein Steuerberater hat dieses Dokument oder eine Regel
daraus geprüft.

**IDs** werden einmal vergeben und nie neu nummeriert. Fällt eine Regel weg, bleibt ihre Nummer
frei. Die Lean-Theoreme tragen dieselben IDs.

**Feldnamen** sind die aus `rechnung.yaml` (`leistung.einordnung`, `leistungsort` …), `ich.yaml`
(`kleinunternehmer`) und den Kundendateien (`kunde.land` …).

**Gesetzesstand:** Wortlaut von gesetze-im-internet.de (UStG, UStDV) und EUR-Lex (MwStSystRL,
konsolidierte Fassung), abgerufen am 2026-10-08.

---

## Teil 1 – Geltungsbereich

### Abgedeckt

- **Aussteller:** ein Unternehmer, der sein Unternehmen vom Inland aus betreibt, ohne Betriebsstätte
  im Ausland. Regelbesteuerung oder Kleinunternehmer nach § 19 UStG.
- **Umsatz:** sonstige Leistungen (Dienstleistungen) gegen Entgelt, einschließlich Auslagen, die als
  Nebenleistung dazugehören (z. B. Reisekosten).
- **Leistungsarten:** die Grundregel (§ 3a Abs. 1 und 2), Katalogleistungen (§ 3a Abs. 4) und
  kulturelle, künstlerische, wissenschaftliche, unterrichtende und ähnliche Leistungen
  (§ 3a Abs. 3 Nr. 3).
- **Kunden:** Unternehmer und Privatpersonen in Deutschland, in anderen EU-Staaten und im Drittland.
- **Steuersätze:** 19 % und 7 %, 0 % nur als Folge von Nichtsteuerbarkeit, Steuerschuldnerschaft des
  Leistungsempfängers oder Steuerbefreiung nach § 19.
- **Währung:** EUR; USD und GBP nur ohne deutschen Steuerausweis.
- **Pro forma:** ein Entwurf der Rechnung zur Prüfung durch den Kunden, aus denselben Daten, deutlich
  als „keine Rechnung“ gekennzeichnet (R38).

### Außen vor

Für jede dieser Situationen gilt: Das Werkzeug kann sie nicht richtig abbilden. Wo es sie erkennen
kann, bricht es ab. Wo es sie nicht erkennen kann (weil sie von Tatsachen abhängt, die nicht in den
Rechnungsdaten stehen), liegt die Verantwortung beim Menschen, der die Rechnung anlegt.

| Situation | Vorschrift | Was das Werkzeug tut |
| --- | --- | --- |
| Lieferung von Waren (auch innergemeinschaftliche Lieferung, Fernverkauf) | §§ 3, 3c, 6a UStG | nicht vorgesehen; Positionen sind immer sonstige Leistungen |
| Leistungen im Zusammenhang mit einem Grundstück | § 3a Abs. 3 Nr. 1 | erkennt es nicht; Verantwortung beim Menschen |
| Vermietung von Beförderungsmitteln | § 3a Abs. 3 Nr. 2 | erkennt es nicht |
| Restaurationsleistungen, Arbeiten an beweglichen Gegenständen | § 3a Abs. 3 Nr. 3a | erkennt es nicht |
| Vermittlungsleistungen an Privatpersonen | § 3a Abs. 3 Nr. 4 | erkennt es nicht |
| Eintrittsberechtigungen zu Veranstaltungen an Unternehmer (Ticketverkauf) | § 3a Abs. 3 Nr. 5 | erkennt es nicht |
| Telekommunikation, Rundfunk, elektronisch erbrachte Leistungen an Privatpersonen in der EU (OSS); bis 2015 Katalog Nr. 11–13 | § 3a Abs. 5 | keine Einordnung dafür; erkennt es nicht |
| Bank-, Finanz- und Versicherungsumsätze, Geschäfte mit Gold, Silber, Platin | § 3a Abs. 4 Satz 2 Nr. 6, § 4 Nr. 8 und 10 | keine Einordnung dafür: meist steuerfrei, und Steuerbefreiungen außer § 19 kennt das Werkzeug nicht |
| Nutzung oder Auswertung im Drittland | § 3a Abs. 8 | erkennt es nicht |
| Leistungsort einer Privatperson-Leistung in einem anderen EU-Staat (z. B. Workshop für Privatleute in Paris) | § 3a Abs. 3 Nr. 3 | **bricht ab**: Steuer wäre im anderen Staat zu erklären |
| Nicht unternehmerisch tätige juristische Person mit USt-IdNr. als Kunde | § 3a Abs. 2 Satz 3 | wird wie ein Unternehmer behandelt, wenn `unternehmer: true` gesetzt ist; Verantwortung beim Menschen |
| Leistung an eine Betriebsstätte des Kunden in einem anderen Land als seinem Sitz | § 3a Abs. 2 Satz 2 | erkennt es nicht; maßgeblich ist das Land in den Kundendaten |
| Prüfung, ob eine Position den ermäßigten Satz von 7 % erhält | § 12 Abs. 2 | der Mensch wählt 7 % je Position, das Werkzeug prüft den Katalog nicht |
| Umsatzgrenzen der Kleinunternehmerregelung (25.000 € / 100.000 €) | § 19 Abs. 1 | kennt keine Jahresumsätze; die Einstellung `kleinunternehmer` verantwortet der Mensch |
| Kleinunternehmer aus anderen EU-Staaten (KU-IdNr.) | § 19 Abs. 4 | nicht vorgesehen |
| Im Voraus vereinbarte Entgeltminderungen (Skonto, Rabatt) | § 14 Abs. 4 Nr. 7 | nicht vorgesehen; Beträge sind immer endgültig |
| Gutschrift (Abrechnung durch den Kunden) | § 14 Abs. 2 Satz 5, Abs. 4 Nr. 10 | nicht vorgesehen |
| Hinweis auf Aufbewahrungspflicht des Empfängers | § 14 Abs. 4 Nr. 9 | entfällt mangels Grundstücksleistungen |
| Anzahlungsrechnungen, Storno, Rechnungskorrektur | § 14 Abs. 5, § 17 | nicht vorgesehen (geplant) |
| Fremdwährung mit deutschem Steuerausweis | § 16 Abs. 6 | **bricht ab** |
| Besondere Gebiete (Büsingen, Helgoland, Kanaren, Kanalinseln, Nordirland …) | § 1 Abs. 2, 2a | nicht unterschieden; Land wird nach ISO-Code eingeordnet |
| Prüfung der USt-IdNr. des Kunden (qualifizierte Bestätigungsabfrage) | § 18e | nicht vorgesehen; die Nummer wird als gegeben angenommen |
| Zusammenfassende Meldung, Umsatzsteuer-Voranmeldung | §§ 18, 18a | außerhalb des Werkzeugs |

---

## Teil 2 – Quellen

Wörtliche Auszüge; Auslassungen sind mit „[…]“ markiert. Hervorhebungen fehlen bewusst.

### Q1 – § 1 Abs. 1 Nr. 1 und Abs. 2a UStG: Steuerbarkeit, Gebiete

> (1) Der Umsatzsteuer unterliegen die folgenden Umsätze:
> 1. die Lieferungen und sonstigen Leistungen, die ein Unternehmer im Inland gegen Entgelt im Rahmen
>    seines Unternehmens ausführt. […]

> (2a) […] Gemeinschaftsgebiet im Sinne dieses Gesetzes umfasst das Inland im Sinne des Absatzes 2
> Satz 1 und die Gebiete der übrigen Mitgliedstaaten der Europäischen Union, die nach dem
> Gemeinschaftsrecht als Inland dieser Mitgliedstaaten gelten (übriges Gemeinschaftsgebiet).
> Drittlandsgebiet im Sinne dieses Gesetzes ist das Gebiet, das nicht Gemeinschaftsgebiet ist.

Daraus folgen: **R1**, **R2**.

### Q2 – § 3a Abs. 1 UStG: Ort der sonstigen Leistung, Grundregel

> Eine sonstige Leistung wird vorbehaltlich der Absätze 2 bis 8 und der §§ 3b und 3e an dem Ort
> ausgeführt, von dem aus der Unternehmer sein Unternehmen betreibt. […]

Daraus folgt: **R4**.

### Q3 – § 3a Abs. 2 Satz 1 UStG: Leistung an einen Unternehmer

> Eine sonstige Leistung, die an einen Unternehmer für dessen Unternehmen ausgeführt wird, wird
> vorbehaltlich der Absätze 3 bis 8 und der §§ 3b und 3e an dem Ort ausgeführt, von dem aus der
> Empfänger sein Unternehmen betreibt.

Daraus folgt: **R3**.

### Q4 – § 3a Abs. 3 Nr. 3 UStG: kulturelle, unterrichtende und ähnliche Leistungen an Nichtunternehmer

> Kulturelle, künstlerische, wissenschaftliche, unterrichtende, sportliche, unterhaltende oder
> ähnliche Leistungen, wie Leistungen im Zusammenhang mit Messen und Ausstellungen, einschließlich der
> Leistungen der jeweiligen Veranstalter sowie die damit zusammenhängenden Tätigkeiten, die für die
> Ausübung der Leistungen unerlässlich sind, an einen Empfänger, der weder ein Unternehmer ist, für
> dessen Unternehmen die Leistung ausgeführt wird, noch eine nichtunternehmerisch tätige juristische
> Person, der eine Umsatzsteuer-Identifikationsnummer erteilt worden ist, werden dort ausgeführt, wo
> sie vom Unternehmer tatsächlich erbracht werden. Werden die Leistungen per Streaming übertragen oder
> auf andere Weise virtuell verfügbar gemacht, gilt abweichend von Satz 1 als Ort der sonstigen
> Leistung der Ort, an dem der Empfänger ansässig ist oder seinen Wohnsitz oder gewöhnlichen
> Aufenthaltsort hat.

Daraus folgen: **R5**, **R6**.

### Q5 – § 3a Abs. 4 UStG: Katalogleistungen an Nichtunternehmer im Drittland

> Ist der Empfänger einer der in Satz 2 bezeichneten sonstigen Leistungen weder ein Unternehmer, für
> dessen Unternehmen die Leistung bezogen wird, noch eine nicht unternehmerisch tätige juristische
> Person, der eine Umsatzsteuer-Identifikationsnummer erteilt worden ist, und hat er seinen Wohnsitz
> oder Sitz im Drittlandsgebiet, wird die sonstige Leistung an seinem Wohnsitz oder Sitz ausgeführt.
> Sonstige Leistungen im Sinne des Satzes 1 sind:
> 1. die Einräumung, Übertragung und Wahrnehmung von Patenten, Urheberrechten, Markenrechten und
>    ähnlichen Rechten;
> 2. die sonstigen Leistungen, die der Werbung oder der Öffentlichkeitsarbeit dienen, einschließlich
>    der Leistungen der Werbungsmittler und der Werbeagenturen;
> 3. die sonstigen Leistungen aus der Tätigkeit als Rechtsanwalt, Patentanwalt, Steuerberater,
>    Steuerbevollmächtigter, Wirtschaftsprüfer, vereidigter Buchprüfer, Sachverständiger, Ingenieur,
>    Aufsichtsratsmitglied, Dolmetscher und Übersetzer sowie ähnliche Leistungen anderer Unternehmer,
>    insbesondere die rechtliche, wirtschaftliche und technische Beratung;
> 4. die Datenverarbeitung;
> 5. die Überlassung von Informationen einschließlich gewerblicher Verfahren und Erfahrungen;
> 6. a) Bank- und Finanzumsätze, […] sowie Versicherungsumsätze […], b) die sonstigen Leistungen im
>    Geschäft mit Gold, Silber und Platin. […]
> 7. die Gestellung von Personal;
> 8. der Verzicht auf Ausübung eines der in Nummer 1 bezeichneten Rechte;
> 9. der Verzicht, ganz oder teilweise eine gewerbliche oder berufliche Tätigkeit auszuüben;
> 10. die Vermietung beweglicher körperlicher Gegenstände, ausgenommen Beförderungsmittel;
> 11.–13. (weggefallen)
> 14. die Gewährung des Zugangs zum Erdgasnetz, zum Elektrizitätsnetz oder zu Wärme- oder Kältenetzen
>     […].

Daraus folgen: **R7**, **R8**.

### Q6 – § 12 Abs. 1 und 2 UStG: Steuersätze

> (1) Die Steuer beträgt für jeden steuerpflichtigen Umsatz 19 Prozent der Bemessungsgrundlage […].
> (2) Die Steuer ermäßigt sich auf sieben Prozent für die folgenden Umsätze: […]

Daraus folgt: **R10**.

### Q7 – Art. 44 und Art. 196 MwStSystRL (Richtlinie 2006/112/EG): Steuerschuldner im anderen EU-Staat

> Art. 44: Als Ort einer Dienstleistung an einen Steuerpflichtigen, der als solcher handelt, gilt der
> Ort, an dem dieser Steuerpflichtige den Sitz seiner wirtschaftlichen Tätigkeit hat. […]

> Art. 196: Die Mehrwertsteuer schuldet der Steuerpflichtige oder die nicht steuerpflichtige
> juristische Person mit einer Mehrwertsteuer-Identifikationsnummer, für den/die eine Dienstleistung
> nach Artikel 44 erbracht wird, wenn die Dienstleistung von einem nicht in diesem Mitgliedstaat
> ansässigen Steuerpflichtigen erbracht wird.

Daraus folgt: **R11**.

### Q8 – § 14 Abs. 4 Satz 1 UStG: Pflichtangaben

> Eine Rechnung muss folgende Angaben enthalten:
> 1. den vollständigen Namen und die vollständige Anschrift des leistenden Unternehmers und des
>    Leistungsempfängers,
> 2. die dem leistenden Unternehmer vom Finanzamt erteilte Steuernummer oder die ihm vom
>    Bundeszentralamt für Steuern erteilte Umsatzsteuer-Identifikationsnummer,
> 3. das Ausstellungsdatum,
> 4. eine fortlaufende Nummer mit einer oder mehreren Zahlenreihen, die zur Identifizierung der
>    Rechnung vom Rechnungsaussteller einmalig vergeben wird (Rechnungsnummer),
> 5. die Menge und die Art (handelsübliche Bezeichnung) der gelieferten Gegenstände oder den Umfang
>    und die Art der sonstigen Leistung,
> 6. den Zeitpunkt der Lieferung oder sonstigen Leistung; […]
> 7. das nach Steuersätzen und einzelnen Steuerbefreiungen aufgeschlüsselte Entgelt für die Lieferung
>    oder sonstige Leistung (§ 10) sowie jede im Voraus vereinbarte Minderung des Entgelts, sofern sie
>    nicht bereits im Entgelt berücksichtigt ist,
> 8. den anzuwendenden Steuersatz sowie den auf das Entgelt entfallenden Steuerbetrag oder im Fall
>    einer Steuerbefreiung einen Hinweis darauf, dass für die Lieferung oder sonstige Leistung eine
>    Steuerbefreiung gilt,
> 9. in den Fällen des § 14b Abs. 1 Satz 5 einen Hinweis auf die Aufbewahrungspflicht des
>    Leistungsempfängers und
> 10. in den Fällen der Ausstellung der Rechnung durch den Leistungsempfänger oder durch einen von ihm
>     beauftragten Dritten gemäß Absatz 2 Satz 5 die Angabe „Gutschrift“.

Daraus folgen: **R20** bis **R27**.

### Q9 – § 14a Abs. 1 UStG: Rechnung bei Umsätzen in einem anderen Mitgliedstaat

> Hat der Unternehmer seinen Sitz, seine Geschäftsleitung, eine Betriebsstätte, von der aus der Umsatz
> ausgeführt wird, oder in Ermangelung eines Sitzes seinen Wohnsitz oder gewöhnlichen Aufenthalt im
> Inland und führt er einen Umsatz in einem anderen Mitgliedstaat aus, an dem eine Betriebsstätte in
> diesem Mitgliedstaat nicht beteiligt ist, so ist er zur Ausstellung einer Rechnung mit der Angabe
> „Steuerschuldnerschaft des Leistungsempfängers“ verpflichtet, wenn die Steuer in dem anderen
> Mitgliedstaat von dem Leistungsempfänger geschuldet wird und keine Gutschrift gemäß § 14 Absatz 2
> Satz 5 vereinbart worden ist. Führt der Unternehmer eine sonstige Leistung im Sinne des § 3a Absatz 2
> in einem anderen Mitgliedstaat aus, so ist die Rechnung bis zum fünfzehnten Tag des Monats, der auf
> den Monat folgt, in dem der Umsatz ausgeführt worden ist, auszustellen. In dieser Rechnung sind die
> Umsatzsteuer-Identifikationsnummer des Unternehmers und die des Leistungsempfängers anzugeben. […]

Daraus folgen: **R28**, **R29**, **R30**.

Hinweis: § 14a **Abs. 5** verlangt dieselbe Angabe für den umgekehrten Fall (§ 13b Abs. 2, die
Steuer schuldet ein Empfänger im Inland). Für Rechnungen dieses Werkzeugs ist Abs. 1 einschlägig.

### Q10 – § 14c UStG: zu hoher und unberechtigter Steuerausweis

> (1) Hat der Unternehmer in einer Rechnung für eine Lieferung oder sonstige Leistung einen höheren
> Steuerbetrag, als er nach diesem Gesetz für den Umsatz schuldet, gesondert ausgewiesen (unrichtiger
> Steuerausweis), schuldet er auch den Mehrbetrag. […]
> (2) Wer in einer Rechnung einen Steuerbetrag gesondert ausweist, obwohl er zum gesonderten Ausweis
> der Steuer nicht berechtigt ist (unberechtigter Steuerausweis), schuldet den ausgewiesenen Betrag.
> […]

Daraus folgen: **R12**, **R33**.

### Q11 – § 19 Abs. 1 UStG: Kleinunternehmer (Fassung seit 2025)

> Ein von einem im Inland oder in den in § 1 Absatz 3 bezeichneten Gebieten ansässigen Unternehmer
> bewirkter Umsatz im Sinne des § 1 Absatz 1 Nummer 1 ist steuerfrei, wenn der Gesamtumsatz nach
> Absatz 2 im vorangegangenen Kalenderjahr 25 000 Euro nicht überschritten hat und im laufenden
> Kalenderjahr 100 000 Euro nicht überschreitet. In den Fällen des Satzes 1 finden die Vorschriften
> über die Steuerbefreiung innergemeinschaftlicher Lieferungen (§ 4 Nummer 1 Buchstabe b, § 6a), über
> den Verzicht auf Steuerbefreiungen (§ 9), über die Angabe der Umsatzsteuer-Identifikationsnummern in
> einer Rechnung (§ 14a Absatz 1 Satz 3, Absatz 3 Satz 2 und Absatz 7 Satz 2) und über die
> Erklärungspflichten (§ 18 Absatz 1 bis 4) keine Anwendung; […]

Daraus folgen: **R13** bis **R17**.

### Q12 – § 34a UStDV: Rechnung eines Kleinunternehmers

> Eine Rechnung über Umsätze, die nach § 19 Absatz 1 des Gesetzes steuerfrei sind, muss mindestens
> folgende Angaben enthalten:
> 1. den vollständigen Namen und die vollständige Anschrift des leistenden Unternehmers und des
>    Leistungsempfängers,
> 2. die dem leistenden Unternehmer vom Finanzamt erteilte Steuernummer oder die ihm vom
>    Bundeszentralamt für Steuern erteilte Umsatzsteuer-Identifikationsnummer oder
>    Kleinunternehmer-Identifikationsnummer,
> 3. das Ausstellungsdatum,
> 4. die Menge und die Art (handelsübliche Bezeichnung) der gelieferten Gegenstände oder den Umfang
>    und die Art der sonstigen Leistung,
> 5. das Entgelt für die Lieferung oder sonstige Leistung in einer Summe mit einem Hinweis darauf, dass
>    für die Lieferung oder sonstige Leistung die Steuerbefreiung für Kleinunternehmer gilt (§ 19 des
>    Gesetzes) und
> 6. […] die Angabe „Gutschrift“.

Daraus folgt: **R16**.

### Q13 – § 16 Abs. 6 UStG: Fremdwährung

> Werte in fremder Währung sind zur Berechnung der Steuer und der abziehbaren Vorsteuerbeträge auf Euro
> nach den Durchschnittskursen umzurechnen, die das Bundesministerium der Finanzen für den Monat
> öffentlich bekanntgibt, in dem die Leistung ausgeführt […] wird. […]

Daraus folgt: **R34**.

### Q14 – Verwaltungsauffassung, kein Gesetz

Nicht im Wortlaut zitiert, weil keine Rechtsnorm, aber Grundlage einzelner Annahmen:

- **Einheitlichkeit der Leistung (UStAE Abschn. 3.10):** Eine Nebenleistung teilt das umsatzsteuerliche
  Schicksal der Hauptleistung. Grundlage für **R9**.
- **Nachweis der Unternehmereigenschaft (UStAE Abschn. 3a.2):** bei EU-Kunden über die USt-IdNr., bei
  Drittland-Kunden über eine Bescheinigung oder andere Belege. Grundlage der Annahmen zu **R3**.

### Q15 – § 14 Abs. 1 Satz 1 UStG: Was eine Rechnung ist

> Rechnung ist jedes Dokument, mit dem über eine Lieferung oder sonstige Leistung abgerechnet wird,
> gleichgültig, wie dieses Dokument im Geschäftsverkehr bezeichnet wird.

Daraus folgt: **R38**.

---

## Teil 3 – Regeln

Jede Regel hat dieselbe Form: **Quelle** – **Regel** – **Annahmen** – **Werkzeug** (betroffene Felder
und Verhalten) – **Status**.

### Gebiete und Steuerbarkeit

#### R1 – Länderkategorie

- **Quelle:** Q1 (§ 1 Abs. 2a UStG).
- **Regel:** Jedes Land ist genau eines von: Inland (Deutschland), übriges Gemeinschaftsgebiet (ein
  anderer EU-Mitgliedstaat) oder Drittlandsgebiet (alles andere).
- **Annahmen:** Ein Land ist durch seinen ISO-Code bestimmt; Sondergebiete (Büsingen, Helgoland,
  Kanaren, Nordirland …) werden nicht unterschieden. Das Vereinigte Königreich ist seit 2021
  Drittland.
- **Werkzeug:** `kunde.land`; EU-Liste `EU_LAENDER` in `rules.py` mit Datum.
- **Status:** Annahme – ungeprüft (die Einteilung selbst ist Gesetz; ungeprüft ist nur die gepflegte
  Liste).

#### R2 – Steuerbar ist nur, was im Inland ausgeführt wird

- **Quelle:** Q1 (§ 1 Abs. 1 Nr. 1 UStG).
- **Regel:** Eine sonstige Leistung ist in Deutschland steuerbar genau dann, wenn ihr Leistungsort
  im Inland liegt. Liegt er im Ausland, fällt keine deutsche Umsatzsteuer an.
- **Annahmen:** Der Aussteller ist Unternehmer und erbringt die Leistung gegen Entgelt im Rahmen
  seines Unternehmens.
- **Werkzeug:** keine eigene Angabe; folgt aus R3–R8.
- **Status:** Annahme – ungeprüft.

### Leistungsort

Der Leistungsort hängt von drei Merkmalen ab: der **Leistungsart** (Grundregel, Katalogleistung,
Tätigkeitsleistung), dem **Status des Empfängers** (Unternehmer oder nicht) und einem **Ort** (Sitz
des Empfängers, Sitz des Ausstellers oder Ort der Tätigkeit). R3–R8 legen diese Funktion fest; die
vollständige Tabelle steht in Teil 4.

#### R3 – Leistung an einen Unternehmer: Sitz des Empfängers

- **Quelle:** Q3 (§ 3a Abs. 2 Satz 1 UStG); für EU-Kunden auch Q7 (Art. 44 MwStSystRL).
- **Regel:** Ist der Empfänger ein Unternehmer, der die Leistung für sein Unternehmen bezieht, liegt
  der Leistungsort dort, wo er sein Unternehmen betreibt – unabhängig von der Leistungsart.
- **Annahmen:**
  - Das Land in den Kundendaten ist der Ort, von dem aus der Kunde sein Unternehmen betreibt; eine
    abweichende Betriebsstätte gibt es nicht.
  - Der Kunde bezieht die Leistung für sein Unternehmen.
  - Ein Unternehmer im Drittland weist sich durch Registereintrag, Steuernummer oder Ähnliches aus;
    das Werkzeug verlangt das nicht, empfiehlt es aber (`register`, `ustid`).
  - Ein Unternehmer in der EU weist sich durch seine USt-IdNr. aus (siehe R29).
  - Die Ausnahmen in § 3a Abs. 3 Nr. 1, 2, 3a, 5 und Abs. 8 greifen nicht (Teil 1).
- **Werkzeug:** `kunde.unternehmer`, `kunde.land`, `kunde.ustid`.
- **Status:** Annahme – ungeprüft.

#### R4 – Grundregel bei Nichtunternehmern: Sitz des Ausstellers

- **Quelle:** Q2 (§ 3a Abs. 1 UStG).
- **Regel:** Ist der Empfänger kein Unternehmer und greift keine der Ausnahmen R5–R7, liegt der
  Leistungsort dort, wo der Aussteller sein Unternehmen betreibt, also im Inland.
- **Annahmen:** Der Aussteller betreibt sein Unternehmen vom Inland aus und hat keine Betriebsstätte
  im Ausland.
- **Werkzeug:** `kunde.unternehmer: false`, `leistung.einordnung: sonstige`. Steht in den Stammdaten des
  Ausstellers (`land`) nicht `DE`, bricht das Werkzeug ab: Es bildet das deutsche UStG ab und gilt nur für
  Aussteller mit Sitz in Deutschland. Angenommen bleibt nur, dass es keine Betriebsstätte im Ausland gibt.
- **Status:** Annahme – ungeprüft.

#### R5 – Tätigkeitsleistung an Nichtunternehmer: Ort der Tätigkeit

- **Quelle:** Q4 (§ 3a Abs. 3 Nr. 3 Satz 1 UStG).
- **Regel:** Ist die Leistung kulturell, künstlerisch, wissenschaftlich, unterrichtend, sportlich,
  unterhaltend oder ähnlich und der Empfänger kein Unternehmer, liegt der Leistungsort dort, wo die
  Leistung tatsächlich erbracht wird.
- **Annahmen:** Ob eine Leistung in diese Gruppe gehört, entscheidet der Mensch (Abgrenzung etwa
  Vortrag ↔ Beratung, siehe Teil 6). Die Leistung wird an einem Ort erbracht, in einem Land.
- **Werkzeug:** `leistung.einordnung`: `kulturell`, `kuenstlerisch`, `wissenschaftlich`,
  `unterrichtend`, `sportlich` oder `unterhaltend`; `leistung.ort` (Land).
- **Status:** Annahme – ungeprüft.

#### R6 – Tätigkeitsleistung, virtuell: Wohnsitz des Empfängers

- **Quelle:** Q4 (§ 3a Abs. 3 Nr. 3 Satz 2 UStG).
- **Regel:** Wird eine Leistung nach R5 per Streaming übertragen oder auf andere Weise virtuell
  verfügbar gemacht, liegt der Leistungsort dort, wo der Empfänger ansässig ist oder seinen Wohnsitz
  hat.
- **Annahmen:** Das Land in den Kundendaten ist der Wohnsitz.
- **Werkzeug:** `leistung.ort: online`.
- **Status:** Annahme – ungeprüft.

#### R7 – Katalogleistung an Nichtunternehmer im Drittland: Wohnsitz des Empfängers

- **Quelle:** Q5 (§ 3a Abs. 4 UStG).
- **Regel:** Ist die Leistung eine der in § 3a Abs. 4 Satz 2 genannten und der Empfänger kein
  Unternehmer mit Wohnsitz oder Sitz im Drittlandsgebiet, liegt der Leistungsort an seinem Wohnsitz.
- **Annahmen:** Welche Nummer des Katalogs zutrifft, entscheidet der Mensch und gibt sie an.
- **Werkzeug:** `leistung.einordnung`: ein Wort aus der Katalogtabelle in Teil 4 (Nr. 1–5, 7–10, 14).
- **Status:** Annahme – ungeprüft.

#### R8 – Katalogleistung an Nichtunternehmer in der EU oder im Inland: Grundregel

- **Quelle:** Q5 (§ 3a Abs. 4 Satz 1 nennt nur das Drittlandsgebiet), Q2.
- **Regel:** Wohnt der Empfänger einer Katalogleistung im Inland oder in einem anderen EU-Staat, gilt
  die Grundregel (R4): Leistungsort im Inland.
- **Annahmen:** wie R4.
- **Werkzeug:** wie R7.
- **Status:** Annahme – ungeprüft.

#### R9 – Eine Einordnung je Rechnung; Nebenleistungen folgen der Hauptleistung

- **Quelle:** Q14 (Einheitlichkeit der Leistung, Verwaltungsauffassung).
- **Regel:** Eine Rechnung hat eine Einordnung und damit einen Leistungsort; er gilt für alle
  Positionen. Nebenleistungen (z. B. Reisekosten, Material) teilen Leistungsort und Steuersatz ihrer
  Hauptleistung. Leistungen verschiedener Einordnung gehören auf getrennte Rechnungen. Leistungen
  derselben Einordnung dürfen verschiedene Steuersätze haben (19 % und 7 %, R10); die Rechnung
  schlüsselt das Entgelt dann nach Sätzen auf (§ 14 Abs. 4 Nr. 7 und 8).
- **Annahmen:** Weiterberechnete Auslagen sind Nebenleistung und Teil des Entgelts, kein durchlaufender
  Posten. Getrennte Rechnungen sind strenger als nötig, aber zulässig. Dass gemischte Sätze auf einer
  Rechnung derselben Einordnung zulässig sind, ist eine Annahme (Teil 6).
- **Werkzeug:** `leistung` gilt für die ganze Rechnung, nicht je Position; `leistung.taetigkeit`
  beschreibt die Hauptleistung in eigenen Worten.
- **Status:** Annahme – ungeprüft.

### Steuersatz und Steuerschuldner

#### R10 – Steuersatz bei steuerbarer Leistung

- **Quelle:** Q6 (§ 12 Abs. 1 und 2 UStG).
- **Regel:** Ist die Leistung steuerbar (R2) und nicht steuerfrei (R13), beträgt die Steuer 19 % des
  Entgelts, für die in § 12 Abs. 2 genannten Umsätze 7 %.
- **Annahmen:** Ob eine Position unter § 12 Abs. 2 fällt, entscheidet der Mensch (Teil 1).
- **Werkzeug:** Satz 19 % als Vorgabe, `positionen[].steuersatz: 7` je Position. Das Feld nimmt nur `7`
  an: 19 % und 0 % folgen aus dem Ergebnis der Rechnung, eine Position mit 0 % bei steuerpflichtiger
  Leistung wäre ein zu niedriger Ausweis (eine Steuerbefreiung nach § 4 deckt das Werkzeug nicht ab).
- **Status:** Annahme – ungeprüft.

#### R11 – Steuerschuldnerschaft des Leistungsempfängers in der EU

- **Quelle:** Q7 (Art. 196 MwStSystRL), Q9 (§ 14a Abs. 1 UStG).
- **Regel:** Liegt der Leistungsort nach R3 in einem anderen EU-Mitgliedstaat, ist die Leistung in
  Deutschland nicht steuerbar; die Steuer im anderen Staat schuldet der Empfänger.
- **Annahmen:** Der Aussteller ist im anderen Mitgliedstaat nicht ansässig. Der andere Staat setzt
  Art. 196 um (Pflicht für alle Mitgliedstaaten).
- **Werkzeug:** `kunde.land` in der EU, `kunde.unternehmer` bzw. `kunde.ustid`.
- **Status:** Annahme – ungeprüft.

#### R12 – Kein deutscher Steuerausweis, wenn keine deutsche Steuer geschuldet wird

- **Quelle:** Q10 (§ 14c UStG).
- **Regel:** Ist die Leistung nicht steuerbar (R2), schuldet der Empfänger die Steuer (R11) oder ist
  sie steuerfrei (R13), weist die Rechnung keinen deutschen Steuerbetrag größer als 0 aus. Ein
  höherer Ausweis würde nach § 14c geschuldet.
- **Annahmen:** keine.
- **Werkzeug:** `steuersatz` je Position darf in diesen Fällen nicht gesetzt sein; `resolve` bricht
  sonst ab.
- **Status:** Annahme – ungeprüft.

### Kleinunternehmer (§ 19 UStG)

#### R13 – Steuerfreiheit nur für Umsätze im Inland

- **Quelle:** Q11 (§ 19 Abs. 1 Satz 1 UStG), Q1.
- **Regel:** Ist der Aussteller Kleinunternehmer, ist jede steuerbare Leistung (Leistungsort im
  Inland, R2) steuerfrei: Satz 0 %, kein Steuerbetrag. Leistungen mit Leistungsort im Ausland sind
  schon nicht steuerbar; § 19 berührt sie nicht.
- **Annahmen:** Die Umsatzgrenzen sind eingehalten (Teil 1); der Aussteller hat nicht auf die
  Regelung verzichtet (§ 19 Abs. 3).
- **Werkzeug:** `kleinunternehmer: true` in `ich.yaml`.
- **Status:** Annahme – ungeprüft.

#### R14 – Kleinunternehmer weist nie Umsatzsteuer aus

- **Quelle:** Q10 (§ 14c Abs. 2 UStG), Q11.
- **Regel:** Eine Rechnung eines Kleinunternehmers enthält keinen Steuersatz größer 0 und keinen
  Steuerbetrag größer 0 – in keinem Fall, auch nicht bei manueller Festlegung (R37).
- **Annahmen:** keine.
- **Werkzeug:** `kleinunternehmer: true` schließt `positionen[].steuersatz` aus.
- **Status:** Annahme – ungeprüft.

#### R15 – Kleinunternehmer, Kunde ist Unternehmer in der EU

- **Quelle:** Q9 (§ 14a Abs. 1 Satz 1 UStG), Q11 (§ 19 Abs. 1 Satz 2 UStG).
- **Regel:** Liegt der Leistungsort nach R3 in einem anderen EU-Staat, gilt R11 wie für jeden anderen
  Unternehmer: Die Rechnung trägt die Angabe „Steuerschuldnerschaft des Leistungsempfängers“. Die
  Angabe der USt-IdNrn. (§ 14a Abs. 1 Satz 3) ist für Kleinunternehmer nicht Pflicht.
- **Annahmen:** § 19 Abs. 1 Satz 2 schließt nur Satz 3 aus, nicht Satz 1; die Pflicht zur Angabe
  „Steuerschuldnerschaft des Leistungsempfängers“ bleibt also. Ein § 19-Hinweis kommt nicht dazu, weil
  der Umsatz im Inland nicht steuerbar ist und § 19 ihn nicht erfasst. Das Werkzeug druckt die
  USt-IdNrn. trotzdem, wenn sie vorhanden sind.
- **Werkzeug:** `kleinunternehmer: true`; R29/R30 entfallen.
- **Status:** Annahme – ungeprüft. **Unsicher** – auf der Fragenliste.

#### R16 – Pflichttext des Kleinunternehmers

- **Quelle:** Q12 (§ 34a Nr. 5 UStDV), Q8 (§ 14 Abs. 4 Nr. 8 UStG).
- **Regel:** Ist eine Leistung nach R13 steuerfrei, nennt die Rechnung das Entgelt in einer Summe und
  enthält einen Hinweis, dass die Steuerbefreiung für Kleinunternehmer gilt.
- **Annahmen:** Wortlaut (Vorschlag):
  - de: „Steuerfrei als Leistung eines Kleinunternehmers (§ 19 Abs. 1 UStG).“
  - en: „VAT exempt: small business exemption under section 19 (1) of the German VAT Act (UStG).“

  Die Rechnung zeigt keine Zeile „USt 0,00“, sondern nur den Hinweis, damit sie nicht wie eine
  Rechnung mit Steuerausweis aussieht.
- **Werkzeug:** Pflichttext in Block 8; Summenblock ohne Steuerzeile.
- **Status:** Annahme – ungeprüft.

#### R17 – Kleinunternehmer, Kunde ist Unternehmer im Drittland oder Leistungsort im Drittland

- **Quelle:** Q1, Q3/Q4/Q5, Q11.
- **Regel:** Liegt der Leistungsort im Drittland, ist die Leistung nicht steuerbar; der Pflichttext
  ist derselbe wie für einen regelbesteuerten Aussteller (R31). Ein § 19-Hinweis kommt nicht dazu.
- **Annahmen:** wie R15: § 19 erfasst nur Umsätze im Inland.
- **Werkzeug:** wie R31.
- **Status:** Annahme – ungeprüft.

### Abbruch statt falscher Entscheidung

#### R18 – Leistungsort in einem anderen EU-Staat bei Nichtunternehmern

- **Quelle:** Q4, Grundsatz.
- **Regel:** Ergibt R5 oder R6 einen Leistungsort in einem anderen EU-Staat, wäre die Steuer dort zu
  erklären. Das Werkzeug bricht ab.
- **Annahmen:** keine.
- **Werkzeug:** Abbruch mit Meldung. Nur bei `unternehmer: false`; ist der Status unbekannt (auch bei
  manueller Festlegung des Orts, R37), bricht das Werkzeug nach R19 ab.
- **Status:** Annahme – ungeprüft.

#### R19 – Unvollständige Daten

- **Quelle:** Grundsatz.
- **Regel:** Das Werkzeug entscheidet nur, wenn alle Merkmale bekannt sind, die nach R3–R8 den
  Leistungsort bestimmen. Fehlt eines, bricht es ab und nennt das Feld. Ob der Kunde Unternehmer ist,
  steht in jeder Kundendatei – auch dort, wo die Antwort den Leistungsort nicht ändert. Bei einem
  EU-Unternehmer ohne USt-IdNr. bricht es ebenfalls ab (R29).
- **Annahmen:** keine. Strenger als § 3a, mit Absicht: Als was der Kunde behandelt wurde, gehört zur
  Dokumentation jeder Rechnung (Nachweis, R3; künftig auch, ob an einen inländischen Unternehmer eine
  E-Rechnung geht), und das Werkzeug rät es nicht – auch nicht aus einer USt-IdNr.
- **Werkzeug:** `kunde.unternehmer` ist für jede Rechnung Pflicht. `leistung` (`taetigkeit`,
  `einordnung`, bei Tätigkeitsleistungen `ort`) ebenso – strenger als nötig, weil die Einordnung bei
  Unternehmern das Ergebnis nicht ändert, aber im Ergebnis festgehalten werden soll.
- **Status:** Annahme – ungeprüft.

### Pflichtangaben (§ 14 Abs. 4 UStG)

Bewiesen werden kann: *Wenn das Werkzeug eine Rechnung erzeugt, enthält das Ergebnis
(`rechnung.resolved.json`) jede Angabe dieser Liste.* Dass die Angabe auch im PDF steht, prüft
`rechnung pruefen` über den extrahierten Text – geprüft, nicht bewiesen.

#### R20 – Name und Anschrift beider Seiten

- **Quelle:** Q8 Nr. 1; Q12 Nr. 1.
- **Regel:** Vollständiger Name und vollständige Anschrift des Ausstellers und des Kunden.
- **Annahmen:** Beim Einzelunternehmer ist der Name der natürlichen Person anzugeben; eine
  Geschäftsbezeichnung ersetzt ihn nicht. Der Kunde ist die Person oder Gesellschaft, die die Leistung
  bezieht, nicht der Ansprechpartner.
- **Werkzeug:** `ich.yaml: name, adresse`; `kunde: firma, adresse`.
- **Status:** Annahme – ungeprüft.

#### R21 – Steuernummer oder USt-IdNr. des Ausstellers

- **Quelle:** Q8 Nr. 2; Q12 Nr. 2.
- **Regel:** Mindestens eine von beiden steht auf der Rechnung.
- **Werkzeug:** `ich.yaml: steuernummer`, `ustid`; Pflicht im Schema.
- **Status:** Annahme – ungeprüft.

#### R22 – Ausstellungsdatum

- **Quelle:** Q8 Nr. 3; Q12 Nr. 3.
- **Werkzeug:** `datum` (Vorgabe: heute).
- **Status:** Annahme – ungeprüft.

#### R23 – Rechnungsnummer, einmalig

- **Quelle:** Q8 Nr. 4.
- **Regel:** Jede Rechnung trägt eine Nummer; keine Nummer wird zweimal vergeben. Das Format ist frei,
  Lücken sind nicht verboten.
- **Annahmen:** Rechnungsordner werden nicht gelöscht. Heute bekannte Schwäche: Wird der Ordner der
  jüngsten Rechnung gelöscht, vergibt das Werkzeug seine Nummer erneut.
- **Werkzeug:** Ordnername = Nummer; `naechste_lfd()`: höchste laufende Nummer im Jahr plus eins.
- **Status:** Annahme – ungeprüft.

#### R24 – Umfang und Art der Leistung

- **Quelle:** Q8 Nr. 5; Q12 Nr. 4.
- **Regel:** Jede Position hat eine Beschreibung, eine Menge und eine Einheit.
- **Werkzeug:** `positionen[]: beschreibung, menge, einheit` (alle Pflicht).
- **Status:** Annahme – ungeprüft.

#### R25 – Zeitpunkt der Leistung

- **Quelle:** Q8 Nr. 6.
- **Regel:** Die Rechnung nennt den Tag oder Zeitraum der Leistung, auch wenn er mit dem
  Ausstellungsdatum übereinstimmt.
- **Annahmen:** Strenger als das Gesetz (bei Identität würde ein Hinweis genügen); für Kleinunternehmer
  verlangt § 34a UStDV die Angabe gar nicht – das Werkzeug verlangt sie trotzdem.
- **Werkzeug:** `leistungsdatum` (Pflicht), `leistungsdatum_bis`.
- **Status:** Annahme – ungeprüft.

#### R26 – Entgelt nach Steuersätzen aufgeschlüsselt

- **Quelle:** Q8 Nr. 7.
- **Regel:** Das Nettoentgelt steht getrennt je Steuersatz auf der Rechnung.
- **Werkzeug:** `steuergruppen[]` in `resolved.json`.
- **Status:** Annahme – ungeprüft.

#### R27 – Steuersatz und Steuerbetrag oder Hinweis

- **Quelle:** Q8 Nr. 8; Q9.
- **Regel:** Für jeden Steuersatz stehen Satz und Steuerbetrag auf der Rechnung. Wird keine deutsche
  Steuer ausgewiesen, steht an ihrer Stelle der Pflichttext nach R16, R28 oder R31.
- **Werkzeug:** Summenblock und Block 8.
- **Status:** Annahme – ungeprüft.

### Rechnungen bei Steuerschuldnerschaft in der EU (§ 14a Abs. 1 UStG)

#### R28 – Angabe „Steuerschuldnerschaft des Leistungsempfängers“

- **Quelle:** Q9 (§ 14a Abs. 1 Satz 1 UStG), Q7.
- **Regel:** Liegt der Leistungsort nach R11 in einem anderen EU-Staat, trägt die Rechnung die Angabe
  „Steuerschuldnerschaft des Leistungsempfängers“.
- **Annahmen:** Wortlaut:
  - de: „Steuerschuldnerschaft des Leistungsempfängers (§ 14a Abs. 1 UStG, Art. 196 MwStSystRL).“
  - en: „Reverse charge: VAT is owed by the recipient (Art. 196 VAT Directive 2006/112/EC,
    section 14a (1) German VAT Act).“

  Bei einer englischen Rechnung steht die gesetzliche Angabe nur in englischer Fassung; Annahme, dass
  das genügt (Teil 6).
- **Werkzeug:** Pflichttext Block 8.
- **Status:** Annahme – ungeprüft.

#### R29 – Beide USt-IdNrn. auf der Rechnung

- **Quelle:** Q9 (§ 14a Abs. 1 Satz 3 UStG).
- **Regel:** Bei R28 enthält die Rechnung die USt-IdNr. des Ausstellers und die des Kunden. Gilt nicht
  für Kleinunternehmer (R15).
- **Annahmen:** Ohne USt-IdNr. des Kunden lässt sich keine korrekte Rechnung ausstellen; das Werkzeug
  bricht ab, statt Fall „EU-Unternehmer ohne USt-IdNr.“ anders zu behandeln.
- **Werkzeug:** `kunde.ustid` und `ich.yaml: ustid` Pflicht in diesem Fall.
- **Status:** Annahme – ungeprüft.

#### R30 – Frist: bis zum 15. des Folgemonats

- **Quelle:** Q9 (§ 14a Abs. 1 Satz 2 UStG).
- **Regel:** Bei R28 liegt das Ausstellungsdatum spätestens am 15. Tag des Monats, der auf den Monat
  der Leistung folgt.
- **Annahmen:** Maßgeblich ist das Leistungsdatum (bei Zeitraum: das Ende). Eine verspätete Rechnung
  ist nicht unwirksam; das Werkzeug warnt, statt abzubrechen.
- **Werkzeug:** `datum`, `leistungsdatum`, `leistungsdatum_bis`; Warnung.
- **Status:** Annahme – ungeprüft.

### Pflichttext bei Leistungsort im Drittland

#### R31 – Hinweis auf Leistungsort und Nichtsteuerbarkeit

- **Quelle:** Q1, Q3/Q4/Q5; kein Gesetz schreibt den Text vor.
- **Regel:** Liegt der Leistungsort im Drittland, nennt die Rechnung den Leistungsort und dass die
  Leistung in Deutschland nicht steuerbar ist.
- **Annahmen:** Kein Pflichttext im Sinn von § 14 Abs. 4 Nr. 8 (es liegt keine Steuerbefreiung vor,
  sondern Nichtsteuerbarkeit), aber Praxis: Der Text erklärt, warum keine Umsatzsteuer ausgewiesen ist.
  Wortlaut:
  - de: „Leistungsort: {Land}. Die Leistung ist in Deutschland nicht steuerbar (§ 3a Abs. 2 UStG).“
  - en: „Place of supply: {Country}. Not subject to German VAT; the reverse charge may apply in the
    recipient's country.“

  Die zitierte Vorschrift folgt der Regel, die den Leistungsort bestimmt hat (R3: § 3a Abs. 2; R5:
  § 3a Abs. 3 Nr. 3; R7: § 3a Abs. 4). Der Nachsatz zum Reverse Charge passt nur bei Unternehmern; bei
  Privatpersonen entfällt er.
- **Werkzeug:** Pflichttext Block 8 mit Ländername aus `LAENDER`.
- **Status:** Annahme – ungeprüft.

### Beträge

#### R32 – Steuerbetrag je Satz und Gesamtbetrag

- **Quelle:** Q6, Q8 Nr. 7 und 8.
- **Regel:** Je Steuersatz ist der Steuerbetrag das Nettoentgelt dieser Gruppe mal Satz. Der
  Rechnungsbetrag ist die Summe der Nettoentgelte plus die Summe der Steuerbeträge.
- **Annahmen:** Gerundet wird kaufmännisch auf ganze Cent, und zwar je Zeile und je Steuergruppe.
  Das Gesetz schreibt keine Rundungsmethode vor; das ist eine Entscheidung des Werkzeugs und wird nicht
  bewiesen.
- **Werkzeug:** `runde()`, `steuergruppen`, `netto`, `ust_betrag`, `brutto`.
- **Status:** Annahme – ungeprüft.

#### R33 – Kein zu hoher Steuerausweis

- **Quelle:** Q10 (§ 14c Abs. 1 UStG).
- **Regel:** Der ausgewiesene Steuerbetrag je Gruppe ist nie größer als Nettoentgelt × Satz, gerundet
  auf ganze Cent.
- **Annahmen:** wie R32.
- **Werkzeug:** wie R32.
- **Status:** Annahme – ungeprüft.

#### R34 – Fremdwährung nur ohne deutschen Steuerausweis

- **Quelle:** Q13 (§ 16 Abs. 6 UStG).
- **Regel:** Weist eine Rechnung deutsche Umsatzsteuer aus, ist sie in EUR ausgestellt. In USD oder
  GBP nur, wenn keine deutsche Steuer ausgewiesen wird.
- **Annahmen:** Mit Steuerausweis müsste der Steuerbetrag zusätzlich in Euro zum amtlichen Monatskurs
  angegeben werden (Verwaltungsauffassung, Fundstelle nicht geprüft). Das Werkzeug kann das nicht und
  bricht ab – strenger als das Gesetz.
- **Werkzeug:** `waehrung`; `waehrung_erlaubt()`.
- **Status:** Annahme – ungeprüft.

### Werkzeug-Regeln

#### R35 – Einordnung wird festgehalten

- **Quelle:** Grundsatz.
- **Regel:** Das Ergebnis jeder Rechnung hält fest, welche Merkmale (Land des Kunden, Unternehmer,
  Tätigkeit, Einordnung, Ort, Kleinunternehmer), welcher Leistungsort und welche Regeln (IDs) zur
  Entscheidung geführt haben.
- **Werkzeug:** `leistung`, `leistungsort`, `ergebnis`, `regeln` in `rechnung.resolved.json`.
- **Status:** Werkzeug-Entscheidung, kein Steuerrecht.

#### R36 – (entfallen)

War: Warnung bei ungeprüften Regeln. Entfallen am 2026-10-08: Der Status steht in diesem Dokument,
der Regel-Trace (R35) zeigt, welche Regeln eine Rechnung angewandt hat.

#### R37 – Manuelle Festlegung des Leistungsorts nur mit Begründung

- **Quelle:** Grundsatz.
- **Regel:** Der Mensch darf den Leistungsort festlegen, statt ihn aus R3–R8 ableiten zu lassen, aber
  nur mit schriftlicher Begründung in der Rechnung. Ergebnis, Satz und Pflichttext folgen dann aus dem
  festgelegten Ort nach denselben Regeln wie sonst; R12, R14 und R18 gelten auch dann. Die Begründung
  steht im Ergebnis.
- **Annahmen:** Gedacht für Fälle außerhalb des Geltungsbereichs (z. B. Leistung an eine Betriebsstätte
  des Kunden in einem anderen Land), die der Mensch nach Rücksprache selbst verantwortet. Festgelegt
  wird eine Tatsache, nicht das Ergebnis – so ist etwa ein Kleinunternehmer mit 19 % ausgeschlossen.
- **Werkzeug:** `leistungsort` + `begruendung` in `rechnung.yaml`.
- **Status:** Werkzeug-Entscheidung, kein Steuerrecht.

### Pro forma

#### R38 – Eine Pro forma rechnet nicht ab

- **Quelle:** Q15 (§ 14 Abs. 1 Satz 1 UStG), Q10 (§ 14c UStG).
- **Regel:** Eine Pro forma ist keine Rechnung, weil mit ihr nicht abgerechnet wird: Sie fordert
  nicht zur Zahlung auf, sondern zur Prüfung, und kündigt die Rechnung an. Die Bezeichnung allein
  genügt dafür nicht – nach § 14 Abs. 1 kommt es nicht darauf an, wie ein Dokument heißt. Deshalb:
  - jede Seite trägt die Kopfzeile „PRO FORMA – KEINE RECHNUNG“ / „PRO FORMA – NOT AN INVOICE“, der
    Betreff „(keine Rechnung)“ / „(not an invoice)“, Nummer, Datum und Fälligkeit sind als vorläufig
    bezeichnet;
  - statt der Zahlungsaufforderung steht „Bitte prüfen Sie die Angaben. Die Rechnung folgt nach Ihrer
    Bestätigung.“ / „Please check the details. The invoice will follow upon your confirmation.“;
  - Pro forma und Rechnung entstehen aus denselben Daten nach denselben Regeln: Die Kennzeichnung
    ändert nie Leistungsort, Ergebnis, Satz oder Beträge;
  - eine echte Rechnung trägt keine Pro-forma-Kennzeichnung.
- **Annahmen:** Eine so gekennzeichnete Pro forma, die keine Zahlung verlangt, ist kein Dokument, mit
  dem abgerechnet wird – auch wenn sie Steuerbeträge zeigt. Bleibt sie die einzige Abrechnung (die
  Rechnung folgt nie), könnte sie als Rechnung gelten; dann gälte für einen ausgewiesenen
  Steuerbetrag § 14c. Die Pro forma trägt die Nummer der späteren Rechnung; eine Pro forma ohne
  Rechnung hinterlässt eine Lücke in den Nummern, die zu erklären ist (R23).
- **Werkzeug:** `rechnung bauen --pro-forma`, `rechnung pro-forma <nr> --gesendet-am`
  (Revisionen in `pro-forma/<n>/`), Belegart `proforma` in der Vorlage; `rechnung pruefen` weist die
  Kennzeichnung an der Pro forma nach und ihr Fehlen an der Rechnung.
- **Status:** Annahme – ungeprüft.

---

## Teil 4 – Zuordnung zum Werkzeug

### Die Einordnung der Leistung

`leistung.einordnung` nimmt genau ein Wort aus dieser Tabelle. Das Wort ist der Begriff aus dem Gesetz;
die Gruppe leitet das Werkzeug daraus ab. `rechnung neu` schreibt die Liste als Kommentar in die Datei.

| Einordnung | Fundstelle | Gruppe | Regel bei Privatpersonen |
| --- | --- | --- | --- |
| `kulturell` | § 3a Abs. 3 Nr. 3 | Tätigkeit | R5, R6 |
| `kuenstlerisch` | § 3a Abs. 3 Nr. 3 | Tätigkeit | R5, R6 |
| `wissenschaftlich` | § 3a Abs. 3 Nr. 3 | Tätigkeit | R5, R6 |
| `unterrichtend` | § 3a Abs. 3 Nr. 3 | Tätigkeit | R5, R6 |
| `sportlich` | § 3a Abs. 3 Nr. 3 | Tätigkeit | R5, R6 |
| `unterhaltend` | § 3a Abs. 3 Nr. 3 | Tätigkeit | R5, R6 |
| `rechte` | § 3a Abs. 4 Satz 2 Nr. 1 – Patente, Urheber-, Markenrechte und ähnliche Rechte | Katalog | R7, R8 |
| `werbung` | Nr. 2 – Werbung, Öffentlichkeitsarbeit | Katalog | R7, R8 |
| `beratung` | Nr. 3 – Rechtsanwalt, Steuerberater, Sachverständiger, Ingenieur, Dolmetscher, Übersetzer …; rechtliche, wirtschaftliche, technische Beratung | Katalog | R7, R8 |
| `datenverarbeitung` | Nr. 4 | Katalog | R7, R8 |
| `informationen` | Nr. 5 – Überlassung von Informationen, gewerblichen Verfahren und Erfahrungen | Katalog | R7, R8 |
| – | Nr. 6 – Bank-, Finanz-, Versicherungsumsätze, Edelmetalle | außen vor (Teil 1) | – |
| `personal` | Nr. 7 – Gestellung von Personal | Katalog | R7, R8 |
| `verzicht-recht` | Nr. 8 – Verzicht auf ein Recht aus Nr. 1 | Katalog | R7, R8 |
| `verzicht-taetigkeit` | Nr. 9 – Verzicht auf eine gewerbliche oder berufliche Tätigkeit | Katalog | R7, R8 |
| `vermietung` | Nr. 10 – bewegliche Gegenstände, außer Beförderungsmittel | Katalog | R7, R8 |
| – | Nr. 11–13 – weggefallen, heute § 3a Abs. 5 | außen vor (Teil 1) | – |
| `energienetze` | Nr. 14 – Zugang zu Gas-, Strom-, Wärme-, Kältenetzen | Katalog | R7, R8 |
| `sonstige` | § 3a Abs. 1 und 2 – keine der obigen | Grundregel | R4 |

Bei Unternehmern ist die Gruppe gleichgültig: Es gilt immer R3.

### Die Entscheidungstabelle

Eingaben: Land des Kunden (Inland / EU / Drittland), Unternehmer ja/nein, Gruppe der Einordnung, Ort
der Tätigkeit. Ausgabe: Leistungsort, und daraus das Ergebnis mit Satz und Pflichttext.

**Regelbesteuerung:**

| # | Kunde | Einordnung | Leistungsort | Ergebnis | Satz | Pflichttext | Regeln | früher |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Unternehmer, Inland | jede | Inland | `inland` | 19 % / 7 % | – | R3, R10 | A |
| 2 | Unternehmer, EU | jede | EU-Staat des Kunden | `reverse_charge` | 0 % | Steuerschuldnerschaft | R3, R11, R28–R30 | B |
| 3 | Unternehmer, Drittland | jede | Drittland des Kunden | `nicht_steuerbar` | 0 % | Leistungsort | R3, R31 | C |
| 4 | Privat, Inland | Grundregel, Katalog | Inland | `inland` | 19 % / 7 % | – | R4, R8, R10 | A |
| 5 | Privat, EU | Grundregel, Katalog | Inland | `inland` | 19 % / 7 % | – | R4, R8, R10 | D (Abbruch) |
| 6 | Privat, Drittland | Grundregel | Inland | `inland` | 19 % / 7 % | – | R4, R10 | D (Abbruch) |
| 7 | Privat, Drittland | Katalog | Drittland des Kunden | `nicht_steuerbar` | 0 % | Leistungsort | R7, R31 | D (falsch) |
| 8 | Privat, jedes Land | Tätigkeit, Ort Inland | Inland | `inland` | 19 % / 7 % | – | R5, R10 | A bzw. D |
| 9 | Privat, jedes Land | Tätigkeit, Ort Drittland | Drittland der Tätigkeit | `nicht_steuerbar` | 0 % | Leistungsort | R5, R31 | A bzw. D (falsch) |
| 10 | Privat, jedes Land | Tätigkeit, Ort anderer EU-Staat | dieser EU-Staat | – | – | – | R18 | **Abbruch** |
| 11 | Privat, jedes Land | Tätigkeit, online | Wohnsitz des Kunden | wie Zeile 8, 9 bzw. 10 | | | R6 | – |
| 12 | Unternehmer, EU, ohne USt-IdNr. | jede | EU-Staat des Kunden | – | – | – | R19, R29 | D (**Abbruch**, bleibt) |
| 13 | Unternehmer unbekannt | | | – | – | – | R19 | D (**Abbruch**, bleibt) |
| 14 | jeder, Aussteller nicht in Deutschland | | | – | – | – | R4 | **Abbruch** |

**Kleinunternehmer** (`kleinunternehmer: true` in `ich.yaml`): dieselbe Tabelle bestimmt den
Leistungsort, dann gilt:

| Leistungsort | Ergebnis | Satz | Pflichttext | Regeln |
| --- | --- | --- | --- | --- |
| Inland (Zeilen 1, 4, 5, 6, 8, 11) | `kleinunternehmer` | 0 % | Kleinunternehmer-Hinweis | R13, R14, R16 |
| EU-Staat, Kunde Unternehmer (Zeile 2) | `reverse_charge` | 0 % | Steuerschuldnerschaft; USt-IdNrn. nicht Pflicht | R14, R15, R28, R30 |
| Drittland (Zeilen 3, 7, 9, 11) | `nicht_steuerbar` | 0 % | Leistungsort | R14, R17, R31 |
| Abbruch (Zeilen 10, 12, 13, 14) | – | – | – | R4, R18, R19 |

### Die Ergebnisse

| Ergebnis | Bedeutung | früher |
| --- | --- | --- |
| `inland` | Leistungsort Inland, steuerpflichtig, 19 % oder 7 % | A, D |
| `reverse_charge` | Leistungsort in einem anderen EU-Staat, Steuer schuldet der Kunde | B |
| `nicht_steuerbar` | Leistungsort im Drittland | C |
| `kleinunternehmer` | Leistungsort Inland, steuerfrei nach § 19 | – |

D gibt es nicht mehr. Es fasste zwei verschiedene Dinge zusammen: fehlende Daten (jetzt Abbruch, R19)
und Privatpersonen, deren Leistungsort je nach Einordnung im Inland (`inland`) oder im Drittland
(`nicht_steuerbar`) liegt.

---

## Teil 5 – Regeln im Code

Stand 2026-10-10. Die Steuerentscheidung (R1–R19, R28–R31, R37) steckt in einer einzigen reinen
Funktion, `rules.kern()`. Sie rechnet nur mit abstrakten Merkmalen: Kategorie des Kundenlands,
Unternehmer, USt-IdNrn., Gruppe der Einordnung, Ort der Tätigkeit, Kleinunternehmer, Sitz des
Ausstellers im Inland, Festlegung. Das sind 3456 mögliche Eingaben. Der Satz je Position (R10, R12,
R14) ist die zweite reine Funktion, `rules.satz_position()`. `rules.entscheide()` übersetzt die Daten einer Rechnung in Merkmale und
das Ergebnis zurück in Land, Hinweistext und Meldungen. Jede Rechnung hält in `resolved.json` fest,
welche Regeln angewandt wurden (`regeln`, R35).

| Regel | Umgesetzt in | Geprüft durch |
| --- | --- | --- |
| R1 | `rules.kategorie()`, `EU_LAENDER` | `test_gb_ist_drittland` |
| R2–R12, R13–R19, R29, R31, R37 (Entscheidung) | `rules.kern()` | `test_entscheidungstabelle` (Zeilen aus Teil 4), `test_abbruch_statt_falscher_entscheidung`, `test_kleinunternehmer`, `test_aussteller_ausserhalb_deutschlands_bricht_ab`, und über **alle 3456 Merkmalskombinationen**: `test_kern_ist_total`, `test_kern_aussteller_im_ausland_bricht_immer_ab`, `test_kern_r19_genau_wenn_unternehmer_fehlt`, `test_kern_r18_nur_bei_privatpersonen`, `test_kern_satz_und_ergebnis_passen_zum_leistungsort`, `test_kern_unternehmer_immer_sitz_des_kunden`, `test_kern_kleinunternehmer_weist_nie_steuer_aus`, `test_kern_nennt_nur_regeln_aus_rules_md` |
| Einordnung (Teil 4) | `rules.EINORDNUNGEN`, `models.Einordnung` | `test_einordnungen_passen_zum_modell`, `test_einordnungen_stehen_in_rules_md` |
| R16, R28, R31 (Wortlaut) | `rules.hinweis()` | `test_hinweis_*` |
| R19, R24, R25, R37 (Pflichtfelder) | `models.Input`, `models.Leistung` | `tests/test_resolve.py` |
| R10, R12, R14 (Satz je Position) | `rules.satz_position()`, `models.Position` | `test_satz_position`, `test_positions_steuersatz_*` |
| R32 | `resolve.rechne()` | `tests/test_resolve.py` |
| R30 | `rules.frist_reverse_charge()`, Warnung in `resolve.rechne()` | `test_frist_reverse_charge`, `test_reverse_charge_fristwarnung` |
| R34 | `rules.waehrung_erlaubt()` | `test_fremdwaehrung_*` |
| R20–R29 im PDF | `pruefen.befunde()` | `tests/test_pruefen.py`, `rechnung pruefen` |
| R23 | `rules.naechste_lfd()` | `test_naechste_lfd_*` |
| R38 | `render.baue_pdf(…, pro_forma=True)`, Belegart `proforma` in `invoice.sty`, `festschreiben.pro_forma_festhalten()`, `pruefen.befunde(…, pro_forma)` | `test_pro_forma_ist_gekennzeichnet_und_rechnung_nicht`, `test_pro_forma_revisionen_werden_eingefroren` |
| IDs im Code | – | `test_jede_regel_id_im_code_steht_in_rules_md` |

Das sind Tests, keine Beweise. Die Beweise kommen mit dem Lean-Modell; es prüft `kern()` dann über
alle Eingaben gegen bewiesene Theoreme mit denselben IDs.

**Bekannte Grenzen des Codes:**

- R23: Wird der Ordner der jüngsten Rechnung gelöscht, vergibt das Werkzeug seine Nummer erneut.
- R1: Sondergebiete werden nicht unterschieden (Teil 1).
- R32: Gerundet wird je Zeile und je Steuergruppe; die Methode ist eine Entscheidung des Werkzeugs.

## Teil 6 – Fragen an den Steuerberater

1. **Leistungsort-Funktion (R3–R8, Teil 4):** Stimmt die Entscheidungstabelle im Geltungsbereich?
   Fehlt eine Ausnahme, die für ein Kleingewerbe mit Beratung, Vorträgen und Workshops praktisch
   vorkommt?
2. **Abgrenzung der Leistungsarten (R5, R7):** Ein Vortrag, ein Panel, ein Workshop für Privatleute –
   Tätigkeitsleistung nach § 3a Abs. 3 Nr. 3 oder Beratung nach § 3a Abs. 4 Nr. 3? Gibt es eine
   Faustregel, die wir in die Anleitung schreiben können?
3. **Nebenleistung (R9):** Reisekosten (Flug, Hotel), die mit der Leistung weiterberechnet werden,
   teilen Leistungsort und Steuersatz der Hauptleistung – auch im Inland mit 19 %, obwohl ein Flug
   selbst anders besteuert wäre?
4. **Fundstelle im Reverse-Charge-Text (R28):** § 14a Abs. 1 statt Abs. 5 – einverstanden? Reicht die
   englische Fassung allein auf einer englischen Rechnung?
5. **Nachweis der Unternehmereigenschaft im Drittland (R3):** Was soll in den Kundendaten stehen, damit
   eine Prüfung später nachvollziehen kann, warum der Kunde als Unternehmer behandelt wurde?
6. **Text bei Leistungsort im Drittland (R31):** Braucht es ihn überhaupt? Passt der Wortlaut auch für
   Privatpersonen (ohne Reverse-Charge-Nachsatz)?
7. **Kleinunternehmer und EU-Unternehmer (R15):** Trägt die Rechnung „Steuerschuldnerschaft des
   Leistungsempfängers“? Ist ein zusätzlicher § 19-Hinweis nötig oder schädlich? Muss der
   Kleinunternehmer eine Zusammenfassende Meldung abgeben?
8. **Kleinunternehmer-Hinweis (R16):** Ist der vorgeschlagene Wortlaut ausreichend? Ist es richtig,
   keine Zeile „USt 0,00“ zu drucken?
9. **Kleinunternehmer und Drittland (R17):** nur der Leistungsort-Text, kein § 19-Hinweis – richtig?
10. **Frist (R30):** Warnung genügt, oder soll das Werkzeug eine verspätete Rechnung verweigern?
11. **Pflichtangaben bei nicht steuerbaren Leistungen (R20–R27):** Das Werkzeug wendet den vollen
    Katalog des § 14 Abs. 4 auch an, wenn der Leistungsort im Drittland liegt. Spricht etwas dagegen?
12. **Manuelle Festlegung (R37):** Gibt es Fälle, in denen Sie einen anderen Leistungsort als den
    aus der Tabelle empfehlen würden? Oder soll es diese Möglichkeit gar nicht geben?
13. **Pro forma (R38):** Genügt die Kennzeichnung („keine Rechnung“, vorläufige Nummer, Bitte um Prüfung
    statt Zahlungsaufforderung), damit die Pro forma nicht als Rechnung gilt – auch wenn sie
    Steuerbeträge zeigt? Was gilt, wenn auf eine Pro forma nie eine Rechnung folgt?
14. **Gemischte Sätze (R9, R10):** Darf eine Rechnung über Leistungen derselben Einordnung Positionen
    mit 19 % und 7 % haben (etwa ein Vortrag und die Einräumung von Nutzungsrechten nach § 12 Abs. 2
    Nr. 7 c)? Oder ist das schon eine zweite Hauptleistung, die auf eine eigene Rechnung gehört?
