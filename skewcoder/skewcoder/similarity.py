"""Similarity scores for the viewer's two sliders. Metrics are related here by WORDING or MEANING only,
never through links, equations or mappings:

  metric boundary   within one side, every pair of metrics gets a cosine similarity; the viewer groups metrics at or
                    above the slider's threshold.
  mapping fold      every blog metric against every paper metric (top 8 kept); the viewer folds a blog metric with no
                    by-name mapping into its nearest paper metric when the score clears the slider.

Two bases: "names" (each metric's names: a paper metric's phrase aliases, a blog metric's cleaned label) and "definitions"
(the one-line definitions each side's coder wrote blind to the other side, coding/definitions.json). The viewer uses
definitions when both sides have them, names otherwise. Embeddings: a local sentence-transformer (config.embed_model(),
default all-mpnet-base-v2), no network after the first download.

Writes, per unit:   coding/similarity_names.json, coding/similarity_definitions.json      {"model", "pairs": {"a|b": s}}
        per pair:   <blog>/coding/similarity_map_<paper key>_{names,definitions}.json     {"model", "cross": {blog id: {key: s}}}
"""
import json, re
from pathlib import Path
from . import config

PREFIX = re.compile(r"^(method|model|regime|setting|platform|input model|qualifier|task|representation|hardware|code)\s*:\s*", re.I)
DEF_PREFIX = re.compile(r"^\s*[A-Za-z -]{0,25}?(setting|method|model|regime|platform|task)\s*:\s*", re.I)
_MODEL = {}


def clean(x):
    """Embed the metric's name only: strip a coder's category prefix ("Method: "), a trailing parenthetical gloss and a
    trailing symbol ("Number of qubits n")."""
    x = PREFIX.sub("", (x or "").strip())
    x = re.sub(r"\s*\([^()]*\)\s*$", "", x)
    x = re.sub(r"\s+(\$?\\?[A-Za-z]{1,3}(_\{?\w+\}?)?(\([^)]*\))?\$?)$", lambda m: "" if len(x.split()) > 1 else m.group(0), x)
    return x.strip()


def is_symbol(a):
    a = (a or "").strip()
    return bool(re.fullmatch(r"\$?\\?[A-Za-z]{1,3}(_\{?[\w,]+\}?)?(\^\{?\w+\}?)?(\([^)]*\))?\$?", a)) or a.startswith("\\")


def names_text(label, aliases):
    """Paper metric: its phrase aliases (verbatim from the paper), the cleaned label only when it has none. Blog metric
    (aliases=None): its cleaned label. Never sentence context, which would carry the words of a link."""
    parts, seen = [], set()
    for x in [a for a in (aliases or []) if not is_symbol(a)] or [label]:
        x = clean(x)
        if x and x.lower() not in seen: seen.add(x.lower()); parts.append(x)
    return "; ".join(parts) or (label or "")


def _model():
    name = config.embed_model()
    if name not in _MODEL:
        try: from sentence_transformers import SentenceTransformer
        except ImportError: raise SystemExit("similarity needs the optional extra: pip install 'skewcoder[similarity]'")
        _MODEL[name] = SentenceTransformer(name, device="cpu")
    return _MODEL[name]


def _enc(texts): return _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)


def _j(p): return json.loads(Path(p).read_text(encoding="utf-8"))


def items(unit_dir, basis):
    """[(id, text)] for a unit on one basis, or None when that basis is not available."""
    u = Path(unit_dir); kind = _j(u / "unit.json")["kind"]
    if basis == "definitions":
        p = u / "coding" / "definitions.json"
        if not p.exists(): return None
        return [(k, DEF_PREFIX.sub("", v)) for k, v in _j(p)["definitions"].items()]
    if kind == "paper": return [(q["key"], names_text(q["label"], q.get("aliases"))) for q in _j(u / "coding" / "paper_quantities.json")["paper_quantities"]]
    return [(b["id"], names_text(b["label"], None)) for b in _j(u / "coding" / "blog_metrics.json")["blog_concepts"]]


def score_unit(unit_dir):
    import numpy as np  # noqa: F401  (sentence-transformers brings it)
    u = Path(unit_dir); out = {}
    for basis in ("names", "definitions"):
        it = items(u, basis)
        if not it: continue
        keys = [k for k, _ in it]; E = _enc([t for _, t in it]); S = E @ E.T
        pairs = {keys[i] + "|" + keys[j]: round(float(S[i, j]), 4) for i in range(len(keys)) for j in range(i + 1, len(keys))}
        (u / "coding" / f"similarity_{basis}.json").write_text(json.dumps({"_doc": f"Cosine similarity of {basis} (skewcoder.similarity).", "model": config.embed_model(),
                                                                           "texts": dict(it), "pairs": pairs}, ensure_ascii=False), encoding="utf-8")
        out[basis] = len(keys)
    print(f"  similarity {u.name}: " + ", ".join(f"{b} ({n} metrics)" for b, n in out.items()))
    return out


def score_pair(blog_dir, paper_dir):
    import numpy as np
    b, p = Path(blog_dir), Path(paper_dir); pkey = _j(p / "unit.json")["key"]; done = []
    for basis in ("names", "definitions"):
        ib, ip = items(b, basis), items(p, basis)
        if not ib or not ip: continue
        X = _enc([t for _, t in ib]) @ _enc([t for _, t in ip]).T; pk = [k for k, _ in ip]; cross = {}
        for i, (bid, _) in enumerate(ib):
            order = np.argsort(-X[i])[:8]; cross[bid] = {pk[j]: round(float(X[i, j]), 4) for j in order}
        (b / "coding" / f"similarity_map_{pkey}_{basis}.json").write_text(json.dumps({"_doc": f"Blog metric x paper metric cosine similarity of {basis}, top 8 per blog metric (skewcoder.similarity).",
                                                                                     "model": config.embed_model(), "cross": cross}, ensure_ascii=False), encoding="utf-8")
        done.append(basis)
    print(f"  similarity map {b.name} x {p.name}: {', '.join(done) or 'nothing (no codings)'}")
    return done
