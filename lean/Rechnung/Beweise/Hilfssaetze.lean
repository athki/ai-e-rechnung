/-
Hilfssätze zwischen Daten, Sachverhalt und Kern; die Aussagen in Abbruch.lean, Leistungsort.lean und
Folgen.lean stützen sich darauf:

- `merkmale_some`: was `merkmale` aus den Daten macht.
- `kern_trace`: Im Trace steht genau eine Ortsregel, an dritter Stelle; alle Regeln danach haben keine
  Vorschrift aus § 3a.
- `unternehmer_passt`: Entscheidet der Kern, ist der Unternehmerstatus der Daten der wirkliche.
- `ohne_festlegung`: Ohne Festlegung nennt das Werkzeug den Ort des Gesetzes, mit der Kategorie, mit
  der der Kern gerechnet hat, und seine Ortsregel gehört zur Vorschrift, die nach § 3a greift.
- `mit_festlegung`: Mit Festlegung nennt es den festgelegten Ort.
- `ort_massgeblich_ok`: beides zusammen, für den maßgeblichen Ort.
-/
import Rechnung.Beweise.Kern

namespace Rechnung

variable {g : Gebiete}

/-- Was `merkmale` aus den Daten macht: jedes Feld übernommen bzw. als Kategorie, und die Leistung aus
Gruppe und Ort. -/
theorem merkmale_some {d : Daten g} {m : Merkmale} (h : merkmale d = some m) :
    m.kunde = g.kategorie d.kunde_land ∧ m.unternehmer = d.unternehmer ∧
    m.kunde_ustid = d.kunde_ustid ∧ m.kleinunternehmer = d.kleinunternehmer ∧
    m.aussteller_ustid = d.aussteller_ustid ∧
    m.aussteller_inland = (g.kategorie d.aussteller_land == .inland) ∧
    m.festgelegt = d.festgelegt.map g.kategorie ∧
    ((d.einordnung.gruppe = .taetigkeit ∧ d.ort = some .online ∧ m.leistung = .taetigkeit .online) ∨
     (∃ l, d.einordnung.gruppe = .taetigkeit ∧ d.ort = some (.land l) ∧
       m.leistung = .taetigkeit (.land (g.kategorie l))) ∨
     (d.einordnung.gruppe = .katalog ∧ d.ort = none ∧ m.leistung = .katalog) ∨
     (d.einordnung.gruppe = .grundregel ∧ d.ort = none ∧ m.leistung = .grundregel)) := by
  unfold merkmale at h
  rcases hg : d.einordnung.gruppe <;> rcases ho : d.ort with _ | (l | _) <;>
    simp [hg, ho] at h <;> subst h <;> simp

/-- Im Trace steht genau eine Ortsregel `x`, an dritter Stelle; keine Regel danach hat eine Vorschrift
aus § 3a. -/
theorem kern_trace {m : Merkmale} {k : KernErgebnis} (h : kern m = .ok k) :
    ∃ u x rest, m.unternehmer = some u ∧ kern_ort m u = (k.ort_quelle, k.ort, [x]) ∧
      x ∈ ortsregeln ∧ k.regeln = [.R1, .R2, x, .R9] ++ rest ∧
      rest.filterMap Regel.vorschrift = [] := by
  obtain ⟨-, u, hu, x, hko, hx, rs, he, hs, hr⟩ := kern_ok h
  refine ⟨u, x, k.regeln.drop 4, hu, hko, hx, ?_⟩
  rcases kern_ergebnis_ok he with
    ⟨_, _, he', rfl⟩ | ⟨_, _, he', rfl⟩ | ⟨_, _, _, he', rfl⟩ |
    ⟨_, _, _, _, _, he', rfl⟩ | ⟨_, _, he', rfl⟩ | ⟨_, _, he', rfl⟩ <;>
    simp only [he'] at hs <;> simp [hr, hs] <;> (try split) <;> simp [Regel.vorschrift]

/-- Entscheidet der Kern, steht in den Daten der wirkliche Unternehmerstatus des Empfängers. -/
theorem unternehmer_passt {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {k : KernErgebnis}
    (hp : Passt g d s) (hm : merkmale d = some m) (h : kern m = .ok k) :
    d.unternehmer = some s.empfaenger_unternehmer := by
  obtain ⟨-, u, hu, -⟩ := kern_ok h
  rw [(merkmale_some hm).2.1] at hu
  cases u
  · rw [hu, hp.annahme_R3_privat hu]
  · rw [hu, hp.annahme_R3_fuer_unternehmen hu]

/-- Entscheidet der Kern, sitzt der Aussteller im Inland. -/
theorem aussteller_im_inland {d : Daten g} {m : Merkmale} {k : KernErgebnis}
    (hm : merkmale d = some m) (h : kern m = .ok k) :
    g.kategorie d.aussteller_land = .inland := by
  have := (kern_ok h).1
  rw [(merkmale_some hm).2.2.2.2.2.1] at this
  simpa using this

/-- Ohne Festlegung, für jede Ausgabe von `kern_ort` (auch wenn der Kern danach abbricht): Das Werkzeug
nennt den Ort des Gesetzes, rechnet mit seiner Kategorie, und seine Ortsregel gehört zur Vorschrift,
die nach § 3a greift. -/
theorem ohne_festlegung_ort {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {k : KernErgebnis}
    {x : Regel} (hp : Passt g d s) (hf : d.festgelegt = none) (hm : merkmale d = some m)
    (hinl : g.kategorie d.aussteller_land = .inland)
    (hko : kern_ort m s.empfaenger_unternehmer = (k.ort_quelle, k.ort, [x])) :
    x.vorschrift = some (vorschrift s) ∧
      ort_land d k = some (leistungsort s) ∧ k.ort = g.kategorie (leistungsort s) := by
  obtain ⟨hk, -, -, -, -, -, hmf, hl⟩ := merkmale_some hm
  have hsitz := hp.annahme_R3_R6_sitz
  have hauss := hp.annahme_R4_sitz
  have hein := hp.annahme_R5_R7_einordnung
  simp only [hf, Option.map_none] at hmf
  unfold kern_ort at hko
  rw [hmf] at hko
  cases hsu : s.empfaenger_unternehmer
  · rw [hsu] at hko
    rcases hl with ⟨hg, ho, hle⟩ | ⟨l, hg, ho, hle⟩ | ⟨hg, ho, hle⟩ | ⟨hg, ho, hle⟩ <;>
      rw [hle] at hko
    · -- Tätigkeit, online: § 3a Abs. 3 Nr. 3 Satz 2
      have herb := hp.annahme_R6_virtuell ho
      simp only [Prod.mk.injEq] at hko
      obtain ⟨hq, ho', hx⟩ := hko
      simp only [List.cons.injEq, and_true] at hx
      subst hx
      simp [ort_land, ← hq, ← ho', hk, Regel.vorschrift, vorschrift, leistungsort, abs2,
        abs3_nr3_satz1, abs3_nr3_satz2, abs4, hsu, hein, hg, herb, hsitz]
    · -- Tätigkeit vor Ort: § 3a Abs. 3 Nr. 3 Satz 1
      have herb := hp.annahme_R5_ort l ho
      simp only [Prod.mk.injEq] at hko
      obtain ⟨hq, ho', hx⟩ := hko
      simp only [List.cons.injEq, and_true] at hx
      subst hx
      simp [ort_land, ← hq, ← ho', ho, Regel.vorschrift, vorschrift, leistungsort, abs2,
        abs3_nr3_satz1, abs3_nr3_satz2, abs4, hsu, hein, hg, herb]
    · -- Katalog: § 3a Abs. 4 im Drittland, sonst Abs. 1
      rw [hk] at hko
      by_cases hd : g.kategorie d.kunde_land = .drittland
      · simp only [hd, ↓reduceIte, Prod.mk.injEq] at hko
        obtain ⟨hq, ho', hx⟩ := hko
        simp only [List.cons.injEq, and_true] at hx
        subst hx
        simp [ort_land, ← hq, ← ho', hd, Regel.vorschrift, vorschrift, leistungsort, abs2,
          abs3_nr3_satz1, abs3_nr3_satz2, abs4, hsu, hein, hg, hsitz]
      · simp only [hd, ↓reduceIte, Prod.mk.injEq] at hko
        obtain ⟨hq, ho', hx⟩ := hko
        simp only [List.cons.injEq, and_true] at hx
        subst hx
        simp [ort_land, ← hq, ← ho', hd, hinl, Regel.vorschrift, vorschrift, leistungsort, abs1, abs2,
          abs3_nr3_satz1, abs3_nr3_satz2, abs4, hsu, hein, hg, hsitz, hauss]
    · -- Grundregel: § 3a Abs. 1
      simp only [Prod.mk.injEq] at hko
      obtain ⟨hq, ho', hx⟩ := hko
      simp only [List.cons.injEq, and_true] at hx
      subst hx
      simp [ort_land, ← hq, ← ho', hinl, Regel.vorschrift, vorschrift, leistungsort, abs1, abs2,
        abs3_nr3_satz1, abs3_nr3_satz2, abs4, hsu, hein, hg, hauss]
  · -- Unternehmer: § 3a Abs. 2
    rw [hsu] at hko
    simp only [Prod.mk.injEq] at hko
    obtain ⟨hq, ho', hx⟩ := hko
    simp only [List.cons.injEq, and_true] at hx
    subst hx
    simp [ort_land, ← hq, ← ho', hk, Regel.vorschrift, vorschrift, leistungsort, abs2,
      abs3_nr3_satz1, abs3_nr3_satz2, abs4, hsu, hsitz]

/-- Ohne Festlegung: Das Werkzeug nennt den Ort des Gesetzes, rechnet mit seiner Kategorie, und seine
Ortsregel gehört zur Vorschrift, die nach § 3a greift. -/
theorem ohne_festlegung {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {k : KernErgebnis}
    (hp : Passt g d s) (hf : d.festgelegt = none) (hm : merkmale d = some m) (h : kern m = .ok k) :
    ∃ x, kern_ort m s.empfaenger_unternehmer = (k.ort_quelle, k.ort, [x]) ∧
      x.vorschrift = some (vorschrift s) ∧
      ort_land d k = some (leistungsort s) ∧ k.ort = g.kategorie (leistungsort s) := by
  obtain ⟨u, x, -, hu, hko, -⟩ := kern_trace h
  rw [(merkmale_some hm).2.1, unternehmer_passt hp hm h] at hu
  cases hu
  exact ⟨x, hko, ohne_festlegung_ort hp hf hm (aussteller_im_inland hm h) hko⟩

/-- Mit Festlegung: Das Werkzeug nennt den festgelegten Ort und rechnet mit seiner Kategorie; die
Ortsregel ist R37. -/
theorem mit_festlegung {d : Daten g} {m : Merkmale} {k : KernErgebnis} {l : g.Land}
    (hf : d.festgelegt = some l) (hm : merkmale d = some m) (h : kern m = .ok k) :
    ort_land d k = some l ∧ k.ort_quelle = .festgelegt ∧ k.ort = g.kategorie l ∧
      k.regeln = [.R1, .R2, .R37, .R9] ++ (k.regeln.drop 4) := by
  obtain ⟨-, -, -, -, -, -, hmf, -⟩ := merkmale_some hm
  obtain ⟨u, x, rest, -, hko, -, hr, -⟩ := kern_trace h
  rw [hf, Option.map_some] at hmf
  unfold kern_ort at hko
  rw [hmf] at hko
  simp only [Prod.mk.injEq, List.cons.injEq, and_true] at hko
  obtain ⟨hq, ho, rfl⟩ := hko
  simp [ort_land, ← hq, ← ho, hf, hr]

/-- Der maßgebliche Ort: Das Werkzeug nennt ihn und rechnet mit seiner Kategorie, mit und ohne
Festlegung. -/
theorem ort_massgeblich_ok {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {k : KernErgebnis}
    (hp : Passt g d s) (hm : merkmale d = some m) (h : kern m = .ok k) :
    ort_land d k = some (ort_massgeblich d s) ∧ k.ort = g.kategorie (ort_massgeblich d s) := by
  cases hf : d.festgelegt with
  | none =>
    obtain ⟨-, -, -, hl, ho⟩ := ohne_festlegung hp hf hm h
    simp [ort_massgeblich, hf, hl, ho]
  | some l =>
    obtain ⟨hl, -, ho, -⟩ := mit_festlegung hf hm h
    simp [ort_massgeblich, hf, hl, ho]

/-- Hilfssatz (b): Das Land, das das Werkzeug als Leistungsort nennt, hat die Kategorie, mit der der
Kern gerechnet hat. -/
theorem ort_land_kategorie {d : Daten g} {s : Sachverhalt g} {m : Merkmale} {k : KernErgebnis}
    {l : g.Land} (hp : Passt g d s) (hm : merkmale d = some m) (h : kern m = .ok k)
    (hl : ort_land d k = some l) :
    l = ort_massgeblich d s ∧ k.ort = g.kategorie l := by
  obtain ⟨hl', ho⟩ := ort_massgeblich_ok hp hm h
  rw [hl] at hl'
  cases hl'
  exact ⟨rfl, ho⟩

end Rechnung
