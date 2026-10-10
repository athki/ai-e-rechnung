/-
Axiom-Prüfung, läuft nach `lake build` (siehe `pruefen.sh`).

`lake build` allein beweist nicht genug: Ein Theorem kann sich auf `sorryAx` stützen (offener Beweis)
oder über `native_decide` dem Compiler statt dem Kernel vertrauen. Dieser Befehl geht jedes Theorem im
Namespace `Rechnung` durch, druckt die Axiome, auf denen es ruht, und bricht ab, wenn eines davon nicht
zu den drei Standardaxiomen von Lean gehört.
-/
import Lean
import Rechnung

open Lean Elab Command

/-- Die Standardaxiome von Lean; alles andere lässt die Prüfung scheitern. -/
def erlaubteAxiome : List Name := [``propext, ``Classical.choice, ``Quot.sound]

elab "#pruefe_axiome" : command => do
  let env ← getEnv
  let theoreme := env.constants.toList.filterMap fun (name, info) =>
    match info with
    | .thmInfo _ => if name.getRoot == `Rechnung then some name else none
    | _ => none
  let theoreme := theoreme.toArray.qsort (·.toString < ·.toString)
  if theoreme.isEmpty then
    throwError "Keine Theoreme im Namespace Rechnung gefunden."
  let mut fehler := #[]
  for name in theoreme do
    let axiome ← liftCoreM (collectAxioms name)
    let fremd := axiome.filter (!erlaubteAxiome.contains ·)
    let liste := if axiome.isEmpty then "keine" else ", ".intercalate (axiome.toList.map toString)
    logInfo m!"{name}: {liste}"
    unless fremd.isEmpty do
      fehler := fehler.push m!"{name} stützt sich auf {fremd.toList}"
  unless fehler.isEmpty do
    throwError m!"Nicht bewiesen:\n{MessageData.joinSep fehler.toList "\n"}"
  logInfo m!"Geprüft: {theoreme.size}, alle nur auf Standardaxiomen."

#pruefe_axiome
