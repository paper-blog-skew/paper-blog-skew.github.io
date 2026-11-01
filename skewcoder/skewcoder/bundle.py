"""The bundle: everything the viewer shows for one pair, or for one paper or one blog alone, in one folder.

  <out>/bundle.json      format "skew-bundle/1" (below)
  <out>/figs/<key>/...   figure, equation and page images the texts refer to ("figs/<key>/<file>")

bundle.json
  format, id, status ("coded" | "text only"), sides (["paper", "blog"], ["paper"] or ["blog"]), made, exported_by,
  rule_versions        the rule versions the coding runs recorded
  paper, blog          citation fields of each side (null for a side not given)
  docs                 {"paper": rebuilt text, "blog": rebuilt text}   (blocks with ids, HTML/TeX)
  anchors              where every coded quote and every numbered equation sits in the texts
  Q, PR, rels, labels  the paper's metrics, prose links, equation relations (parsed), display labels
  B, E                 the blog's metrics (with their mapping onto Q when both sides are given) and links
  sim                  similarity scores for the metric boundary and mapping-fold sliders
  audit                the gates' result on this bundle's codings (failures listed; a site should refuse failures)
  runs                 one line per accepted coding run: step, unit, model, backend, rule version, when

With one side only, the other side's fields are null or empty and no mapping exists: the viewer withholds the map. Nothing in the bundle is computed by the viewer's display rules; those stay in the site.
"""
import datetime as dt, html as H, json, re, shutil
from pathlib import Path
from . import __version__, audit, texts
from .textbuild import locate_quote

FORMAT = "skew-bundle/1"


def _j(p): return json.loads(Path(p).read_text(encoding="utf-8"))


def parse_relations(src):
    """relations.html holds one <template> per relation; TeX lives in HTML so it needs no escaping."""
    out = []
    for m in re.finditer(r'<template data-id="([^"]+)" data-eq="([^"]+)" data-vars="([^"]+)"([^>]*)>(.*?)</template>', src, flags=re.S):
        tid, eq, vs, attrs, inner = m.groups()
        cond = {k: H.unescape(v) for k, v in re.findall(r'data-(cond|cond-quote|cond-where|cond-vars)="([^"]*)"', attrs)}
        nums = []
        for a, b in re.findall(r"\((\d+)\)(?:[–-]\((\d+)\))?", eq): nums.extend(range(int(a), int(b) + 1) if b else [int(a)])
        t = re.search(r'<span class="t">(.*?)</span>', inner, flags=re.S)
        body = re.sub(r'<span class="t">.*?</span>', "", inner, count=1, flags=re.S).strip()
        bad = [mm.group(0)[:80] for mm in re.finditer(r"\$\$.*?\$\$|\$[^$]*?\$", inner, flags=re.S) if "<" in mm.group(0) or ">" in mm.group(0)]
        out.append({"id": tid, "eq": eq, "nums": nums, "vars": vs.split(), "title": t.group(1).strip() if t else tid, "html": body,
                    "cond": cond.get("cond", ""), "cond_quote": cond.get("cond-quote", ""), "cond_where": cond.get("cond-where", ""),
                    "cond_vars": cond.get("cond-vars", "").split(), "_raw_angle_in_math": bad})
    return out


def meta(u):
    keep = ("key", "title", "cite", "url", "firm", "doi", "note", "id")
    m = {k: u[k] for k in keep if u.get(k)}
    if u["kind"] == "blog": m.setdefault("id", u["key"])
    return m


def paper_anchors(doc, cd):
    A = {"eq": {}, "quotes": {}, "missed": [], "leads": {}}
    for b in doc["blocks"]:
        if b["type"] == "eq" and b.get("num"): A["eq"][str(b["num"])] = b["id"]
    if (cd / "relation_leads.json").exists():
        # attachment sentences: located within a few blocks of the equation they attach to
        idx = {b["id"]: i for i, b in enumerate(doc["blocks"])}
        for rid, its in _j(cd / "relation_leads.json")["leads"].items():
            acc = []
            for it in its:
                eqb = A["eq"].get(str(it["eq"])); loc = None
                if eqb is not None and it.get("quote"):
                    i0 = idx[eqb]; loc = locate_quote({"blocks": doc["blocks"][max(0, i0 - 6): i0 + 7]}, it["quote"])
                acc.append(dict(it, **(loc or {"block": None})))
            A["leads"][rid] = acc
    for l in _j(cd / "paper_prose_links.json")["paper_prose_links"]:
        loc = locate_quote(doc, l["quote"])
        if loc: A["quotes"][l["id"]] = loc
        else: A["missed"].append(l["id"])
        # a setting cell in the matrix highlights its source: the condition quote of the conditioned statement ("cond:<id>")
        if l.get("condition_quote"):
            cl = locate_quote(doc, l["condition_quote"])
            if cl: A["quotes"]["cond:" + l["id"]] = cl
    for m in re.finditer(r'<template data-id="([^"]+)"[^>]*?data-cond-quote="([^"]*)"', (cd / "relations.html").read_text(encoding="utf-8")):
        cl = locate_quote(doc, H.unescape(m.group(2))) if m.group(2) else None
        if cl: A["quotes"]["cond:" + m.group(1)] = cl
    return A


def blog_anchors(doc, B, E):
    A = {"quotes": {}, "missed": []}
    for b in B:
        for mi, mref in enumerate(b.get("mentions") or [{"quote": b.get("quote", "")}]):   # the first mention keeps the node id, the rest are id~k
            mid = b["id"] if mi == 0 else f'{b["id"]}~{mi}'
            loc = locate_quote(doc, mref["quote"]) if mref.get("quote") else None
            if loc: A["quotes"][mid] = loc
            else: A["missed"].append(mid)
    for i, e in enumerate(E):
        loc = locate_quote(doc, e["quote"]) if e.get("quote") else None
        if loc: A["quotes"]["e%d" % i] = loc
        else: A["missed"].append("e%d" % i)
    return A


def runs(unit_dir):
    out = []
    for r in sorted((Path(unit_dir) / "runs").glob("*/run.json")):
        j = _j(r)
        if j.get("accepted"):
            out.append({"step": j.get("step"), "unit": j.get("unit"), "started": j.get("started"), "backend": j.get("backend", "cli"),
                        "model": (j.get("model_used") or [j.get("model_requested")]), "rule_version": j.get("rule_version"), "skewcoder": j.get("skewcoder")})
    return out


def _sim(cd, name):
    p = cd / name
    return _j(p) if p.exists() else None


def export(out_dir, paper=None, blog=None, bundle_id=None, short=None, extra=None, require_clean=True, fig_base=None):
    """paper / blog: unit folders (either may be None). Writes <out_dir>/bundle.json and figs/. Returns the bundle dict."""
    if not (paper or blog): raise SystemExit("export needs a paper unit, a blog unit, or both")
    P = texts.load_unit(paper) if paper else None; Bu = texts.load_unit(blog) if blog else None
    sides = [s for s, u in (("paper", P), ("blog", Bu)) if u]
    bid = bundle_id or "_".join(u["key"] for u in (Bu, P) if u)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    docs = {"paper": texts.load_doc(P["_dir"]) if P else None, "blog": texts.load_doc(Bu["_dir"]) if Bu else None}
    b = {"format": FORMAT, "id": bid, "short": short or "", "sides": sides, "made": dt.date.today().isoformat(),
         "exported_by": {"skewcoder": __version__},
         "paper": meta(P) if P else None, "blog": meta(Bu) if Bu else None, "docs": docs,
         "anchors": {"paper": {"eq": {}, "quotes": {}, "missed": [], "leads": {}}, "blog": {"quotes": {}, "missed": []}},
         "Q": [], "PR": [], "rels": [], "alg": None, "labels": {}, "B": [], "E": [],
         "sim": {"paper": {}, "blog": {}, "map": {}, "model": None, "basis": "names"}, "audit": {"failures": []}, "runs": []}
    coded = []
    if P and (P["_dir"] / "coding" / "paper_quantities.json").exists() and (P["_dir"] / "coding" / "relations.html").exists():
        cd = P["_dir"] / "coding"
        b["Q"] = _j(cd / "paper_quantities.json")["paper_quantities"]
        b["PR"] = _j(cd / "paper_prose_links.json")["paper_prose_links"]
        b["rels"] = parse_relations((cd / "relations.html").read_text(encoding="utf-8"))
        b["labels"] = _j(cd / "display_labels.json")["labels"] if (cd / "display_labels.json").exists() else {}
        b["anchors"]["paper"] = paper_anchors(docs["paper"], cd); coded.append("paper")
        # the equations reduced (skewcoder.algebra); recomputed when the coder's formulas are newer than the last reduction
        if (cd / "equations.json").exists():
            from . import algebra
            if not (cd / "algebra.json").exists() or (cd / "algebra.json").stat().st_mtime < (cd / "equations.json").stat().st_mtime: algebra.run_unit(P["_dir"])
            b["alg"] = _j(cd / "algebra.json")
        b["audit"]["failures"] += audit.audit_paper(P["_dir"])["failures"]; b["runs"] += runs(P["_dir"])
    if Bu and (Bu["_dir"] / "coding" / "blog_metrics.json").exists() and (Bu["_dir"] / "coding" / "blog_links.json").exists():
        cd = Bu["_dir"] / "coding"
        b["B"] = _j(cd / "blog_metrics.json")["blog_concepts"]
        if not P:   # a blog alone carries no mapping: any mapping fields in its unit are dropped
            for x in b["B"]:
                for k in ("preimage", "alias_used", "mapping", "mapping_note", "preimage_note", "preimage_unsure"): x.pop(k, None)
                x["preimage"] = []
        b["E"] = _j(cd / "blog_links.json")["blog_edges"]
        b["anchors"]["blog"] = blog_anchors(docs["blog"], b["B"], b["E"]); coded.append("blog")
        fb = audit.audit_blog(Bu["_dir"], P["_dir"] if P else None)["failures"]
        if not P: fb = [f for f in fb if f["kind"] != "mapping-without-paper"]   # the mapping is stripped above
        b["audit"]["failures"] += fb; b["runs"] += runs(Bu["_dir"])
    b["status"] = "coded" if coded == sides else ("partly coded" if coded else "text only")
    b["coded"] = coded
    # consistency gates
    F = b["audit"]["failures"]; keys = {q["key"] for q in b["Q"]}; bids = {x["id"] for x in b["B"]}
    for r in b["rels"]:
        if [v for v in r["vars"] if v not in keys]: F.append({"kind": "unknown-key", "where": r["id"], "detail": "relation uses an unknown metric key"})
        if not r["nums"]: F.append({"kind": "no-equation", "where": r["id"], "detail": f"no numbered equation in data-eq={r['eq']!r}"})
        if r.pop("_raw_angle_in_math"): F.append({"kind": "raw-angle", "where": r["id"], "detail": "raw < or > inside math (use \\lt / \\gt)"})
    for l in b["PR"]:
        if l["a"] not in keys or l["b"] not in keys: F.append({"kind": "unknown-key", "where": l["id"], "detail": "prose link uses an unknown metric key"})
    for x in b["B"]:
        if P and [k for k in x.get("preimage", []) if k not in keys]: F.append({"kind": "unknown-key", "where": x["id"], "detail": "preimage key not among the paper's metrics"})
    for e in b["E"]:
        if e["source"] not in bids or e["target"] not in bids: F.append({"kind": "unknown-id", "where": f"{e['source']}->{e['target']}", "detail": "blog link joins an unknown metric"})
    if require_clean and F:
        for f in F[:40]: print(f"  FAIL {f.get('unit', '')} {f.get('kind')} {f.get('where')}: {f.get('detail')}")
        raise SystemExit(f"{bid}: {len(F)} audit failure(s); bundle not written (use --allow-failures to inspect)")
    # similarity: definitions when every side present has them (and the map, when there is one), names otherwise
    sp = _sim(P["_dir"] / "coding", "similarity_definitions.json") if P else None
    sb = _sim(Bu["_dir"] / "coding", "similarity_definitions.json") if Bu else None
    sm = _sim(Bu["_dir"] / "coding", f"similarity_map_{P['key']}_definitions.json") if (P and Bu) else None
    use_def = (not P or sp) and (not Bu or sb) and (not (P and Bu) or sm)
    basis = "definitions" if use_def else "names"
    if not use_def:
        sp = _sim(P["_dir"] / "coding", "similarity_names.json") if P else None
        sb = _sim(Bu["_dir"] / "coding", "similarity_names.json") if Bu else None
        sm = _sim(Bu["_dir"] / "coding", f"similarity_map_{P['key']}_names.json") if (P and Bu) else None
    b["sim"] = {"paper": (sp or {}).get("pairs", {}), "blog": (sb or {}).get("pairs", {}), "map": (sm or {}).get("cross", {}),
                "model": next((s.get("model") for s in (sp, sb, sm) if s and s.get("model")), None), "basis": basis}
    if not (P and Bu): b["sim"]["map"] = {}
    # the rule versions the coding was made under, read from the run records (never assumed from the current rules)
    b["rule_versions"] = sorted({r["rule_version"] for r in b["runs"] if r.get("rule_version")})
    if extra: b.update(extra)
    # figures: the texts refer to "figs/<key>/<file>"; the unit keeps them in text/figs/
    for u in (P, Bu):
        if not u: continue
        src = u["_dir"] / "text" / "figs"
        if src.exists():
            dst = out / "figs" / u["key"]
            if dst.exists(): shutil.rmtree(dst)
            shutil.copytree(src, dst)
    s = json.dumps(b, ensure_ascii=False)
    if fig_base:   # a bundle served from elsewhere (the pipeline server): image paths become absolute addresses
        s = s.replace('"figs/', '"' + fig_base.rstrip("/") + '/figs/'); b = json.loads(s)
    (out / "bundle.json").write_text(s, encoding="utf-8")
    print(f"  bundle {bid} -> {out}: sides {sides}, coded {coded}; {len(b['Q'])} paper metrics, {len(b['rels'])} relations, {len(b['PR'])} prose links, "
          f"{len(b['B'])} blog metrics, {len(b['E'])} blog links; similarity on {basis}; audit failures {len(F)}")
    return b
