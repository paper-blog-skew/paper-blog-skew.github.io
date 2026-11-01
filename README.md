# Mapping technical artifacts: paper ↔ blog

For a scientific paper and the firm blog post written about it, this tool finds every measurable quantity each text
names (**metrics**) and every dependence each text states between two of them (**links**), maps the blog's metrics onto
the paper's, and shows where the blog's metrics and links sit against the paper's. Every coded item carries a verbatim
quote from its text, and every quote is checked against the text.

| folder | what |
|---|---|
| `skewcoder/` | the pipeline: a paper and/or a blog in, one **bundle** (all the coded data, in one folder) out |
| `skewsite/` | the website: builds a static site from bundles |
| `sample data/` | the five sample paper–blog pairs the website shows |

## Code a new paper and/or blog

```
cd skewcoder
pip install -e '.[api,similarity]'
export ANTHROPIC_API_KEY=…  SKEWCODER_BACKEND=api
skewcoder run --workspace work --paper 2211.09133 --blog https://example.com/blog/post/
```
Either side may be left out: one side alone is coded and no map is made. The bundle is written to `work/bundles/<id>/`.
See `skewcoder/README.md` for inputs, steps, the model backends and the rules.

## Build the website

```
cd skewsite
python3 build.py                 # dist/index.html and dist/method.html
python3 tools/render_check.py    # optional: clicks through every pair in headless Chrome
```
`skewsite/site.json` lists the pairs shown. See `skewsite/README.md`.

## Requirements

Python 3.10+. The pipeline needs beautifulsoup4, lxml and PyMuPDF; the `api` extra adds the Anthropic SDK and the
`similarity` extra adds sentence-transformers. The website build needs only the standard library; its check needs
Google Chrome.

## Licence

MIT (see `LICENSE`). The sample data contains text and figures rebuilt from the papers and blogs it cites; those
remain their publishers' and authors' work.
