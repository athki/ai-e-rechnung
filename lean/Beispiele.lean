/-
Was jede Aussage an Beispielen fordert, abgeleitet aus ihrem Typ (Rechnung/Erfuellbarkeit.lean): zum
Lesen neben Aussagen.lean. Keine Beweise; die Beispiele stehen in Rechnung/Beweise/Erfuellbar.lean,
`Pruefung.lean` verlangt sie. Läuft nach dem Build (`pruefen.sh`).
-/
import Rechnung

open Lean Elab Command Rechnung.Erfuellbarkeit

#eval show CommandElabM Unit from do
  let aussagen := ((← getEnv).constants.toList.filterMap fun (name, info) =>
    match info with
    | .defnInfo d =>
      if (`Rechnung.Aussage).isPrefixOf name && name != `Rechnung.Aussage && d.type == .sort .zero
      then some name else none
    | _ => none).toArray.qsort (·.toString < ·.toString)
  for a in aussagen do
    match ← liftTermElabM (forderung a) with
    | none => logInfo m!"{a.componentsRev.head!}: ohne Voraussetzungen, nichts zu zeigen"
    | some f => logInfo m!"{a.componentsRev.head!}:\n{f}"
