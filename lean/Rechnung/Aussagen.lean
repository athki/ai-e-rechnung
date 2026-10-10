/-
Die Aussagen: je Regel aus RULES.md (R2–R19, R28–R31, R37) mindestens eine, mit derselben ID, dazu die
Aussagen über das Ganze (eindeutig, nie anders, Abbruch nur aus genannten Gründen).

In Schritt 8.4 sind das nur formulierte Sätze (`def … : Prop`): Lean prüft, dass sie wohlgeformt sind,
nicht, dass sie stimmen. Bewiesen werden sie in 8.5 als Theoreme gleichen Namens im Namespace
`Rechnung` (`theorem R3_… : Aussage.R3_…`). `Pruefung.lean` meldet je Aussage, ob es dieses Theorem gibt.

Ohne eigene Aussage, weil der Typ sie schon trägt: R1 (jedes Land hat genau eine Kategorie,
Gebiete.lean) und R9 (eine Einordnung je Rechnung: `Daten` hat genau ein Feld `einordnung`).

Alle Regeln: Status Annahme – ungeprüft. Ein Steuerberater hat RULES.md nicht geprüft.
-/
import Rechnung.Bruecke
import Rechnung.Werkzeug.Satz

namespace Rechnung

variable {g : Gebiete}

/-! ## Hilfsbegriffe -/

/-- Der Leistungsort, nach dem sich die Folgen richten: der festgelegte (R37), sonst der aus § 3a. -/
def ort_massgeblich (d : Daten g) (s : Sachverhalt g) : g.Land :=
  d.festgelegt.getD (leistungsort s)

/-- Die Folgen nach dem Gesetz stimmen mit dem überein, was das Werkzeug für den Ort `l` entschieden
hat: Ergebnis, Satz, Pflichtangaben im Trace, und die USt-IdNrn. liegen vor, wo sie Pflicht sind. -/
def FolgenStimmen (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (l : g.Land) (k : KernErgebnis) : Prop :=
  let f := folgen g s.aussteller_klein s.empfaenger_unternehmer l
  (k.ergebnis = .inland ↔ f.steuerbar = true ∧ f.steuerfrei = false) ∧
  (k.ergebnis = .kleinunternehmer ↔ f.steuerfrei = true) ∧
  (k.ergebnis = .reverse_charge ↔ f.empfaenger_schuldet = true) ∧
  (k.ergebnis = .nicht_steuerbar ↔ g.kategorie l = .drittland) ∧
  (f.steuersatz = some k.satz ∨ (f.steuersatz = none ∧ k.satz = 0)) ∧
  (Regel.R28 ∈ k.regeln ↔ f.angabe_steuerschuldnerschaft = true) ∧
  (Regel.R29 ∈ k.regeln ↔ f.ustids_pflicht = true) ∧
  (Regel.R16 ∈ k.regeln ↔ f.hinweis_kleinunternehmer = true) ∧
  (f.ustids_pflicht = true → d.kunde_ustid = true ∧ d.aussteller_ustid = true)

namespace Aussage

/-! ## Gebiete und Steuerbarkeit -/

/-- **R2 – Steuerbar ist nur, was im Inland ausgeführt wird** (§ 1 Abs. 1 Nr. 1 UStG). -/
def R2_steuerbar_genau_im_inland : Prop :=
  ∀ (g : Gebiete) (l : g.Land), steuerbar g l = true ↔ l = g.inland

/-! ## Leistungsort (§ 3a UStG) -/

/-- **R3–R8 – Höchstens eine Vorschrift.** Für jeden Sachverhalt greift höchstens eine der Vorschriften
§ 3a Abs. 2, Abs. 3 Nr. 3 Satz 1, Satz 2 und Abs. 4; greift keine, gilt Abs. 1. Die Rangfolge in
`leistungsort` ändert im Geltungsbereich also nichts. -/
def R3_R8_eindeutig : Prop :=
  ∀ (g : Gebiete) (s : Sachverhalt g), (greifende s).length ≤ 1

/-- **R3 – Leistung an einen Unternehmer: Sitz des Empfängers** (§ 3a Abs. 2 Satz 1 UStG). Entscheidet
das Werkzeug ohne Festlegung, und ist der Kunde Unternehmer, liegt der Ort dort, wo er sein Unternehmen
betreibt, und R3 steht im Trace. -/
def R3_unternehmer_sitz_des_kunden : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    s.empfaenger_unternehmer = true →
    ort_land d k = some s.empfaenger_sitz ∧ Regel.R3 ∈ k.regeln

/-- **R4 – Aussteller außerhalb Deutschlands.** Das Werkzeug bricht genau dann nach R4 ab, wenn das Land
des Ausstellers nicht das Inland ist. Ohne `Passt`: Das prüft das Werkzeug selbst. -/
def R4_aussteller_im_ausland_bricht_ab : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (m : Merkmale), merkmale d = some m →
    (kern m = .error ⟨.R4, .aussteller_ausland⟩ ↔ g.kategorie d.aussteller_land ≠ .inland)

/-- **R4 – Grundregel bei Nichtunternehmern: Sitz des Ausstellers** (§ 3a Abs. 1 UStG). -/
def R4_grundregel_sitz_des_ausstellers : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    s.empfaenger_unternehmer = false → s.einordnung.gruppe = .grundregel →
    ort_land d k = some s.aussteller_sitz

/-- **R5 – Tätigkeitsleistung an Nichtunternehmer: Ort der Tätigkeit** (§ 3a Abs. 3 Nr. 3 Satz 1). -/
def R5_taetigkeit_ort_der_erbringung : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis) (l : g.Land),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    s.empfaenger_unternehmer = false → s.einordnung.gruppe = .taetigkeit → s.erbringung = .vor_ort l →
    ort_land d k = some l ∧ Regel.R5 ∈ k.regeln

/-- **R6 – Tätigkeitsleistung, virtuell: Wohnsitz des Empfängers** (§ 3a Abs. 3 Nr. 3 Satz 2). -/
def R6_virtuell_wohnsitz : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    s.empfaenger_unternehmer = false → s.einordnung.gruppe = .taetigkeit → s.erbringung = .virtuell →
    ort_land d k = some s.empfaenger_sitz ∧ Regel.R6 ∈ k.regeln

/-- **R7 – Katalogleistung an Nichtunternehmer im Drittland: Wohnsitz des Empfängers**
(§ 3a Abs. 4 UStG). -/
def R7_katalog_drittland_wohnsitz : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    s.empfaenger_unternehmer = false → s.einordnung.gruppe = .katalog →
    g.kategorie s.empfaenger_sitz = .drittland →
    ort_land d k = some s.empfaenger_sitz ∧ Regel.R7 ∈ k.regeln

/-- **R8 – Katalogleistung an Nichtunternehmer in der EU oder im Inland: Grundregel**
(§ 3a Abs. 4 Satz 1 nennt nur das Drittlandsgebiet; § 3a Abs. 1). -/
def R8_katalog_sonst_grundregel : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    s.empfaenger_unternehmer = false → s.einordnung.gruppe = .katalog →
    g.kategorie s.empfaenger_sitz ≠ .drittland →
    ort_land d k = some s.aussteller_sitz

/-! ## Steuersatz und Steuerschuldner -/

/-- **R10 – Steuersatz** (§ 12 Abs. 1 und 2 UStG). Der Satz einer Position ist der des Gesetzes für den
Leistungsort; `e` ist die Ermäßigung. Annahme R10: Wer `steuersatz: 7` angibt, ordnet die Position
richtig unter § 12 Abs. 2 ein – deshalb steht hier dasselbe `e` für Angabe und Tatsache. Wo das Gesetz
keinen deutschen Steuerbetrag kennt, bricht das Werkzeug bei `e` ab und setzt sonst 0. -/
def R10_satz_je_position : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis) (l : g.Land)
    (e : Bool),
    Passt g d s → merkmale d = some m → kern m = .ok k → ort_land d k = some l →
    (match steuersatz g s.aussteller_klein l e with
     | some n => satz_position k.satz d.kleinunternehmer e = .ok n
     | none => if e then ∃ a, satz_position k.satz d.kleinunternehmer e = .error a
               else satz_position k.satz d.kleinunternehmer e = .ok 0)

/-- **R11 – Steuerschuldnerschaft des Leistungsempfängers in der EU** (Art. 196 MwStSystRL).
Reverse Charge genau dann, wenn der Empfänger die Steuer im anderen Mitgliedstaat schuldet. -/
def R11_reverse_charge_genau_wenn_empfaenger_schuldet : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis) (l : g.Land),
    Passt g d s → merkmale d = some m → kern m = .ok k → ort_land d k = some l →
    (k.ergebnis = .reverse_charge ↔ empfaenger_schuldet g s.empfaenger_unternehmer l = true)

/-- **R12 – Kein deutscher Steuerausweis, wo keine deutsche Steuer geschuldet wird** (§ 14c UStG).
R12 steht genau dann im Trace, wenn ein regelbesteuerter Aussteller 0 % ausweist. -/
def R12_genau_bei_null_prozent_regelbesteuert : Prop :=
  ∀ (m : Merkmale) (k : KernErgebnis), kern m = .ok k →
    (Regel.R12 ∈ k.regeln ↔ m.kleinunternehmer = false ∧ k.satz = 0)

/-! ## Kleinunternehmer (§ 19 UStG) -/

/-- **R13 – Steuerfreiheit nur für Umsätze im Inland** (§ 19 Abs. 1 Satz 1 UStG). -/
def R13_kleinunternehmer_genau_wenn_steuerfrei : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis) (l : g.Land),
    Passt g d s → merkmale d = some m → kern m = .ok k → ort_land d k = some l →
    (k.ergebnis = .kleinunternehmer ↔ steuerfrei g s.aussteller_klein l = true)

/-- **R14 – Kleinunternehmer weist nie Umsatzsteuer aus** (§ 14c Abs. 2 UStG), auch nicht bei
Festlegung und auch nicht je Position. R14 steht genau beim Kleinunternehmer im Trace. -/
def R14_kleinunternehmer_nie_steuer : Prop :=
  ∀ (m : Merkmale) (k : KernErgebnis), kern m = .ok k →
    (Regel.R14 ∈ k.regeln ↔ m.kleinunternehmer = true) ∧
    (m.kleinunternehmer = true →
      k.satz = 0 ∧ ∀ (e : Bool) (n : Nat), satz_position k.satz true e = .ok n → n = 0)

/-- **R15 – Kleinunternehmer, Kunde ist Unternehmer in der EU** (§ 14a Abs. 1 Satz 1, § 19 Abs. 1
Satz 2 UStG). Die Angabe „Steuerschuldnerschaft des Leistungsempfängers“ bleibt (R28), die USt-IdNrn.
sind nicht Pflicht: kein R29 im Trace, kein Abbruch nach R29. Status: **unsicher**. -/
def R15_kleinunternehmer_eu_ohne_ustids : Prop :=
  (∀ (m : Merkmale) (k : KernErgebnis), kern m = .ok k → m.kleinunternehmer = true →
    k.ergebnis = .reverse_charge → Regel.R28 ∈ k.regeln ∧ Regel.R15 ∈ k.regeln ∧ Regel.R29 ∉ k.regeln) ∧
  (∀ (m : Merkmale) (a : Abbruch), kern m = .error a → m.kleinunternehmer = true → a.regel ≠ .R29)

/-- **R16 – Pflichttext des Kleinunternehmers** (§ 34a Nr. 5 UStDV): R16 im Trace genau beim Ergebnis
`kleinunternehmer`; dass das Gesetz den Hinweis genau dann verlangt, sagt `Ergebnis_fasst_Folgen_zusammen`. -/
def R16_hinweis_genau_bei_kleinunternehmer : Prop :=
  ∀ (m : Merkmale) (k : KernErgebnis), kern m = .ok k →
    (Regel.R16 ∈ k.regeln ↔ k.ergebnis = .kleinunternehmer)

/-- **R17 – Kleinunternehmer, Leistungsort im Drittland:** nicht steuerbar, derselbe Hinweis wie beim
regelbesteuerten Aussteller (R31). -/
def R17_kleinunternehmer_drittland : Prop :=
  ∀ (m : Merkmale) (k : KernErgebnis), kern m = .ok k → m.kleinunternehmer = true →
    k.ort = .drittland →
    k.ergebnis = .nicht_steuerbar ∧ Regel.R17 ∈ k.regeln ∧ Regel.R31 ∈ k.regeln

/-! ## Abbruch statt falscher Entscheidung -/

/-- **R18 – Leistungsort in einem anderen EU-Staat bei Nichtunternehmern.** Ein Abbruch nach R18 heißt:
Der Kunde ist als Privatperson angegeben und der maßgebliche Ort liegt in einem anderen EU-Staat – und
umgekehrt. -/
def R18_abbruch_genau_bei_privatperson_in_der_eu : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale),
    Passt g d s → merkmale d = some m → g.kategorie d.aussteller_land = .inland →
    (kern m = .error ⟨.R18, .eu_privat⟩ ↔
      d.unternehmer = some false ∧ g.kategorie (ort_massgeblich d s) = .eu)

/-- **R19 – Unvollständige Daten.** `unternehmer` ist für jeden Kunden Pflicht: Sitzt der Aussteller im
Inland, bricht das Werkzeug genau dann nach R19 ab, wenn die Angabe fehlt – auch dort, wo die Antwort
den Leistungsort nicht ändern würde (strenger als § 3a, mit Absicht; RULES.md R19). Ohne `Passt`: Das
prüft das Werkzeug selbst. -/
def R19_abbruch_genau_wenn_unternehmer_fehlt : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (m : Merkmale),
    merkmale d = some m → g.kategorie d.aussteller_land = .inland →
    ((∃ gr, kern m = .error ⟨.R19, gr⟩) ↔ d.unternehmer = none)

/-! ## Steuerschuldnerschaft in der EU (§ 14a Abs. 1 UStG) -/

/-- **R28 – Angabe „Steuerschuldnerschaft des Leistungsempfängers“:** im Trace genau bei Reverse
Charge. -/
def R28_angabe_genau_bei_reverse_charge : Prop :=
  ∀ (m : Merkmale) (k : KernErgebnis), kern m = .ok k →
    (Regel.R28 ∈ k.regeln ↔ k.ergebnis = .reverse_charge)

/-- **R29 – Beide USt-IdNrn. auf der Rechnung.** Ein Abbruch nach R29 heißt: Das Gesetz verlangt die
USt-IdNrn., und eine fehlt – und umgekehrt, wenn der Kunde als Unternehmer angegeben ist. -/
def R29_abbruch_genau_bei_fehlender_ustid : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale),
    Passt g d s → merkmale d = some m → g.kategorie d.aussteller_land = .inland →
    d.unternehmer = some true →
    ((∃ gr, kern m = .error ⟨.R29, gr⟩) ↔
      ustids_pflicht g s.aussteller_klein s.empfaenger_unternehmer (ort_massgeblich d s) = true ∧
      (d.kunde_ustid = false ∨ d.aussteller_ustid = false))

/-- **R30 – Frist bis zum 15. des Folgemonats** (§ 14a Abs. 1 Satz 2 UStG): im Trace genau bei Reverse
Charge; die Warnung selbst gibt `resolve` aus. -/
def R30_frist_genau_bei_reverse_charge : Prop :=
  ∀ (m : Merkmale) (k : KernErgebnis), kern m = .ok k →
    (Regel.R30 ∈ k.regeln ↔ k.ergebnis = .reverse_charge)

/-! ## Hinweis bei Leistungsort im Drittland -/

/-- **R31 – Hinweis auf Leistungsort und Nichtsteuerbarkeit.** Ist das Ergebnis `nicht_steuerbar`, steht
R31 im Trace, die zitierte Vorschrift ist die, die nach § 3a tatsächlich greift, und der
Unternehmerstatus für den Reverse-Charge-Nachsatz ist der wirkliche. -/
def R31_hinweis_nennt_die_richtige_vorschrift : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    k.ergebnis = .nicht_steuerbar →
    Regel.R31 ∈ k.regeln ∧ fundstelle k = some (vorschrift s) ∧
    unternehmer_fuer_hinweis m = some s.empfaenger_unternehmer

/-! ## Manuelle Festlegung -/

/-- **R37 – Manuelle Festlegung des Leistungsorts.** Ab dem festgelegten Ort folgt alles dem Gesetz.
Ob der festgelegte Ort stimmt, sagt diese Aussage nicht; das verantwortet der Mensch mit seiner
Begründung. -/
def R37_festlegung_nur_des_orts : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis) (l : g.Land),
    Passt g d s → d.festgelegt = some l → merkmale d = some m → kern m = .ok k →
    ort_land d k = some l ∧ k.ort_quelle = .festgelegt ∧ Regel.R37 ∈ k.regeln ∧
    FolgenStimmen g d s l k

/-! ## Das Ganze -/

/-- **Nie anders als das Gesetz.** Entscheidet das Werkzeug ohne Festlegung, dann stimmen Leistungsort
(als Land und als Kategorie), die Vorschrift im Trace und alle Folgen mit dem Gesetz überein – für jeden
Sachverhalt, der zu den Daten passt. -/
def Werkzeug_nie_anders : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → d.festgelegt = none → merkmale d = some m → kern m = .ok k →
    ort_land d k = some (leistungsort s) ∧ k.ort = g.kategorie (leistungsort s) ∧
    vorschrift s ∈ k.regeln.filterMap Regel.vorschrift ∧
    FolgenStimmen g d s (leistungsort s) k

/-- **Ergebnis fasst die Folgen zusammen.** Das eine Wort des Werkzeugs (`inland`, `reverse_charge`,
`nicht_steuerbar`, `kleinunternehmer`) mit dem Satz gibt genau die Antworten des Gesetzes auf seine
einzelnen Fragen wieder (R10, R11, R13, R16, R28, R29) – mit und ohne Festlegung. -/
def Ergebnis_fasst_Folgen_zusammen : Prop :=
  ∀ (g : Gebiete) (d : Daten g) (s : Sachverhalt g) (m : Merkmale) (k : KernErgebnis),
    Passt g d s → merkmale d = some m → kern m = .ok k →
    FolgenStimmen g d s (ort_massgeblich d s) k

/-- **Abbruch nur aus genannten Gründen:** R4, R18, R19 oder R29. -/
def Abbruch_nur_aus_genannten_gruenden : Prop :=
  ∀ (m : Merkmale) (a : Abbruch), kern m = .error a → a.regel ∈ [Regel.R4, .R18, .R19, .R29]

end Aussage

end Rechnung
