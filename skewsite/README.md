# skewsite — the viewer for paper ↔ blog maps

A static website that shows, for a scientific paper and the firm blog post about it, every metric each text names, the
links each text states between them, and a map of where the blog's metrics and links sit against the paper's. It reads
**bundles** made by the [skewcoder](../skewcoder) pipeline and computes nothing about the coding itself.

## Build

```
python3 build.py                    # dist/index.html (KaTeX inlined, works offline) + dist/method.html
python3 build.py --mode cdn         # smaller page, KaTeX from a CDN
python3 tools/render_check.py       # headless Chrome clicks through every metric and node; exit 1 on any problem
```
Python 3 standard library only. The checks need Google Chrome (`CHROME=/path/to/chrome` if it is not in the macOS place).

## What it reads

`site.json` lists the pairs in order. As shipped, it shows the five sample pairs in `../sample data/`:

```json
{"title": "Mapping Technical Artifacts",
 "pipeline_url": "https://…",                       (optional: see "Visitors' own texts")
 "pairs": [{"id": "MIC-442_Low2023", "bundle": "../sample data/bundles/MIC-442_Low2023", "short": "Trotter steps",
            "scopes": {…}, "paper": {…display overrides…}, "accept_audit": "<reason, only if needed>"}]}
```

Each `bundle` folder holds `bundle.json` (format `skew-bundle/1`, described in `skewcoder/skewcoder/bundle.py`) and the
figures under `figs/`. A bundle may hold a paper alone or a blog alone: the missing side says it was not given and the
map is withheld.

The build refuses a bundle whose codings fail the pipeline's audit unless `accept_audit` gives a reason.

## Display rules applied here (not in the data)

- Settings (models, methods, platforms, regimes) are shown as ordinary metrics: category prefixes such as "Method:" are
  dropped and "qualifier" reads "setting" (`scrub_settings` in build.py; the same rule in app.js for bundles loaded
  at run time).
- Everything else (the sliders, the tables, the matrices) is in `src/js/app.js`.

## Visitors' own texts

`"upload": false` in `site.json` hides "Compare your own pair" (as shipped). With it on and without `pipeline_url`, "Compare your own pair" shows the two pages and codes nothing. With it, the form
sends the links to a skewcoder job server (`skewcoder serve`), shows its progress at `#/job/<id>`, and opens the
finished bundle like a sample pair.

## Other files

| path | what |
|---|---|
| `src/` | the viewer: `js/app.js` and CSS |
| `vendor/katex-0.16.9/` | KaTeX (MIT), inlined in offline builds |
| `methods/` | the "How this was made" page: `body.html` (text) + `build_method_doc.py` (figures, contents) |
| `tools/render_check.py` | the click-through check |
| `deploy/push_github.sh` | build, check, publish `dist/` to GitHub Pages |
| `../sample data/bundles/` | the sample data the site shows |
