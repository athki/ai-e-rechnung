/-
Gebiete (RULES.md R1; § 1 Abs. 2 und 2a UStG).

Das Modell legt nicht fest, welche Länder es gibt und welches in der EU liegt: `Gebiete` ist ein
Parameter jeder Aussage. Fest steht nur, was das Gesetz selbst sagt – jedes Land gehört zu genau
einer Kategorie, und es gibt genau ein Inland. Welches Land welche Kategorie hat (`EU_LAENDER` in
`rules.py`), ist gepflegt und getestet, nicht bewiesen.
-/

namespace Rechnung

/-- **R1 – Länderkategorie.** § 1 Abs. 2a UStG: „Gemeinschaftsgebiet im Sinne dieses Gesetzes umfasst
das Inland im Sinne des Absatzes 2 Satz 1 und die Gebiete der übrigen Mitgliedstaaten der Europäischen
Union, die nach dem Gemeinschaftsrecht als Inland dieser Mitgliedstaaten gelten (übriges
Gemeinschaftsgebiet). Drittlandsgebiet im Sinne dieses Gesetzes ist das Gebiet, das nicht
Gemeinschaftsgebiet ist.“

Dass jedes Land genau eine der drei Kategorien hat, ergibt sich daraus, dass `Gebiete.kategorie` eine
Funktion in diesen Typ ist; ein eigenes Theorem gibt es dafür nicht. Sondergebiete (Büsingen,
Helgoland, Kanaren, Nordirland …) unterscheidet das Modell nicht (RULES.md Teil 1).
Status: Annahme – ungeprüft (ungeprüft ist die gepflegte Liste, nicht die Einteilung). -/
inductive Kategorie
  | inland
  | eu          -- übriges Gemeinschaftsgebiet
  | drittland
  deriving DecidableEq, Repr

/-- Die Länder und ihre Kategorien. `inland` ist das Inland im Sinne des UStG, also Deutschland; sein
Name spielt für keinen Schluss eine Rolle. `inland_eindeutig`: Es gibt genau ein Inland (§ 1 Abs. 2
UStG). Die übrigen EU-Staaten und das Drittland bleiben beliebig groß. -/
structure Gebiete where
  Land             : Type
  kategorie        : Land → Kategorie
  inland           : Land
  inland_eindeutig : ∀ l, kategorie l = .inland ↔ l = inland

end Rechnung
