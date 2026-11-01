"""Completeness: the mechanical candidate list a metrics coder must account for in full.

A coder must find every metric first and conflate only through the viewer's metric boundary slider. Checking that coded
names are quoted does not show that every wording was coded: a silent merge of two look-alike wordings, or a wording
left out as minor, would pass. This module lists every phrase in the unit's prose that looks like a
name for a measurable thing; the coder must code each one or list it under `not_metrics` with a reason, and the audit
fails on any candidate left unaccounted for.

Candidates, mechanically, from every prose block (equations, figures and tables are skipped):
  1. "number of X"            X = up to 3 following words, stopping at a stopword, a number or punctuation;
  2. <modifiers> HEAD          HEAD a measurement head (cost, complexity, error, rate, time, size, depth, …),
                               with up to 2 contiguous preceding modifier words (stopwords, numbers, -ly adverbs and
                               generic words such as "same", "such", "more" are not modifiers);
Deduplicated by a normalised form (case, hyphen/space, a final plural). Each candidate keeps its count and up to three
occurrences (block id, section, sentence). Nothing here decides anything: over-generation is expected, and "not a
metric: a value on [x]" or "acknowledgements, not part of the argument" are valid reasons.
"""
import json, re, unicodedata
from pathlib import Path
from .audit import doc_text_blocks
from .texts import load_doc, load_unit

# general measurement heads only
HEADS = ["cost", "costs", "complexity", "complexities", "error", "errors", "rate", "rates", "time", "times",
         "depth", "depths", "overhead", "overheads", "accuracy", "precision", "norm", "norms", "size", "sizes", "count", "counts",
         "probability", "probabilities", "threshold", "thresholds", "volume", "volumes", "speed", "speeds", "speedup", "speedups",
         "runtime", "runtimes", "memory", "bound", "bounds", "scaling", "width", "length", "distance", "variance",
         "temperature", "energy", "frequency", "duration", "throughput", "latency", "yield", "efficiency", "performance",
         "resources", "budget", "gap", "strength", "range", "dimension", "rank", "degree",
         "noise", "lifetime", "entropy", "connectivity", "capacity", "power", "exponent", "factor"]
HEAD_SET = set(HEADS)
STOP = set("""a an the of in on for to and or with by as at from into onto over under than then this that these those its it their
our we they you he she is are was were be been being which who whom whose what when where while if so such same other any each every
all some much many more most less least very further additional new given certain various also only just not no nor both either
neither per via about above below between among within without upon across after before during since until up down out off
can could may might must shall should will would do does did has have had having one two three four five here there thus hence
however therefore e.g i.e etc following previous desired related similar analogous first second third final resulting
corresponding respective above below former latter whole entire same overall-""".replace("overall-", "").split())
WORD = re.compile(r"[A-Za-z][A-Za-z\-']*|\S")


def norm(p):
    """Normalised form for deduplication and for matching a coded name: NFKC, lowercase, hyphen/underscore as space, a final
    plural dropped."""
    p = unicodedata.normalize("NFKC", str(p)).lower().replace("-", " ").replace("_", " ")
    p = re.sub(r"[^a-z0-9 ]+", " ", p); w = p.split()
    if w:
        last = w[-1]
        if len(last) > 4 and last.endswith("ies"): last = last[:-3] + "y"
        elif len(last) > 3 and last.endswith("s") and not last.endswith("ss"): last = last[:-1]
        w[-1] = last
    return " ".join(w)


def sentences(text):
    for m in re.finditer(r"[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$", text):
        s = m.group(0).strip()
        if s: yield s


def is_mod(tok):
    t = tok.lower()
    return bool(re.fullmatch(r"[a-z][a-z\-']*", t)) and t not in STOP and not t.endswith("ly") and len(t) > 1


def candidates_in(sentence):
    toks = WORD.findall(sentence); out = []
    for i, t in enumerate(toks):
        tl = t.lower()
        # 1. number of X
        if tl == "number" and i + 1 < len(toks) and toks[i + 1].lower() == "of":
            j, xs = i + 2, []
            while j < len(toks) and len(xs) < 3 and is_mod(toks[j]): xs.append(toks[j]); j += 1
            if xs: out.append(("number of", "number of " + " ".join(xs)))
        # 2. modifiers + measurement head
        if tl in HEAD_SET:
            mods, j = [], i - 1
            while j >= 0 and len(mods) < 2 and is_mod(toks[j]) and toks[j].lower() not in HEAD_SET | {"number"}: mods.insert(0, toks[j]); j -= 1
            out.append((norm(tl), " ".join(mods + [t])))
    return out


def build(unit_dir, write=True):
    """Write <unit>/text/metric_candidates.json and return it."""
    u = load_unit(unit_dir); d = u["_dir"]; doc = load_doc(d)
    secs = {b["id"]: (b.get("sec") or "") for b in doc["blocks"]}
    C = {}
    def add(head, phrase, bid, s, src):
        k = norm(phrase)
        if not k or len(k) < 3: return
        c = C.setdefault(k, {"phrase": phrase.strip(), "norm": k, "head": head, "source": src, "count": 0, "sections": [], "occurrences": []})
        c["count"] += 1
        sec = secs.get(bid, "")
        if sec not in c["sections"]: c["sections"].append(sec)
        if len(c["occurrences"]) < 3: c["occurrences"].append({"block": bid, "sec": sec, "sentence": s[:300]})
    for bid, text in doc_text_blocks(doc):
        for s in sentences(text):
            for head, phrase in candidates_in(s): add(head, phrase, bid, s, "pattern")
    cands = sorted(C.values(), key=lambda c: (c["head"], c["norm"]))
    out = {"_doc": "Mechanical metric candidates (skewcoder/completeness.py). Every candidate must be coded "
                   "as a metric name (a mechanical variant counts) or listed under not_metrics with a reason; nothing here is a decision.",
           "unit": d.name, "kind": u["kind"], "n": len(cands), "candidates": cands}
    if write: (d / "text" / "metric_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def coded_names(kind, coding):
    """Every wording the coding uses for a metric: paper aliases and labels; blog labels, matched spans and naming sentences' names."""
    names = set()
    if kind == "paper":
        for q in coding:
            for a in [q.get("label", "")] + list(q.get("aliases") or []): names.add(norm(a))
    else:
        for b in coding:
            names.add(norm(b.get("label", "")))
            names.add(norm(re.sub(r"\s*\([^()]*\)\s*$", "", b.get("label", ""))))
            for m in b.get("mentions") or []:
                if m.get("matched"): names.add(norm(m["matched"]))
            for a in (b.get("naming_sentences") or {}): names.add(norm(a))
    names.discard(""); return names


def unaccounted(cands, kind, coding, not_metrics, not_metric_sections=None):
    """Candidates neither coded (a coded name whose normalised form equals the candidate: a wording inside a longer coded
    name does not count, since "cost" and "combination cost" are two wordings)
    nor listed under not_metrics with a reason (by phrase), nor lying wholly in sections excluded with a reason."""
    names = coded_names(kind, coding)
    nm = {norm(x.get("phrase", "")) for x in (not_metrics or []) if (x.get("reason") or "").strip()}
    xsec = set()
    for x in not_metric_sections or []:
        if (x.get("reason") or "").strip(): xsec.update(str(s) for s in (x.get("sections") or []))
    out = []
    for c in cands:
        k = c["norm"]
        if k in names or k in nm: continue
        if xsec and all(s in xsec for s in c["sections"]): continue
        out.append(c)
    return out
