/-
Die Rechnungsdaten auf Länder-Ebene und ihre Übersetzung in Merkmale und zurück: Spiegel von
`rules.merkmale()` und dem Teil von `rules.entscheide()`, der Land, Fundstelle und Unternehmerstatus
für den Hinweistext bestimmt.
-/
import Rechnung.Gesetz.Leistungsort
import Rechnung.Werkzeug.Kern

namespace Rechnung

/-- Ort einer Tätigkeitsleistung, wie er in `rechnung.yaml` steht: ein Land oder `online`. -/
inductive OrtAngabe (Land : Type)
  | land (l : Land)
  | online

/-- Was das Werkzeug aus `ich.yaml`, der Kundendatei und `rechnung.yaml` liest, soweit es die
Steuerentscheidung betrifft. -/
structure Daten (g : Gebiete) where
  kunde_land       : g.Land
  unternehmer      : Option Bool
  kunde_ustid      : Bool
  einordnung       : Einordnung
  ort              : Option (OrtAngabe g.Land)   -- `leistung.ort`
  kleinunternehmer : Bool
  aussteller_land  : g.Land
  aussteller_ustid : Bool
  festgelegt       : Option g.Land               -- `leistungsort:` (R37)

variable {g : Gebiete}

/-- `rules.merkmale()`. `none`, wo `models.Leistung` die Daten zurückweist: Ort fehlt bei einer
Tätigkeitsleistung oder steht bei einer anderen. -/
def merkmale (d : Daten g) : Option Merkmale :=
  let leistung : Option Leistungsmerkmal :=
    match d.einordnung.gruppe, d.ort with
    | .taetigkeit, some .online => some (.taetigkeit .online)
    | .taetigkeit, some (.land l) => some (.taetigkeit (.land (g.kategorie l)))
    | .taetigkeit, none => none
    | .katalog, none => some .katalog
    | .grundregel, none => some .grundregel
    | _, some _ => none
  leistung.map fun l => {
    kunde := g.kategorie d.kunde_land
    unternehmer := d.unternehmer
    kunde_ustid := d.kunde_ustid
    leistung := l
    kleinunternehmer := d.kleinunternehmer
    aussteller_ustid := d.aussteller_ustid
    aussteller_inland := g.kategorie d.aussteller_land == .inland
    festgelegt := d.festgelegt.map g.kategorie }

/-- Das Land des Leistungsorts (`entscheide()`: Quelle → Land). `none` nur bei Daten, aus denen
`kern` diese Quelle nicht liefern kann. -/
def ort_land (d : Daten g) (k : KernErgebnis) : Option g.Land :=
  match k.ort_quelle with
  | .kunde => some d.kunde_land
  | .taetigkeit => match d.ort with
    | some (.land l) => some l
    | _ => none
  | .aussteller => some d.aussteller_land
  | .festgelegt => d.festgelegt

/-- Die Vorschrift zu einer Ortsregel (`rules.FUNDSTELLE`). -/
def Regel.vorschrift : Regel → Option Vorschrift
  | .R3 => some .abs2
  | .R4 => some .abs1
  | .R5 => some .abs3_nr3_satz1
  | .R6 => some .abs3_nr3_satz2
  | .R7 => some .abs4
  | .R8 => some .abs1
  | _ => none

/-- Die Fundstelle im Hinweistext (`entscheide()`): die Vorschrift der letzten Ortsregel im Trace;
`none` bei manueller Festlegung. -/
def fundstelle (k : KernErgebnis) : Option Vorschrift :=
  if k.ort_quelle = .festgelegt then none
  else (k.regeln.filterMap Regel.vorschrift).getLast?

/-- Der Unternehmerstatus, den `entscheide()` an den Hinweistext weitergibt; er entscheidet über den
Reverse-Charge-Nachsatz bei Leistungsort im Drittland (R31). -/
def unternehmer_fuer_hinweis (m : Merkmale) : Option Bool :=
  m.unternehmer

end Rechnung
