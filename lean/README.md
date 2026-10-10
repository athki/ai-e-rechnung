# Lean: proofs for the tax rules

This folder will hold a Lean 4 model of the tax rules in [`RULES.md`](../RULES.md) and machine-checked
proofs about it. It is not part of the invoice tool: writing invoices never needs Lean.

**Status (step 8.3): setup only. Nothing about the tax rules is proved yet.** The single theorem,
`Rechnung.build_laeuft : 2 + 2 = 4`, only shows that the toolchain, the build and the axiom check work.

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

## Build and check

Two commands, both run `pruefen.sh`: `lake build`, then [`Pruefung.lean`](Pruefung.lean), which lists
the axioms every theorem in namespace `Rechnung` rests on.

```sh
make lean      # on the host; needs elan (https://github.com/leanprover/elan)
make beweise   # in Docker, nothing to install: the invoice image plus Lean, proofs rebuilt from scratch
```

The check fails if

- a proof is left open (`sorry`): every warning is an error (`lakefile.toml`),
- a theorem rests on anything but Lean's standard axioms (`propext`, `Classical.choice`, `Quot.sound`);
  this rules out `native_decide`, which trusts the compiler instead of the kernel.

The Lean version is pinned in [`lean-toolchain`](lean-toolchain); the container installs the same one.
No dependencies, no Mathlib.

## Names

The code and the rules are written in German, and the Lean model mirrors their names so that
`rules.py`, `RULES.md` and the proofs can be read side by side. Field names keep the Python spelling
(`kunde_ustid`, not `kundeUstid`). Theorems carry the rule ID: `R14_kleinunternehmer_weist_nie_steuer_aus`.

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
| `Basis`, `Pruefung` | basics, check |
