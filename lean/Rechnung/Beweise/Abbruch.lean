/-
Beweise der Aussagen über Abbrüche, bezogen auf die Daten: R4 (Aussteller im Ausland), R19 (Unternehmer
fehlt), R18 (Privatperson, Ort in einem anderen EU-Staat), R29 (USt-IdNr. fehlt).
-/
import Rechnung.Beweise.Hilfssaetze

namespace Rechnung

variable {g : Gebiete}

/-- Mit welcher Kategorie der Kern rechnet: der des maßgeblichen Orts – auch wenn er danach abbricht. -/
theorem kategorie_kern_ort {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {u : Bool} {q : OrtQuelle}
    {o : Kategorie} {x : Regel} (hp : Passt g d s) (hm : merkmale d = some m)
    (hinl : g.kategorie d.aussteller_land = .inland) (hu : d.unternehmer = some u)
    (hko : kern_ort m u = (q, o, [x])) :
    o = g.kategorie (ort_massgeblich d s) := by
  have hus : u = s.empfaenger_unternehmer := by
    cases u
    · exact (hp.annahme_R3_privat hu).symm
    · exact (hp.annahme_R3_fuer_unternehmen hu).symm
  subst hus
  cases hf : d.festgelegt with
  | none =>
    have := ohne_festlegung_ort (k := ⟨q, o, .inland, 0, []⟩) hp hf hm hinl hko
    simpa [ort_massgeblich, hf] using this.2.2
  | some l =>
    have hmf := (merkmale_some hm).2.2.2.2.2.2.1
    rw [hf, Option.map_some] at hmf
    unfold kern_ort at hko
    rw [hmf] at hko
    simp only [Prod.mk.injEq] at hko
    simp [ort_massgeblich, hf, hko.2.1]

/-- Sitzt der Aussteller im Inland und ist `unternehmer` angegeben, bricht der Kern genau dann ab, wenn
`kern_ergebnis` abbricht, und aus demselben Grund. -/
theorem kern_fehler_iff {m : Merkmale} {u : Bool} {q : OrtQuelle} {o : Kategorie} {x : Regel}
    (hi : m.aussteller_inland = true) (hu : m.unternehmer = some u)
    (hko : kern_ort m u = (q, o, [x])) (a : Abbruch) :
    kern m = .error a ↔ kern_ergebnis m u o [.R1, .R2, x, .R9] = .error a := by
  unfold kern
  simp only [hi, Bool.not_true, hu, hko, List.cons_append, List.nil_append]
  rcases kern_ergebnis m u o [.R1, .R2, x, .R9] with b | ⟨e, rs⟩ <;> simp

theorem R4_aussteller_im_ausland_bricht_ab : Aussage.R4_aussteller_im_ausland_bricht_ab := by
  intro g d m hm
  have hi := (merkmale_some hm).2.2.2.2.2.1
  constructor
  · intro h
    rcases kern_fehler h with ⟨hf, -⟩ | ⟨-, -, ha⟩ | ⟨-, u, -, _, _, x, -, he⟩
    · rw [hi] at hf
      simpa using hf
    · cases ha
    · rcases (kern_ergebnis_fehler he).2 with ⟨-, ha⟩ | ⟨-, -, -, ha⟩ | ⟨-, -, -, -, ha⟩ <;> cases ha
  · intro hne
    have : m.aussteller_inland = false := by simpa [hi] using hne
    unfold kern
    simp [this]

theorem R19_abbruch_genau_wenn_unternehmer_fehlt : Aussage.R19_abbruch_genau_wenn_unternehmer_fehlt := by
  intro g d m hm hinl
  obtain ⟨-, hu, -, -, -, hi, -⟩ := merkmale_some hm
  rw [hinl] at hi
  simp only [beq_self_eq_true] at hi
  constructor
  · rintro ⟨gr, h⟩
    rcases kern_fehler h with ⟨hf, -⟩ | ⟨-, hn, -⟩ | ⟨-, u, -, _, _, x, -, he⟩
    · rw [hi] at hf
      cases hf
    · rw [← hu, hn]
    · rcases (kern_ergebnis_fehler he).2 with ⟨-, ha⟩ | ⟨-, -, -, ha⟩ | ⟨-, -, -, -, ha⟩ <;> cases ha
  · intro hn
    refine ⟨.unternehmer_fehlt, ?_⟩
    unfold kern
    simp [hi, hu, hn]

theorem R18_abbruch_genau_bei_privatperson_in_der_eu :
    Aussage.R18_abbruch_genau_bei_privatperson_in_der_eu := by
  intro g d s m hp hm hinl
  obtain ⟨-, hmu, -, -, -, hi, -⟩ := merkmale_some hm
  rw [hinl] at hi
  simp only [beq_self_eq_true] at hi
  cases hdu : d.unternehmer with
  | none =>
    have h19 : kern m = .error ⟨.R19, .unternehmer_fehlt⟩ := by
      unfold kern
      simp [hi, hmu, hdu]
    simp [h19]
  | some u =>
    rw [hdu] at hmu
    obtain ⟨x, hx, -⟩ := kern_ort_eine_regel m u
    rcases hko : kern_ort m u with ⟨q, o, r⟩
    rw [hko] at hx
    simp only at hx
    subst hx
    rw [kern_fehler_iff hi hmu hko, ← kategorie_kern_ort hp hm hinl hdu hko]
    unfold kern_ergebnis
    cases o <;> cases u <;> cases m.kleinunternehmer <;> cases m.kunde_ustid <;>
      cases m.aussteller_ustid <;> simp

theorem R29_abbruch_genau_bei_fehlender_ustid : Aussage.R29_abbruch_genau_bei_fehlender_ustid := by
  intro g d s m hp hm hinl hdu
  obtain ⟨-, hmu, hc, hk, ha, hi, -⟩ := merkmale_some hm
  rw [hinl] at hi
  simp only [beq_self_eq_true] at hi
  rw [hdu] at hmu
  have hsu := hp.annahme_R3_fuer_unternehmen hdu
  have hkl := hp.annahme_R13_grenzen
  obtain ⟨x, hx, -⟩ := kern_ort_eine_regel m true
  rcases hko : kern_ort m true with ⟨q, o, r⟩
  rw [hko] at hx
  simp only at hx
  subst hx
  simp only [kern_fehler_iff hi hmu hko, ← kategorie_kern_ort hp hm hinl hdu hko, ustids_pflicht,
    empfaenger_schuldet, hsu, hkl, ← hk, ← hc, ← ha]
  unfold kern_ergebnis
  cases o <;> cases m.kleinunternehmer <;> cases m.kunde_ustid <;> cases m.aussteller_ustid <;> simp

end Rechnung
