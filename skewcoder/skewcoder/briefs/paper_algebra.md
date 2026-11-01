# Coder brief: paper EQUATIONS as formulas

You are writing the equations of ONE paper as formulas a computer can reduce. The paper's metrics and its links are
already coded and frozen. You do not decide which metrics are linked: you write down what each equation states, and
the reduction (redundancy, rank, minimal linked groups) is done mechanically afterwards.

## What you may read
- `paper.md` — the paper, one block per line with block ids; numbered equations appear with their numbers.
- `paper_quantities.json` — the paper's metrics (frozen): each `key` with its names and symbols.
- `relations.html` — the equation relations (frozen): one `<template>` per relation, with `data-id`, `data-eq` (the
  equation numbers) and `data-vars` (the keys of the metrics the relation contains).
- `BRIEF.md` — this brief.

## Rules

- **B4 One entry per relation.** For every relation in `relations.html`, write one entry with its `rel` id and a
  list of `statements`. Every equation number in the relation's `data-eq` has at least one statement. An equation
  number that holds several equalities (aligned lines, a chain a = b = c) gets one statement per equality.
- **B5 Equalities.** A statement that is an equality between scalar quantities has `"kind": "equality"`, with `lhs`
  and `rhs` written in Python syntax:
  - symbols: the metric keys from the relation's `data-vars`, used as plain names, and auxiliary symbols;
  - an **auxiliary symbol** is a quantity the equation needs that is not one of the paper's metrics (an
    intermediate variable, an unnamed constant). Declare each one once under `aux`, with what it is and the quote
    that names it. Use one name per quantity across the whole paper, so two equations about the same intermediate
    quantity share it. A number the paper gives (2, 1/2, π) is written as a number, never as a symbol;
  - operations: `+ - * / **`, `sqrt`, `exp`, `log`, `sin`, `cos`, `tan`, `pi`, `imag_unit` (the imaginary unit), and numbers. Nothing
    else. A metric key is always read as that metric, even when it looks like a constant (`I`, `E`, `N`).
  - Write what the equation states, exactly. Never add a relationship the paper does not state (no physical law
    from outside the paper, no definition the paper does not give), and never replace an equation by a consequence
    of it. A definition the paper states ("we define x as …", ":=") is an equality.
- **B6 Not algebraic.** Every other statement has `"kind": "not algebraic"` and a short `reason`: an inequality or
  bound; a big-O, Θ, Ω, ≈ or ∼ statement; a sum, product or integral whose range depends on a metric; a limit; a
  statement about operators, matrices or states; an expectation value; a probability distribution. For it, list
  under `pairs` every pair of the relation's metrics that the statement makes depend on each other, in your
  reading, and under `independent` any pair it states to be independent. A pair you do not list is not linked by
  this statement. When an operator statement contains an explicit scalar equality between listed metrics (a
  rotation angle written as a product of two metrics), that equality may be given as its own `equality`
  statement, with a `note` saying where it sits.
- Every metric key you use must be in that relation's `data-vars`. A metric in `data-vars` that the equation does
  not actually contain is left out, with a `note` on the relation saying why.

## Output file (write in this folder)

`equations.json`
```json
{"_doc": "Equations as formulas under B4–B6. LLM-coded by Claude (<model>) on <date> from paper.md, with metrics and relations frozen.",
 "aux": {"F": {"meaning": "the drag force on the vehicle", "quote": "where F is the drag force"}},
 "relations": [
  {"rel": "R1", "statements": [
    {"eq": 1, "kind": "equality", "lhs": "E", "rhs": "m*v**2/2"},
    {"eq": 2, "kind": "equality", "lhs": "P", "rhs": "F*v"}]},
  {"rel": "R2", "statements": [
    {"eq": 3, "kind": "not algebraic", "reason": "upper bound", "pairs": [["range", "cap"], ["range", "load"]], "independent": []}],
   "note": "temp is listed in data-vars but the bound does not contain it"}
 ]}
```

## Check before you report
Run `bash check.sh`: every relation and every equation number must be covered, every formula must parse, every
symbol must be a key of that relation or a declared auxiliary symbol, every pair must use the relation's keys.
Fix every failure. Report: counts (relations; statements by kind; auxiliary symbols), the check result, and every
judgement call another coder might make differently (one line each). Do not paste the file.
