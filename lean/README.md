# Verification: what is proved, what is tested, what is assumed

This is the English entry point to how the invoice tool's tax decisions are checked. The tool itself,
its code and [`RULES.md`](../RULES.md) are written in German; this file explains the whole chain from
the law to the PDF, says for each link how far it can be trusted, and shows how to reproduce every
check. The second half describes the Lean 4 model in this folder. Writing invoices never needs Lean.

## In one paragraph

No AI decides anything about tax. A small rule core in Python, `rules.kern()`, decides the place of
supply, the VAT treatment and which statements an invoice must carry. A Lean 4 model of that core is
proved to follow the documented rules (27 statements, all proved, Lean's standard axioms only), and
the Python core gives the same answer as the model on every one of its 3456 possible inputs. The rules
themselves are reasoned readings of the German VAT Act; no tax advisor has reviewed them yet. The
facts that go in (is the customer a business, how is the service classified) are entered by a person
or an AI and are not checked by anything. All of this is stated per rule and, with
`rechnung begruendung`, per invoice.

## The chain

| Link | What it is | How it is secured | What you have to trust |
| --- | --- | --- | --- |
| Law → `RULES.md` | rules R1…R38 in plain German, with the wording of the law and a status per rule | not provable; meant to be reviewed by a tax advisor, **not done yet** – every rule is "Annahme – ungeprüft" (assumption, unreviewed) | the reading of the law |
| `RULES.md` → Lean statements | one statement per rule, same ID, in [`Rechnung/Aussagen.lean`](Rechnung/Aussagen.lean) | read side by side; each rule in `RULES.md` names its statements (`Nachweis:`), a test keeps both lists equal | the person reading them |
| Lean statements → Lean model | the decision as Lean definitions | **proved**, each statement by a theorem of exactly its type; each statement with hypotheses has an example where they all hold | Lean's kernel and its three standard axioms |
| Lean model → `rules.py` | `rules.kern()` and `rules.satz_position()`, the code that runs | **compared on every input** (3456 and 8), plus the classification table (17 words); not a proof | Lean's compiler, which computes the model's answers (`#eval`), and pytest |
| Country code → category | which country is Germany, EU, non-EU | **tested** (EU list dated, known pitfalls GB, CH, NO …); unknown codes are refused, not guessed | the list in `rules.py` |
| Data → facts | customer's country, business status, classification of the service | **assumed**; each assumption is a field of `Passt` in [`Rechnung/Bruecke.lean`](Rechnung/Bruecke.lean) with its rule ID | whoever entered the data |
| Amounts, numbers | net, VAT, total, rounding, invoice numbers | **tested**, not modelled | the tests |
| `rechnung.resolved.json` → PDF | the printed invoice | **checked**: `rechnung pruefen` finds every mandatory statement in the text of the PDF | `pdftotext` and the check list in `pruefen.py` |

Each rule in `RULES.md` carries two separate labels: its **status** (does the rule state the law
correctly? – nobody has confirmed that yet) and its **proof level** (`Nachweis`: does the tool do what
the rule says? – `bewiesen` proved, `getestet` tested, `im PDF geprüft` checked in the PDF, `keiner`
none, with the reason).

## Trust base

- **Proofs:** the Lean kernel, and only `propext`, `Classical.choice`, `Quot.sound`. No `sorry` (every
  warning is an error), no `native_decide`. `Pruefung.lean` checks this for every theorem.
- **Comparison:** the model's answers in [`abgleich/kern.json`](abgleich/kern.json) are computed by
  Lean's compiler, not checked by the kernel. That the list of inputs is complete *is* proved.
  pytest then holds the Python code against the file.
- **Inputs:** everything in `Passt`. A proof says "if the data describe the facts, the tool decides as
  the law does"; it cannot say that the data describe the facts.
- **Scope:** services (not goods), issuer based in Germany, no special territories, no financial
  services; `RULES.md` part 1 lists what is out. Where the tool can tell that a case is out of scope
  (issuer abroad, a private customer with place of supply in another EU state, missing data) it refuses
  instead of deciding. Whether a case is in scope at all – a service, not a supply of goods, for
  instance – is part of what is entered.

## Reproduce

Nothing to install but Docker:

```sh
git clone https://github.com/athki/ai-e-rechnung.git && cd ai-e-rechnung
make beweise                # builds the invoice image, then Lean on top; rebuilds every proof,
                            # checks axioms and examples, compares abgleich/kern.json with the model
```

With Python ([uv](https://docs.astral.sh/uv/)) on the host, the comparison and one invoice's reasoning:

```sh
uv sync
uv run pytest -q tests/test_abgleich.py tests/test_begruendung.py   # no Lean, no LaTeX needed
uv run rechnung demo                                                 # six sample invoices (needs LaTeX)
uv run rechnung begruendung demo-output/nicht-steuerbar-sample-ltd
```

Without LaTeX, `docker run` does the same: build the image (`docker build -t rechnung .`), then
`docker run --rm -v "$PWD/probe":/gewerbe rechnung demo --ziel /gewerbe/demo` and
`docker run --rm -v "$PWD/probe":/gewerbe rechnung begruendung /gewerbe/demo/nicht-steuerbar-sample-ltd`.
`make schatten` runs all of it, both containers, as the project does before every commit.

## One invoice, end to end

`rechnung begruendung <invoice>` prints, in German, why an invoice says what it says: the facts it
was decided on (and where each comes from), every rule that was applied in order, with its legal
source, its wording, its assumptions, its status and its proof level, and what is assumed, proved and
tested. It decides nothing itself; it reads the frozen `rechnung.resolved.json` and `RULES.md`, and
checks that the rule core still reaches the same decision on the same facts. An excerpt for the sample
invoice to a UK company for a panel appearance in London:

```markdown
# Begründung der Steuerentscheidung – Rechnung DEMO-2026-0003

- **Kunde:** Sample Ltd (GB)
- **Ergebnis:** `nicht_steuerbar`
- **Leistungsort:** GB (Vereinigtes Königreich), Sitz bzw. Wohnsitz des Kunden (R3)
[…]
- **Spur:** geprüft – `rules.entscheide()` kommt auf denselben Fakten heute zu derselben Entscheidung.

## Fakten

Angegeben von Mensch oder AI, vom Werkzeug nicht geprüft. […]

| Angabe | Herkunft | Wert | Das Werkzeug liest daraus |
| --- | --- | --- | --- |
| Land des Kunden | `kunden/sample-ltd.yaml: land` | GB | Drittlandsgebiet (R1) |
| Unternehmer | `kunden/sample-ltd.yaml: unternehmer` | ja |  |
| Einordnung | `rechnung.yaml: leistung.einordnung` | unterrichtend | Tätigkeitsleistung, § 3a Abs. 3 Nr. 3 UStG |
[…]

### 3. R3 – Leistung an einen Unternehmer: Sitz des Empfängers

- **Quelle:** Q3 (§ 3a Abs. 2 Satz 1 UStG); für EU-Kunden auch Q7 (Art. 44 MwStSystRL).
- **Regel:** Ist der Empfänger ein Unternehmer, der die Leistung für sein Unternehmen bezieht, liegt
  der Leistungsort dort, wo er sein Unternehmen betreibt – unabhängig von der Leistungsart.
- **Annahmen:** […]
- **Status:** Annahme – ungeprüft.
- **Nachweis:** bewiesen – `Aussage.R3_unternehmer_sitz_des_kunden`, `Aussage.R3_R8_eindeutig`.
[…]
```

In words: the customer is a business (`unternehmer: ja`) based outside the EU, so under § 3a (2) the
place of supply is the UK (R3), the service is not taxable in Germany, and the invoice carries no
German VAT but a statement naming the place of supply (R31). That the tool applies R3 as written is
proved for the model and compared for the code; that R3 reads the law correctly is an unreviewed
assumption; that the customer is a business is what someone entered.

## What is not shown, and open problems

- **What is general and what is finite.** The law level quantifies over every assignment of countries
  to Germany / EU / non-EU (`Gebiete` is a parameter, with exactly one Germany), so its statements
  hold for any such world, not just today's EU. The tool level is finite: `kern()` has 3456 inputs,
  which is why an exhaustive comparison with Python is possible at all. The substance is in the law
  level and in `Passt`, not in enumerating the cases.
- **Not modelled:** amounts and rounding, invoice numbers, the country list, the PDF. They are tested
  or checked, as the table above says.
- **Not provable:** that `RULES.md` states the law correctly, and that the data entered are true.
- **Open, and inviting:** proofs over unbounded domains – that VAT per rate is net × rate and the total
  is net plus VAT for every list of positions, that no invoice number is issued twice given the folder
  rules; and a comparison whose expected answers are checked by the kernel (a `decide`d table) instead
  of computed by `#eval`. Neither is built.

---

**The rest of this file is about the Lean model itself.**

**Status (step 8.7): all 27 statements are proved, each by a theorem of the same name, and each has an
example showing that its hypotheses can hold. `rules.kern()` and `rules.satz_position()` give the same
answer as the model on every possible input.** That last part is an exhaustive comparison, not a proof;
see [Comparison with the Python code](#comparison-with-the-python-code).

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
