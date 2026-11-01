# Coder brief: paper METRICS

You are coding the metrics of ONE scientific paper. You code the paper on its own: you do not have, and must not
look for, the blog that reported on it, any other coding, or anything outside this folder. The paper's metrics
and names come from the paper's own words only. You do NOT code links in this pass; a separate coder does that
later, on the list you produce.

## What you may read
- `paper.md` — the paper, one block per line with block ids (`[p12]`), headings, numbered equations with TeX.
- `candidates.json` — the mechanical candidate list you must account for (see Completeness).
- `missing_metrics.json` — only in append mode (see Append mode).
- `BRIEF.md` — this brief.
Nothing else.

Vocabulary: **metric** = a dimension the paper treats as measurable, never a value. A setting a result is stated
under (a model, a method, a platform, a code, a task, a regime, a representation) is a metric like any other.
**name** = a symbol or a phrase the paper uses for a metric. The paper and the blog are coded under the same test
for what counts as a metric (A3, A4 here; C2, C3 for the blog).

## Rules

- **A1 Find every metric first.** List every wording the paper uses for a measurable thing in scope, whatever
  its importance: never leave one out as minor. A wording that looks like another name for a metric you have
  already coded ("running cost" beside "operating cost") is its own metric unless a naming construction joins
  them (A5 case 2). Never merge two wordings because they seem to mean the same thing: conflation by meaning is
  done later, by a reader, with the viewer's metric boundary slider, and it cannot be undone if you merge now.
- **A2 Scope.** Read the whole paper; its appendices and supplementary material have already been cut from
  `paper.md`. Record where each metric is named: `scope: "results"` when it is named in the abstract or in a numbered
  result statement (theorem, lemma, corollary, proposition, numbered equation); otherwise `"intro"`, `"prelim"` (a
  preliminaries section) or `"body"`, by where it is first named.
- **A3 Symbols.** Every symbol the paper defines and uses in a numbered equation or formula is a metric; the formula
  is its frame (`formula`). Exclude
  dummy indices (i, j, k, ℓ …) and objects that are only acted with, never measured (operators, matrices,
  transforms, functions applied to something). List every exclusion with its reason in `exclusions`. A
  property of an excluded object can be a metric (the cost of evaluating a function, the norm of a matrix), named by
  the symbol the paper writes for it.
- **A4 Frames.** A dimension named in words is a paper metric only inside a measurement frame. Frames, strongest
  first: scientific notation; number + unit noun ("2,880 charge cycles"); percent or fold ("100× faster"); scaling frame
  (grows with, scales as, the more X the less Y); measurement head (number of, cost of, rate of, time to, size of);
  degree-modified property (very high efficiency, low error, much faster); superlative achievement (largest to date,
  first ever); explicit naming (the metric of, a benchmark of); formula (the wording is defined by, or stands in, an
  equation: "where n is the number of cells"). Future tense and hedges (will, could, aims to, might, we expect) mark a sentence as not a
  measurement. For each name record the frame and the matched span in `alias_frames`. A setting's frame is `setting`,
  with the clause that states the result under it as the matched span. A setting the paper states a result under is a metric like any other, named by the
  paper's own words, with no special flag, and its `label` is the paper's own words with no category prefix (never "Model: …", "Method: …", "Regime: …"). Unit nouns (cells, cycles, samples) are not metrics; the *number of* them is.
- **Family heads.** A generic head (scale, quality, speed, performance, benchmark, resource) is never a metric by
  itself: read the sentence for the dimension it names.
- **A5 One name, one metric.** Every distinct wording is its own metric. Two wordings are one name of one metric
  only in two cases:
  1. **mechanical variants** of one wording: plural/singular, hyphen/space, capitalisation, and a symbol together
     with the phrase it is defined by ("the number of cells n": `n` and `number of cells` are one metric);
  2. a **naming construction** in the paper, quoted in `naming_sentences`: "X, which we refer to as Y", "X, denoted
     by Y", "we call X Y", "X (written Y)", "X, abbreviated Y". "That is" / "i.e." count only when they introduce
     a symbol or an explicit alternative wording.
  A sentence that relates two wordings by **dependence** ("X depends on Y", "X scales with Y", "X determines Y",
  "X is limited by Y", a formula F = 1 − e) NEVER makes them one metric: that is a link, coded by the links coder,
  and the two stay two metrics. When in doubt, keep two metrics: lumping is a reading choice made later by a
  semantic dial, and it cannot be undone if you merge now. So [cell failure rate], [failure rate] and [reliability] are
  three metrics unless the paper names one as the other.
- **A6 Quotes.** For each name, a verbatim sentence of the paper in which it occurs inside its frame (`alias_quotes`, copied
  exactly from paper.md, 8 words or more where the sentence allows). A symbol living only in equations is quoted
  from the sentence that introduces it ("where n is the number of cells"). A name you cannot quote is not a name;
  never invent a wording.
- **A7 First naming.** `named_in`: where the paper first names the metric (abstract / Thm 2 / §3.1 / p.2 …).
- One node per metric. Do not split a metric by its units or values. Do not merge what the paper keeps distinct.

## Completeness: `candidates.json`
`candidates.json` is a mechanical list of every phrase in the text that looks like a name for a measurable thing
(a measurement head such as cost, complexity, error, rate, time, size, depth, bound; and every "number of X"),
with its count, sections and up to three sentences. It decides nothing and
over-generates on purpose. Account for **every** candidate, one of three ways:
1. code it: a metric name equal to it (up to mechanical variants: case, plural, hyphen);
2. list it under `not_metrics` in your output file: `{"phrase": "<the candidate>", "reason": "…"}`. Good reasons:
   "a value on [x], not a dimension", "the word names an object, not a measure", "generic use, no dimension",
   "acknowledgements, not part of the paper's argument", "outside any measurement frame", "a hedge or future tense:
   not a measurement". The reason must be specific; "not relevant" or "minor" is not a reason;
3. exclude a whole section with a reason under `not_metric_sections`: `{"sections": ["7.1", "7.2"], "reason": "…"}`
   (a candidate is then accounted for only if all its occurrences lie in excluded sections).
The check fails on any candidate left unaccounted for. Do not code a metric just to clear a candidate: if it is
not a metric, say why.

## Append mode: `missing_metrics.json`
When this folder holds `missing_metrics.json`, you are not coding from scratch: `paper_quantities.json` is already
coded and a later coder (the links coder, or the mapping coder working from a blog) needed a wording that is not on
the list. For each entry (`name`, `quote`, `note`):
- decide it under A1–A7 exactly as if you had met it in the first pass, reading the text around the sentence;
- if it is a metric, **append** it (new key, its names with quotes, scope, named_in) and its display label; if it is
  a name of a metric already listed by a naming construction, add the name with its quote and naming sentence to
  that metric (the only change allowed to an existing metric is adding a name joined by a naming construction);
- never change, rename, re-key or remove anything else already on the list;
- write `append_report.json`: `{"decisions": [{"name": "…", "decision": "added | name of <key> | not a metric", "key": "…", "reason": "…"}]}`,
  one row per entry.

## Output files (write both in this folder)

1. `paper_quantities.json`
```json
{"_doc": "Paper metrics for <cite> under A1–A7. LLM-coded by Claude (<model>) on <date> from paper.md only; no blog was available to the coder.",
 "exclusions": ["dummy indices i, j, k", "operators acted with: H, U"],
 "not_metrics": [{"phrase": "lower bound", "reason": "generic use: 'a lower bound on X' is a value statement on X, not a dimension"}],
 "not_metric_sections": [{"sections": ["Acknowledgements"], "reason": "acknowledgements: funding statements, no measurement"}],
 "paper_quantities": [
  {"key": "n", "label": "Number of cells n", "kind": "symbol", "scope": "results", "named_in": "abstract",
   "aliases": ["n", "number of cells"],
   "alias_quotes": {"n": "where n is the number of cells in the pack", "number of cells": "where n is the number of cells in the pack"},
   "alias_frames": {"n": "formula: where n is", "number of cells": "measurement head: number of cells"},
   "naming_sentences": {"number of cells": "where n is the number of cells in the pack"}},
  {"key": "chem", "label": "Cell chemistry", "kind": "phrase", "scope": "body", "named_in": "§2",
   "aliases": ["lithium iron phosphate chemistry"], "alias_quotes": {"lithium iron phosphate chemistry": "…"},
   "alias_frames": {"lithium iron phosphate chemistry": "superlative achievement: the highest cycle life of any chemistry"}}
 ]}
```
   `key`: short lowercase ASCII, unique; the symbol where there is one. `kind`: `symbol` / `phrase`. Every alias
   has its quote and its frame. `naming_sentences` has an entry for every alias after the first: the sentence that makes it the
   same name (a mechanical variant may reuse the alias quote).
2. `display_labels.json` — `{"_doc": "Display-only labels.", "labels": {"n": "$n$", "cost": "operating cost"}}`: TeX in
   `$…$` for symbols, 2–3 plain words for phrases.

## Check before you report
Run `bash check.sh`. It locates every quote, checks that every name has a frame, and checks every key. Fix every failure; do not weaken a rule to
pass. Then report: counts (metrics by scope and kind, names, naming merges), the check result, and
every judgement call another coder might make differently (one line each). Do not paste the files.
