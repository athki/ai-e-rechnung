/-
Die Regel-IDs aus RULES.md Teil 3 als Typ: Eine ID, die es nicht gibt, lässt sich nicht hinschreiben.
R36 ist entfallen und fehlt deshalb. Dass jede ID hier in RULES.md steht, prüft ein Python-Test
(`test_kern_nennt_nur_regeln_aus_rules_md`, `test_lean_nennt_nur_regeln_aus_rules_md`); Lean liest RULES.md nicht.
-/

namespace Rechnung

inductive Regel
  | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10
  | R11 | R12 | R13 | R14 | R15 | R16 | R17 | R18 | R19 | R20
  | R21 | R22 | R23 | R24 | R25 | R26 | R27 | R28 | R29 | R30
  | R31 | R32 | R33 | R34 | R35 | R37 | R38
  deriving DecidableEq, Repr

end Rechnung
