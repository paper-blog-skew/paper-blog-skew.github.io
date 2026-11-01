# Coder brief: paper LINKS

You are coding the links of ONE scientific paper whose metrics are already coded and frozen. You code from the
paper alone: no blog, no other coding, nothing outside this folder. You may only join metrics that are on the
frozen list, by their keys. You must not edit `paper_quantities.json`. If a link needs a metric that is not on the
list, you do not add it and you do not stretch another key to cover it: you report it under `missing_metrics`.

## What you may read
- `paper.md` — the paper, one block per line with block ids.
- `paper_quantities.json` — the frozen metric list: `key`, `label`, `aliases`. Read only.
- `BRIEF.md` — this brief.

Vocabulary: **link** = a statement that two metrics depend on each other; **relation** = a link stated by a
numbered equation; **prose link** = a link stated in a sentence; **condition** = the regime a link holds under.

## Rules

- **B1 Equations.** Every numbered equation (definitions included) is a constraint on the metrics it contains.
  Code a relation for every numbered equation, or a tight group of consecutive numbered equations stating one
  result, that contains **two or more** listed metrics. Every numbered equation appears either in some relation's
  `data-eq` or in `uncoded_equations` with a reason (fewer than two listed metrics; a proof step that only
  rearranges; an operator identity). Inequalities, big-O statements, expectation values, operator statements are
  coded the same way: they link the metrics they contain; your reading goes in the relation's note.
- **B2 Attachment sentence.** For a metric named only in words that you list in an equation's `data-vars`, give
  in `relation_leads.json` the sentence near the equation that attaches the name to it ("where ε is the target
  accuracy"); a theorem or lemma heading counts.
- **B3 Prose links.** A sentence that joins two listed metrics with an explicit connective (depends on, scales
  with, limited by, requires, as X grows Y falls, determines, because of, bounded by, within error, to within a
  precision of, the more X the less Y) is a prose link: one row per (sentence, pair), whole paper. Two metrics
  in one sentence with no connective are not a link. A naming sentence ("X, which we call Y") is not a link
  either: it is a name, already handled by the metrics coder. A statement of independence ("the memory does not
  depend on the run time") is kept with `polarity: "negated"`. Quote the clause that carries the connective.
- **Polarity** is `positive` or `negated`, nothing else, on every row and every relation.
- **Condition.** When the statement holds only under a stated regime (a parameter range, a theorem hypothesis, a
  case split, a model, a method), record `condition` (your words), `condition_quote` (verbatim),
  `condition_where` (block id, theorem or section), and `condition_vars`: the keys of the listed metrics the
  condition names, including the metric for the setting when the condition is "stated under" a model, a method or a platform. A
  section-level setting says so ("§4 setting" / "Methods setting").
- **Missing metrics.** A link whose end is a measurable thing not on the list goes to `missing_metrics`:
  `name` (the paper's wording, verbatim), `quote` (the verbatim sentence that needs it; the check locates it) and
  `note` (which listed metric it would link to). The link itself is not coded now. A metrics-append pass decides
  each entry and, if it is added, this links pass re-runs on the appended list. Never invent a key, never reuse a
  near key, and never treat the wording as another name for a listed metric: that is the metrics coder's decision.

## Output files (write all four in this folder)

1. `relations.html` — one `<template>` per relation inside `<div hidden id="rels"> … </div>`:
```html
<template data-id="R1" data-eq="(1)" data-vars="E m v" data-source="equation" data-polarity="positive" data-cond="stated under: model" data-cond-vars="model" data-cond-quote="We model the vehicle as a point mass on a flat road" data-cond-where="p5">
<span class="t">Kinetic energy of the vehicle</span>
$$E = \tfrac{1}{2} m v^2$$
<p>Your reading, one or two sentences. Use \lt and \gt, never raw < or > inside maths.</p>
</template>
```
   `data-eq`: `(7)`, `(7),(9)` or `(7)-(9)`; `data-vars`: keys only; `data-cond*` only when conditioned.
2. `paper_prose_links.json`
```json
{"_doc": "Prose links under B3. LLM-coded by Claude (<model>) on <date> from paper.md and the frozen metric list only.",
 "paper_prose_links": [
  {"id": "P1", "section": "abstract", "scope": "abstract", "quote": "the driving range is limited by the energy density of the cells", "connective": "limited by", "a": "range", "b": "dens", "polarity": "positive",
   "condition": "stated for cells at room temperature", "condition_quote": "for cells kept at room temperature", "condition_where": "p1", "condition_vars": ["temp"]}
 ]}
```
   `scope` ∈ abstract / intro / prelim / body. Ids unique. Add `"note"` where a reader needs it.
3. `relation_leads.json` — `{"_doc": "Attachment sentences (B2).", "leads": {"R1": [{"var": "eps", "eq": 7, "quote": "where ε is the target accuracy"}]}}` (may be `{"leads": {}}`).
4. `paper_links_report.json` — `{"uncoded_equations": [{"eq": 12, "reason": "…"}], "missing_metrics": [{"name": "…", "quote": "…", "note": "…"}]}`.

## Check before you report
Run `bash check.sh`: every quote must locate, every key must exist, every numbered equation must be covered,
polarity must be positive or negated. Fix every failure. Report: counts (relations, uncoded equations, prose rows
by scope, conditioned, negated, missing metrics), the check result, and every judgement call (one line each).
