/-
Beweise der Aussagen über die Folgen: Satz je Position (R10), Steuerschuldnerschaft (R11), § 19 (R13),
Festlegung (R37), und die beiden Aussagen über das Ganze. Kern ist `folgen_stimmen`: Für den Ort, den
das Werkzeug nennt, stimmen alle Folgen nach dem Gesetz mit seiner Entscheidung überein.
-/
import Rechnung.Beweise.Leistungsort

namespace Rechnung

variable {g : Gebiete}

/-- Für den Ort `l`, den das Werkzeug nennt, stimmen die Folgen nach dem Gesetz (`folgen`) mit Ergebnis,
Satz und Trace überein. Fallunterscheidung wie im Kern; die Kategorie von `l` ist die, mit der der
Kern gerechnet hat (`ort_land_kategorie`). -/
theorem folgen_stimmen {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {k : KernErgebnis}
    {l : g.Land} (hp : Passt g d s) (hm : merkmale d = some m) (h : kern m = .ok k)
    (hl : ort_land d k = some l) : FolgenStimmen g d s l k := by
  obtain ⟨-, hkat⟩ := ort_land_kategorie hp hm h hl
  have hus := unternehmer_passt hp hm h
  obtain ⟨-, hmu, hc, hkl, ha, -⟩ := merkmale_some hm
  have hklein := hp.annahme_R13_grenzen
  obtain ⟨q, o, e, sa, r⟩ := k
  simp only at hkat
  replace hkat := hkat.symm
  unfold FolgenStimmen folgen
  kern_faelle h <;>
    simp_all [steuerbar, steuerfrei, steuersatz, empfaenger_schuldet, angabe_steuerschuldnerschaft,
      ustids_pflicht, hinweis_kleinunternehmer]

theorem R10_satz_je_position : Aussage.R10_satz_je_position := by
  intro g d s m k l e hp hm h hl
  obtain ⟨-, hkat⟩ := ort_land_kategorie hp hm h hl
  obtain ⟨-, -, -, hkl, -⟩ := merkmale_some hm
  have hklein := hp.annahme_R13_grenzen
  obtain ⟨q, o, er, sa, r⟩ := k
  simp only at hkat
  replace hkat := hkat.symm
  kern_faelle h <;> cases e <;>
    simp_all [steuersatz, steuerbar, steuerfrei, satz_position]

theorem R11_reverse_charge_genau_wenn_empfaenger_schuldet :
    Aussage.R11_reverse_charge_genau_wenn_empfaenger_schuldet := by
  intro g d s m k l hp hm h hl
  have := folgen_stimmen hp hm h hl
  unfold FolgenStimmen at this
  exact this.2.2.1

theorem R13_kleinunternehmer_genau_wenn_steuerfrei : Aussage.R13_kleinunternehmer_genau_wenn_steuerfrei := by
  intro g d s m k l hp hm h hl
  have := folgen_stimmen hp hm h hl
  unfold FolgenStimmen at this
  exact this.2.1

theorem R37_festlegung_nur_des_orts : Aussage.R37_festlegung_nur_des_orts := by
  intro g d s m k l hp hf hm h
  obtain ⟨hl, hq, -, hr⟩ := mit_festlegung hf hm h
  refine ⟨hl, hq, ?_, folgen_stimmen hp hm h hl⟩
  rw [hr]
  simp

theorem Werkzeug_nie_anders : Aussage.Werkzeug_nie_anders := by
  intro g d s m k hp hf hm h
  obtain ⟨-, -, -, hfm, hl, -⟩ := ortsregel_im_trace hp hf hm h
  obtain ⟨-, -, -, -, ho⟩ := ohne_festlegung hp hf hm h
  exact ⟨hl, ho, by simp [hfm], folgen_stimmen hp hm h hl⟩

theorem Ergebnis_fasst_Folgen_zusammen : Aussage.Ergebnis_fasst_Folgen_zusammen := by
  intro g d s m k hp hm h
  exact folgen_stimmen hp hm h (ort_massgeblich_ok hp hm h).1

end Rechnung
