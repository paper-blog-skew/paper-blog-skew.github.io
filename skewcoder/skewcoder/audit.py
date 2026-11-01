"""Part (e): the validation gates, mechanical.

paper side  A4  every name of a paper metric carries a quote (alias_quotes) that is located in the paper and contains
                the name; the name itself is found in the paper text by the loosened matcher, or (a one- or two-letter
                symbol) by its quote.
            B   every prose-link quote and condition quote is located; every key named by a link, a relation or a
                condition exists in the metric list; every numbered equation is in some relation's data-eq or in
                uncoded_equations with a reason; the links coder's `missing_metrics` are reported, never silently added.
blog side   C   every mention quote is located; every alias_used word occurs in the blog; every preimage key exists in
                the paper's metric list; a mapping is "by name" only when alias_used is a variant of a paper name AND
                occurs in that node's own mention sentences; any other mapping fails.
            D   every link quote is located; both ends (and condition ends) are coded nodes.
Polarity on every link row is "positive" or "negated"; no other value.
Also:
completeness every mechanical metric candidate (completeness.py; candidates.json in a sandbox, else
                text/metric_candidates.json) is a coded name (normalised equality) or listed under not_metrics with a
                reason, or lies wholly in sections excluded under not_metric_sections with a reason.
mapping   by name only: mapping "inferred" fails; every preimage key needs alias_used found in the node's mentions.
missing   every missing_metrics entry (links reports, mapping_report.json) has a name and a sentence that locates
                (in the paper for the mapping step).
Nothing is dropped here; it reports. Exit 1 on any failure.
"""
import html as H, json, re, sys, unicodedata
from pathlib import Path
from .textbuild import locate_quote, plain
from .texts import load_doc

POLARITY = {"positive", "negated"}


def loose_re(a):
    """Port of the viewer's looseRe: words split on space/hyphen/underscore, each with a plural-tolerant suffix, joined by
    whitespace-or-hyphen, word-bounded, case-insensitive. None when the name is too short."""
    a2 = str(a).strip()
    if len(re.sub(r"[_\s()]", "", a2)) < 3: return None
    parts = []
    for w in [x for x in re.split(r"[\s\-_]+", a2) if x]:
        base = w.replace("(", "").replace(")", ""); suf = ""
        if len(base) > 4 and base.lower().endswith("ies"): base, suf = base[:-3], "(?:y|ies)"
        elif len(base) > 4 and base.lower().endswith("es"): base, suf = base[:-2], "(?:e|es|s)?"
        elif len(base) > 3 and base.lower().endswith("s"): base, suf = base[:-1], "(?:s|es)?"
        elif len(base) > 3 and base.lower().endswith("y"): base, suf = base[:-1], "(?:y|ies)"
        elif len(base) > 3: suf = "(?:s|es)?"
        parts.append(re.escape(base) + suf)
    try: return re.compile(r"(^|[^A-Za-z0-9])(" + r"[\s\-]+".join(parts) + r")(?![A-Za-z0-9])", re.I)
    except re.error: return None


def doc_text_blocks(doc):
    for b in doc["blocks"]:
        if b["type"] in ("eq", "fig", "table") or not b.get("html"): continue
        yield b["id"], unicodedata.normalize("NFKC", plain(b["html"]))


def count_in_doc(doc, phrase):
    rx = loose_re(phrase)
    if rx is None or not doc: return None
    return sum(len(rx.findall(t)) for _, t in doc_text_blocks(doc))


def in_quote(name, quote):
    # a symbol with a subscript is written "F_XEB" / "e_2_c" in the coder's text file; the matcher splits names on
    # "_" and joins the parts with space-or-hyphen, so the quote (and the doc text, where tags are masked to spaces) is read
    # with "_" and "^" as spaces before matching
    rx = loose_re(name); q = unicodedata.normalize("NFKC", quote).replace("_", " ").replace("^", " ")
    if rx is not None: return bool(rx.search(q))
    return unicodedata.normalize("NFKC", name).replace("_", " ").replace("^", " ") in q   # short symbol: exact substring, same normalisation


def parse_relations(html):
    out = []
    for m in re.finditer(r'<template data-id="([^"]+)" data-eq="([^"]+)" data-vars="([^"]+)"([^>]*)>', html):
        tid, eq, vs, attrs = m.groups()
        cond = {k: H.unescape(v) for k, v in re.findall(r'data-(cond|cond-quote|cond-where|cond-vars|polarity)="([^"]*)"', attrs)}
        nums = []
        for part in eq.split(","):
            r = re.findall(r"\d+", part)
            if len(r) == 2 and "-" in part: nums += list(range(int(r[0]), int(r[1]) + 1))
            else: nums += [int(x) for x in r]
        out.append({"id": tid, "eq": eq, "nums": nums, "vars": vs.split(), "cond_quote": cond.get("cond-quote", ""), "cond_vars": cond.get("cond-vars", "").split(), "polarity": cond.get("polarity", "positive")})
    return out


def _candidates(unit_dir, coding_dir):
    for p in (Path(coding_dir) / "candidates.json", Path(unit_dir) / "text" / "metric_candidates.json"):
        if p.exists(): return json.loads(p.read_text(encoding="utf-8")).get("candidates", [])
    return None


def _completeness(fail, W, counts, kind, coded, top, unit_dir, coding_dir):
    """Every candidate accounted for."""
    from . import completeness as CP
    cands = _candidates(unit_dir, coding_dir)
    if cands is None: W.append("no metric candidates file: completeness not checked (run completeness.build)"); return
    nm = top.get("not_metrics") or []
    for x in nm:
        if not (x.get("reason") or "").strip(): fail("not-metric-without-reason", x.get("phrase"), "every not_metrics entry needs a reason")
    un = CP.unaccounted(cands, kind, coded, nm, top.get("not_metric_sections"))
    counts.update({"candidates": len(cands), "candidates_unaccounted": len(un)})
    for c in un: fail("candidate-unaccounted", f"“{c['phrase']}” ×{c['count']}", f"{c['occurrences'][0]['block']} §{c['occurrences'][0]['sec']}: {c['occurrences'][0]['sentence'][:120]}")


def _missing(fail, counts, rows, doc, where, label):
    counts[label] = len(rows)
    for mm in rows:
        if not (mm.get("name") or "").strip(): fail("missing-metric-without-name", where, str(mm)[:120])
        q = mm.get("quote") or mm.get("sentence") or ""
        if not q: fail("missing-metric-without-sentence", f"{where} “{mm.get('name')}”", "a missing metric is reported with the sentence that needs it")
        elif doc is not None and not locate_quote(doc, q): fail("missing-metric-sentence-not-located", f"{where} “{mm.get('name')}”", q[:140])


def _load(path, field):
    p = Path(path)
    if not p.exists(): return None
    j = json.loads(p.read_text(encoding="utf-8"))
    return j if field is None else j.get(field, [])


def audit_paper(paper_dir, strict=True, doc=None, coding_dir=None):
    """paper_dir is a unit folder (text/ + coding/); or pass doc and coding_dir explicitly (sandbox check)."""
    paper_dir = Path(paper_dir); doc = doc or load_doc(paper_dir); c = Path(coding_dir) if coding_dir else paper_dir / "coding"
    F, W, counts = [], [], {}
    def fail(kind, where, detail): F.append({"unit": paper_dir.name, "side": "paper", "kind": kind, "where": where, "detail": detail})
    Q = _load(c / "paper_quantities.json", "paper_quantities")
    if Q is None: W.append(f"{paper_dir.name}: no metrics coded yet"); return {"unit": paper_dir.name, "failures": F, "notes": W, "counts": counts}
    keys = {q["key"] for q in Q}
    if len(keys) < len(Q): fail("duplicate-key", "paper_quantities", str([q["key"] for q in Q if [x["key"] for x in Q].count(q["key"]) > 1]))
    counts.update({"metrics": len(Q), "names": 0, "names_found": 0, "names_by_quote": 0, "names_missing": 0})
    for q in Q:
        aq = q.get("alias_quotes") or {}; un = q.get("unlocated") or {}
        if not q.get("aliases"): fail("metric-without-name", q["key"], "every metric needs at least one name (alias)")
        for a in q.get("aliases", []):
            counts["names"] += 1
            n = count_in_doc(doc, a); quote = aq.get(a); qloc = locate_quote(doc, quote) if quote else None
            if strict and not quote: fail("name-without-quote", f"{q['key']} “{a}”", "every name needs a located quote in alias_quotes")
            if strict and not (q.get("alias_frames") or {}).get(a): fail("name-without-frame", f"{q['key']} “{a}”", "every name needs the measurement frame it sits in (alias_frames)")
            if quote and not qloc: fail("name-quote-not-located", f"{q['key']} “{a}”", quote[:140])
            if quote and qloc and not in_quote(a, quote): fail("name-not-in-its-quote", f"{q['key']} “{a}”", quote[:140])
            if n: counts["names_found"] += 1
            elif qloc and in_quote(a, quote): counts["names_by_quote"] += 1
            elif a in un: W.append({"key": q["key"], "name": a, "reason": un[a]})
            else: counts["names_missing"] += 1; fail("name-not-in-paper", f"{q['key']} “{a}”", "no occurrence in the paper text" + ("" if n is not None else " (too short for the matcher; needs a quote)"))
        for a, s in (q.get("naming_sentences") or {}).items():
            # a second name joins a metric only on a naming construction, quoted
            if a not in q.get("aliases", []): fail("naming-sentence-for-unknown-name", f"{q['key']} “{a}”", "naming_sentences keys must be names of the metric")
            if not locate_quote(doc, s): fail("naming-sentence-not-located", f"{q['key']} “{a}”", s[:140])
    _completeness(fail, W, counts, "paper", Q, _load(c / "paper_quantities.json", None) or {}, paper_dir, c)
    # ---- links (may be absent: metrics-only state)
    PR = _load(c / "paper_prose_links.json", "paper_prose_links")
    relp = c / "relations.html"; rels = parse_relations(relp.read_text(encoding="utf-8")) if relp.exists() else None
    LR = _load(c / "paper_links_report.json", None) or {}
    if PR is None and rels is None: W.append(f"{paper_dir.name}: no links coded yet"); return {"unit": paper_dir.name, "failures": F, "notes": W, "counts": counts}
    PR = PR or []; rels = rels or []
    counts.update({"prose": len(PR), "relations": len(rels), "uncoded_equations": len(LR.get("uncoded_equations") or []), "missing_metrics": len(LR.get("missing_metrics") or [])})
    seen_ids = set()
    for l in PR:
        if l.get("id") in seen_ids: fail("prose-duplicate-id", l.get("id"), "")
        seen_ids.add(l.get("id"))
        for k in ("a", "b"):
            if l.get(k) not in keys: fail("prose-unknown-key", l.get("id"), str(l.get(k)))
        if l.get("a") == l.get("b"): fail("prose-self-link", l.get("id"), l.get("a"))
        for k in l.get("condition_vars", []) or []:
            if k not in keys: fail("prose-unknown-condition-key", l.get("id"), k)
        if l.get("polarity") not in POLARITY: fail("prose-polarity", l.get("id"), f"polarity must be positive or negated, got {l.get('polarity')!r}")
        if not l.get("quote") or not locate_quote(doc, l["quote"]): fail("prose-quote-not-located", l.get("id"), (l.get("quote") or "")[:140])
        if l.get("condition_quote") and not locate_quote(doc, l["condition_quote"]): fail("condition-quote-not-located", l.get("id"), l["condition_quote"][:140])
    eq_nums = {b["num"] for b in doc["blocks"] if b["type"] == "eq" and b.get("num")}
    covered = set()
    for r in rels:
        for k in r["vars"] + r["cond_vars"]:
            if k not in keys: fail("relation-unknown-key", r["id"], k)
        if len(set(r["vars"])) < 2: fail("relation-fewer-than-two-metrics", r["id"], " ".join(r["vars"]))
        if r["polarity"] not in POLARITY: fail("relation-polarity", r["id"], r["polarity"])
        if r["cond_quote"] and not locate_quote(doc, r["cond_quote"]): fail("relation-condition-quote-not-located", r["id"], r["cond_quote"][:140])
        for n in r["nums"]:
            if eq_nums and n not in eq_nums: fail("relation-unknown-equation", r["id"], f"({n}) is not a numbered equation of the text")
            covered.add(n)
    for u in LR.get("uncoded_equations") or []:
        covered.add(int(u["eq"]))
        if not u.get("reason"): fail("uncoded-equation-without-reason", f"({u['eq']})", "")
    for n in sorted(eq_nums - covered): fail("equation-not-covered", f"({n})", "every numbered equation is in a relation's data-eq or in uncoded_equations with a reason")
    _missing(fail, counts, LR.get("missing_metrics") or [], doc, "paper_links_report", "missing_metrics")
    for mm in LR.get("missing_metrics") or []:
        W.append({"missing_metric": mm.get("name"), "quote": (mm.get("quote") or "")[:140], "note": "goes to the metrics-append pass"})
    leads = _load(c / "relation_leads.json", "leads") or {}
    for rid, items in leads.items():
        for it in items:
            if it.get("var") not in keys: fail("lead-unknown-key", rid, str(it.get("var")))
            if it.get("quote") and not locate_quote(doc, it["quote"]): W.append({"lead_not_located": rid, "quote": it["quote"][:140]})
    return {"unit": paper_dir.name, "failures": F, "notes": W, "counts": counts}


def audit_blog(blog_dir, paper_dir=None, strict=True, doc=None, coding_dir=None, paper_coding_dir=None, paper_doc=None):
    """blog_dir is a unit folder; paper_dir the paper unit the blog maps onto (needed once preimages exist);
    or pass doc, coding_dir and paper_coding_dir explicitly (sandbox check)."""
    blog_dir = Path(blog_dir); doc = doc or load_doc(blog_dir); c = Path(coding_dir) if coding_dir else blog_dir / "coding"
    F, W, counts = [], [], {}
    def fail(kind, where, detail): F.append({"unit": blog_dir.name, "side": "blog", "kind": kind, "where": where, "detail": detail})
    B = _load(c / "blog_metrics.json", "blog_concepts")
    if B is None: W.append(f"{blog_dir.name}: no metrics coded yet"); return {"unit": blog_dir.name, "failures": F, "notes": W, "counts": counts}
    bids = [b["id"] for b in B]
    if len(set(bids)) < len(bids): fail("duplicate-id", "blog_metrics", str([x for x in bids if bids.count(x) > 1]))
    bids = set(bids)
    counts.update({"blog_metrics": len(B), "mentions": 0})
    for b in B:
        ms = b.get("mentions") or []
        if not ms: fail("node-without-mention", b["id"], "every blog metric needs at least one quoted mention")
        for m in ms:
            counts["mentions"] += 1
            if not m.get("quote") or not locate_quote(doc, m["quote"]): fail("mention-quote-not-located", b["id"], (m.get("quote") or "")[:140])
            if strict and not m.get("frame"): fail("mention-without-frame", b["id"], "every mention needs the measurement frame it sits in")
    _completeness(fail, W, counts, "blog", B, _load(c / "blog_metrics.json", None) or {}, blog_dir, c)
    # ---- mapping (needs the paper)
    pcd = Path(paper_coding_dir) if paper_coding_dir else (Path(paper_dir) / "coding" if paper_dir else None)
    Q = _load(pcd / "paper_quantities.json", "paper_quantities") if pcd else None
    if any(b.get("preimage") for b in B):
        if Q is None: fail("mapping-without-paper", "blog_metrics", "preimages are set but no paper folder was given to check them against")
        else:
            QI = {q["key"]: q for q in Q}; counts.update({"mappings": 0, "mappings_by_name": 0, "mappings_inferred": 0, "recovered": sum(1 for b in B if b.get("class") == "recovered")})
            for b in B:
                for k, w in (b.get("alias_used") or {}).items():
                    if w and count_in_doc(doc, w) == 0: fail("alias_used-not-in-blog", f"{b['id']}→{k}", f"“{w}”")
                for k in b.get("preimage", []) or []:
                    counts["mappings"] += 1
                    if k not in QI: fail("preimage-unknown-key", b["id"], k); continue
                    names = [a for a in QI[k].get("aliases", []) if a not in (QI[k].get("unlocated") or {})]
                    w = ((b.get("alias_used") or {}).get(k) or "").strip()
                    mts = " ".join(unicodedata.normalize("NFKC", m.get("quote", "")) for m in (b.get("mentions") or []))
                    hit = bool(w) and any(in_quote(a, w) or in_quote(w, a) for a in names) and in_quote(w, mts)
                    if hit: counts["mappings_by_name"] += 1
                    else: fail("mapping-rests-on-no-paper-name", f"{b['id']}→{k}", "mapping is by name only — alias_used must be a paper name occurring in this node's mentions; otherwise leave the preimage empty (folding is the viewer's mapping-granularity slider)")
                if b.get("mapping") == "inferred": counts["mappings_inferred"] += 1; fail("inferred-mapping-not-allowed", b["id"], "no inferred mappings")
    else: W.append(f"{blog_dir.name}: not mapped yet")
    MR = _load(c / "mapping_report.json", None)
    if MR is not None:
        if paper_doc is None and paper_dir: paper_doc = load_doc(paper_dir)
        _missing(fail, counts, MR.get("missing_metrics") or [], paper_doc, "mapping_report", "missing_paper_metrics")
    E = _load(c / "blog_links.json", "blog_edges")
    if E is None: W.append(f"{blog_dir.name}: no links coded yet"); return {"unit": blog_dir.name, "failures": F, "notes": W, "counts": counts}
    counts["blog_links"] = len(E)
    LR = _load(c / "blog_links_report.json", None) or {}
    _missing(fail, counts, LR.get("missing_metrics") or [], doc, "blog_links_report", "missing_metrics")
    for mm in LR.get("missing_metrics") or []: W.append({"missing_metric": mm.get("name"), "quote": (mm.get("quote") or "")[:140], "note": "goes to the metrics-append pass"})
    seen = set()
    for e in E:
        pk = (e.get("source"), e.get("target"))
        if pk in seen: fail("link-duplicate", f"{pk[0]}→{pk[1]}", "one edge per ordered pair; put further sentences in quotes[]")
        seen.add(pk)
        if e.get("source") not in bids or e.get("target") not in bids: fail("link-unknown-end", f"{e.get('source')}→{e.get('target')}", "")
        if e.get("source") == e.get("target"): fail("link-self", e.get("source"), "")
        for k in e.get("condition_vars", []) or []:
            if k not in bids: fail("link-unknown-condition-end", f"{e.get('source')}→{e.get('target')}", k)
        if e.get("polarity") not in POLARITY: fail("link-polarity", f"{e.get('source')}→{e.get('target')}", f"got {e.get('polarity')!r}")
        if "type" in e: fail("link-typed-against-paper", f"{e.get('source')}→{e.get('target')}", "the blog coder cannot type an edge against the paper; remove `type`")
        if not e.get("quote") or not locate_quote(doc, e["quote"]): fail("link-quote-not-located", f"{e.get('source')}→{e.get('target')}", (e.get("quote") or "")[:140])
        for q in (e.get("quotes") or [])[1:]:
            if not locate_quote(doc, q): fail("link-extra-quote-not-located", f"{e.get('source')}→{e.get('target')}", q[:140])
        if e.get("condition_quote") and not locate_quote(doc, e["condition_quote"]): fail("link-condition-quote-not-located", f"{e.get('source')}→{e.get('target')}", e["condition_quote"][:140])
    return {"unit": blog_dir.name, "failures": F, "notes": W, "counts": counts}


def show(rep):
    print(f"  {rep['unit']}: {rep['counts']}")
    for n in rep["notes"]: print(f"    note: {n}")
    for f in rep["failures"]: print(f"    FAIL {f['side']} {f['kind']} {f['where']}: {f['detail']}")
    return len(rep["failures"])


def audit_algebra(work):
    """Equations as formulas (brief paper_algebra.md): every relation and equation covered, every formula parses over the
    relation's keys and declared auxiliary symbols, every pair uses the relation's keys; then the reduction must run."""
    from . import algebra
    work = Path(work); F = []
    def fail(k, w, d): F.append({"unit": work.name, "side": "paper", "kind": k, "where": w, "detail": d})
    rels = parse_relations((work / "relations.html").read_text(encoding="utf-8"))
    keys = [q["key"] for q in json.loads((work / "paper_quantities.json").read_text(encoding="utf-8"))["paper_quantities"]]
    p = work / "equations.json"
    if not p.exists(): fail("missing_file", "equations.json", "not written"); return {"unit": work.name, "notes": [], "failures": F, "counts": {}}
    try: E = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: fail("unreadable", "equations.json", str(e)); return {"unit": work.name, "notes": [], "failures": F, "counts": {}}
    for f in algebra.check(E, rels, keys): fail(f["kind"], f["where"], f["detail"])
    counts = {"relations": len(rels)}
    if not F:
        try:
            A = algebra.analyze(E, rels, keys); counts.update(A["counts"]); notes = A["notes"]
        except Exception as e: fail("reduction-failed", "equations.json", f"{type(e).__name__}: {e}"[:300]); notes = []
    else: notes = []
    return {"unit": work.name, "notes": notes, "failures": F, "counts": counts}


DEP_WORDS = re.compile(r"\b(depends?|dependent|depending|scales (?:with|as)|scaling (?:with|as)|scaled|grows?|growing|limits?|limited|limiting|determines?|determined|requires?|required|because|leads? to|proportional|increases?|increasing|decreases?|decreasing|affects?|affected|as a function of|bounded|causes?|caused|enables?|allows?|improves?|reduces?)\b", re.I)


def audit_definitions(work, kind):
    """Definition pass: one definition per metric, 6-25 words, no dependence words, no multi-word name of
    another metric on the list."""
    work = Path(work); F = []
    def fail(k, w, d): F.append({"unit": work.name, "side": kind, "kind": k, "where": w, "detail": d})
    if kind == "paper":
        items = {q["key"]: [q["label"]] + list(q.get("aliases", [])) for q in json.loads((work / "paper_quantities.json").read_text(encoding="utf-8"))["paper_quantities"]}
    else:
        items = {b["id"]: [b["label"]] + [m.get("matched") for m in b.get("mentions", []) if m.get("matched")] for b in json.loads((work / "blog_metrics.json").read_text(encoding="utf-8"))["blog_concepts"]}
    p = work / "definitions.json"
    if not p.exists(): fail("missing_file", "definitions.json", "not written"); return {"unit": work.name, "notes": [], "failures": F, "counts": {}}
    D = json.loads(p.read_text(encoding="utf-8")).get("definitions", {})
    for k in items:
        if k not in D: fail("missing_definition", k, "no definition")
    for k in D:
        if k not in items: fail("unknown_id", k, "not on the metric list")
    multi = {k: [n for n in names if n and len(n.split()) >= 2] for k, names in items.items()}
    for k, d in D.items():
        if k not in items: continue
        n = len(str(d).split())
        if n < 6 or n > 25: fail("length", k, f"{n} words")
        m = DEP_WORDS.search(str(d))
        if m: fail("dependence_word", k, f"“{m.group(0)}” in: {d}")
        low = str(d).lower()
        for o, names in multi.items():
            if o == k: continue
            own = {x.lower() for x in items[k] if x}
            for nm in names:
                if nm.lower() in low and nm.lower() not in own: fail("other_metric_name", k, f"names another metric ({o}: “{nm}”)"); break
    return {"unit": work.name, "notes": [], "failures": F, "counts": {"metrics": len(items), "definitions": len(D)}}
