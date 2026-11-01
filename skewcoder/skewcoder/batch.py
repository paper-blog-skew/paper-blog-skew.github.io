"""`skewcoder.py batch <workspace>/pairs.json --jobs N`: every step of every pair, in dependency order, at most N model
sessions at a time. Steps whose outputs already exist in coding/ are skipped, so a batch can be re-run after a failure and
picks up where it stopped. Nothing is run twice; a paper shared by two blogs is coded once.

One iteration of each loop, recorded in each run's run.json under "loop" and in
<unit>/coding/loop_state.json:
  paper chain   metrics → links → (links reported missing_metrics?) metrics_append → links again
  blog chain    metrics → links → (links reported missing_metrics?) metrics_append → links again
  mapping       waits for both chains → mapping
  mapping loop  after every mapping: the paper metrics the mapping coders reported missing (all blogs of that paper,
                pooled) → paper metrics_append → paper links again → every mapping of that paper again
  equations     once the paper's links are final: its equations written as formulas (paper_algebra), then reduced
                mechanically (skewcoder.algebra → coding/algebra.json)
"""
import json, threading, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import texts, candidates, runner, audit


def have(unit, f): return (Path(unit) / "coding" / f).exists()


def _json(unit, f):
    p = Path(unit) / "coding" / f
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _state(unit):
    return _json(unit, "loop_state.json")


def _set_state(unit, key, val):
    st = _state(unit); st[key] = val
    (Path(unit) / "coding" / "loop_state.json").write_text(json.dumps(st, indent=1, ensure_ascii=False), encoding="utf-8")


def _mapped(unit):
    B = _json(unit, "blog_metrics.json").get("blog_concepts", [])
    return any(x.get("preimage") or x.get("mapping") or x.get("class") in ("both", "recovered") for x in B)


def chain(unit, kind, model, timeout):
    """metrics → links → one append loop. Returns True when metrics and links exist."""
    mfile, lfile, rfile = ("paper_quantities.json", "relations.html", "paper_links_report.json") if kind == "paper" else ("blog_metrics.json", "blog_links.json", "blog_links_report.json")
    if not have(unit, mfile): runner.run(f"{kind}_metrics", unit, model=model, timeout=timeout)
    if have(unit, mfile) and not have(unit, lfile): runner.run(f"{kind}_links", unit, model=model, timeout=timeout)
    if not (have(unit, mfile) and have(unit, lfile)): return False
    mm = _json(unit, rfile).get("missing_metrics") or []
    if mm and not _state(unit).get("links_append"):
        rec = runner.run(f"{kind}_metrics_append", unit, model=model, timeout=timeout, missing=mm, loop={"loop": "links→append", "iteration": 1})
        _set_state(unit, "links_append", {"missing": len(mm), "accepted": bool(rec and rec.get("accepted")), "run": rec.get("started") if rec else None})
        if rec and rec.get("accepted"): runner.run(f"{kind}_links", unit, model=model, timeout=timeout, loop={"loop": "links after append", "iteration": 1})
    return True


def map_one(b, pp, model, timeout, loop=None):
    runner.premap_source(Path(b)); candidates.build(b, pp); return runner.run("mapping", b, paper_dir=pp, model=model, timeout=timeout, loop=loop)


def pipeline(pairs, W, jobs=3, model=None, timeout=3600, log=print):
    """pairs: [{"id", "paper": <unit path or None>, "blog": <unit path or None>}]. A pair with one side only codes that side
    (text, metrics, links, definitions) and stops: no mapping, no map."""
    papers, blogs = {}, {}
    for p in pairs:
        if not (p.get("paper") or p.get("blog")): raise SystemExit(f"{p.get('id')}: neither a paper nor a blog")
        if p.get("paper"): papers[p["paper"]] = W / p["paper"]
        if p.get("blog"): blogs[p["blog"]] = (W / p["blog"], W / p["paper"] if p.get("paper") else None)
    for u in list(papers.values()) + [b for b, _ in blogs.values()]:
        if not (u / "text" / "text.md").exists(): texts.build(u)
    done = {}; events = {k: threading.Event() for k in list(papers) + list(blogs)}
    def run_chain(key, unit, kind):
        try: done[key] = chain(unit, kind, model, timeout)
        except Exception: log(traceback.format_exc()); done[key] = False
        events[key].set()
    def run_map(p):
        if not (p.get("paper") and p.get("blog")): return          # one side alone: no mapping
        b, pp = blogs[p["blog"]]; events[p["paper"]].wait(); events[p["blog"]].wait()
        if not (done.get(p["paper"]) and done.get(p["blog"])): log(f"  {p['id']}: mapping skipped (a chain did not finish)"); return
        if _mapped(b) and have(b, "mapping_report.json"): log(f"  {p['id']}: already mapped"); return
        try: map_one(b, pp, model, timeout)
        except Exception: log(traceback.format_exc())
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        fs = [ex.submit(run_chain, k, u, "paper") for k, u in papers.items()] + [ex.submit(run_chain, k, u, "blog") for k, (u, _) in blogs.items()]
        mt = [threading.Thread(target=run_map, args=(p,)) for p in pairs]   # own threads: they wait on chain events
        for t in mt: t.start()
        for f in fs: f.result()
        for t in mt: t.join()
    # ---- mapping loop (mapping → paper append): pooled per paper, one iteration
    for key, pp in papers.items():
        if _state(pp).get("mapping_append"): continue
        mine = [p for p in pairs if p.get("paper") == key and p.get("blog")]; mm = []
        for p in mine:
            b, _ = blogs[p["blog"]]
            for x in _json(b, "mapping_report.json").get("missing_metrics") or []: mm.append(dict(x, from_blog=p["blog"]))
        if not mm: continue
        try:
            rec = runner.run("paper_metrics_append", pp, model=model, timeout=timeout, missing=mm, loop={"loop": "mapping→paper append", "iteration": 1})
            _set_state(pp, "mapping_append", {"missing": len(mm), "accepted": bool(rec and rec.get("accepted"))})
            if rec and rec.get("accepted"):
                runner.run("paper_links", pp, model=model, timeout=timeout, loop={"loop": "paper links after mapping append", "iteration": 1})
                for p in mine:
                    b, _ = blogs[p["blog"]]; map_one(b, pp, model, timeout, loop={"loop": "mapping after paper append", "iteration": 1})
        except Exception: log(traceback.format_exc())
    # ---- definitions: last, once every metric list is final (after all appends). One per paper and per blog,
    # each blind to the other side; rerun when the metric list is newer than its definitions.
    def stale(u, metrics_file):
        d, m = u / "coding" / "definitions.json", u / "coding" / metrics_file
        return m.exists() and (not d.exists() or d.stat().st_mtime < m.stat().st_mtime)
    def stale_eq(u):
        e, r = u / "coding" / "equations.json", u / "coding" / "relations.html"
        return r.exists() and (not e.exists() or e.stat().st_mtime < r.stat().st_mtime)
    todo = [(u, "paper_algebra") for u in papers.values() if stale_eq(u)]
    todo += [(u, "paper_definitions") for u in papers.values() if stale(u, "paper_quantities.json")] + [(u, "blog_definitions") for u, _ in blogs.values() if stale(u, "blog_metrics.json")]
    def run_def(arg):
        u, step = arg
        try: runner.run(step, u, model=model, timeout=timeout)
        except Exception: log(traceback.format_exc())
    with ThreadPoolExecutor(max_workers=jobs) as ex: list(ex.map(run_def, todo))
    log("  equations and definitions done")
    nf = 0
    for p in pairs:
        print(f"== {p['id']}")
        if p.get("paper"): nf += audit.show(audit.audit_paper(papers[p["paper"]]))
        if p.get("blog"): b, pp = blogs[p["blog"]]; nf += audit.show(audit.audit_blog(b, pp))
    print(f"batch audit: {nf} failure(s)"); return nf


def batch(pairs_json, jobs=3, model=None, timeout=3600, only=None):
    pj = Path(pairs_json).resolve(); W = pj.parent; m = json.loads(pj.read_text(encoding="utf-8"))
    pairs = [p for p in m["pairs"] if not only or p["id"] in only]
    lock = threading.Lock()
    def log(msg):
        with lock: print(msg, flush=True)
    return pipeline(pairs, W, jobs, model, timeout, log)
