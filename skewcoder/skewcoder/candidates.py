"""Mechanical half of part (d): every paper name (alias) found in the blog text, laid beside the blog coder's mentions.
Nothing is decided here."""
import json, re, unicodedata
from pathlib import Path
from .audit import loose_re
from .textbuild import plain, locate_quote
from .texts import load_doc


def sentences(doc):
    for b in doc["blocks"]:
        if b["type"] in ("eq", "fig", "table") or not b.get("html"): continue
        t = unicodedata.normalize("NFKC", plain(b["html"]))
        for m in re.finditer(r"[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$", t):
            s = m.group(0).strip()
            if s: yield b["id"], s, m.start()


def build(blog_dir, paper_dir):
    blog_dir, paper_dir = Path(blog_dir), Path(paper_dir)
    blog = load_doc(blog_dir)
    Q = json.loads((paper_dir / "coding" / "paper_quantities.json").read_text(encoding="utf-8"))["paper_quantities"]
    # lay the hits beside the blog coder's own nodes (before any mapping), so a re-mapping starts clean
    src = blog_dir / "coding" / "blog_metrics_premap.json"
    if not src.exists(): src = blog_dir / "coding" / "blog_metrics.json"
    B = json.loads(src.read_text(encoding="utf-8"))["blog_concepts"]
    sents = list(sentences(blog)); hits = []
    for q in Q:
        un = q.get("unlocated") or {}
        for a in q.get("aliases", []):
            if a in un: continue
            rx = loose_re(a)
            if rx is None: continue
            for bid, s, _ in sents:
                if rx.search(s): hits.append({"key": q["key"], "alias": a, "block": bid, "sentence": s})
    covered = set(); nodes = []
    for b in B:
        ms = []
        for m in b.get("mentions", []) or []:
            loc = locate_quote(blog, m["quote"]); here = []
            if loc:
                qn = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", m["quote"])).strip().lower()
                for i, hh in enumerate(hits):
                    if hh["block"] != loc["block"]: continue
                    if qn[:60] in hh["sentence"].lower() or hh["sentence"].lower()[:60] in qn or hh["sentence"].lower().find(qn[:40]) >= 0:
                        here.append({"key": hh["key"], "alias": hh["alias"]}); covered.add(i)
            ms.append({"quote": m["quote"], "frame": m.get("frame"), "paper_names_in_sentence": here})
        nodes.append({"id": b["id"], "label": b["label"], "kind": b.get("kind"), "mentions": ms})
    elsewhere = {}
    for i, hh in enumerate(hits):
        if i in covered: continue
        elsewhere.setdefault(hh["key"], []).append({"alias": hh["alias"], "block": hh["block"], "sentence": hh["sentence"]})
    out = {"blog": blog_dir.name, "paper": paper_dir.name,
           "paper_metrics": [{"key": q["key"], "label": q["label"], "names": q.get("aliases", [])} for q in Q],
           "blog_nodes": nodes, "paper_name_hits_outside_coded_mentions": elsewhere,
           "_doc": "Mechanical candidates (skewcoder candidates). A hit is a paper name found in a blog sentence by the loosened matcher; nothing here is a decision."}
    (blog_dir / "coding").mkdir(exist_ok=True)
    (blog_dir / "coding" / "map_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_in = sum(1 for n in nodes for m in n["mentions"] if m["paper_names_in_sentence"])
    print(f"  {blog_dir.name}: {len(hits)} paper-name hits; {n_in} coded mentions carry a paper name; {sum(len(v) for v in elsewhere.values())} hits outside coded mentions on {len(elsewhere)} paper metrics")
    return out
