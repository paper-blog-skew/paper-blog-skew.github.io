#!/usr/bin/env python3
"""Build the site from bundles: dist/index.html (front page + paper / blog / map views for every pair) and dist/method.html.

    python3 build.py                  # offline: KaTeX + fonts inlined -> dist/index.html
    python3 build.py --mode cdn       # KaTeX from a CDN (smaller file) -> dist/index-cdn.html

Input: site.json lists the pairs in order, each pointing at a bundle folder (bundle.json + figs/) made by the skewcoder
pipeline. The site computes nothing about the coding: it reads bundles, applies its display rules (below), checks the
bundle is well formed and copies the figures. Needs only the Python 3 standard library.
"""
import argparse, base64, html as _html, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC, VENDOR = ROOT / "src", ROOT / "vendor" / "katex-0.16.9"
FORMAT = "skew-bundle/1"
GOOGLE_FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;'
                '8..60,600&family=Source+Sans+3:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')
KATEX_CDN = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">\n'
             '<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>\n'
             '<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>')
TYPESET_FN = """<script>
function typeset(el){
  if(!window.renderMathInElement) return;
  renderMathInElement(el,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],
    throwOnError:false, ignoredTags:['script','noscript','style','textarea','pre','code','template']});
}
</script>"""
# the fields of a bundle the viewer reads
VIEW_FIELDS = ("id", "status", "sides", "short", "paper", "blog", "scopes", "docs", "anchors", "Q", "PR", "B", "E", "labels", "rels", "alg", "sim")

PREFIX_RX = re.compile(r"^(Method|Model|Regime|Setting|Representation|Task|Input model|Platform|Approximation|Qualifier|Code|Hardware)\s*:\s*")
QUAL_RX = re.compile(r"\b([Qq])ualifier(s?)\b")


def scrub_settings(Q, PR, B, E, labels, rels):
    """Display rule: settings (models, methods, platforms, regimes...) are ordinary metrics. Nothing shown on the
    site marks them apart: the coders' category prefixes ("Method: ", ...) are stripped from labels, the `qualifier` flag is
    dropped, and the word "qualifier" in the coders' notes reads "setting". The bundle is not changed."""
    def word(x): return QUAL_RX.sub(lambda m: ("S" if m.group(1) == "Q" else "s") + "etting" + m.group(2), x)
    def walk(o):
        if isinstance(o, dict): o.pop("qualifier", None); return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list): return [walk(v) for v in o]
        if isinstance(o, str): return word(o)
        return o
    Q, PR, B, E = walk(Q), walk(PR), walk(B), walk(E)
    for q in Q: q["label"] = PREFIX_RX.sub("", q["label"])
    for b in B: b["label"] = PREFIX_RX.sub("", b["label"])
    labels = {k: PREFIX_RX.sub("", word(v)) if isinstance(v, str) else v for k, v in (labels or {}).items()}
    return Q, PR, B, E, labels, walk(rels)


def read(p): return Path(p).read_text(encoding="utf-8")


def fail(msg): sys.exit("BUILD CHECK FAILED: " + msg)


def load(entry, dist, allow_failures=False):
    bdir = ROOT / entry["bundle"]
    if not (bdir / "bundle.json").exists(): fail(f"{entry['id']}: no bundle at {entry['bundle']} (make it with `skewcoder bundle`)")
    b = json.loads(read(bdir / "bundle.json"))
    if b.get("format") != FORMAT: fail(f"{entry['id']}: bundle format {b.get('format')!r}, this site reads {FORMAT}")
    nf = len(b.get("audit", {}).get("failures", []))
    if nf and not (entry.get("accept_audit") or allow_failures):
        fail(f"{entry['id']}: the bundle's codings fail {nf} audit check(s); fix the coding, or give accept_audit with a reason in site.json")
    for side in ("paper", "blog"):                      # display overrides from site.json
        if entry.get(side) and b.get(side) is not None: b[side] = dict(b[side], **entry[side])
    for k in ("short", "scopes"):
        if entry.get(k): b[k] = entry[k]
    b["id"] = entry["id"]
    # figures: copy the bundle's figs/<key>/ into dist/figs/<key>/ and check every image the texts name exists
    if (bdir / "figs").exists():
        for d in (bdir / "figs").iterdir():
            if d.is_dir(): shutil.copytree(d, dist / "figs" / d.name, dirs_exist_ok=True)
    for side in ("paper", "blog"):
        doc = (b.get("docs") or {}).get(side)
        for blk in (doc or {}).get("blocks", []):
            for img in (blk.get("imgs") or []) + ([blk["img"]] if blk.get("img") else []):
                if not (dist / img).exists(): fail(f"{entry['id']}: image {img} is missing from the bundle")
    b["Q"], b["PR"], b["B"], b["E"], b["labels"], b["rels"] = scrub_settings(b["Q"], b["PR"], b["B"], b["E"], b["labels"], b["rels"])
    v = {k: b.get(k) for k in VIEW_FIELDS if k in b}
    v["provenance"] = {"made": b.get("made"), "rule_versions": b.get("rule_versions"), "audit_failures": nf, "accepted_because": entry.get("accept_audit") if nf else None}
    print(f"  {entry['id']}: sides {b.get('sides')}, status {b.get('status')}; {len(b['Q'])} paper metrics, {len(b['rels'])} relations, "
          f"{len(b['PR'])} prose links, {len(b['B'])} blog metrics, {len(b['E'])} blog links; similarity {b['sim'].get('basis')}; audit failures {nf}")
    return v


def metric_counts(pairs):
    """The methods page's table of paper metrics, computed from the bundles this site shows (one row per paper)."""
    rows, seen = [], set()
    for v in pairs.values():
        P = v.get("paper"); Q = v.get("Q") or []
        if not P or not Q or P.get("key") in seen: continue
        seen.add(P.get("key"))
        m = re.match(r"([A-Za-z][A-Za-z-]*?)(\d{4})$", v["id"].split("_")[-1]); name = f"{m.group(1)} et al. {m.group(2)}" if m else P.get("title", "")
        short = (v.get("short") or "").split(" · ")[0]
        sym = sum(1 for q in Q if q.get("kind") == "symbol"); out = sum(1 for q in Q if q.get("scope") not in ("results", "L6"))
        named = sum(1 for q in Q if q.get("naming_sentences"))
        rows.append(f"<tr><td>{_html.escape(name)}{' (' + _html.escape(short) + ')' if short else ''}</td><td>{sym}</td><td>{len(Q) - sym}</td><td>{out}</td><td>{named}</td><td>{len(Q)}</td></tr>")
    return ("<table><tr><th>Paper</th><th>Symbol</th><th>Phrase</th><th>Of which named only outside the abstract and numbered results</th>"
            "<th>Metrics with a second name joined by a naming sentence</th><th>Total</th></tr>\n" + "".join(rows) + "</table>")


def equation_counts(pairs):
    """The methods page's table of the papers' equations after reduction (one row per paper), from the bundles' `alg`."""
    rows, seen = [], set()
    for v in pairs.values():
        P = v.get("paper"); A = v.get("alg")
        if not P or P.get("key") in seen: continue
        seen.add(P.get("key"))
        m = re.match(r"([A-Za-z][A-Za-z-]*?)(\d{4})$", v["id"].split("_")[-1]); name = f"{m.group(1)} et al. {m.group(2)}" if m else P.get("title", "")
        if not A:
            rows.append(f"<tr><td>{_html.escape(name)}</td><td>{len(v.get('rels') or [])}</td><td colspan=\"6\">not reduced</td></tr>"); continue
        c = A.get("counts", {}); L = [l for l in A.get("links", []) if l.get("src") == "algebra"]
        algp = {(l["a"], l["b"]) for l in L}; modp = {(l["a"], l["b"]) for l in A.get("links", []) if l.get("src") == "model"} - algp
        sizes = [l["size"] for l in L if l.get("size")]
        by = ", ".join(f"{n}: {sizes.count(n)}" for n in sorted(set(sizes))) + (f", larger: {sum(1 for l in L if not l.get('size'))}" if any(not l.get("size") for l in L) else "")
        rk = A.get("rank") or {}; rank = (str(next(iter(rk.values()))) if len(rk) == 1 else f"{min(rk.values())}–{max(rk.values())} over {len(rk)} regimes") if rk else "0"
        rows.append(f"<tr><td>{_html.escape(name)}</td><td>{len(v.get('rels') or [])}</td><td>{c.get('equalities', 0)}</td><td>{c.get('redundant', 0)}</td><td>{rank}</td>"
                    f"<td>{c.get('not_algebraic', 0)}</td><td>{len(algp)}{' (' + by + ')' if by else ''}</td><td>{len(modp)}</td></tr>")
    return ("<table><tr><th>Paper</th><th>Equation relations</th><th>Equalities</th><th>Of which redundant</th><th>Rank</th><th>Statements that are not equalities</th>"
            "<th>Pairs linked by the algebra (by size of the smallest linked group)</th><th>Further pairs read by the model</th></tr>\n" + "".join(rows) + "</table>")


def inline_katex():
    css = read(VENDOR / "katex.min.css")
    def fix_src(m):
        parts = re.findall(r'url\(([^)]+)\)\s*format\("?[a-z0-9]+"?\)', m.group(1))
        w2 = [p for p in parts if p.endswith(".woff2")]
        return 'src:url(data:font/woff2;base64,%s) format("woff2")' % base64.b64encode((VENDOR / w2[0]).read_bytes()).decode()
    css = re.sub(r'src:((?:url\([^)]+\)\s*format\("?[a-z0-9]+"?\),?)+)', fix_src, css)
    if "fonts/" in css: fail("a KaTeX font reference was not inlined")
    return ("<style>" + css + "</style>\n<script>" + read(VENDOR / "katex.min.js") + "</script>\n<script>"
            + read(VENDOR / "contrib" / "auto-render.min.js") + "</script>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline", "cdn"], default="offline")
    ap.add_argument("--site", default="site.json")
    ap.add_argument("--out")
    ap.add_argument("--allow-audit-failures", action="store_true", help="build despite audit failures (inspection only; never publish)")
    a = ap.parse_args()
    site = json.loads(read(ROOT / a.site))
    out = Path(a.out) if a.out else ROOT / "dist" / ("index.html" if a.mode == "offline" else "index-cdn.html")
    dist = out.parent; dist.mkdir(parents=True, exist_ok=True)
    if (dist / "figs").exists(): shutil.rmtree(dist / "figs")
    pairs, order = {}, []
    for e in site["pairs"]:
        pairs[e["id"]] = load(e, dist, a.allow_audit_failures); order.append(e["id"])
    data_js = json.dumps(pairs, ensure_ascii=False).replace("</", "<\\/")
    libs = inline_katex() if a.mode == "offline" else (GOOGLE_FONTS + "\n" + KATEX_CDN)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(site.get('title', 'Mapping Technical Artifacts'))}</title>
<style>
{read(SRC / 'css' / 'base.css')}
</style>
<style>
{read(SRC / 'css' / 'skew.css')}
</style>
<style>
{read(SRC / 'css' / 'app.css')}
</style>
{libs}
{TYPESET_FN}
</head>
<body>
<div class="wrap" id="app"></div>
<script>window.PAIRS = {data_js}; window.PAIR_ORDER = {json.dumps(order)}; window.SITE = {json.dumps({k: site[k] for k in ('pipeline_url', 'upload') if k in site})};</script>
<script>
{read(SRC / 'js' / 'app.js')}
</script>
</body>
</html>
"""
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}  ({len(page)//1024} KB, mode={a.mode}, pairs={order})")
    # "How this was made": methods/build_method_doc.py writes the methods page; it rides along as method.html with a back link
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "methods" / "build_method_doc.py")], check=True, capture_output=True)
    src = ROOT / "methods" / "method.html"
    bar = ('<style>.sitebar{position:sticky;top:0;z-index:20;background:#fff;border-bottom:1px solid #e6e8ec;font-size:14px}'
           '.sitebar div{max-width:860px;margin:0 auto;padding:10px 24px;display:flex;gap:18px;align-items:center}'
           '.sitebar a{color:#0072B2;text-decoration:none;font-weight:600}.sitebar a:hover{text-decoration:underline}'
           '.sitebar span{color:#6b7380}</style>'
           '<div class="sitebar"><div><a href="./">← back to the skew site</a><span>How this was made</span></div></div>')
    doc = read(src).replace("<body>", "<body>" + bar, 1).replace("[[METRIC_COUNTS]]", metric_counts(pairs)).replace("[[EQUATION_COUNTS]]", equation_counts(pairs))
    (dist / "method.html").write_text(doc, encoding="utf-8"); print(f"wrote {dist / 'method.html'}")


if __name__ == "__main__":
    main()
