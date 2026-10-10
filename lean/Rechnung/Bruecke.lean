/-
Die Brücke zwischen den Ebenen: Wann passt ein Sachverhalt (Gesetz) zu den Rechnungsdaten (Werkzeug)?

Jedes Feld von `Passt` ist eine Annahme aus RULES.md mit ihrer Regel-ID: dass die Daten, die Mensch oder
AI eingeben, die Tatsachen richtig wiedergeben. Das kann kein Beweis zeigen. Jede Aussage, die beide
Ebenen verbindet, setzt `Passt` voraus; was hier steht, ist also genau das, was angenommen und nicht
bewiesen ist.
-/
import Rechnung.Gesetz.Folgen
import Rechnung.Werkzeug.Merkmale

namespace Rechnung

/-- Der Sachverhalt `s` passt zu den Daten `d`. -/
structure Passt (g : Gebiete) (d : Daten g) (s : Sachverhalt g) : Prop where
  /-- R3, R6: Das Land in der Kundendatei ist der Ort, von dem aus der Kunde sein Unternehmen betreibt,
  bei einer Privatperson ihr Wohnsitz; eine abweichende Betriebsstätte gibt es nicht. -/
  annahme_R3_R6_sitz : s.empfaenger_sitz = d.kunde_land
  /-- R3: `unternehmer: true` heißt, der Kunde ist Unternehmer und bezieht die Leistung für sein
  Unternehmen. -/
  annahme_R3_fuer_unternehmen : d.unternehmer = some true → s.empfaenger_unternehmer = true
  /-- R3: `unternehmer: false` heißt, der Kunde bezieht die Leistung nicht als Unternehmer für sein
  Unternehmen. -/
  annahme_R3_privat : d.unternehmer = some false → s.empfaenger_unternehmer = false
  /-- R4: `land` in `ich.yaml` ist der Ort, von dem aus der Aussteller sein Unternehmen betreibt; eine
  Betriebsstätte im Ausland gibt es nicht. -/
  annahme_R4_sitz : s.aussteller_sitz = d.aussteller_land
  /-- R5, R7: Die Einordnung in `rechnung.yaml` trifft zu. -/
  annahme_R5_R7_einordnung : s.einordnung = d.einordnung
  /-- R5: `ort` ist das Land, in dem die Tätigkeit tatsächlich erbracht wird. -/
  annahme_R5_ort : ∀ l, d.ort = some (.land l) → s.erbringung = .vor_ort l
  /-- R6: `ort: online` heißt, die Leistung wird per Streaming übertragen oder auf andere Weise virtuell
  verfügbar gemacht. -/
  annahme_R6_virtuell : d.ort = some .online → s.erbringung = .virtuell
  /-- R13: `kleinunternehmer: true` heißt, § 19 Abs. 1 ist anwendbar: Umsatzgrenzen eingehalten, kein
  Verzicht nach § 19 Abs. 3. -/
  annahme_R13_grenzen : s.aussteller_klein = d.kleinunternehmer

end Rechnung
