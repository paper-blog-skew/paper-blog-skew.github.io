# Coder brief: blog LINKS

You are coding the links of ONE firm blog post whose metrics are already coded and frozen. You code from the blog
alone: no paper, no other coding, nothing outside this folder. You may only join nodes on the frozen list, by
their ids. You must not edit `blog_metrics.json`. A link whose end is not on the list is reported under
`missing_metrics`, not coded, and no id is stretched to cover it. Each entry: `name` (the blog's wording,
verbatim), `quote` (the verbatim sentence that needs it; the check locates it), `note` (the listed node it would
link to). A metrics-append pass decides each and, if a node is added, this pass re-runs on the appended list.

## What you may read
- `blog.md` — the blog, one block per line with block ids.
- `blog_metrics.json` — the frozen nodes: `id`, `label`, `kind`, `mentions`. Read only.
- `BRIEF.md` — this brief.

## Rules

- **D1 Edge.** One sentence that joins two listed nodes with an explicit connective (depends on, scales with,
  limited by, requires, as X grows Y falls, determines, because of, the more X the less Y, bounded by, leads to,
  allows, enables … to) is an edge, directed as the sentence states it (source = the cause or the thing varied,
  target = what changes). Two nodes in one sentence with no connective are not an edge. A naming sentence ("X,
  which we also call Y") is not an edge. Quote the clause that carries the connective. A sentence stating
  independence is kept with `polarity: "negated"`.
- **Polarity** is `positive` or `negated`, nothing else.
- **Condition.** If the link is stated under a condition the blog names (a processor, a regime, "for packs
  beyond N cells"), record `condition`, `condition_quote` and `condition_vars` (node ids the condition names).
- **D2 Non-metric explanations.** A sentence that explains a metric by something that is not a metric ("because
  the casing is made of steel") goes under `nonmetric_explanations` in the report, not as an edge.
- Do not type the edge against the paper (no faithful / collapsed / invented): you have not seen the paper. No
  `type` field.
- One edge per ordered pair; every further sentence stating the same edge goes in its `quotes` list.

## Output files (write both in this folder)

1. `blog_links.json`
```json
{"_doc": "Blog links under D1–D2. LLM-coded by Claude (<model>) on <date> from blog.md and the frozen node list only.",
 "blog_edges": [
  {"source": "ncycle", "target": "cap", "quote": "The more charge cycles, the lower the capacity", "connective": "the more … the lower", "polarity": "positive", "quotes": ["The more charge cycles, the lower the capacity"]}
 ]}
```
2. `blog_links_report.json` — `{"nonmetric_explanations": [{"metric": "ncell", "quote": "…", "note": "…"}], "missing_metrics": [{"name": "…", "quote": "…", "note": "…"}]}`.

## Check before you report
Run `bash check.sh`: every quote must locate, both ends must be listed ids, polarity positive or negated, no
`type`. Fix every failure. Report: counts (edges; negated; conditioned; non-metric explanations; missing metrics),
the check result, and every judgement call (one line each).
