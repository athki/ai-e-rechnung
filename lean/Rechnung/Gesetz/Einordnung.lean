/-
Die Einordnung der Leistung (RULES.md Teil 4): ein Begriff aus § 3a UStG je Rechnung. Spiegel von
`rules.EINORDNUNGEN`. Welcher Begriff auf eine Leistung zutrifft, entscheidet der Mensch; das ist die
Annahme `annahme_R5_R7_einordnung` in `Passt` (Bruecke.lean).
-/

namespace Rechnung

/-- Die drei Gruppen, nach denen § 3a bei Nichtunternehmern unterscheidet. -/
inductive Gruppe
  | taetigkeit   -- § 3a Abs. 3 Nr. 3
  | katalog      -- § 3a Abs. 4 Satz 2
  | grundregel   -- § 3a Abs. 1 und 2
  deriving DecidableEq, Repr

/-- Die Begriffe aus § 3a UStG, wie RULES.md Teil 4 sie führt. Katalog Nr. 6 (Bank, Finanz,
Versicherung, Edelmetalle) und Nr. 11–13 (weggefallen) stehen bewusst nicht darin (RULES.md Teil 1);
ebenso wenig die Ausnahmen § 3a Abs. 3 Nr. 1, 2, 3a, 5 und Abs. 8 (Grundstücke, Beförderung,
Restaurationsleistungen …) – solche Leistungen sind im Modell nicht darstellbar. -/
inductive Einordnung
  | kulturell | kuenstlerisch | wissenschaftlich | unterrichtend | sportlich | unterhaltend
  | rechte | werbung | beratung | datenverarbeitung | informationen
  | personal | verzicht_recht | verzicht_taetigkeit | vermietung | energienetze
  | sonstige
  deriving DecidableEq, Repr

namespace Einordnung

/-- Gruppe der Einordnung; Spiegel des ersten Eintrags in `rules.EINORDNUNGEN`. -/
def gruppe : Einordnung → Gruppe
  | kulturell | kuenstlerisch | wissenschaftlich | unterrichtend | sportlich | unterhaltend => .taetigkeit
  | rechte | werbung | beratung | datenverarbeitung | informationen
  | personal | verzicht_recht | verzicht_taetigkeit | vermietung | energienetze => .katalog
  | sonstige => .grundregel

/-- Fundstelle der Einordnung; Spiegel des zweiten Eintrags in `rules.EINORDNUNGEN`, wörtlich. -/
def fundstelle : Einordnung → String
  | kulturell | kuenstlerisch | wissenschaftlich | unterrichtend | sportlich | unterhaltend =>
      "§ 3a Abs. 3 Nr. 3 UStG"
  | rechte => "§ 3a Abs. 4 Satz 2 Nr. 1 UStG"
  | werbung => "§ 3a Abs. 4 Satz 2 Nr. 2 UStG"
  | beratung => "§ 3a Abs. 4 Satz 2 Nr. 3 UStG"
  | datenverarbeitung => "§ 3a Abs. 4 Satz 2 Nr. 4 UStG"
  | informationen => "§ 3a Abs. 4 Satz 2 Nr. 5 UStG"
  | personal => "§ 3a Abs. 4 Satz 2 Nr. 7 UStG"
  | verzicht_recht => "§ 3a Abs. 4 Satz 2 Nr. 8 UStG"
  | verzicht_taetigkeit => "§ 3a Abs. 4 Satz 2 Nr. 9 UStG"
  | vermietung => "§ 3a Abs. 4 Satz 2 Nr. 10 UStG"
  | energienetze => "§ 3a Abs. 4 Satz 2 Nr. 14 UStG"
  | sonstige => "§ 3a Abs. 1 und 2 UStG"

/-- Das Wort, wie es in `rechnung.yaml` steht (`verzicht-recht` mit Bindestrich). -/
def wort : Einordnung → String
  | kulturell => "kulturell" | kuenstlerisch => "kuenstlerisch" | wissenschaftlich => "wissenschaftlich"
  | unterrichtend => "unterrichtend" | sportlich => "sportlich" | unterhaltend => "unterhaltend"
  | rechte => "rechte" | werbung => "werbung" | beratung => "beratung"
  | datenverarbeitung => "datenverarbeitung" | informationen => "informationen"
  | personal => "personal" | verzicht_recht => "verzicht-recht"
  | verzicht_taetigkeit => "verzicht-taetigkeit" | vermietung => "vermietung"
  | energienetze => "energienetze" | sonstige => "sonstige"

end Einordnung

end Rechnung
