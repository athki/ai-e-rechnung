/-
Prüfung nach `lake build` (siehe `pruefen.sh`). Zwei Teile:

1. **Aussage ↔ Theorem.** Jede `Rechnung.Aussage.X : Prop` (Aussagen.lean) braucht ein Theorem, dessen
   Typ genau `Rechnung.Aussage.X` ist – nicht eine ähnliche, schwächere Fassung. Lean selbst prüft nur,
   dass vorhandene Theoreme stimmen, nicht, dass jede Aussage eines hat. In Schritt 8.4 sind die
   Aussagen formuliert und noch offen; das ist erlaubt (`offenErlaubt`). Ab 8.5 ist jede offene Aussage
   ein Fehler.
2. **Axiome.** `lake build` allein beweist nicht genug: Ein Theorem kann sich auf `sorryAx` stützen
   (offener Beweis) oder über `native_decide` dem Compiler statt dem Kernel vertrauen. Jedes Theorem im
   Namespace `Rechnung` darf nur auf den drei Standardaxiomen von Lean ruhen.
-/
import Lean
import Rechnung

open Lean Elab Command

/-- Schritt 8.4: Aussagen ohne Theorem sind erlaubt. Ab 8.5 auf `false`. -/
def offenErlaubt : Bool := true

/-- Die Standardaxiome von Lean; alles andere lässt die Prüfung scheitern. -/
def erlaubteAxiome : List Name := [``propext, ``Classical.choice, ``Quot.sound]

elab "#pruefe_aussagen_und_axiome" : command => do
  let env ← getEnv
  let konstanten := env.constants.toList
  let theoreme := (konstanten.filterMap fun (name, info) =>
    match info with
    | .thmInfo t => if name.getRoot == `Rechnung then some (name, t.type) else none
    | _ => none).toArray.qsort (·.1.toString < ·.1.toString)
  let aussagen := (konstanten.filterMap fun (name, info) =>
    match info with
    | .defnInfo d =>
      if (`Rechnung.Aussage).isPrefixOf name && name != `Rechnung.Aussage && d.type == .sort .zero
      then some name else none
    | _ => none).toArray.qsort (·.toString < ·.toString)
  if aussagen.isEmpty then
    throwError "Keine Aussagen im Namespace Rechnung.Aussage gefunden."

  -- 1. Aussage ↔ Theorem
  let mut offen := #[]
  for a in aussagen do
    match theoreme.find? (·.2 == .const a []) with
    | some (t, _) => logInfo m!"bewiesen  {a.componentsRev.head!}  durch {t}"
    | none =>
      offen := offen.push a
      logInfo m!"offen     {a.componentsRev.head!}"
  logInfo m!"Aussagen: {aussagen.size}, bewiesen: {aussagen.size - offen.size}, offen: {offen.size}"
  unless offen.isEmpty || offenErlaubt do
    throwError m!"Ohne Beweis: {offen.toList}"

  -- 2. Axiome
  let mut fehler := #[]
  for (name, _) in theoreme do
    let axiome ← liftCoreM (collectAxioms name)
    let fremd := axiome.filter (!erlaubteAxiome.contains ·)
    unless fremd.isEmpty do
      fehler := fehler.push m!"{name} stützt sich auf {fremd.toList}"
  unless fehler.isEmpty do
    throwError m!"Nicht bewiesen:\n{MessageData.joinSep fehler.toList "\n"}"
  -- Auch die Hilfssätze, die Lean selbst erzeugt (`deriving DecidableEq` …), gehen mit durch.
  logInfo m!"Theoreme: {theoreme.size} (mit automatisch erzeugten), alle nur auf Standardaxiomen."

#pruefe_aussagen_und_axiome
