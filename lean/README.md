# Lean: proofs for the tax rules

This folder holds a Lean 4 model of the tax rules in [`RULES.md`](../RULES.md) and machine-checked
proofs about it. It is not part of the invoice tool: writing invoices never needs Lean.

**Status (step 8.6): all 27 statements are proved, each by a theorem of the same name, and each has an
example showing that its hypotheses can hold. `rules.kern()` and `rules.satz_position()` give the same
answer as the model on every possible input.** That last part is an exhaustive comparison, not a proof;
see [Comparison with the Python code](#comparison-with-the-python-code).

## The chain, and which link this folder covers

```
law (UStG)
  └─ RULES.md            rules R1…Rn in plain German, with citations    to be reviewed by a tax advisor (not done yet); not provable
      └─ Lean theorems   one per rule, same ID (e.g. R14_…)             read side by side with RULES.md
          └─ Lean model  the decision as Lean definitions               proved by Lean
              └─ rules.py  rules.kern() in Python, the running code      exhaustive comparison, all 3456 inputs
```

The tool keeps running Python. Lean proves properties of a model of `rules.kern()`; a test compares
that model with the Python code on every possible input (the inputs are finite: country category,
business customer yes/no/unknown, VAT IDs, kind of service, place of activity, small business, issuer in Germany, override).

What will stay unproved, and is said so: that the rules match the law (no tax advisor has reviewed
RULES.md yet; every rule is a reasoned but unreviewed assumption), that the facts entered are true (whether a
customer is a business, how a service is classified), the mapping from country code to category,
invoice numbers and amounts (net, VAT, total; tested, not modelled in Lean), and the PDF output (checked
by `rechnung pruefen`, not proved).

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
  `rules.merkmale()` – same features, same cases, same rule trace in the same order. The comparison
  below checks the mirror against the Python code on all 3456 inputs.
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

## Proofs

The proofs live in [`Rechnung/Beweise/`](Rechnung/Beweise), one file per group of statements, in the
order they build on each other:

| File | Statements | How |
| --- | --- | --- |
| `Gesetz.lean` | R2, R3–R8 at most one provision | law level only |
| `Kern.lean` | R12, R14–R17, R28, R30, refusals only for stated reasons | what a result or a refusal of `kern` looks like (`kern_ok`, `kern_fehler`), then case analysis by place and small business |
| `Hilfssaetze.lean` | – | the bridge: without an override the tool names the place of the law, with the category the core used, and its place rule belongs to the provision that applies (`ohne_festlegung`); with an override, the fixed place (`mit_festlegung`) |
| `Abbruch.lean` | R4, R18, R19, R29 | each refusal happens exactly for its reason |
| `Leistungsort.lean` | R3–R8, R31 | which place and provision the law gives under each statement's hypotheses |
| `Folgen.lean` | R10, R11, R13, R37, `Ergebnis_fasst_Folgen_zusammen`, `Werkzeug_nie_anders` | `folgen_stimmen`: for the place the tool names, every consequence matches the law |
| `Erfuellbar.lean` | examples for all statements | a world of three countries |

The proofs are case analyses over the questions the core itself asks, closed by `simp`; `decide` only
settles small concrete facts (is a rule in a given list), never a whole statement.

## Comparison with the Python code

[`Rechnung/Abgleich.lean`](Rechnung/Abgleich.lean) lists every input of `kern` (3456), every rate
`satz_position` can receive from `kern` (19 or 0, times small business and reduced rate: 8) and every
classification word (17), and proves that nothing is missing (`alle_vollstaendig`,
`einordnungen_vollstaendig`, `satz_aus_kern`). [`Abgleich.lean`](Abgleich.lean) evaluates the model
on each of them and writes the answers to [`abgleich/kern.json`](abgleich/kern.json), one line per
input: place, its source, result, rate, the rule trace in order and the cited provision, or the refusal
with rule and reason; for each classification word its group and provision. Field names are those of
`rules.py`.

The file is checked in. `make abgleich` rewrites it; nothing else does. `pruefen.sh` regenerates it on
every run and fails if it differs from the checked-in file, so it always matches the proved model.
`tests/test_abgleich.py` (part of `make test`, no Lean needed) checks that Python enumerates exactly
the same inputs and that `rules.py` gives exactly the same answer on each.

What is trusted: the answers are computed with `#eval`, that is by Lean's compiler, not checked by the
kernel. The proofs themselves rest on the kernel and Lean's standard axioms only; the compiler is
trusted for the comparison data alone. Not compared, because it depends on actual countries rather
than categories: the country-code-to-category table in `rules.py` and which country a place source
stands for. Both are tested in Python.

## Build and check

Two commands, both run `pruefen.sh`: `lake build`, then [`Tabelle.lean`](Tabelle.lean), which prints
the decision table of RULES.md part 4 as computed by the Lean `kern`, then
[`Beispiele.lean`](Beispiele.lean), which prints the examples each statement requires (see below), then
[`Pruefung.lean`](Pruefung.lean), which reports for every statement whether a theorem proves exactly it
and whether its examples exist, and checks the axioms every theorem in namespace `Rechnung` rests on,
and finally compares `abgleich/kern.json` with the model.

```sh
make lean      # on the host; needs elan (https://github.com/leanprover/elan)
make beweise   # in Docker, nothing to install: the invoice image plus Lean, proofs rebuilt from scratch
```

The check fails if

- a proof is left open (`sorry`): every warning is an error (`lakefile.toml`),
- a statement has no theorem whose type is exactly that statement (`offenErlaubt` in `Pruefung.lean`,
  `false` since step 8.5),
- a statement with hypotheses has no examples: "if V then F" is also proved when V can never hold, and
  then it says nothing. So every statement needs a proved example in which all its hypotheses hold at
  once, and for an "if and only if" one example where the left side holds and one where it does not
  (otherwise both sides might always be false). What is required is derived mechanically from the type
  of the statement ([`Rechnung/Erfuellbarkeit.lean`](Rechnung/Erfuellbarkeit.lean)), not typed by hand;
  the examples live in [`Rechnung/Beweise/Erfuellbar.lean`](Rechnung/Beweise/Erfuellbar.lean), in a
  small world of three countries (Germany, France, the US),
- `abgleich/kern.json` does not match the model (run `make abgleich` if the change is intended, then
  `make test`),
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
| `erfuellbar`, `Beispiel`, `welt` | satisfiable, example, (example) world |
| `Tabelle`, `Pruefung` | table, check |
| `Abgleich`, `alle`, `vollstaendig` | comparison, all, complete |
