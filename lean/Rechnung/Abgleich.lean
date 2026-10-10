/-
Grundlage des Abgleichs mit `rules.py` (Schritt 8.6): alle Eingaben von `kern`, `satz_position` und
`Einordnung.gruppe` als Listen, und Sätze, dass nichts fehlt. `lean/Abgleich.lean` schreibt daraus
`lean/abgleich/kern.json` – je Eingabe die Antwort des bewiesenen Modells –, pytest vergleicht
`rules.py` dagegen (`tests/test_abgleich.py`).

Bewiesen ist hier nur die Vollständigkeit der Listen. Die Antworten in der Datei rechnet Lean mit
`#eval` aus der Definition aus; dabei wird Leans Compiler vertraut, nicht dem Kernel. Die Beweise der
Aussagen berührt das nicht.
-/
import Rechnung.Werkzeug.Satz
import Rechnung.Beweise.Kern

namespace Rechnung
namespace Abgleich

def kategorien : List Kategorie := [.inland, .eu, .drittland]
def bools : List Bool := [true, false]
def unternehmer : List (Option Bool) := [some true, some false, none]
def leistungen : List Leistungsmerkmal :=
  kategorien.map (fun k => .taetigkeit (.land k)) ++ [.taetigkeit .online, .katalog, .grundregel]
def festlegungen : List (Option Kategorie) := none :: kategorien.map some

/-- Alle Merkmale, in fester Reihenfolge: 3 · 3 · 2 · 6 · 2 · 2 · 2 · 4 = 3456. -/
def alle : List Merkmale :=
  kategorien.flatMap fun kunde =>
  unternehmer.flatMap fun u =>
  bools.flatMap fun kunde_ustid =>
  leistungen.flatMap fun leistung =>
  bools.flatMap fun ku =>
  bools.flatMap fun aussteller_ustid =>
  bools.flatMap fun aussteller_inland =>
  festlegungen.map fun festgelegt =>
    { kunde, unternehmer := u, kunde_ustid, leistung, kleinunternehmer := ku, aussteller_ustid,
      aussteller_inland, festgelegt }

/-- Alle Einordnungswörter (RULES.md Teil 4). -/
def einordnungen : List Einordnung :=
  [.kulturell, .kuenstlerisch, .wissenschaftlich, .unterrichtend, .sportlich, .unterhaltend,
   .rechte, .werbung, .beratung, .datenverarbeitung, .informationen,
   .personal, .verzicht_recht, .verzicht_taetigkeit, .vermietung, .energienetze, .sonstige]

/-- Die Sätze, die `kern` liefern kann (`satz_aus_kern`): der Bereich von `satz` in `satz_position`. -/
def saetze : List Nat := [19, 0]

theorem mem_kategorien (k : Kategorie) : k ∈ kategorien := by cases k <;> simp [kategorien]
theorem mem_bools (b : Bool) : b ∈ bools := by cases b <;> simp [bools]
theorem mem_unternehmer (u : Option Bool) : u ∈ unternehmer := by
  rcases u with _ | _ | _ <;> simp [unternehmer]
theorem mem_leistungen (l : Leistungsmerkmal) : l ∈ leistungen := by
  rcases l with (⟨k⟩ | _) | _ | _
  · cases k <;> simp [leistungen, kategorien]
  all_goals simp [leistungen]
theorem mem_festlegungen (f : Option Kategorie) : f ∈ festlegungen := by
  rcases f with _ | k
  · simp [festlegungen]
  · cases k <;> simp [festlegungen, kategorien]

/-- **Vollständig:** Jede mögliche Eingabe von `kern` steht in `alle`. Bekommt `Merkmale` ein neues
Feld oder ein Typ einen neuen Wert, scheitert dieser Beweis, bis die Aufzählung nachgezogen ist. -/
theorem alle_vollstaendig (m : Merkmale) : m ∈ alle := by
  obtain ⟨kunde, u, kunde_ustid, leistung, ku, aussteller_ustid, aussteller_inland, festgelegt⟩ := m
  simp only [alle, List.mem_flatMap, List.mem_map]
  exact ⟨kunde, mem_kategorien _, u, mem_unternehmer _, kunde_ustid, mem_bools _, leistung,
    mem_leistungen _, ku, mem_bools _, aussteller_ustid, mem_bools _, aussteller_inland, mem_bools _,
    festgelegt, mem_festlegungen _, rfl⟩

/-- **Vollständig:** Jedes Einordnungswort steht in `einordnungen`. -/
theorem einordnungen_vollstaendig (e : Einordnung) : e ∈ einordnungen := by
  cases e <;> simp [einordnungen]

/-- **Vollständig:** `kern` liefert nur Sätze aus `saetze`; mehr Eingaben hat `satz_position` im
Werkzeug nicht. -/
theorem satz_aus_kern {m : Merkmale} {k : KernErgebnis} (h : kern m = .ok k) : k.satz ∈ saetze := by
  obtain ⟨_, _, _, _, _, _, _, _, hs, _⟩ := kern_ok h
  rw [hs]
  split <;> simp [saetze]

end Abgleich
end Rechnung
