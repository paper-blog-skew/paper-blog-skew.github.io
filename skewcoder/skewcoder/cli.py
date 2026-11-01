"""skewcoder — code a paper and/or the blog post about it for the paper–blog skew measure.

End to end (one side alone is fine: it is coded and no map is made):
  skewcoder run --workspace W --paper 2211.09133 --blog https://…/blog/…      fetch, text, code, define, score, bundle
  skewcoder run --workspace W --paper papers/MyPaper2024                       a unit folder works as input too

Steps one at a time (a unit is a folder with unit.json and sources/):
  skewcoder fetch paper <arXiv id | link | PDF> --workspace W [--key K]
  skewcoder fetch blog  <link | .html | .pdf>  --workspace W [--key K] [--paper KEY]
  skewcoder text     <unit>                     (a) rebuild the text
  skewcoder candidates <unit>                   the mechanical metric candidates
  skewcoder metrics  <unit>                     (b) code its metrics             (model, sandboxed)
  skewcoder links    <unit>                     (c) code its links               (model, sandboxed, metrics frozen)
  skewcoder define   <unit>                         one definition per metric    (model, sandboxed)
  skewcoder algebra  <paper>                        equations as formulas (model, sandboxed), then the reduction
  skewcoder algebra  <paper> --reduce-only          the reduction alone: redundancy, rank, minimal linked groups
  skewcoder map      <blog> --paper <paper>     (d) candidates + mapping         (mechanical + model)
  skewcoder audit    <unit> [--paper <paper>]   (e) the gates; exit 1 on failure
  skewcoder similarity <unit> [--paper <paper>]     scores for the viewer's sliders
  skewcoder bundle   --out DIR [--paper P] [--blog B]   everything the viewer shows, in one folder
  skewcoder batch    <workspace>/pairs.json [--bundles DIR]   every pair, dependency-ordered
  skewcoder accept   <unit>/runs/<run> --note "…"   take a finished run's outputs after a tool-side fix
  skewcoder serve    --workspace W [--port 8765]    the job server a website can submit to (see server.py)

Model backend: SKEWCODER_BACKEND=cli (Claude Code, default) or api (ANTHROPIC_API_KEY). See skewcoder/config.py.
"""
import argparse, json, sys
from pathlib import Path
from . import texts, audit, candidates, runner, batch, completeness


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skewcoder", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def common(p, paper=False, llm=False):
        p.add_argument("unit")
        if paper: p.add_argument("--paper", help="the paper unit folder")
        if llm: llm_opts(p)
    def llm_opts(p):
        p.add_argument("--model", help="model (default: SKEWCODER_MODEL, else opus)"); p.add_argument("--timeout", type=int, default=3600); p.add_argument("--max-turns", type=int)
        p.add_argument("--accept-failures", action="store_true", help="copy outputs into coding/ even if the audit fails")
        p.add_argument("--dry", action="store_true", help="assemble the sandbox and stop")
    p = sub.add_parser("fetch"); p.add_argument("kind", choices=["paper", "blog"]); p.add_argument("source"); p.add_argument("--workspace", required=True)
    p.add_argument("--key"); p.add_argument("--paper", help="(blog) the key of the paper it reports on")
    common(sub.add_parser("text")); common(sub.add_parser("candidates"))
    common(sub.add_parser("metrics"), llm=True); common(sub.add_parser("links"), llm=True)
    common(sub.add_parser("map"), paper=True, llm=True); common(sub.add_parser("define"), llm=True)
    p = sub.add_parser("algebra"); common(p, llm=True); p.add_argument("--reduce-only", action="store_true")
    p = sub.add_parser("audit"); common(p, paper=True); p.add_argument("--json"); p.add_argument("--lenient", action="store_true")
    p = sub.add_parser("similarity"); common(p, paper=True)
    p = sub.add_parser("bundle"); p.add_argument("--out", required=True); p.add_argument("--paper"); p.add_argument("--blog"); p.add_argument("--id")
    p.add_argument("--allow-failures", action="store_true"); p.add_argument("--fig-base")
    p = sub.add_parser("run"); p.add_argument("--workspace", required=True); p.add_argument("--paper"); p.add_argument("--blog"); p.add_argument("--out")
    p.add_argument("--paper-key"); p.add_argument("--blog-key"); p.add_argument("--id"); p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--model"); p.add_argument("--timeout", type=int, default=3600); p.add_argument("--no-similarity", action="store_true"); p.add_argument("--allow-failures", action="store_true"); p.add_argument("--fig-base")
    p = sub.add_parser("batch"); p.add_argument("pairs_json"); p.add_argument("--jobs", type=int, default=3); p.add_argument("--model"); p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--only", nargs="*"); p.add_argument("--bundles", help="also score and bundle every pair into this folder")
    p = sub.add_parser("accept"); p.add_argument("run_dir"); p.add_argument("--note", required=True, help="why the run is accepted (e.g. a correction to the audit)")
    p = sub.add_parser("check"); p.add_argument("sandbox"); p.add_argument("--step", required=True); p.add_argument("--text", required=True); p.add_argument("--paper-coding"); p.add_argument("--paper-text")
    p = sub.add_parser("serve"); p.add_argument("--workspace", required=True); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)

    if a.cmd == "fetch":
        from . import fetch
        (fetch.add_paper(a.workspace, a.source, a.key) if a.kind == "paper" else fetch.add_blog(a.workspace, a.source, a.key, a.paper)); return
    if a.cmd == "text": texts.build(a.unit); return
    if a.cmd == "candidates":
        o = completeness.build(a.unit); print(f"  {o['unit']}: {o['n']} metric candidates -> text/metric_candidates.json"); return
    if a.cmd == "accept": sys.exit(0 if runner.accept(a.run_dir, a.note) else 1)
    if a.cmd == "check":
        rep = runner.check_sandbox(a.sandbox, a.step, a.text, a.paper_coding, a.paper_text); nf = audit.show(rep)
        print(f"check: {nf} failure(s)"); sys.exit(1 if nf else 0)
    if a.cmd == "audit":
        u = texts.load_unit(a.unit)
        rep = audit.audit_paper(a.unit, strict=not a.lenient) if u["kind"] == "paper" else audit.audit_blog(a.unit, a.paper, strict=not a.lenient)
        nf = audit.show(rep)
        if a.json: Path(a.json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"audit: {nf} failure(s)"); sys.exit(1 if nf else 0)
    if a.cmd == "similarity":
        from . import similarity
        similarity.score_unit(a.unit)
        if a.paper: similarity.score_unit(a.paper); similarity.score_pair(a.unit, a.paper)
        return
    if a.cmd == "bundle":
        from . import bundle
        bundle.export(a.out, paper=a.paper, blog=a.blog, bundle_id=a.id, require_clean=not a.allow_failures, fig_base=a.fig_base); return
    if a.cmd == "run":
        from . import pipeline
        pipeline.run(a.workspace, a.paper, a.blog, a.out, a.paper_key, a.blog_key, a.jobs, a.model, a.timeout, not a.no_similarity, a.allow_failures, a.id, a.fig_base); return
    if a.cmd == "batch":
        nf = batch.batch(a.pairs_json, a.jobs, a.model, a.timeout, a.only)
        if a.bundles:
            from . import bundle
            pj = Path(a.pairs_json).resolve(); W = pj.parent
            for p in json.loads(pj.read_text(encoding="utf-8"))["pairs"]:
                if a.only and p["id"] not in a.only: continue
                Pu, Bu = (W / p["paper"] if p.get("paper") else None), (W / p["blog"] if p.get("blog") else None)
                try:
                    from . import similarity
                    for u in (Pu, Bu):
                        if u: similarity.score_unit(u)
                    if Pu and Bu: similarity.score_pair(Bu, Pu)
                except SystemExit as e: print(f"  note: similarity skipped ({e})")
                bundle.export(Path(a.bundles) / p["id"], paper=Pu, blog=Bu, bundle_id=p["id"], short=p.get("short"), require_clean=False)
        sys.exit(1 if nf else 0)
    if a.cmd == "serve":
        from . import server
        server.serve(a.workspace, a.host, a.port); return
    kw = dict(model=a.model, timeout=a.timeout, accept_failures=a.accept_failures, dry=a.dry, max_turns=a.max_turns)
    if a.cmd == "algebra" and a.reduce_only: kw = {}
    u = texts.load_unit(a.unit); kind = u["kind"]
    if a.cmd == "metrics": runner.run(f"{kind}_metrics", a.unit, **kw); return
    if a.cmd == "links": runner.run(f"{kind}_links", a.unit, **kw); return
    if a.cmd == "define": runner.run(f"{kind}_definitions", a.unit, **kw); return
    if a.cmd == "algebra":
        if kind != "paper": sys.exit("algebra runs on a paper unit")
        if a.reduce_only:
            from . import algebra
            algebra.run_unit(a.unit); return
        runner.run("paper_algebra", a.unit, **kw); return
    if a.cmd == "map":
        if kind != "blog" or not a.paper: sys.exit("map runs on a blog unit with --paper")
        runner.premap_source(Path(a.unit).resolve()); candidates.build(a.unit, a.paper); runner.run("mapping", a.unit, paper_dir=a.paper, **kw); return


if __name__ == "__main__":
    main()
