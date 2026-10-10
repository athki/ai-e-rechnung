/-
Spiegel von `rules.kern()`: dieselben Merkmale, dieselbe Fallunterscheidung, derselbe Regel-Trace in
derselben Reihenfolge. Schritt 8.6 vergleicht beide über alle 3456 Eingaben.

Eine Abweichung in der Form, nicht im Inhalt: Python führt Gruppe und Ort der Tätigkeit als zwei
Felder (`gruppe`, `taetigkeit_ort`), und `models.Leistung` erzwingt, dass der Ort genau bei
Tätigkeitsleistungen dasteht. Hier sagt das der Typ `Leistungsmerkmal`.
-/
import Rechnung.Gesetz.Gebiete
import Rechnung.Gesetz.Einordnung
import Rechnung.Werkzeug.Regel

namespace Rechnung

/-- Ort einer Tätigkeitsleistung, als Kategorie oder `online` (Python: `taetigkeit_ort`). -/
inductive OrtTaetigkeit
  | land (k : Kategorie)
  | online
  deriving DecidableEq, Repr

/-- Gruppe der Einordnung, bei Tätigkeitsleistungen mit Ort. -/
inductive Leistungsmerkmal
  | taetigkeit (ort : OrtTaetigkeit)
  | katalog
  | grundregel
  deriving DecidableEq, Repr

/-- Alles, wovon die Steuerentscheidung abhängt (`rules.Merkmale`). -/
structure Merkmale where
  kunde             : Kategorie        -- Kategorie des Kundenlands
  unternehmer       : Option Bool      -- aus der Kundendatei; none = nicht angegeben
  kunde_ustid       : Bool             -- Kunde hat eine USt-IdNr.
  leistung          : Leistungsmerkmal -- Python: gruppe und taetigkeit_ort
  kleinunternehmer  : Bool             -- Aussteller nach § 19 UStG
  aussteller_ustid  : Bool             -- Aussteller hat eine USt-IdNr.
  aussteller_inland : Bool             -- Aussteller betreibt sein Unternehmen vom Inland aus (R4)
  festgelegt        : Option Kategorie -- manuell festgelegter Leistungsort (R37)
  deriving DecidableEq, Repr

/-- Woher der Leistungsort kommt (`ORT_KUNDE` …). -/
inductive OrtQuelle
  | kunde | taetigkeit | aussteller | festgelegt
  deriving DecidableEq, Repr

/-- Das Ergebnis einer Rechnung (`models.Ergebnis`). -/
inductive Ergebnis
  | inland | reverse_charge | nicht_steuerbar | kleinunternehmer
  deriving DecidableEq, Repr

/-- `rules.KernErgebnis`. -/
structure KernErgebnis where
  ort_quelle : OrtQuelle
  ort        : Kategorie
  ergebnis   : Ergebnis
  satz       : Nat          -- 19 oder 0; 7 % je Position über `satz_position`
  regeln     : List Regel
  deriving DecidableEq, Repr

/-- Gründe eines Abbruchs (`rules.Abbruch.grund`). -/
inductive Grund
  | aussteller_ausland | unternehmer_fehlt | eu_privat | kunde_ustid_fehlt | eigene_ustid_fehlt
  | satz_ohne_steuer
  deriving DecidableEq, Repr

/-- `rules.Abbruch`: Das Werkzeug entscheidet nicht und sagt, warum. -/
structure Abbruch where
  regel : Regel
  grund : Grund
  deriving DecidableEq, Repr

/-- Leistungsort (R3–R8, R37): Quelle, Kategorie und Ortsregeln. -/
def kern_ort (m : Merkmale) (unternehmer : Bool) : OrtQuelle × Kategorie × List Regel :=
  match m.festgelegt, unternehmer with
  | some f, _ => (.festgelegt, f, [.R37])
  | none, true => (.kunde, m.kunde, [.R3])
  | none, false =>
    match m.leistung with
    | .taetigkeit .online => (.kunde, m.kunde, [.R6])
    | .taetigkeit (.land k) => (.taetigkeit, k, [.R5])
    | .katalog => if m.kunde = .drittland then (.kunde, m.kunde, [.R7]) else (.aussteller, .inland, [.R8])
    | .grundregel => (.aussteller, .inland, [.R4])

/-- Ergebnis und Regeln aus dem Leistungsort (R10–R17, R28–R31), oder Abbruch (R18, R29). -/
def kern_ergebnis (m : Merkmale) (unternehmer : Bool) (ort : Kategorie) (regeln : List Regel) :
    Except Abbruch (Ergebnis × List Regel) :=
  let ku := m.kleinunternehmer
  match ort with
  | .inland =>
    if ku then .ok (.kleinunternehmer, regeln ++ [.R13, .R16]) else .ok (.inland, regeln ++ [.R10])
  | .eu =>
    if !unternehmer then .error ⟨.R18, .eu_privat⟩
    else
      if ku then
        -- § 19 Abs. 1 Satz 2 UStG schließt § 14a Abs. 1 Satz 3 aus: keine USt-IdNrn. nötig (R15).
        .ok (.reverse_charge, regeln ++ [.R11, .R15, .R28, .R30])
      else if !m.kunde_ustid then .error ⟨.R29, .kunde_ustid_fehlt⟩
      else if !m.aussteller_ustid then .error ⟨.R29, .eigene_ustid_fehlt⟩
      else .ok (.reverse_charge, regeln ++ [.R11, .R28, .R29, .R30])
  | .drittland =>
    .ok (.nicht_steuerbar, regeln ++ (if ku then [.R17, .R31] else [.R31]))

/-- **Der Entscheidungskern** (`rules.kern()`): die Entscheidungstabelle aus RULES.md Teil 4 als
reine Funktion über Merkmale. -/
def kern (m : Merkmale) : Except Abbruch KernErgebnis :=
  -- R4: Das Werkzeug bildet das deutsche UStG ab und rechnet nur für Aussteller mit Sitz im Inland.
  if !m.aussteller_inland then .error ⟨.R4, .aussteller_ausland⟩ else
  -- R19: Ob der Kunde Unternehmer ist, steht in jeder Kundendatei; das Werkzeug rät es nicht.
  match m.unternehmer with
  | none => .error ⟨.R19, .unternehmer_fehlt⟩
  | some unternehmer =>
    let (quelle, ort, ort_regeln) := kern_ort m unternehmer
    match kern_ergebnis m unternehmer ort ([.R1, .R2] ++ ort_regeln ++ [.R9]) with
    | .error a => .error a
    | .ok (ergebnis, regeln) =>
      let satz := if ergebnis = .inland then 19 else 0
      let regeln := if satz = 0 then regeln ++ [if m.kleinunternehmer then .R14 else .R12] else regeln
      .ok ⟨quelle, ort, ergebnis, satz, regeln⟩

end Rechnung
