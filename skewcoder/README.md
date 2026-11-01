# skewcoder — code a paper and the blog post about it

Give it a scientific paper, the firm blog post written about it, or either one alone. It rebuilds each text, codes
every **metric** each text names and every **link** each text states between two metrics (the paper with the blog
closed, the blog with the paper closed), maps the blog's metrics onto the paper's by name, and checks every row against
the text. Everything it writes carries a verbatim quote; a quote that cannot be found in the text is a failure, not a
row. The result is one **bundle**: everything the [skewsite](../skewsite) viewer shows.

The coding is done by a language model (Claude), one sandboxed session per step, under written rules (`skewcoder/briefs/`).
Rule set in force: `rule_version` at the top of `skewcoder/briefs/RULES.md`.

## Install

```
pip install -e .                    # text rebuild, audit, bundles (beautifulsoup4, lxml, PyMuPDF)
pip install -e '.[api]'             # to run the model through the Anthropic API
pip install -e '.[similarity]'      # scores for the viewer's sliders (sentence-transformers; ~400 MB model, fetched once)
```
or run from a checkout without installing: `python3 skewcoder.py <command> …`.

## Run

```
skewcoder run --workspace work --paper 2211.09133 --blog https://…/blog/post/
skewcoder run --workspace work --paper https://…/paper.pdf            # a paper alone: coded, no map
skewcoder run --workspace work --blog  saved_page.html                # a blog alone
```
`run` fetches the inputs, rebuilds the texts, codes each side, maps the blog onto the paper (only when both are given),
writes one definition per metric, scores similarity and writes `work/bundles/<id>/`. Steps whose outputs exist are
skipped, so a run that stopped can be started again.

Many pairs at once: `skewcoder batch work/pairs.json --bundles work/bundles` (`pairs.json`: `{"pairs": [{"id", "paper":
"papers/<key>", "blog": "blogs/<key>"}]}`; either side may be left out).

### Which model runs, and who pays

| `SKEWCODER_BACKEND` | how | needs |
|---|---|---|
| `cli` (default) | the Claude Code CLI, headless (`claude -p`) | Claude Code installed and logged in; runs count against that account |
| `api` | the Anthropic API directly | `ANTHROPIC_API_KEY`; `pip install -e '.[api]'` |

`SKEWCODER_MODEL` picks the model (default Opus). Each step's record (`<unit>/runs/<step>_<time>/run.json`) keeps the
backend, the model actually used, token usage (and cost where the CLI reports it), the brief's hash, the rule version,
the audit result and the coder's own report. A long paper is a long session: an hour or more per step is normal.

### Inputs

| input | what is used |
|---|---|
| arXiv id or link | the LaTeX source (numbered equations kept as TeX); the PDF if arXiv holds no source |
| a PDF (file or link) | its text; numbered equations are cropped as images (add their TeX in `sources/equations.json` to have them read) |
| a blog link, saved `.html` or `.pdf` | the article text; if the page runs on into other posts, set `source.html_stop` in `unit.json` |

Citation fields come only from arXiv's API or the page's own meta tags; anything else is left blank to fill by hand.
Appendices and supplementary material are cut from papers before coding (`keep_appendices` / `appendix_from` in `unit.json`).

## Steps, one at a time

| command | what | who |
|---|---|---|
| `fetch paper\|blog <source> --workspace W` | make a unit folder (`unit.json` + `sources/`) | script |
| `text <unit>` | rebuild the text as blocks with ids | script |
| `candidates <unit>` | every wording that looks like a metric; the coder must code or reject each | script |
| `metrics <unit>` | code the metrics | model |
| `links <unit>` | code the links; may only join metrics already coded | model |
| `define <unit>` | one definition per metric | model |
| `algebra <paper> [--reduce-only]` | write the equations as formulas, then reduce them: redundancy, rank, minimal linked groups | model, then script |
| `map <blog> --paper <paper>` | map the blog's metrics onto the paper's, by name only | script + model |
| `audit <unit> [--paper P]` | the gates; exit 1 on failure | script |
| `similarity <unit> [--paper P]` | scores for the viewer's metric-boundary and mapping sliders | script |
| `bundle --out DIR [--paper P] [--blog B]` | the viewer's data in one folder | script |
| `serve --workspace W` | a job server a website can send texts to (`server.py`) | script |

## The job server

`skewcoder serve --workspace W` lets a website send texts to the pipeline. It takes `POST /jobs {"paper", "blog"}`
(links or an arXiv id only), runs `skewcoder run` for each job in turn, and serves the finished bundle; the website
polls `GET /jobs/<id>`. It refuses addresses on private networks and caps the runs per day. Settings (environment):
`SKEWCODER_PUBLIC_URL`, `SKEWCODER_ALLOWED_ORIGINS`, `SKEWCODER_MAX_JOBS_PER_DAY` (default 10),
`SKEWCODER_ACCESS_TOKEN` (optional), `SKEWCODER_WORKERS`, `SKEWCODER_JOB_TIMEOUT`. The API key is read from the
environment or from `~/.config/skewcoder/.env` on the machine that runs the server (see `.env.example`); the website
never sees it.

## Rules and briefs

`skewcoder/briefs/RULES.md` is the rulebook; `skewcoder/briefs/*.md` are the instructions each step's model receives.
A change of rule means every unit is coded again from scratch; nothing is patched forward.
