/-
Schreibt die Antworten des Lean-Modells für den Abgleich mit `rules.py` (Schritt 8.6) als JSON auf
die Standardausgabe, eine Zeile je Eingabe. `make abgleich` legt sie als `abgleich/kern.json` ab,
`pruefen.sh` vergleicht sie bei jedem Lauf mit der eingecheckten Datei, `tests/test_abgleich.py`
vergleicht `rules.py` dagegen.

Die Antworten rechnet `#eval` bzw. `--run` aus den Definitionen aus, denen die Beweise gelten; dabei
wird Leans Compiler vertraut. Die Eingaben kommen aus `Rechnung.Abgleich`, deren Vollständigkeit
bewiesen ist (`alle_vollstaendig`, `einordnungen_vollstaendig`, `satz_aus_kern`).

Die Felder tragen die Namen aus `rules.py`. Einzige Übersetzung: Lean führt Gruppe und Ort einer
Tätigkeit als einen Typ (`Leistungsmerkmal`), Python als zwei Felder (`gruppe`, `taetigkeit_ort`).
-/
import Rechnung

open Rechnung Rechnung.Abgleich

/-- Name eines Konstruktors ohne Namespace: `Rechnung.Regel.R3` → `R3`. Die Namen sind dieselben
wie die Werte in `rules.py`. -/
def kurz {α : Type} [Repr α] (x : α) : String :=
  ((toString (repr x)).splitOn ".").getLast!

def text (s : String) : String := "\"" ++ s ++ "\""
def wahr (b : Bool) : String := if b then "true" else "false"
def oder_null {α : Type} (f : α → String) : Option α → String
  | some x => f x
  | none => "null"
def objekt (felder : List (String × String)) : String :=
  "{" ++ ", ".intercalate (felder.map fun (k, v) => text k ++ ": " ++ v) ++ "}"
def liste (xs : List String) : String := "[" ++ ", ".intercalate xs ++ "]"

def gruppe_und_ort : Leistungsmerkmal → String × String
  | .taetigkeit (.land k) => (text "taetigkeit", text (kurz k))
  | .taetigkeit .online => (text "taetigkeit", text "online")
  | .katalog => (text "katalog", "null")
  | .grundregel => (text "grundregel", "null")

def eingabe (m : Merkmale) : String :=
  let (gruppe, ort) := gruppe_und_ort m.leistung
  objekt [
    ("kunde", text (kurz m.kunde)),
    ("unternehmer", oder_null wahr m.unternehmer),
    ("kunde_ustid", wahr m.kunde_ustid),
    ("gruppe", gruppe),
    ("taetigkeit_ort", ort),
    ("kleinunternehmer", wahr m.kleinunternehmer),
    ("aussteller_ustid", wahr m.aussteller_ustid),
    ("aussteller_inland", wahr m.aussteller_inland),
    ("festgelegt", oder_null (text ∘ kurz) m.festgelegt)]

def abbruch (a : Abbruch) : String :=
  objekt [("abbruch", objekt [("regel", text (kurz a.regel)), ("grund", text (kurz a.grund))])]

def antwort_kern : Except Abbruch KernErgebnis → String
  | .error a => abbruch a
  | .ok k => objekt [
      ("ort_quelle", text (kurz k.ort_quelle)),
      ("ort", text (kurz k.ort)),
      ("ergebnis", text (kurz k.ergebnis)),
      ("satz", toString k.satz),
      ("regeln", liste (k.regeln.map (text ∘ kurz))),
      ("fundstelle", oder_null (text ∘ Vorschrift.zitat) (fundstelle k))]

def zeile_kern (m : Merkmale) : String :=
  objekt [("eingabe", eingabe m), ("antwort", antwort_kern (kern m))]

def zeile_satz (satz : Nat) (ku ermaessigt : Bool) : String :=
  let antwort := match satz_position satz ku ermaessigt with
    | .error a => abbruch a
    | .ok s => objekt [("satz", toString s)]
  objekt [("eingabe", objekt [("satz", toString satz), ("kleinunternehmer", wahr ku),
    ("ermaessigt", wahr ermaessigt)]), ("antwort", antwort)]

def zeile_einordnung (e : Einordnung) : String :=
  objekt [("wort", text e.wort), ("gruppe", text (kurz e.gruppe)), ("fundstelle", text e.fundstelle)]

/-- Ein Block: Name und je Eintrag eine Zeile. -/
def block (name : String) (zeilen : List String) : String :=
  "  " ++ text name ++ ": [\n    " ++ ",\n    ".intercalate zeilen ++ "\n  ]"

def main : IO Unit := do
  let satz := saetze.flatMap fun s => bools.flatMap fun ku => bools.map fun e => zeile_satz s ku e
  IO.println ("{\n" ++ ",\n".intercalate [
    block "kern" (alle.map zeile_kern),
    block "satz_position" satz,
    block "einordnung" (einordnungen.map zeile_einordnung)] ++ "\n}")
