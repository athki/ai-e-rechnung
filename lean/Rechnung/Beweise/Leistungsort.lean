/-
Beweise der Aussagen zum Leistungsort ohne Festlegung (R3–R8) und zum Hinweis bei Leistungsort im
Drittland (R31). Alle stützen sich auf `ohne_festlegung` (Hilfssaetze.lean): Das Werkzeug nennt den Ort
nach § 3a, und seine Ortsregel gehört zur Vorschrift, die greift. Je Aussage bleibt auszurechnen,
welcher Ort und welche Vorschrift das unter ihren Voraussetzungen sind.
-/
import Rechnung.Beweise.Hilfssaetze

namespace Rechnung

variable {g : Gebiete}

/-- Ohne Festlegung steht die Ortsregel `x` im Trace, sie gehört zur Vorschrift, die nach § 3a greift,
und sie ist die einzige Regel im Trace mit einer Vorschrift aus § 3a. -/
theorem ortsregel_im_trace {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {k : KernErgebnis}
    (hp : Passt g d s) (hf : d.festgelegt = none) (hm : merkmale d = some m) (h : kern m = .ok k) :
    ∃ x, x ∈ k.regeln ∧ x.vorschrift = some (vorschrift s) ∧
      k.regeln.filterMap Regel.vorschrift = [vorschrift s] ∧
      ort_land d k = some (leistungsort s) ∧ k.ort_quelle ≠ .festgelegt := by
  obtain ⟨x, hko, hv, hl, -⟩ := ohne_festlegung hp hf hm h
  obtain ⟨u, x', rest, hu, hko', -, hr, hrest⟩ := kern_trace h
  rw [(merkmale_some hm).2.1, unternehmer_passt hp hm h] at hu
  cases hu
  rw [hko] at hko'
  simp only [Prod.mk.injEq, List.cons.injEq, and_true, true_and] at hko'
  subst hko'
  have hmf := (merkmale_some hm).2.2.2.2.2.2.1
  rw [hf, Option.map_none] at hmf
  refine ⟨x, by simp [hr], hv, ?_, hl, ?_⟩
  · rw [hr]
    simp only [List.cons_append, List.nil_append, List.filterMap_cons, hv]
    simp [Regel.vorschrift, hrest]
  · have hq : (kern_ort m s.empfaenger_unternehmer).1 = k.ort_quelle := by rw [hko]
    rw [← hq]
    unfold kern_ort
    rw [hmf]
    split <;> (try split) <;> (try split) <;> simp_all

theorem R3_unternehmer_sitz_des_kunden : Aussage.R3_unternehmer_sitz_des_kunden := by
  intro g d s m k hp hf hm h hu
  obtain ⟨x, hx, hv, -, hl, -⟩ := ortsregel_im_trace hp hf hm h
  simp only [vorschrift, abs3_nr3_satz1, abs3_nr3_satz2, abs4, abs2, hu] at hv
  cases x <;> simp [Regel.vorschrift] at hv
  simp [hl, hx, leistungsort, abs3_nr3_satz1, abs3_nr3_satz2, abs4, abs2, hu]

theorem R4_grundregel_sitz_des_ausstellers : Aussage.R4_grundregel_sitz_des_ausstellers := by
  intro g d s m k hp hf hm h hu hg
  obtain ⟨-, -, -, -, hl, -⟩ := ortsregel_im_trace hp hf hm h
  simp [hl, leistungsort, abs3_nr3_satz1, abs3_nr3_satz2, abs4, abs2, abs1, hu, hg]

theorem R5_taetigkeit_ort_der_erbringung : Aussage.R5_taetigkeit_ort_der_erbringung := by
  intro g d s m k l hp hf hm h hu hg he
  obtain ⟨x, hx, hv, -, hl, -⟩ := ortsregel_im_trace hp hf hm h
  simp only [vorschrift, abs3_nr3_satz1, hu, hg, he] at hv
  cases x <;> simp [Regel.vorschrift] at hv
  simp [hl, hx, leistungsort, abs3_nr3_satz1, hu, hg, he]

theorem R6_virtuell_wohnsitz : Aussage.R6_virtuell_wohnsitz := by
  intro g d s m k hp hf hm h hu hg he
  obtain ⟨x, hx, hv, -, hl, -⟩ := ortsregel_im_trace hp hf hm h
  simp only [vorschrift, abs3_nr3_satz1, abs3_nr3_satz2, hu, hg, he] at hv
  cases x <;> simp [Regel.vorschrift] at hv
  simp [hl, hx, leistungsort, abs3_nr3_satz1, abs3_nr3_satz2, hu, hg, he]

theorem R7_katalog_drittland_wohnsitz : Aussage.R7_katalog_drittland_wohnsitz := by
  intro g d s m k hp hf hm h hu hg hd
  obtain ⟨x, hx, hv, -, hl, -⟩ := ortsregel_im_trace hp hf hm h
  simp only [vorschrift, abs3_nr3_satz1, abs3_nr3_satz2, abs4, hu, hg, hd] at hv
  cases x <;> simp [Regel.vorschrift] at hv
  simp [hl, hx, leistungsort, abs3_nr3_satz1, abs3_nr3_satz2, abs4, hu, hg, hd]

theorem R8_katalog_sonst_grundregel : Aussage.R8_katalog_sonst_grundregel := by
  intro g d s m k hp hf hm h hu hg hd
  obtain ⟨-, -, -, -, hl, -⟩ := ortsregel_im_trace hp hf hm h
  simp [hl, leistungsort, abs3_nr3_satz1, abs3_nr3_satz2, abs4, abs2, abs1, hu, hg, hd]

/-- Ist das Ergebnis `nicht_steuerbar`, steht R31 im Trace. -/
theorem R31_im_trace {m : Merkmale} {k : KernErgebnis} (h : kern m = .ok k)
    (he : k.ergebnis = .nicht_steuerbar) : Regel.R31 ∈ k.regeln := by
  obtain ⟨q, o, e, s, r⟩ := k
  simp only at he
  kern_faelle h <;> simp_all

theorem R31_hinweis_nennt_die_richtige_vorschrift : Aussage.R31_hinweis_nennt_die_richtige_vorschrift := by
  intro g d s m k hp hf hm h he
  obtain ⟨-, -, -, hfm, -, hq⟩ := ortsregel_im_trace hp hf hm h
  refine ⟨R31_im_trace h he, ?_, ?_⟩
  · simp [fundstelle, hq, hfm]
  · simp [unternehmer_fuer_hinweis, (merkmale_some hm).2.1, unternehmer_passt hp hm h]

end Rechnung
