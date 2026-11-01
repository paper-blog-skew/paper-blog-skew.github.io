# Coder brief: MAPPING blog metrics onto paper metrics

You are the mapping coder for ONE paper–blog pair. Both codings are frozen. Your job is the one step that needs
both: for each blog metric, say which paper metric(s) it stands for (its **preimage**), and add the blog metrics
that the paper's own names reveal. You may not change anything under `paper/`, and you may not change
`blog_links.json`.

## What you may read
- `map_candidates.json` — every paper name found in the blog text by the loosened matcher, laid beside the blog
  coder's mentions (mechanical, no decisions), plus the paper's metric list.
- `paper/paper_quantities.json`, `paper/display_labels.json` — the paper's metrics and names. Read only.
- `blog_metrics.json` — the blog's nodes; you rewrite this file in place. `blog_links.json` — read only.
- `blog.md`, `paper/paper.md` — the two texts.
- `BRIEF.md` — this brief.

## Rules

- **By name.** A mapping is "by name" when one of the paper's names for the metric occurs in one of this node's
  own mention sentences. Record it in `alias_used[key] = <the paper's name as the blog uses it>`. That word must
  occur in the node's mentions, not merely somewhere in the blog.
- **Recovered, one rule for every hit.** For every paper-name hit in the candidates file:
  - if a coded node already covers that sentence (same dimension), add the paper metric to its `preimage`, set
    `alias_used`, and its `class` becomes `both`;
  - if a coded node exists for that dimension but not for that sentence, **append the sentence as a recovered
    mention** of that node (`source: "recovered"`, `alias_used`) and map it;
  - if no node covers the dimension and the blog uses the name as a dimension, **add a node** with
    `class: "recovered"`, `id: "r_<key>"`, a label in the blog's words, the sentence as its mention, the paper
    metric as its preimage;
  - if the name is used only incidentally ("time" in "at the same time"), list it under `rejected_hits` with the
    reason.
  A recovered mention or node passes the same test as any metric: the name sits inside a measurement frame in that
  sentence (the frames of the metrics briefs), and the sentence is not future tense or hedged. Record its `frame` and
  `matched` span. A hit outside any frame, or in a hedged sentence, goes to `rejected_hits` with that reason; a hit
  in a sentence a coded node already covers is mapped as above.
- **Which paper metric.** Judge by what the blog sentence measures, not by the word alone. A blog word the paper
  uses for a setting (a model, a method, a platform) maps to that metric.
- **Several paper metrics.** A blog node may stand for two or more paper metrics; list them all and add
  `preimage_note`: *bundle* (the blog names each component and treats them as one dimension), *nested* (one paper
  metric is an instance of the other) or *unsure* (the text does not settle which), the last also setting
  `"preimage_unsure": true`. This is a mapping judgement, not a merge: the paper's metrics stay separate.
- **By name only; no inferred mappings.** Map a blog node to a paper metric only when
  one of the paper's names for that metric occurs in one of the node's own mention sentences (`alias_used`). Never
  map because the blog's wording "plainly measures the same thing" under other words: a blog metric may refer to
  something wholly outside the paper, and folding a blog metric into its nearest paper metric is a reading choice
  made in the viewer with the mapping granularity slider, never by you. Do not set `"mapping": "inferred"`.
- **Missing paper metrics.** When the blog's wording for a node (or a variant of it) occurs in the
  **paper** text but no paper metric on the frozen list carries that name ("asymptotic cost" written in the paper,
  not coded), do not map the node to a near paper metric. Report it in `mapping_report.json` under
  `missing_metrics`: `name` (the paper's wording, verbatim), `quote` (a verbatim sentence of **paper.md** that uses
  it; the check locates it in the paper), `note` (the blog node id and its mention). A paper metrics-append pass
  decides it; if it is added, the mapping re-runs.
- **Empty preimage.** A blog metric with no by-name counterpart keeps `preimage: []` and `class: "discerned"`. That
  is a finding, not a failure.
- Do not change the blog coder's ids, labels, mentions or quotes (you may only append recovered mentions). You
  may add: `preimage`, `alias_used`, `class`, `mapping`, `mapping_note`, `preimage_note`, `preimage_unsure`,
  recovered mentions and nodes, `rejected_hits`, and your sentence in `_doc`.

## Output
Rewrite `blog_metrics.json` in place, and write `mapping_report.json`:
`{"missing_metrics": [{"name": "…", "quote": "<paper sentence>", "note": "…"}], "rejected_hits": [...]}` (empty lists
when there are none). Append to `_doc`: "Mapping (by name / recovered) LLM-coded by
Claude (<model>) on <date> with both codings frozen."

## Check before you report
Run `bash check.sh`: every mapping must be by name (alias_used, a paper name, in the node's own mentions); no
`mapping: "inferred"`; every quote must locate (missing-metric quotes in the paper); every key must exist. Fix every failure. Report: counts (nodes before/after;
with a preimage, of which unsure; missing paper metrics reported; recovered mentions and nodes; rejected hits), the check
result, and every judgement call (one line each).
