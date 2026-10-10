/-
Erfüllbarkeit der Aussagen: Eine Aussage „wenn V, dann F“ ist auch dann bewiesen, wenn V nie eintreten
kann – dann sagt sie nichts. Deshalb braucht jede Aussage Beispiele, in denen ihre Voraussetzungen
zugleich gelten. Welche Beispiele das sind, leitet `forderung` mechanisch aus dem Typ der Aussage ab;
von Hand abgetippt könnten sie von der Aussage abweichen.

Die Ableitung, von außen nach innen:
- Variablen (`∀ (d : Daten g)`) werden zu `∃`, Voraussetzungen (`Passt g d s → …`) zu „und“.
- Eine Folgerung `A ∧ B`: jeder Teil für sich, mit denselben Variablen und Voraussetzungen; was er
  selbst an Variablen und Voraussetzungen mitbringt, kommt dazu.
- Eine Folgerung `A ↔ B`: je ein Beispiel, in dem `A` gilt, und eines, in dem `A` nicht gilt – sonst
  könnten beide Seiten immer falsch (oder immer wahr) sein, und die Aussage unterschiede nichts.
- Jede andere Folgerung: ein Beispiel für die Voraussetzungen. Ohne Voraussetzungen ist nichts zu
  zeigen (die Aussage kann nicht leer bewiesen sein).

Gleiche Beispiele werden zusammengefasst. Was eine Aussage fordert, ist die Konjunktion all ihrer
Beispiele. `erfuellbar X := …` legt das Theorem `Rechnung.Erfuellbar.X` mit genau diesem Typ an;
`Pruefung.lean` leitet die Forderung noch einmal ab und verlangt ein Theorem dieses Typs.
-/
import Lean
import Rechnung.Aussagen

open Lean Meta Elab Command

namespace Rechnung.Erfuellbarkeit

/-- `∃ x₁ … xₙ, p₁ ∧ … ∧ pₘ`; `True` ohne Bedingungen. -/
def zeuge (variablen : Array Expr) (bedingungen : Array Expr) : MetaM Expr := do
  let mut rumpf := bedingungen.back?.getD (mkConst ``True)
  for p in bedingungen.pop.reverse do
    rumpf := mkAnd p rumpf
  for x in variablen.reverse do
    rumpf ← mkAppM ``Exists #[← mkLambdaFVars #[x] rumpf]
  return rumpf

/-- Die Beispiele zu einer Aussage, nach den Regeln oben. -/
partial def beispiele (e : Expr) : MetaM (Array Expr) :=
  go #[] #[] e
where
  go (variablen voraussetzungen : Array Expr) (e : Expr) : MetaM (Array Expr) :=
    forallTelescope e fun xs rumpf => do
      let mut variablen := variablen
      let mut voraussetzungen := voraussetzungen
      for x in xs do
        let t ← inferType x
        if ← isProp t then voraussetzungen := voraussetzungen.push t
        else variablen := variablen.push x
      match_expr rumpf with
      | And a b => return (← go variablen voraussetzungen a) ++ (← go variablen voraussetzungen b)
      | Iff a _ =>
        return #[← zeuge variablen (voraussetzungen.push a),
                 ← zeuge variablen (voraussetzungen.push (mkNot a))]
      | _ =>
        if voraussetzungen.isEmpty then return #[]
        else return #[← zeuge variablen voraussetzungen]

/-- Was die Aussage `aussage` an Beispielen fordert, als ein Satz; `none`, wenn nichts zu zeigen ist. -/
def forderung (aussage : Name) : MetaM (Option Expr) := do
  let info ← getConstInfoDefn aussage
  let mut alle : Array Expr := #[]
  for b in ← beispiele info.value do
    unless alle.contains b do alle := alle.push b
  match alle.back? with
  | none => return none
  | some letztes => return some (alle.pop.foldr mkAnd letztes)

/-- `erfuellbar R3_… := beweis` legt `Rechnung.Erfuellbar.R3_… : <Forderung von Aussage.R3_…>` an. -/
syntax (name := erfuellbarBefehl) "erfuellbar " ident " := " term : command

@[command_elab erfuellbarBefehl]
def elabErfuellbar : CommandElab := fun stx => do
  let kurz := stx[1].getId
  let aussage := `Rechnung.Aussage ++ kurz
  let name := `Rechnung.Erfuellbar ++ kurz
  liftTermElabM <| Term.withDeclName name do
    let some typ ← forderung aussage
      | throwError "{aussage} hat keine Voraussetzungen; es ist nichts zu zeigen."
    let beweis ← Term.elabTermEnsuringType stx[3] typ
    Term.synthesizeSyntheticMVarsNoPostponing
    let beweis ← instantiateMVars beweis
    if beweis.hasMVar then throwError "Beispiel für {aussage} unvollständig: {beweis}"
    addDecl (.thmDecl { name, levelParams := [], type := typ, value := beweis })

end Rechnung.Erfuellbarkeit
