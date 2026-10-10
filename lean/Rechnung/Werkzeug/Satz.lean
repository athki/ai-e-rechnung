/-
Spiegel von `rules.satz_position()`: der Satz einer Position (R10, R12, R14).
-/
import Rechnung.Werkzeug.Kern

namespace Rechnung

/-- Satz einer Position: der Satz der Rechnung, oder 7 %, wenn der Mensch die Position als ermäßigt
einordnet (§ 12 Abs. 2 UStG). Ermäßigt geht nur, wo deutsche Steuer ausgewiesen wird; sonst Abbruch
(R14 beim Kleinunternehmer, sonst R12). -/
def satz_position (satz : Nat) (kleinunternehmer ermaessigt : Bool) : Except Abbruch Nat :=
  if !ermaessigt then .ok satz
  else if satz = 0 then .error ⟨if kleinunternehmer then .R14 else .R12, .satz_ohne_steuer⟩
  else .ok 7

end Rechnung
