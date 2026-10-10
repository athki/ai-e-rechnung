/-
Beweise der Aussagen, die nur vom Kern handeln (R12, R14–R17, R28, R30, Abbruch nur aus genannten
Gründen). Erst zwei Hilfssätze, die zerlegen, wie ein Ergebnis von `kern` aussieht; dann je Aussage eine
Fallunterscheidung nach dem Ort und danach, ob der Aussteller Kleinunternehmer ist.
-/
import Rechnung.Aussagen

namespace Rechnung

/-- Die Ortsregeln: was `kern_ort` in den Trace schreibt. -/
def ortsregeln : List Regel := [.R3, .R4, .R5, .R6, .R7, .R8, .R37]

/-- `kern_ort` schreibt genau eine Regel in den Trace, und zwar eine Ortsregel. -/
theorem kern_ort_eine_regel (m : Merkmale) (u : Bool) :
    ∃ x, (kern_ort m u).2.2 = [x] ∧ x ∈ ortsregeln := by
  unfold kern_ort
  split
  · exact ⟨.R37, rfl, by decide⟩
  · exact ⟨.R3, rfl, by decide⟩
  · split
    · exact ⟨.R6, rfl, by decide⟩
    · exact ⟨.R5, rfl, by decide⟩
    · split
      · exact ⟨.R7, rfl, by decide⟩
      · exact ⟨.R8, rfl, by decide⟩
    · exact ⟨.R4, rfl, by decide⟩

/-- Wie ein Ergebnis von `kern` aussieht: Der Aussteller sitzt im Inland, `unternehmer` ist angegeben,
Quelle und Ort kommen aus `kern_ort` mit genau einer Ortsregel `x`, Ergebnis und Regeln aus
`kern_ergebnis`, dahinter der Satz und R12 bzw. R14 bei 0 %. -/
theorem kern_ok {m : Merkmale} {k : KernErgebnis} (h : kern m = .ok k) :
    m.aussteller_inland = true ∧ ∃ u, m.unternehmer = some u ∧
      ∃ x, kern_ort m u = (k.ort_quelle, k.ort, [x]) ∧ x ∈ ortsregeln ∧
      ∃ rs, kern_ergebnis m u k.ort [.R1, .R2, x, .R9] = .ok (k.ergebnis, rs) ∧
        k.satz = (if k.ergebnis = .inland then 19 else 0) ∧
        k.regeln = (if k.satz = 0 then rs ++ [if m.kleinunternehmer then .R14 else .R12] else rs) := by
  unfold kern at h
  cases hi : m.aussteller_inland <;> simp only [hi, Bool.not_false, Bool.not_true] at h
  · cases h
  refine ⟨rfl, ?_⟩
  cases hu : m.unternehmer with
  | none => simp [hu] at h
  | some u =>
    simp only [hu] at h
    obtain ⟨x, hx, hmem⟩ := kern_ort_eine_regel m u
    rcases hko : kern_ort m u with ⟨q, o, r⟩
    rw [hko] at h hx
    simp only at hx
    subst hx
    simp only [List.cons_append, List.nil_append] at h
    rcases he : kern_ergebnis m u o [.R1, .R2, x, .R9] with a | ⟨e, rs⟩ <;> rw [he] at h
    · cases h
    · cases h
      exact ⟨u, rfl, x, hko, hmem, rs, he, rfl, rfl⟩

/-- Was `kern_ergebnis` liefert, je Ort. `p` ist der Trace bis dahin. -/
theorem kern_ergebnis_ok {m : Merkmale} {u : Bool} {o : Kategorie} {p rs : List Regel} {e : Ergebnis}
    (h : kern_ergebnis m u o p = .ok (e, rs)) :
    (o = .inland ∧ m.kleinunternehmer = true ∧ e = .kleinunternehmer ∧ rs = p ++ [.R13, .R16]) ∨
    (o = .inland ∧ m.kleinunternehmer = false ∧ e = .inland ∧ rs = p ++ [.R10]) ∨
    (o = .eu ∧ u = true ∧ m.kleinunternehmer = true ∧ e = .reverse_charge ∧
      rs = p ++ [.R11, .R15, .R28, .R30]) ∨
    (o = .eu ∧ u = true ∧ m.kleinunternehmer = false ∧ m.kunde_ustid = true ∧
      m.aussteller_ustid = true ∧ e = .reverse_charge ∧ rs = p ++ [.R11, .R28, .R29, .R30]) ∨
    (o = .drittland ∧ m.kleinunternehmer = true ∧ e = .nicht_steuerbar ∧ rs = p ++ [.R17, .R31]) ∨
    (o = .drittland ∧ m.kleinunternehmer = false ∧ e = .nicht_steuerbar ∧ rs = p ++ [.R31]) := by
  unfold kern_ergebnis at h
  cases o <;> cases hk : m.kleinunternehmer <;> cases u <;>
    cases hc : m.kunde_ustid <;> cases ha : m.aussteller_ustid <;>
    simp [hk, hc, ha] at h <;> simp [h]

/-- Wie ein Abbruch von `kern` aussieht: R4, R19, oder ein Abbruch aus `kern_ergebnis`. -/
theorem kern_fehler {m : Merkmale} {a : Abbruch} (h : kern m = .error a) :
    (m.aussteller_inland = false ∧ a = ⟨.R4, .aussteller_ausland⟩) ∨
    (m.aussteller_inland = true ∧ m.unternehmer = none ∧ a = ⟨.R19, .unternehmer_fehlt⟩) ∨
    (m.aussteller_inland = true ∧ ∃ u, m.unternehmer = some u ∧
      ∃ q o x, kern_ort m u = (q, o, [x]) ∧
      kern_ergebnis m u o [.R1, .R2, x, .R9] = .error a) := by
  unfold kern at h
  cases hi : m.aussteller_inland <;> simp only [hi, Bool.not_false, Bool.not_true] at h
  · cases h; simp
  cases hu : m.unternehmer with
  | none => simp only [hu] at h; cases h; simp
  | some u =>
    simp only [hu] at h
    obtain ⟨x, hx, -⟩ := kern_ort_eine_regel m u
    rcases hko : kern_ort m u with ⟨q, o, r⟩
    rw [hko] at h hx
    simp only at hx
    subst hx
    simp only [List.cons_append, List.nil_append] at h
    rcases he : kern_ergebnis m u o [.R1, .R2, x, .R9] with b | ⟨e, rs⟩ <;> rw [he] at h
    · cases h
      exact .inr (.inr ⟨rfl, u, rfl, q, o, x, hko, he⟩)
    · cases h

/-- Wann `kern_ergebnis` abbricht: nur bei Ort in einem anderen EU-Staat, nach R18 oder R29. -/
theorem kern_ergebnis_fehler {m : Merkmale} {u : Bool} {o : Kategorie} {p : List Regel} {a : Abbruch}
    (h : kern_ergebnis m u o p = .error a) :
    o = .eu ∧
    ((u = false ∧ a = ⟨.R18, .eu_privat⟩) ∨
     (u = true ∧ m.kleinunternehmer = false ∧ m.kunde_ustid = false ∧
       a = ⟨.R29, .kunde_ustid_fehlt⟩) ∨
     (u = true ∧ m.kleinunternehmer = false ∧ m.kunde_ustid = true ∧ m.aussteller_ustid = false ∧
       a = ⟨.R29, .eigene_ustid_fehlt⟩)) := by
  unfold kern_ergebnis at h
  cases o <;> cases hk : m.kleinunternehmer <;> cases u <;>
    cases hc : m.kunde_ustid <;> cases ha : m.aussteller_ustid <;>
    simp [hk, hc, ha] at h <;> simp [h]

/-- Zerlegt `h : kern m = .ok ⟨q, o, e, s, r⟩` in alle Fälle, die `kern` kennt: Ort, Kleinunternehmer,
Ortsregel. In jedem Fall sind Ergebnis, Satz und Trace ausgerechnet. -/
syntax "kern_faelle " term : tactic
set_option hygiene false in
macro_rules
  | `(tactic| kern_faelle $h) => `(tactic|
    (obtain ⟨_, _, _, x, _, hx, _, he, hs, hr⟩ := kern_ok $h
     simp only at he hs hr
     simp only [ortsregeln, List.mem_cons, List.not_mem_nil, or_false] at hx
     rcases kern_ergebnis_ok he with
       ⟨rfl, _, rfl, rfl⟩ | ⟨rfl, _, rfl, rfl⟩ | ⟨rfl, rfl, _, rfl, rfl⟩ |
       ⟨rfl, rfl, _, _, _, rfl, rfl⟩ | ⟨rfl, _, rfl, rfl⟩ | ⟨rfl, _, rfl, rfl⟩ <;>
     rcases hx with rfl | rfl | rfl | rfl | rfl | rfl | rfl))

/-! ## Die Aussagen -/

theorem R12_genau_bei_null_prozent_regelbesteuert : Aussage.R12_genau_bei_null_prozent_regelbesteuert := by
  intro m ⟨q, o, e, s, r⟩ h
  kern_faelle h <;> simp_all

theorem R14_kleinunternehmer_nie_steuer : Aussage.R14_kleinunternehmer_nie_steuer := by
  intro m ⟨q, o, e, s, r⟩ h
  kern_faelle h <;> simp_all [satz_position]

theorem R15_kleinunternehmer_eu_ohne_ustids : Aussage.R15_kleinunternehmer_eu_ohne_ustids := by
  refine ⟨?_, ?_⟩
  · intro m ⟨q, o, e, s, r⟩ h
    kern_faelle h <;> simp_all
  · intro m a h hk
    rcases kern_fehler h with ⟨_, rfl⟩ | ⟨_, _, rfl⟩ | ⟨_, u, _, _, _, x, _, he⟩
    · decide
    · decide
    · rcases (kern_ergebnis_fehler he).2 with ⟨_, rfl⟩ | ⟨_, hk', _⟩ | ⟨_, hk', _⟩
      · decide
      · simp_all
      · simp_all

theorem R16_hinweis_genau_bei_kleinunternehmer : Aussage.R16_hinweis_genau_bei_kleinunternehmer := by
  intro m ⟨q, o, e, s, r⟩ h
  kern_faelle h <;> simp_all

theorem R17_kleinunternehmer_drittland : Aussage.R17_kleinunternehmer_drittland := by
  intro m ⟨q, o, e, s, r⟩ h
  kern_faelle h <;> simp_all

theorem R28_angabe_genau_bei_reverse_charge : Aussage.R28_angabe_genau_bei_reverse_charge := by
  intro m ⟨q, o, e, s, r⟩ h
  kern_faelle h <;> simp_all

theorem R30_frist_genau_bei_reverse_charge : Aussage.R30_frist_genau_bei_reverse_charge := by
  intro m ⟨q, o, e, s, r⟩ h
  kern_faelle h <;> simp_all

theorem Abbruch_nur_aus_genannten_gruenden : Aussage.Abbruch_nur_aus_genannten_gruenden := by
  intro m a h
  rcases kern_fehler h with ⟨_, rfl⟩ | ⟨_, _, rfl⟩ | ⟨_, u, _, _, _, x, _, he⟩
  · decide
  · decide
  · rcases (kern_ergebnis_fehler he).2 with ⟨_, rfl⟩ | ⟨_, _, _, rfl⟩ | ⟨_, _, _, _, rfl⟩ <;> decide

end Rechnung
