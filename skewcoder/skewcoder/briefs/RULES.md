rule_version: 1.1

# The coding rules

Every coding step is done by a language model following one brief in this folder; the brief is its system prompt.
This page states the rules those briefs share and lists where each numbered rule lives. Every run records the
`rule_version` above and the hash of the brief it ran under. When a rule changes, every text is coded again from
scratch; nothing is patched forward.

## The briefs

| step | brief | rules |
|---|---|---|
| paper metrics | `paper_metrics.md` | A1–A7 |
| paper links | `paper_links.md` | B1–B3 |
| paper equations as formulas | `paper_algebra.md` | B4–B6 |
| blog metrics | `blog_metrics.md` | C1–C4 |
| blog links | `blog_links.md` | D1–D2 |
| mapping (blog metrics onto paper metrics) | `mapping.md` | unnumbered |
| definitions (either side) | `definitions.md` | unnumbered |

## Rules every step follows

- **Separation.** The paper is coded with the blog closed, and the blog with the paper closed. Only the mapping step
  sees both, and by then both codings are frozen. No blog word may enter a paper file.
- **Metrics first, then links.** Metrics are coded first and frozen. Links are coded in a separate pass that may only
  join metrics already on the list. Nothing in the links pass may change the metric list, and no link may make two
  metrics one.
- **Find every metric, in the whole text.** The coder reads the whole paper or blog (a paper's appendices are cut
  first) and lists every wording that names a measurable thing, however minor, and however much it looks like another
  name for a metric already coded. Every paper is read the same way, whatever its kind.
- **One test for a metric, on both sides.** A wording is a metric only inside a measurement frame (scientific
  notation, number + unit noun, percent or fold, scaling frame, measurement head, degree-modified property,
  superlative achievement, explicit naming, formula), or as a setting a claim is stated under; a future-tense or
  hedged sentence is not a measurement; a generic head (scale, quality, speed, performance) is never a metric by
  itself. Paper rules A3–A4 and blog rules C2–C3 state
  the same test, every name or mention records its frame, and the audit fails on one without.
- **One name, one metric.** Every distinct wording is its own metric. Two wordings are one name only (i) as mechanical
  variants of one wording (plural, hyphen, capitalisation, a symbol with the phrase it is defined by), or (ii) on a
  **naming construction** in the text, quoted: "X, which we refer to as Y", "denoted by", "we call", "written as",
  "abbreviated". A **dependence construction** ("depends on", "scales with", "determines", any formula) never merges
  two wordings: it is a link. Whether two metrics are "really one" is a reading choice made in the viewer with the
  metric boundary slider, never by the coder.
- **Completeness is checked.** Each metrics step receives a mechanical list of every phrase with a measurement head
  (cost, complexity, error, rate, time, size, depth, bound, …) and every "number of X". The coder codes each candidate or lists it under `not_metrics` with a specific
  reason; whole sections may be excluded with a reason. The audit fails on any candidate left unaccounted for.
- **Every row carries its quote.** A name, a mention, a link, a condition: each comes with a verbatim sentence that
  the audit locates in the text. A name that cannot be quoted is not a name.
- **Polarity** is `positive` or `negated`, nothing else.
- **Settings are metrics.** A setting a result is stated under (a model, a method, a platform) is a metric like any
  other, and a link to it is a link like any other.
- **Missing metrics.** A links coder, or the mapping coder, that needs a metric not on the frozen list reports it
  with its sentence and does not add it. A metrics-append pass decides each report under the metrics rules and may
  only add metrics; the links pass then runs again, and after a paper append every mapping of that paper runs again.
  One round of each loop.
- **Mapping is by name only.** A blog metric is mapped onto a paper metric only when one of the paper's names for it
  occurs in that blog metric's own sentences. A blog metric with no such name keeps an empty mapping: it may refer to
  something outside the paper. Folding an unmapped blog metric into its nearest paper metric is a reading choice made
  in the viewer with the mapping slider.
- **Definitions.** Once the metrics are frozen, each side's coder writes one definition per metric from its own text
  only: what is measured, of what, in what unit; never what it depends on, and never another metric's name.
- **Equations are reduced mechanically.** The model writes each equation as a formula in the paper's metrics, or
  marks it as not an equality and lists the pairs it makes dependent. The computer then removes redundant equalities
  (Gröbner basis, Buchberger's algorithm; for equalities with exp, log or trigonometric functions, whether the rank
  rises), counts the independent ones (the rank), and links two metrics when they sit in a common minimal linked
  group, reporting the size of the smallest (`skewcoder/algebra.py`). Equations under different stated conditions
  are reduced separately.
- **Appendices are not coded.** A paper's appendices and supplementary material are cut before any step reads it.
- **Mark, never delete.** Exclusions, uncoded equations, rejected matches and missing metrics are listed with a
  reason, never dropped silently.
