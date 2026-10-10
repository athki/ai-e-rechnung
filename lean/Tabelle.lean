/-
Die Entscheidungstabelle aus RULES.md Teil 4, ausgerechnet mit dem Lean-`kern`. Keine Beweise: eine
Probe zum Lesen neben RULES.md. Läuft nach dem Build (`pruefen.sh`).
-/
import Rechnung

open Rechnung

/-- Name eines Konstruktors ohne Namespace: `Rechnung.Regel.R3` → `R3`. -/
def kurz {α : Type} [Repr α] (x : α) : String :=
  ((toString (repr x)).splitOn ".").getLast!

def zeige : Except Abbruch KernErgebnis → String
  | .error a => s!"Abbruch {kurz a.regel} ({kurz a.grund})"
  | .ok k =>
    s!"{kurz k.ort} ({kurz k.ort_quelle}), {kurz k.ergebnis}, {k.satz} %, " ++
      ", ".intercalate (k.regeln.map kurz)

/-- Regelbesteuerter Aussteller im Inland mit USt-IdNr., ohne Festlegung. -/
def basis : Merkmale :=
  { kunde := .inland, unternehmer := some true, kunde_ustid := true, leistung := .katalog,
    kleinunternehmer := false, aussteller_ustid := true, aussteller_inland := true, festgelegt := none }

def zeilen : List (String × Merkmale) := [
  ("1  Unternehmer, Inland",                    { basis with kunde := .inland }),
  ("2  Unternehmer, EU",                        { basis with kunde := .eu }),
  ("3  Unternehmer, Drittland",                 { basis with kunde := .drittland, kunde_ustid := false }),
  ("4  Privat, Inland, Grundregel",             { basis with unternehmer := some false, kunde_ustid := false, leistung := .grundregel }),
  ("5  Privat, EU, Katalog",                    { basis with kunde := .eu, unternehmer := some false, kunde_ustid := false }),
  ("6  Privat, Drittland, Grundregel",          { basis with kunde := .drittland, unternehmer := some false, kunde_ustid := false, leistung := .grundregel }),
  ("7  Privat, Drittland, Katalog",             { basis with kunde := .drittland, unternehmer := some false, kunde_ustid := false }),
  ("8  Privat, Tätigkeit im Inland",            { basis with kunde := .drittland, unternehmer := some false, kunde_ustid := false, leistung := .taetigkeit (.land .inland) }),
  ("9  Privat, Tätigkeit im Drittland",         { basis with unternehmer := some false, kunde_ustid := false, leistung := .taetigkeit (.land .drittland) }),
  ("10 Privat, Tätigkeit in anderem EU-Staat",  { basis with unternehmer := some false, kunde_ustid := false, leistung := .taetigkeit (.land .eu) }),
  ("11 Privat, Drittland, Tätigkeit online",    { basis with kunde := .drittland, unternehmer := some false, kunde_ustid := false, leistung := .taetigkeit .online }),
  ("12 Unternehmer, EU, ohne USt-IdNr.",        { basis with kunde := .eu, kunde_ustid := false }),
  ("13 Unternehmer unbekannt, Drittland",       { basis with kunde := .drittland, unternehmer := none, kunde_ustid := false }),
  ("14 Aussteller nicht im Inland",             { basis with aussteller_inland := false }),
  ("K  Kleinunternehmer, Inland",               { basis with kleinunternehmer := true, aussteller_ustid := false }),
  ("K  Kleinunternehmer, EU-Unternehmer",       { basis with kunde := .eu, kunde_ustid := false, kleinunternehmer := true, aussteller_ustid := false }),
  ("K  Kleinunternehmer, Drittland",            { basis with kunde := .drittland, kleinunternehmer := true, aussteller_ustid := false })
]

#eval do
  IO.println "Entscheidungstabelle (RULES.md Teil 4), ausgerechnet mit Rechnung.kern:"
  for (name, m) in zeilen do
    IO.println s!"  {name.pushn ' ' (40 - name.length)} → {zeige (kern m)}"
