/-
Der Ort der sonstigen Leistung, § 3a UStG (RULES.md R3–R8). Je Absatz bzw. Satz eine Funktion; sie
liefert `none`, wenn die Vorschrift den Fall nicht regelt. `leistungsort` setzt sie in der Rangfolge
des Gesetzes zusammen: Abs. 1 und 2 gelten „vorbehaltlich“ der Absätze 3 bis 8, Abs. 1 auch
vorbehaltlich Abs. 2.
-/
import Rechnung.Gesetz.Sachverhalt

namespace Rechnung

variable {g : Gebiete}

/-- **§ 3a Abs. 1 UStG (R4, R8):** „Eine sonstige Leistung wird vorbehaltlich der Absätze 2 bis 8 und
der §§ 3b und 3e an dem Ort ausgeführt, von dem aus der Unternehmer sein Unternehmen betreibt.“
Greift immer, wenn nichts anderes greift. -/
def abs1 (s : Sachverhalt g) : g.Land :=
  s.aussteller_sitz

/-- **§ 3a Abs. 2 Satz 1 UStG (R3):** „Eine sonstige Leistung, die an einen Unternehmer für dessen
Unternehmen ausgeführt wird, wird vorbehaltlich der Absätze 3 bis 8 und der §§ 3b und 3e an dem Ort
ausgeführt, von dem aus der Empfänger sein Unternehmen betreibt.“ -/
def abs2 (s : Sachverhalt g) : Option g.Land :=
  if s.empfaenger_unternehmer then some s.empfaenger_sitz else none

/-- **§ 3a Abs. 3 Nr. 3 Satz 1 UStG (R5):** „Kulturelle, künstlerische, wissenschaftliche,
unterrichtende, sportliche, unterhaltende oder ähnliche Leistungen […] an einen Empfänger, der weder
ein Unternehmer ist, für dessen Unternehmen die Leistung ausgeführt wird, noch eine
nichtunternehmerisch tätige juristische Person, der eine Umsatzsteuer-Identifikationsnummer erteilt
worden ist, werden dort ausgeführt, wo sie vom Unternehmer tatsächlich erbracht werden.“ -/
def abs3_nr3_satz1 (s : Sachverhalt g) : Option g.Land :=
  if !s.empfaenger_unternehmer && s.einordnung.gruppe == .taetigkeit then
    match s.erbringung with
    | .vor_ort l => some l
    | .virtuell  => none
  else none

/-- **§ 3a Abs. 3 Nr. 3 Satz 2 UStG (R6):** „Werden die Leistungen per Streaming übertragen oder auf
andere Weise virtuell verfügbar gemacht, gilt abweichend von Satz 1 als Ort der sonstigen Leistung der
Ort, an dem der Empfänger ansässig ist oder seinen Wohnsitz oder gewöhnlichen Aufenthaltsort hat.“ -/
def abs3_nr3_satz2 (s : Sachverhalt g) : Option g.Land :=
  if !s.empfaenger_unternehmer && s.einordnung.gruppe == .taetigkeit then
    match s.erbringung with
    | .vor_ort _ => none
    | .virtuell  => some s.empfaenger_sitz
  else none

/-- **§ 3a Abs. 4 Satz 1 UStG (R7):** „Ist der Empfänger einer der in Satz 2 bezeichneten sonstigen
Leistungen weder ein Unternehmer, für dessen Unternehmen die Leistung bezogen wird, noch eine nicht
unternehmerisch tätige juristische Person, der eine Umsatzsteuer-Identifikationsnummer erteilt worden
ist, und hat er seinen Wohnsitz oder Sitz im Drittlandsgebiet, wird die sonstige Leistung an seinem
Wohnsitz oder Sitz ausgeführt.“ Die in Satz 2 bezeichneten Leistungen sind die der Gruppe `katalog`
(Einordnung.lean). Wohnt der Empfänger im Inland oder in einem anderen EU-Staat, regelt Abs. 4 den
Fall nicht; dann gilt Abs. 1 (R8). -/
def abs4 (s : Sachverhalt g) : Option g.Land :=
  if !s.empfaenger_unternehmer && s.einordnung.gruppe == .katalog
      && g.kategorie s.empfaenger_sitz == .drittland then
    some s.empfaenger_sitz
  else none

/-- Die Vorschriften aus § 3a, die das Modell kennt. -/
inductive Vorschrift
  | abs1
  | abs2
  | abs3_nr3_satz1
  | abs3_nr3_satz2
  | abs4
  deriving DecidableEq, Repr

/-- Die Fundstelle, wie das Werkzeug sie im Hinweistext zitiert (`rules.FUNDSTELLE`): Satz 1 und
Satz 2 von Abs. 3 Nr. 3 zitiert es gleich. -/
def Vorschrift.zitat : Vorschrift → String
  | .abs1 => "§ 3a Abs. 1 UStG"
  | .abs2 => "§ 3a Abs. 2 UStG"
  | .abs3_nr3_satz1 | .abs3_nr3_satz2 => "§ 3a Abs. 3 Nr. 3 UStG"
  | .abs4 => "§ 3a Abs. 4 UStG"

/-- Welche Vorschrift den Ort bestimmt, in der Rangfolge des Gesetzes. -/
def vorschrift (s : Sachverhalt g) : Vorschrift :=
  if (abs3_nr3_satz1 s).isSome then .abs3_nr3_satz1
  else if (abs3_nr3_satz2 s).isSome then .abs3_nr3_satz2
  else if (abs4 s).isSome then .abs4
  else if (abs2 s).isSome then .abs2
  else .abs1

/-- Der Leistungsort nach § 3a, in der Rangfolge des Gesetzes. -/
def leistungsort (s : Sachverhalt g) : g.Land :=
  (abs3_nr3_satz1 s <|> abs3_nr3_satz2 s <|> abs4 s <|> abs2 s).getD (abs1 s)

/-- Die Vorschriften unter Abs. 2 bis 4, die für `s` greifen. Im Geltungsbereich höchstens eine
(Aussage `R3_R8_eindeutig`); die Rangfolge in `leistungsort` ändert dann nichts. -/
def greifende (s : Sachverhalt g) : List Vorschrift :=
  (if (abs2 s).isSome then [.abs2] else []) ++
  (if (abs3_nr3_satz1 s).isSome then [.abs3_nr3_satz1] else []) ++
  (if (abs3_nr3_satz2 s).isSome then [.abs3_nr3_satz2] else []) ++
  (if (abs4 s).isSome then [.abs4] else [])

end Rechnung
