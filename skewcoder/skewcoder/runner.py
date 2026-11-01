"""Parts (b), (c), (d): one coder run = one sandbox + one headless model session + the audit + a run record.

The sandbox is a fresh folder holding ONLY the inputs that step may read (the separation rule: the paper is coded
with the blog closed, the blog with the paper closed; the mapping sees both codings frozen). The model runs with its
working directory set to the sandbox, with Read/Write/Edit and one shell command (`bash check.sh`, the audit)
allowed, and nothing else; in headless mode every other tool call is denied. Frozen inputs are hashed before and
after; a run that changed one is refused. Outputs are copied into <unit>/coding/ only when the audit passes
(or --accept-failures is given); whatever was there before is kept under runs/<run>/replaced/.

The metrics steps get the mechanical candidate list (candidates.json); the append steps get the frozen-in-place metric file plus missing_metrics.json and may only add metrics; the mapping step is by
name only and writes mapping_report.json with the paper metrics it found missing. The loop that ties them
together (links → append → links again; mapping → paper append → paper links → mapping again, one iteration each)
lives in batch.pipeline.

Backend (skewcoder/backends): `cli` runs the Claude Code CLI (`claude -p`) on the account logged in to it; `api` runs the
same session on the Anthropic API (ANTHROPIC_API_KEY). Choose with SKEWCODER_BACKEND. The run record
(runs/<run>/run.json) keeps the backend, the model actually used, token usage (and cost where the backend reports it),
the brief's hash and rule version, the audit result and the coder's own report.
"""
import datetime as dt, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path
from . import __version__, audit, texts, completeness, config, backends

HERE = Path(__file__).resolve().parent
BRIEFS = HERE / "briefs"   # inside the package, so an installed copy carries them
PKG_PARENT = HERE.parent   # check.sh runs `python -m skewcoder check` with this on PYTHONPATH (works from a checkout and when installed)

STEPS = {
    # inputs: (relative to unit) -> sandbox name; frozen = must not change; outputs = files the coder writes (sandbox root)
    "paper_metrics": {"kind": "paper", "brief": "paper_metrics.md", "text": "paper.md", "candidates": True,
                      "frozen": {}, "outputs": ["paper_quantities.json", "display_labels.json"]},
    "paper_metrics_append": {"kind": "paper", "brief": "paper_metrics.md", "text": "paper.md", "candidates": True, "append": "paper_quantities",
                      "frozen": {}, "editable": {"coding/paper_quantities.json": "paper_quantities.json", "coding/display_labels.json": "display_labels.json"},
                      "outputs": ["paper_quantities.json", "display_labels.json", "append_report.json"]},
    "paper_links":   {"kind": "paper", "brief": "paper_links.md", "text": "paper.md",
                      "frozen": {"coding/paper_quantities.json": "paper_quantities.json"},
                      "outputs": ["relations.html", "paper_prose_links.json", "relation_leads.json", "paper_links_report.json"]},
    "blog_metrics":  {"kind": "blog", "brief": "blog_metrics.md", "text": "blog.md", "candidates": True,
                      "frozen": {}, "outputs": ["blog_metrics.json"]},
    "blog_metrics_append": {"kind": "blog", "brief": "blog_metrics.md", "text": "blog.md", "candidates": True, "append": "blog_concepts",
                      "frozen": {}, "editable": {"coding/blog_metrics.json": "blog_metrics.json"},
                      "outputs": ["blog_metrics.json", "append_report.json"]},
    "blog_links":    {"kind": "blog", "brief": "blog_links.md", "text": "blog.md",
                      "frozen": {"coding/blog_metrics.json": "blog_metrics.json"},
                      "outputs": ["blog_links.json", "blog_links_report.json"]},
    # definition pass. Each side defines its own metrics (what is measured, of what, in what unit; never what it
    # depends on), blind to the other side, so the two sides can be compared by meaning without a coder judging the match.
    "paper_definitions": {"kind": "paper", "brief": "definitions.md", "text": "paper.md",
                      "frozen": {"coding/paper_quantities.json": "paper_quantities.json"}, "outputs": ["definitions.json"]},
    "blog_definitions": {"kind": "blog", "brief": "definitions.md", "text": "blog.md",
                      "frozen": {"coding/blog_metrics_nomap.json": "blog_metrics.json"}, "outputs": ["definitions.json"]},
    # equations as formulas: each relation's equations written so the algebra (skewcoder.algebra) can reduce them
    "paper_algebra": {"kind": "paper", "brief": "paper_algebra.md", "text": "paper.md",
                      "frozen": {"coding/paper_quantities.json": "paper_quantities.json", "coding/relations.html": "relations.html"},
                      "outputs": ["equations.json"]},
    "mapping":       {"kind": "blog", "brief": "mapping.md", "text": "blog.md",
                      "frozen": {"coding/blog_links.json": "blog_links.json", "coding/map_candidates.json": "map_candidates.json"},
                      "paper_inputs": {"text/text.md": "paper/paper.md", "coding/paper_quantities.json": "paper/paper_quantities.json", "coding/display_labels.json": "paper/display_labels.json"},
                      "editable": {"coding/blog_metrics_premap.json": "blog_metrics.json"},
                      "outputs": ["blog_metrics.json", "mapping_report.json"]},
}


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rule_version():
    m = re.search(r"^rule_version:\s*(\S+)", (BRIEFS / "RULES.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "unknown"


def prompt_for(step, unit, spec, backend="cli"):
    outs = ", ".join(spec["outputs"])
    t = {"paper_metrics": f"Code the METRICS of the paper in paper.md (title: {unit.get('title')}). Follow the brief exactly (it is in your system prompt and in BRIEF.md). Write {outs} in this folder.",
         "paper_links": f"Code the LINKS of the paper in paper.md (title: {unit.get('title')}). The metrics are already coded and frozen in paper_quantities.json: you may only join metrics by their keys from that file, and you must not edit it. Write {outs} in this folder.",
         "blog_metrics": f"Code the METRICS of the blog post in blog.md (title: {unit.get('title')}). Follow the brief exactly (system prompt, also BRIEF.md). Write {outs} in this folder.",
         "blog_links": f"Code the LINKS of the blog post in blog.md (title: {unit.get('title')}). The blog's metrics are already coded and frozen in blog_metrics.json: you may only join nodes by their ids from that file, and you must not edit it. Write {outs} in this folder.",
         "paper_metrics_append": f"APPEND MODE. The paper's metrics are already coded in paper_quantities.json (title: {unit.get('title')}). missing_metrics.json lists wordings a later coder needed but did not find on the list, each with its sentence. Decide each under A1–A7 and append the metrics it names with their quotes; never change, rename or remove an existing metric. Write {outs} in this folder.",
         "blog_metrics_append": f"APPEND MODE. The blog's metrics are already coded in blog_metrics.json (title: {unit.get('title')}). missing_metrics.json lists wordings the links coder needed but did not find on the list, each with its sentence. Decide each under C1–C4 and append the nodes it names with their mentions; never change, rename or remove an existing node. Write {outs} in this folder.",
         "paper_definitions": f"DEFINE each metric of the paper in paper.md (title: {unit.get('title')}). The metrics are frozen in paper_quantities.json; write one definition per key. Follow the brief exactly (system prompt, also BRIEF.md). Write {outs} in this folder.",
         "blog_definitions": f"DEFINE each metric of the blog post in blog.md (title: {unit.get('title')}). The metrics are frozen in blog_metrics.json; write one definition per id. Follow the brief exactly (system prompt, also BRIEF.md). Write {outs} in this folder.",
         "paper_algebra": f"WRITE THE EQUATIONS of the paper in paper.md (title: {unit.get('title')}) as formulas. The metrics (paper_quantities.json) and the equation relations (relations.html) are frozen: write one entry per relation, using only that relation's metric keys and declared auxiliary symbols. Follow the brief exactly (system prompt, also BRIEF.md). Write {outs} in this folder.",
         "mapping": f"MAP the blog's metrics (blog_metrics.json, which you rewrite in place) onto the paper's metrics (paper/paper_quantities.json, read only). The mechanical candidates are in map_candidates.json; the texts are blog.md and paper/paper.md. Map by name only (no inferred mappings). Write mapping_report.json with the paper metrics you found missing. Do not edit blog_links.json or anything under paper/."}[step]
    return (t + "\n\nWrite the output files early and keep them valid JSON/HTML as you go, so that nothing is lost if the session is cut off. "
            "When the files are complete, run " + ("`bash check.sh`" if backend == "cli" else "the run_check tool") + " (the audit) and fix every failure it reports, then run it again until it passes. "
            "Finally reply with your report: the counts, the audit result, and every judgement call another coder might make differently (one line each). Do not paste file contents into the report.")


def premap_source(d):
    """The blog coder's file as it was before any mapping (a re-mapping after a paper append starts from it). Saved on the
    first mapping; if it is missing, recovered from the last accepted blog_metrics(_append) run's sandbox."""
    pm = d / "coding" / "blog_metrics_premap.json"
    if pm.exists(): return pm
    cur = d / "coding" / "blog_metrics.json"; B = json.loads(cur.read_text(encoding="utf-8")).get("blog_concepts", [])
    if not any(b.get("preimage") or b.get("mapping") or b.get("class") in ("both", "recovered") for b in B): shutil.copy(cur, pm); return pm
    runs = sorted([r for r in (d / "runs").glob("blog_metrics*") if (r / "work" / "blog_metrics.json").exists() and json.loads((r / "run.json").read_text(encoding="utf-8")).get("accepted")])
    if runs: shutil.copy(runs[-1] / "work" / "blog_metrics.json", pm); return pm
    sys.exit(f"{d}: no unmapped blog_metrics.json to map from (coding/blog_metrics_premap.json)")


def run(step, unit_dir, paper_dir=None, model=None, timeout=3600, accept_failures=False, dry=False, max_turns=None, missing=None, loop=None):
    if step not in STEPS: sys.exit(f"unknown step {step}; one of {list(STEPS)}")
    spec = STEPS[step]; unit = texts.load_unit(unit_dir); d = unit["_dir"]
    if unit["kind"] != spec["kind"]: sys.exit(f"{step} runs on a {spec['kind']} unit; {d} is a {unit['kind']}")
    if step == "mapping" and not paper_dir: sys.exit("mapping needs --paper <paper unit folder>")
    if not (d / "text" / "text.md").exists(): sys.exit(f"{d}: no text yet — run `skewcoder.py text` first")
    if step == "mapping": premap_source(d)
    if step == "blog_definitions": write_nomap(d)
    if spec.get("append") and not missing: sys.exit(f"{step} needs the missing_metrics to decide")
    for src in list(spec["frozen"]) + list(spec.get("editable", {})):
        if not (d / src).exists(): sys.exit(f"{d / src} is missing — run the earlier step first")
    ts = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S"); run_dir = d / "runs" / f"{step}_{ts}"; work = run_dir / "work"; work.mkdir(parents=True)
    # ---- assemble the sandbox
    shutil.copy(d / "text" / "text.md", work / spec["text"])
    brief = (BRIEFS / spec["brief"]).read_text(encoding="utf-8"); (work / "BRIEF.md").write_text(brief, encoding="utf-8")
    frozen = {}
    for src, dst in spec["frozen"].items(): shutil.copy(d / src, work / dst); frozen[dst] = sha(work / dst)
    for src, dst in spec.get("editable", {}).items(): shutil.copy(d / src, work / dst)
    if spec.get("candidates"):   # the mechanical candidate list the coder must account for in full
        completeness.build(d); shutil.copy(d / "text" / "metric_candidates.json", work / "candidates.json")
    before = None
    if spec.get("append"):       # the append pass may only add
        (work / "missing_metrics.json").write_text(json.dumps({"missing_metrics": missing}, ensure_ascii=False, indent=1), encoding="utf-8")
        src = work / ("paper_quantities.json" if spec["append"] == "paper_quantities" else "blog_metrics.json")
        before = {x.get("key") or x.get("id"): json.dumps(x, sort_keys=True) for x in json.loads(src.read_text(encoding="utf-8"))[spec["append"]]}
    paper_doc_path = None
    if step == "mapping":
        pd = Path(paper_dir).resolve(); (work / "paper").mkdir()
        for src, dst in spec["paper_inputs"].items():
            if (pd / src).exists(): shutil.copy(pd / src, work / dst); frozen[dst] = sha(work / dst)
        paper_doc_path = pd / "text" / "docs.json"
    # the audit the coder may run: it reads the text outside the sandbox through this script, never through the model
    check = [sys.executable, "-m", "skewcoder", "check", str(work), "--step", step, "--text", str(d / "text" / "docs.json")]
    if paper_doc_path: check += ["--paper-coding", str(work / "paper"), "--paper-text", str(paper_doc_path)]
    (work / "check.sh").write_text("#!/bin/bash\n" + f'PYTHONPATH="{PKG_PARENT}" ' + " ".join(f'"{c}"' for c in check) + "\n", encoding="utf-8")
    be_name = config.backend(); be = backends.get(be_name); model = config.model(model)
    prompt = prompt_for(step, unit, spec, be_name)
    rec = {"loop": loop, "missing_given": missing, "step": step, "unit": d.name, "paper": str(paper_dir) if paper_dir else None, "started": ts, "skewcoder": __version__, "rule_version": rule_version(),
           "brief": spec["brief"], "brief_sha256": hashlib.sha256(brief.encode()).hexdigest(), "backend": be_name, "model_requested": model, "prompt": prompt}
    (run_dir / "run.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    if dry: print(f"  dry run: sandbox at {work}"); return rec
    print(f"  {step} on {d.name}: backend {be_name}, model {model}, sandbox {work}", flush=True); t0 = dt.datetime.now()
    res = be.run(work, prompt, work / "BRIEF.md", model, timeout=timeout, max_turns=max_turns)
    rec["finished"] = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S"); rec["seconds"] = (dt.datetime.now() - t0).total_seconds()
    rec["report"] = res["report"]; rec["model_used"] = res["model_used"]; rec["usage"] = res["usage"]; rec["cost_usd"] = res["cost_usd"]
    rec["turns"] = res["turns"]; rec["session_error"] = res["error"]; rec["backend_raw"] = res["raw"]
    # ---- frozen inputs untouched?
    changed = [f for f, h in frozen.items() if not (work / f).exists() or sha(work / f) != h]
    rec["frozen_changed"] = changed
    # ---- audit on the sandbox outputs
    rep = check_sandbox(work, step, d / "text" / "docs.json", work / "paper" if step == "mapping" else None, paper_doc_path)
    if before is not None:      # nothing already on the list may change in an append pass
        src = work / ("paper_quantities.json" if spec["append"] == "paper_quantities" else "blog_metrics.json")
        try:
            after = {x.get("key") or x.get("id"): json.dumps(x, sort_keys=True) for x in json.loads(src.read_text(encoding="utf-8"))[spec["append"]]}
            for k, v in before.items():
                if after.get(k) != v: rep["failures"].append({"unit": d.name, "side": spec["kind"], "kind": "append-changed-existing", "where": k, "detail": "the append pass may only add metrics"})
            rep["counts"]["appended"] = len(set(after) - set(before))
        except Exception as e: rep["failures"].append({"unit": d.name, "side": spec["kind"], "kind": "append-unreadable", "where": src.name, "detail": str(e)})
    rec["audit"] = rep; nf = len(rep["failures"]); missing_out = [o for o in spec["outputs"] if not (work / o).exists()]
    rec["missing_outputs"] = missing_out
    ok = not changed and not missing_out and (nf == 0 or accept_failures)
    rec["accepted"] = ok
    if ok:
        cd = d / "coding"; cd.mkdir(exist_ok=True); rep_dir = run_dir / "replaced"
        for o in spec["outputs"]:
            if (cd / o).exists(): rep_dir.mkdir(exist_ok=True); shutil.copy(cd / o, rep_dir / o)
            shutil.copy(work / o, cd / o)
        rec["written"] = [str(cd / o) for o in spec["outputs"]]
        if step == "paper_algebra":   # the mechanical reduction follows the coder's formulas at once
            from . import algebra
            rec["algebra_counts"] = algebra.run_unit(d)["counts"]
    (run_dir / "run.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  {'accepted' if ok else 'NOT accepted'}: audit failures {nf}, missing outputs {missing_out}, frozen inputs changed {changed}; record {run_dir / 'run.json'}", flush=True)
    if rec.get("report"): print("  --- coder report ---\n" + rec["report"][:6000], flush=True)
    return rec


def write_nomap(d):
    """The blog's metric list with every trace of the mapping removed (preimage, the paper names it used, mapping notes), so the
    blog's definition coder cannot see the paper's words."""
    B = json.loads((d / "coding" / "blog_metrics.json").read_text(encoding="utf-8"))
    keep = {"_doc": "Blog metrics without mapping fields, for the definition pass.", "blog_concepts": []}
    for b in B["blog_concepts"]:
        keep["blog_concepts"].append({k: v for k, v in b.items() if k not in ("preimage", "alias_used", "mapping", "mapping_note", "preimage_note", "preimage_unsure", "class", "qualifier")})
        keep["blog_concepts"][-1]["mentions"] = [{k: v for k, v in m.items() if k in ("quote", "frame", "matched", "value")} for m in b.get("mentions", [])]
    (d / "coding" / "blog_metrics_nomap.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")


def check_sandbox(work, step, text_docs, paper_coding=None, paper_text=None):
    """The audit as the coder sees it: on the sandbox's files, with the unit's text read from outside the sandbox."""
    work = Path(work); doc = json.loads(Path(text_docs).read_text(encoding="utf-8"))
    pdoc = json.loads(Path(paper_text).read_text(encoding="utf-8")) if paper_text and Path(paper_text).exists() else None
    if step.endswith("_definitions"): return audit.audit_definitions(work, STEPS[step]["kind"])
    if step == "paper_algebra": return audit.audit_algebra(work)
    if STEPS[step]["kind"] == "paper": return audit.audit_paper(work, strict=True, doc=doc, coding_dir=work)
    return audit.audit_blog(work, strict=True, doc=doc, coding_dir=work, paper_coding_dir=paper_coding, paper_doc=pdoc)


def accept(run_dir, note):
    """Re-run the audit on a finished run's sandbox (after a correction to the audit itself) and, if it passes, copy its outputs into coding/.
    The record keeps the original audit and the reason for the later acceptance; the coder's files are not touched."""
    run_dir = Path(run_dir).resolve(); rec = json.loads((run_dir / "run.json").read_text(encoding="utf-8")); step = rec["step"]; spec = STEPS[step]
    d = run_dir.parents[1]; work = run_dir / "work"
    pt = Path(rec["paper"]).resolve() / "text" / "docs.json" if rec.get("paper") else None
    rep = check_sandbox(work, step, d / "text" / "docs.json", work / "paper" if step == "mapping" else None, pt); nf = len(rep["failures"])
    missing = [o for o in spec["outputs"] if not (work / o).exists()]
    if nf or missing or rec.get("frozen_changed"): print(f"  not accepted: failures {nf}, missing {missing}, frozen changed {rec.get('frozen_changed')}"); audit.show(rep); return False
    cd = d / "coding"; cd.mkdir(exist_ok=True); rep_dir = run_dir / "replaced"
    for o in spec["outputs"]:
        if (cd / o).exists(): rep_dir.mkdir(exist_ok=True); shutil.copy(cd / o, rep_dir / o)
        shutil.copy(work / o, cd / o)
    rec["accepted"] = True; rec["accepted_later"] = {"when": dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S"), "note": note, "audit_then": rec["audit"], "audit_now": rep}
    rec["written"] = [str(cd / o) for o in spec["outputs"]]
    (run_dir / "run.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  accepted after fix: {run_dir.name} -> {cd}; {rep['counts']}"); return True
