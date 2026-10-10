/-
Beweise der Aussagen, die nur von der Gesetzes-Ebene handeln: Steuerbarkeit (R2) und dass von den
Vorschriften des § 3a im Geltungsbereich höchstens eine greift (R3–R8).
-/
import Rechnung.Aussagen

namespace Rechnung

/-- R2: Steuerbar ist genau, was im Inland ausgeführt wird. Folgt daraus, dass es genau ein Inland
gibt (`inland_eindeutig`). -/
theorem R2_steuerbar_genau_im_inland : Aussage.R2_steuerbar_genau_im_inland := by
  intro g l
  simp [steuerbar, g.inland_eindeutig]

/-- R3–R8: Höchstens eine Vorschrift greift. Abs. 2 verlangt einen Unternehmer, Abs. 3 Nr. 3 und
Abs. 4 einen Nichtunternehmer; Abs. 3 Nr. 3 verlangt eine Tätigkeit, Abs. 4 eine Katalogleistung;
Satz 1 und Satz 2 von Abs. 3 Nr. 3 schließen sich über den Ort der Erbringung aus. -/
theorem R3_R8_eindeutig : Aussage.R3_R8_eindeutig := by
  intro g s
  obtain ⟨unternehmer, sitz, einordnung, erbringung, _, _⟩ := s
  cases unternehmer <;> cases h : einordnung.gruppe <;> cases erbringung <;>
    simp [greifende, abs2, abs3_nr3_satz1, abs3_nr3_satz2, abs4, h] <;> split <;> simp

end Rechnung
