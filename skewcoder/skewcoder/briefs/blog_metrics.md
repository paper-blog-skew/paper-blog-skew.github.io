# Coder brief: blog METRICS

You are coding the metrics of ONE firm blog post. You code the blog on its own: you do not have, and must not look
for, the paper it reports on, any other coding, or anything outside this folder. The mapping onto the paper is a
later step you do not perform; links are a separate later pass on the list you produce.

## What you may read
- `blog.md` — the blog, one block per line with block ids.
- `candidates.json` — the mechanical candidate list you must account for (see Completeness).
- `missing_metrics.json` — only in append mode (see Append mode).
- `BRIEF.md` — this brief.

Vocabulary: **metric** = a dimension the blog treats as measurable, never a value. A setting a claim is stated
under (a processor, a model, a method, a regime) is a metric like any other. The blog and the paper are coded under
the same test for what counts as a metric (C2, C3 here; A3, A4 for the paper).

## Rules

- **C1 Find every metric first.** List every wording the blog uses for a dimension, whatever its importance:
  never leave one out as minor. A wording that looks like another name for a node you have already coded is its
  own node unless the blog joins them by a naming construction (C4). Never merge for meaning: conflation is done
  later with the viewer's metric boundary slider.
- **C2 Unit.** A blog metric is a dimension, never a value. "400 cells" is a value on *number of cells*; the
  value is recorded on the mention.
- **C3 Discerned.** A dimension noun inside a measurement frame is a blog metric. Frames, strongest first:
  scientific notation; number + unit noun ("2,880 charge cycles"); percent or fold ("100× faster"); scaling frame
  (grows with, scales as, the more X the less Y); measurement head (number of, cost of, rate of, time to, size of);
  degree-modified property (very high efficiency, low error, much faster); superlative achievement (largest to date,
  first ever); explicit naming (the metric of, a benchmark of); formula (the wording is defined by, or stands in, an
  equation: "where n is the number of cells"). Future tense and hedges (will, could, aims to,
  might, we expect) mark a sentence as not a measurement. For each mention record the frame and the matched span.
- **Family heads.** A generic head (scale, quality, speed, performance, benchmark, resource) is never a metric by
  itself: read the sentence for the dimension it names.
- **C4 One name, one metric.** Every distinct wording is its own node. Two wordings are one node only as
  mechanical variants (plural, hyphen, capitalisation) or on a naming construction in the blog, quoted in
  `naming_sentences` ("failure rate, which we also call the fault rate"). "Cycles" and "charges" are two nodes unless
  the blog says they are the same. A sentence relating two wordings by dependence never merges them. When in
  doubt, keep two nodes: lumping is a later reading choice, un-merging is not possible.
- **Settings.** A setting the blog states a claim under is a node like any other ("in our pilot plant, we …");
  its frame is `setting` with the clause that states the claim under it as the matched span. It carries no special flag, and its label has no category prefix (never "Model: …", "Platform: …").
- Every mention carries its verbatim quote (copied exactly from blog.md; 8 words or more where the sentence
  allows). The first mention is the one the site anchors on: make it the clearest.

## Completeness: `candidates.json`
`candidates.json` is a mechanical list of every phrase in the text that looks like a name for a measurable thing
(a measurement head such as cost, complexity, error, rate, time, size, depth, bound; and every "number of X"),
with its count, sections and up to three sentences. It decides nothing and
over-generates on purpose. Account for **every** candidate, one of three ways:
1. code it: a node whose label or a mention's matched span equals it (up to mechanical variants: case, plural, hyphen);
2. list it under `not_metrics` in your output file: `{"phrase": "<the candidate>", "reason": "…"}`. Good reasons:
   "a value on [x], not a dimension", "the word names an object, not a measure", "generic use, no dimension",
   "a hedge or future tense: not a measurement", "outside any measurement frame". The reason must be specific; "not relevant" or "minor" is not a reason;
3. exclude a whole section with a reason under `not_metric_sections`: `{"sections": ["7.1", "7.2"], "reason": "…"}`
   (a candidate is then accounted for only if all its occurrences lie in excluded sections).
The check fails on any candidate left unaccounted for. Do not code a metric just to clear a candidate: if it is
not a metric, say why.

## Append mode: `missing_metrics.json`
When this folder holds `missing_metrics.json`, you are not coding from scratch: `blog_metrics.json` is already coded
and the links coder needed a wording that is not on
the list. For each entry (`name`, `quote`, `note`):
- decide it under C1–C4 exactly as if you had met it in the first pass, reading the text around the sentence;
- if it is a metric, **append** it as a new node (new id, its mentions with quotes, frame and matched span); if the
  blog joins it to an existing node by a naming construction, add it to that node as a mention with its naming
  sentence (the only change allowed to an existing node);
- never change, rename, re-id or remove anything else already on the list;
- write `append_report.json`: `{"decisions": [{"name": "…", "decision": "added | name of <id> | not a metric", "id": "…", "reason": "…"}]}`,
  one row per entry.

## Output file (write in this folder)

`blog_metrics.json`
```json
{"_doc": "Blog metrics for <cite> under C1–C4. LLM-coded by Claude (<model>) on <date> from blog.md only; no paper was available to the coder. preimage is empty: mapping is a later step.",
 "not_metrics": [{"phrase": "lower cost", "reason": "a value (degree) on [cost], coded as a mention of that node"}],
 "blog_concepts": [
  {"id": "ncell", "label": "Number of cells", "class": "discerned", "preimage": [],
   "mentions": [{"quote": "Our new pack holds 400 cells in a single module", "source": "discerned", "frame": "S1 count: NUMBER + unit noun", "matched": "400 cells", "value": "400"}],
   "quote": "Our new pack holds 400 cells in a single module"}
 ]}
```
`id`: short lowercase ASCII, unique. `class` is `discerned` for every node. `quote` repeats the first mention's
quote. `naming_sentences` only where C4 case 2 applies.

## Check before you report
Run `bash check.sh`: every mention must locate and carry its frame, every id must be unique. Fix every
failure. Report: counts (metrics; mentions by frame; naming merges), the check result, and
every judgement call another coder might make differently (one line each). Do not paste the file.
