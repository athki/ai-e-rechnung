/-
Was aus dem Leistungsort folgt (RULES.md R2, R10, R11, R13, R15, R16, R28, R29): je Frage des Gesetzes
eine Funktion. Sie nehmen den Leistungsort als Argument, nicht den Sachverhalt, damit dieselben
Funktionen auch für einen manuell festgelegten Ort gelten (R37).

Nicht hier: der Hinweis bei Leistungsort im Drittland (R31). Kein Gesetz schreibt ihn vor; er ist
Praxis und gehört zur Werkzeug-Ebene.
-/
import Rechnung.Gesetz.Leistungsort

namespace Rechnung


/-- **R2 – § 1 Abs. 1 Nr. 1 UStG:** „Der Umsatzsteuer unterliegen die folgenden Umsätze: 1. die
Lieferungen und sonstigen Leistungen, die ein Unternehmer im Inland gegen Entgelt im Rahmen seines
Unternehmens ausführt.“ Status: Annahme – ungeprüft. -/
def steuerbar (g : Gebiete) (ort : g.Land) : Bool :=
  g.kategorie ort == .inland

/-- **R13 – § 19 Abs. 1 Satz 1 UStG:** „Ein von einem im Inland […] ansässigen Unternehmer bewirkter
Umsatz im Sinne des § 1 Absatz 1 Nummer 1 ist steuerfrei, wenn der Gesamtumsatz […] 25 000 Euro nicht
überschritten hat und im laufenden Kalenderjahr 100 000 Euro nicht überschreitet.“ Lesart: § 19
erfasst nur steuerbare Umsätze, also Leistungsort Inland (R13, R17). Status: Annahme – ungeprüft. -/
def steuerfrei (g : Gebiete) (klein : Bool) (ort : g.Land) : Bool :=
  steuerbar g ort && klein

/-- **R10 – § 12 Abs. 1 und 2 UStG:** „(1) Die Steuer beträgt für jeden steuerpflichtigen Umsatz 19
Prozent der Bemessungsgrundlage […]. (2) Die Steuer ermäßigt sich auf sieben Prozent für die folgenden
Umsätze: […]“ `ermaessigt`: Der Umsatz fällt unter § 12 Abs. 2. `none`: Es gibt keinen deutschen
Steuerbetrag (nicht steuerbar oder steuerfrei). Status: Annahme – ungeprüft. -/
def steuersatz (g : Gebiete) (klein : Bool) (ort : g.Land) (ermaessigt : Bool) : Option Nat :=
  if steuerbar g ort && !steuerfrei g klein ort then some (if ermaessigt then 7 else 19) else none

/-- **R11 – Art. 196 MwStSystRL:** „Die Mehrwertsteuer schuldet der Steuerpflichtige […], für den/die
eine Dienstleistung nach Artikel 44 erbracht wird, wenn die Dienstleistung von einem nicht in diesem
Mitgliedstaat ansässigen Steuerpflichtigen erbracht wird.“ Liegt der Ort in einem anderen EU-Staat
und ist der Empfänger Unternehmer, schuldet er die Steuer dort. Status: Annahme – ungeprüft. -/
def empfaenger_schuldet (g : Gebiete) (unternehmer : Bool) (ort : g.Land) : Bool :=
  g.kategorie ort == .eu && unternehmer

/-- **R28 (und R15) – § 14a Abs. 1 Satz 1 UStG:** Die Rechnung trägt die Angabe
„Steuerschuldnerschaft des Leistungsempfängers“, „wenn die Steuer in dem anderen Mitgliedstaat von dem
Leistungsempfänger geschuldet wird“. Gilt auch für den Kleinunternehmer (R15). Status: Annahme –
ungeprüft. -/
def angabe_steuerschuldnerschaft (g : Gebiete) (unternehmer : Bool) (ort : g.Land) : Bool :=
  empfaenger_schuldet g unternehmer ort

/-- **R29 (und R15) – § 14a Abs. 1 Satz 3 UStG:** „In dieser Rechnung sind die
Umsatzsteuer-Identifikationsnummer des Unternehmers und die des Leistungsempfängers anzugeben.“
§ 19 Abs. 1 Satz 2 UStG: Die Vorschriften „über die Angabe der Umsatzsteuer-Identifikationsnummern in
einer Rechnung (§ 14a Absatz 1 Satz 3 […])“ finden keine Anwendung. Lesart: Das gilt für jede Rechnung
eines Kleinunternehmers. Status: Annahme – ungeprüft, **unsicher** (RULES.md R15, Teil 6). -/
def ustids_pflicht (g : Gebiete) (klein unternehmer : Bool) (ort : g.Land) : Bool :=
  empfaenger_schuldet g unternehmer ort && !klein

/-- **R16 – § 34a Nr. 5 UStDV:** Die Rechnung enthält „das Entgelt für die Lieferung oder sonstige
Leistung in einer Summe mit einem Hinweis darauf, dass für die Lieferung oder sonstige Leistung die
Steuerbefreiung für Kleinunternehmer gilt (§ 19 des Gesetzes)“. Status: Annahme – ungeprüft. -/
def hinweis_kleinunternehmer (g : Gebiete) (klein : Bool) (ort : g.Land) : Bool :=
  steuerfrei g klein ort

/-- Alle Folgen auf einen Blick. -/
structure Folgen where
  steuerbar                    : Bool
  steuerfrei                   : Bool
  steuersatz                   : Option Nat   -- ohne Ermäßigung
  empfaenger_schuldet          : Bool
  angabe_steuerschuldnerschaft : Bool
  ustids_pflicht               : Bool
  hinweis_kleinunternehmer     : Bool
  deriving DecidableEq, Repr

/-- Die Folgen eines Umsatzes mit Leistungsort `ort`. -/
def folgen (g : Gebiete) (klein unternehmer : Bool) (ort : g.Land) : Folgen where
  steuerbar                    := steuerbar g ort
  steuerfrei                   := steuerfrei g klein ort
  steuersatz                   := steuersatz g klein ort false
  empfaenger_schuldet          := empfaenger_schuldet g unternehmer ort
  angabe_steuerschuldnerschaft := angabe_steuerschuldnerschaft g unternehmer ort
  ustids_pflicht               := ustids_pflicht g klein unternehmer ort
  hinweis_kleinunternehmer     := hinweis_kleinunternehmer g klein ort

end Rechnung
