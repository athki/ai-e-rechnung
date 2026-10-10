/-
Erfüllbarkeit: zu jeder Aussage Beispiele, in denen ihre Voraussetzungen zugleich gelten (und bei
„genau dann“ beide Seiten vorkommen). Was gefordert ist, leitet `erfuellbar` aus der Aussage ab
(Erfuellbarkeit.lean); hier stehen nur die Beispiele.

Alle Beispiele spielen in derselben kleinen Welt mit drei Ländern: Deutschland (Inland), Frankreich
(anderer EU-Staat) und den USA (Drittland). Der Aussteller sitzt, wo nicht anders gesagt, in
Deutschland, ist regelbesteuert und hat eine USt-IdNr.; der Kunde ist ein französisches Unternehmen
mit USt-IdNr., die Leistung eine Beratung.
-/
import Rechnung.Erfuellbarkeit

namespace Rechnung.Beispiel

inductive Land | de | fr | us
  deriving DecidableEq, Repr

/-- Die Beispielwelt. -/
abbrev welt : Gebiete where
  Land := Land
  kategorie
    | .de => .inland
    | .fr => .eu
    | .us => .drittland
  inland := .de
  inland_eindeutig := by intro l; cases l <;> decide

/-- Ein Sachverhalt, der zu den Daten `d` passt: Unternehmer, wenn die Daten es sagen, sonst `u`. -/
def sachverhalt {g : Gebiete} (d : Daten g) (u : Bool) : Sachverhalt g where
  empfaenger_unternehmer := d.unternehmer.getD u
  empfaenger_sitz := d.kunde_land
  einordnung := d.einordnung
  erbringung := match d.ort with
    | some (.land l) => .vor_ort l
    | _ => .virtuell
  aussteller_sitz := d.aussteller_land
  aussteller_klein := d.kleinunternehmer

theorem passt {g : Gebiete} (d : Daten g) (u : Bool) : Passt g d (sachverhalt d u) where
  annahme_R3_R6_sitz := rfl
  annahme_R3_fuer_unternehmen := by intro h; simp [sachverhalt, h]
  annahme_R3_privat := by intro h; simp [sachverhalt, h]
  annahme_R4_sitz := rfl
  annahme_R5_R7_einordnung := rfl
  annahme_R5_ort := by intro l h; simp [sachverhalt, h]
  annahme_R6_virtuell := by intro h; simp [sachverhalt, h]
  annahme_R13_grenzen := rfl

/-- Aussteller in Deutschland, regelbesteuert; Kunde französisches Unternehmen mit USt-IdNr.;
Beratung. -/
def basis : Daten welt where
  kunde_land := .fr
  unternehmer := some true
  kunde_ustid := true
  einordnung := .beratung
  ort := none
  kleinunternehmer := false
  aussteller_land := .de
  aussteller_ustid := true
  festgelegt := none

/-- Kunde in Deutschland. -/
def inland : Daten welt := { basis with kunde_land := .de }
/-- Kunde in den USA. -/
def drittland : Daten welt := { basis with kunde_land := .us, kunde_ustid := false }
/-- Aussteller in Frankreich. -/
def aussteller_ausland : Daten welt := { basis with aussteller_land := .fr }
/-- Kleinunternehmer ohne USt-IdNr., Kunde in Deutschland. -/
def klein : Daten welt := { inland with kleinunternehmer := true, aussteller_ustid := false }
/-- Privatperson in Deutschland. -/
def privat : Daten welt := { inland with unternehmer := some false, kunde_ustid := false }

/-- Merkmale zu `basis`. -/
def mbasis : Merkmale where
  kunde := .eu
  unternehmer := some true
  kunde_ustid := true
  leistung := .katalog
  kleinunternehmer := false
  aussteller_ustid := true
  aussteller_inland := true
  festgelegt := none

def minland : Merkmale := { mbasis with kunde := .inland }
def mdrittland : Merkmale := { mbasis with kunde := .drittland }
def mklein : Merkmale := { minland with kleinunternehmer := true, aussteller_ustid := false }

/-! ## Die Beispiele, in der Reihenfolge von Aussagen.lean -/

erfuellbar R2_steuerbar_genau_im_inland :=
  ⟨⟨welt, .de, rfl⟩, ⟨welt, .fr, by decide⟩⟩

erfuellbar R3_unternehmer_sitz_des_kunden :=
  ⟨welt, basis, sachverhalt basis true, _, _, passt _ _, rfl, rfl, rfl, rfl⟩

erfuellbar R4_aussteller_im_ausland_bricht_ab :=
  ⟨⟨welt, aussteller_ausland, _, rfl, rfl⟩, ⟨welt, basis, _, rfl, by intro h; cases h⟩⟩

erfuellbar R4_grundregel_sitz_des_ausstellers :=
  let d := { privat with einordnung := .sonstige }
  ⟨welt, d, sachverhalt d false, _, _, passt _ _, rfl, rfl, rfl, rfl, rfl⟩

erfuellbar R5_taetigkeit_ort_der_erbringung :=
  let d := { privat with einordnung := .kulturell, ort := some (.land .us) }
  ⟨welt, d, sachverhalt d false, _, _, .us, passt _ _, rfl, rfl, rfl, rfl, rfl, rfl⟩

erfuellbar R6_virtuell_wohnsitz :=
  let d := { privat with kunde_land := .us, einordnung := .kulturell, ort := some .online }
  ⟨welt, d, sachverhalt d false, _, _, passt _ _, rfl, rfl, rfl, rfl, rfl, rfl⟩

erfuellbar R7_katalog_drittland_wohnsitz :=
  let d := { privat with kunde_land := .us }
  ⟨welt, d, sachverhalt d false, _, _, passt _ _, rfl, rfl, rfl, rfl, rfl, rfl⟩

erfuellbar R8_katalog_sonst_grundregel :=
  ⟨welt, privat, sachverhalt privat false, _, _, passt _ _, rfl, rfl, rfl, rfl, rfl, by decide⟩

erfuellbar R10_satz_je_position :=
  ⟨welt, inland, sachverhalt inland true, _, _, .de, true, passt _ _, rfl, rfl, rfl⟩

erfuellbar R11_reverse_charge_genau_wenn_empfaenger_schuldet :=
  ⟨⟨welt, basis, sachverhalt basis true, _, _, .fr, passt _ _, rfl, rfl, rfl, rfl⟩,
   ⟨welt, inland, sachverhalt inland true, _, _, .de, passt _ _, rfl, rfl, rfl, by decide⟩⟩

erfuellbar R12_genau_bei_null_prozent_regelbesteuert :=
  ⟨⟨mdrittland, _, rfl, by decide⟩, ⟨minland, _, rfl, by decide⟩⟩

erfuellbar R13_kleinunternehmer_genau_wenn_steuerfrei :=
  ⟨⟨welt, klein, sachverhalt klein true, _, _, .de, passt _ _, rfl, rfl, rfl, rfl⟩,
   ⟨welt, inland, sachverhalt inland true, _, _, .de, passt _ _, rfl, rfl, rfl, by decide⟩⟩

erfuellbar R14_kleinunternehmer_nie_steuer :=
  ⟨⟨mklein, _, rfl, by decide⟩, ⟨minland, _, rfl, by decide⟩, ⟨mklein, _, rfl, rfl⟩,
   ⟨mklein, _, false, 0, rfl, rfl, rfl⟩⟩

erfuellbar R15_kleinunternehmer_eu_ohne_ustids :=
  ⟨⟨{ mklein with kunde := .eu }, _, rfl, rfl, rfl⟩,
   ⟨{ mklein with aussteller_inland := false }, _, rfl, rfl⟩⟩

erfuellbar R16_hinweis_genau_bei_kleinunternehmer :=
  ⟨⟨mklein, _, rfl, by decide⟩, ⟨minland, _, rfl, by decide⟩⟩

erfuellbar R17_kleinunternehmer_drittland :=
  ⟨{ mklein with kunde := .drittland }, _, rfl, rfl, rfl⟩

erfuellbar R18_abbruch_genau_bei_privatperson_in_der_eu :=
  let d := { privat with einordnung := .kulturell, ort := some (.land .fr) }
  ⟨⟨welt, d, sachverhalt d false, _, passt _ _, rfl, rfl, rfl⟩,
   ⟨welt, basis, sachverhalt basis true, _, passt _ _, rfl, rfl, by intro h; cases h⟩⟩

erfuellbar R19_abbruch_genau_wenn_unternehmer_fehlt :=
  ⟨⟨welt, { basis with unternehmer := none }, _, rfl, rfl, _, rfl⟩,
   ⟨welt, basis, _, rfl, rfl, by rintro ⟨_, h⟩; cases h⟩⟩

erfuellbar R28_angabe_genau_bei_reverse_charge :=
  ⟨⟨mbasis, _, rfl, by decide⟩, ⟨minland, _, rfl, by decide⟩⟩

erfuellbar R29_abbruch_genau_bei_fehlender_ustid :=
  let d := { basis with kunde_ustid := false }
  ⟨⟨welt, d, sachverhalt d true, _, passt _ _, rfl, rfl, rfl, _, rfl⟩,
   ⟨welt, basis, sachverhalt basis true, _, passt _ _, rfl, rfl, rfl, by rintro ⟨_, h⟩; cases h⟩⟩

erfuellbar R30_frist_genau_bei_reverse_charge :=
  ⟨⟨mbasis, _, rfl, by decide⟩, ⟨minland, _, rfl, by decide⟩⟩

erfuellbar R31_hinweis_nennt_die_richtige_vorschrift :=
  ⟨welt, drittland, sachverhalt drittland true, _, _, passt _ _, rfl, rfl, rfl, rfl⟩

erfuellbar R37_festlegung_nur_des_orts :=
  let d := { basis with festgelegt := some .us }
  ⟨welt, d, sachverhalt d true, _, _, .us, passt _ _, rfl, rfl, rfl⟩

erfuellbar Werkzeug_nie_anders :=
  ⟨welt, basis, sachverhalt basis true, _, _, passt _ _, rfl, rfl, rfl⟩

erfuellbar Ergebnis_fasst_Folgen_zusammen :=
  ⟨welt, basis, sachverhalt basis true, _, _, passt _ _, rfl, rfl⟩

erfuellbar Abbruch_nur_aus_genannten_gruenden :=
  ⟨{ mbasis with aussteller_inland := false }, _, rfl⟩

end Rechnung.Beispiel
