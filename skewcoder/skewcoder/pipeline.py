"""End to end: whatever the user gives (a paper and/or a blog, as links, files or unit folders) -> one bundle.

  fetch    make the unit folders (skewcoder.fetch)            only for inputs that are not already units
  text     rebuild each text                                   (skewcoder.texts)
  code     metrics -> links -> one append loop per side; mapping when both sides are given (skewcoder.batch)
  define   one definition per metric, each side blind to the other
  score    similarity for the viewer's sliders               (skewcoder.similarity; skipped with a note if not installed)
  bundle   everything the viewer shows                         (skewcoder.bundle)

One side alone is a complete run: it codes that side and stops; no mapping, no map.
"""
from pathlib import Path
from . import batch, bundle, fetch, texts


def unit_or_fetch(W, src, kind, key=None, paper_key=None):
    p = Path(src) if src else None
    if p is not None and (p / "unit.json").exists(): return p.resolve()
    return (fetch.add_paper(W, src, key) if kind == "paper" else fetch.add_blog(W, src, key, paper_key)).resolve()


def run(workspace, paper=None, blog=None, out=None, paper_key=None, blog_key=None, jobs=2, model=None, timeout=3600,
        score=True, allow_failures=False, bundle_id=None, fig_base=None, log=print):
    if not (paper or blog): raise SystemExit("give a paper, a blog, or both")
    W = Path(workspace).resolve(); W.mkdir(parents=True, exist_ok=True)
    P = unit_or_fetch(W, paper, "paper", paper_key) if paper else None
    B = unit_or_fetch(W, blog, "blog", blog_key, texts.load_unit(P)["key"] if P else None) if blog else None
    for u in (P, B):
        if u and not (u / "text" / "text.md").exists(): texts.build(u)
    rel = lambda u: str(u.relative_to(W)) if u and W in u.parents else (str(u) if u else None)
    pid = bundle_id or "_".join(texts.load_unit(u)["key"] for u in (B, P) if u)
    nf = batch.pipeline([{"id": pid, "paper": rel(P), "blog": rel(B)}], W, jobs=jobs, model=model, timeout=timeout, log=log)
    if score:
        try:
            from . import similarity
            for u in (P, B):
                if u: similarity.score_unit(u)
            if P and B: similarity.score_pair(B, P)
        except SystemExit as e:
            log(f"  note: similarity skipped ({e}); the viewer's sliders will have no scores")
    out = Path(out) if out else W / "bundles" / pid
    b = bundle.export(out, paper=P, blog=B, bundle_id=pid, require_clean=not allow_failures, fig_base=fig_base)
    log(f"  done: {out / 'bundle.json'} (audit failures {nf})")
    return out, b
