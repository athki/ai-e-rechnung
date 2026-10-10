/-
Der Sachverhalt: die Tatsachen, nach denen das Gesetz fragt, in seinen eigenen Worten. Kein Begriff
des Werkzeugs kommt hier vor; die Verbindung zu den Rechnungsdaten stellt `Passt` her (Bruecke.lean).

Geltungsbereich (RULES.md Teil 1), im Modell nicht darstellbar und deshalb keine Hypothese: Der
Aussteller ist Unternehmer und leistet gegen Entgelt im Rahmen seines Unternehmens (R2); er ist im
Staat des Empfängers nicht ansässig, und dieser Staat setzt Art. 196 MwStSystRL um (R11); die
Leistung ist eine sonstige Leistung, keine Lieferung; nicht unternehmerisch tätige juristische
Personen mit USt-IdNr. werden nicht eigens unterschieden.
-/
import Rechnung.Gesetz.Gebiete
import Rechnung.Gesetz.Einordnung

namespace Rechnung

/-- Wo eine Tätigkeitsleistung (§ 3a Abs. 3 Nr. 3) erbracht wird: tatsächlich in einem Land
(Satz 1) oder per Streaming bzw. auf andere Weise virtuell (Satz 2). -/
inductive Erbringung (Land : Type)
  | vor_ort (land : Land)
  | virtuell

/-- Die Tatsachen eines Umsatzes, soweit § 1, § 3a, § 12 und § 19 UStG nach ihnen fragen. -/
structure Sachverhalt (g : Gebiete) where
  /-- Der Empfänger ist ein Unternehmer, der die Leistung für sein Unternehmen bezieht
  (§ 3a Abs. 2 Satz 1, Abs. 3 Nr. 3, Abs. 4 Satz 1). -/
  empfaenger_unternehmer : Bool
  /-- Der Ort, von dem aus der Empfänger sein Unternehmen betreibt; bei einem Nichtunternehmer sein
  Wohnsitz oder Sitz (§ 3a Abs. 2 Satz 1, Abs. 3 Nr. 3 Satz 2, Abs. 4 Satz 1). -/
  empfaenger_sitz : g.Land
  /-- Was die Leistung nach § 3a ist. -/
  einordnung : Einordnung
  /-- Wo die Leistung erbracht wird; nach § 3a nur bei Tätigkeitsleistungen von Belang. -/
  erbringung : Erbringung g.Land
  /-- Der Ort, von dem aus der Aussteller sein Unternehmen betreibt (§ 3a Abs. 1). -/
  aussteller_sitz : g.Land
  /-- § 19 Abs. 1 ist auf den Aussteller anwendbar: Umsatzgrenzen eingehalten, kein Verzicht
  (§ 19 Abs. 3). -/
  aussteller_klein : Bool

end Rechnung
