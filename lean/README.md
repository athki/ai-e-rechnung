# Lean: proofs for the tax rules

This folder holds a Lean 4 model of the tax rules in [`RULES.md`](../RULES.md) and, from step 8.5 on,
machine-checked proofs about it. It is not part of the invoice tool: writing invoices never needs Lean.

**Status (step 8.4): the model and the statements are written; nothing is proved yet.** Each statement is
a `def Aussage.… : Prop` – Lean checks that it is well-formed, not that it is true. The proofs come in
step 8.5 as theorems of the same name; until then the check lists every statement as open.

## The chain, and which link this folder covers

```
law (UStG)
  └─ RULES.md            rules R1…Rn in plain German, with citations    to be reviewed by a tax advisor (not done yet); not provable
      └─ Lean theorems   one per rule, same ID (e.g. R14_…)             read side by side with RULES.md
          └─ Lean model  the decision as Lean definitions               proved by Lean
              └─ rules.py  rules.kern() in Python, the running code      exhaustive comparison, all 3456 inputs
```

The tool keeps running Python. Lean proves properties of a model of `rules.kern()`; a test then compares
that model with the Python code on every possible input (the inputs are finite: country category,
business customer yes/no/unknown, VAT IDs, kind of service, place of activity, small business, issuer in Germany, override).

What will stay unproved, and is said so: that the rules match the law (no tax advisor has reviewed
RULES.md yet; every rule is a reasoned but unreviewed assumption), that the facts entered are true (whether a
customer is a business, how a service is classified), the mapping from country code to category, and
the PDF output (checked by `rechnung pruefen`, not proved).

## Two levels and a bridge

The model has two levels, written in the words of their source, and one place where they meet.

- **Law** (`Rechnung/Gesetz/`): the facts the law asks about (`Sachverhalt`: is the recipient a business,
  where is it based, what kind of service, where is it performed) and one function per provision:
  § 3a Abs. 1, 2, 3 Nr. 3 sentence 1 and 2, Abs. 4 for the place of supply (`Leistungsort.lean`), then
  taxable (§ 1), exempt (§ 19), rate (§ 12), who owes the tax (Art. 196 VAT Directive) and the required
  statements (§ 14a, § 34a UStDV) in `Folgen.lean`. Countries are a parameter (`Gebiete`): any set of
  countries, any assignment to Germany / other EU / non-EU, with exactly one Germany. Every statement
  holds for every such assignment; whether the EU list in `rules.py` is right is tested, not proved.
- **Tool** (`Rechnung/Werkzeug/`): an exact mirror of `rules.kern()`, `rules.satz_position()` and
  `rules.merkmale()` – same features, same cases, same rule trace in the same order. Step 8.6 compares
  the mirror with the Python code on all 3456 inputs.
- **Bridge** (`Bruecke.lean`): `Passt d s` says that the invoice data `d` describe the facts `s`. Each of
  its fields is one assumption from RULES.md, named with its rule ID (the customer's country is where it
  does business, `unternehmer: true` means it buys for its business, the classification of the service
  is right, …). Every statement that links the two levels assumes `Passt`; this file is the complete list
  of what is assumed rather than proved.

[`Rechnung/Aussagen.lean`](Rechnung/Aussagen.lean) holds the statements, in the order of the rule IDs,
each with the wording of the law from RULES.md. The main ones: the tool never decides differently from
the law (`Werkzeug_nie_anders`); every refusal happens exactly for its stated reason (`R4_…`, `R18_…`,
`R19_…`, `R29_…`); the one-word result
(`reverse_charge` …) sums up the law's separate answers (`Ergebnis_fasst_Folgen_zusammen`); the
provision cited on the invoice is the one that applies (`R31_…`); a manually set place of supply only
replaces the place (`R37_…`).

Outside the model, because it cannot be expressed in it (RULES.md part 1): special territories,
exceptions in § 3a Abs. 3 Nr. 1, 2, 3a, 5 and Abs. 8, financial services, supplies of goods.

## Build and check

Two commands, both run `pruefen.sh`: `lake build`, then [`Tabelle.lean`](Tabelle.lean), which prints
the decision table of RULES.md part 4 as computed by the Lean `kern`, then
[`Pruefung.lean`](Pruefung.lean), which reports for every statement whether a theorem proves exactly it,
and checks the axioms every theorem in namespace `Rechnung` rests on.

```sh
make lean      # on the host; needs elan (https://github.com/leanprover/elan)
make beweise   # in Docker, nothing to install: the invoice image plus Lean, proofs rebuilt from scratch
```

The check fails if

- a proof is left open (`sorry`): every warning is an error (`lakefile.toml`),
- a statement has no theorem whose type is exactly that statement – allowed in step 8.4, an error from
  8.5 on (`offenErlaubt` in `Pruefung.lean`),
- a theorem rests on anything but Lean's standard axioms (`propext`, `Classical.choice`, `Quot.sound`);
  this rules out `native_decide`, which trusts the compiler instead of the kernel.

The Lean version is pinned in [`lean-toolchain`](lean-toolchain); the container installs the same one.
No dependencies, no Mathlib.

## Names

The code and the rules are written in German, and the Lean model mirrors their names so that
`rules.py`, `RULES.md` and the proofs can be read side by side. Field names keep the Python spelling
(`kunde_ustid`, not `kundeUstid`). Statements and theorems carry the rule ID: `Aussage.R14_kleinunternehmer_nie_steuer`,
proved by `theorem R14_kleinunternehmer_nie_steuer`.

| German | English |
| --- | --- |
| `Rechnung` | invoice (also the namespace) |
| `Merkmale` | features: everything the tax decision depends on |
| `kern` | core: the decision function |
| `KernErgebnis` | result of the core: place of supply, outcome, rate, rules applied |
| `Abbruch` | refusal: the tool stops instead of deciding |
| `Leistungsort` | place of supply |
| `inland` / `eu` / `drittland` | Germany / other EU state / non-EU country |
| `unternehmer` | business customer |
| `ustid` | VAT identification number |
| `kleinunternehmer` | small business exempt under § 19 UStG |
| `reverse_charge` / `nicht_steuerbar` | reverse charge / not taxable in Germany |
| `Gesetz` / `Werkzeug` / `Bruecke` | law / tool / bridge |
| `Sachverhalt` | the facts of a supply |
| `Gebiete`, `Land`, `Kategorie` | territories, country, category |
| `Einordnung`, `Gruppe` | classification of the service (§ 3a), its group |
| `Erbringung`, `vor_ort`, `virtuell` | where an activity is performed: on site, virtually |
| `Folgen` | consequences: taxable, exempt, rate, who owes the tax, required statements |
| `steuerbar`, `steuerfrei`, `steuersatz` | taxable in Germany, exempt, VAT rate |
| `empfaenger_schuldet` | the recipient owes the tax (reverse charge) |
| `Vorschrift`, `abs1` … `abs4` | provision, § 3a paragraph 1 … 4 |
| `Daten` | the invoice data the tool reads |
| `Passt` | the data fit the facts: all assumptions, by rule ID |
| `Aussage`, `annahme_…` | statement, assumption |
| `Tabelle`, `Pruefung` | table, check |
