#!/usr/bin/env python3
"""Build methods/method.html (self-contained, inline SVG figures) and its three figures as standalone SVG files
(figures 1 and 2 are the author's files in figure_files/; figure 3 is drawn here).

    python3 build_method_doc.py

Figures follow the accessibility rules: every distinction is carried without colour first (solid / dashed borders,
line weight and dash pattern, tint on/off), colour is Okabe-Ito blue only, and every figure carries a "How to read" line.
"""
import html, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
INK, QUIET, EDGE, GRID, ACC, TINT = "#1f2328", "#6b7380", "#8a8f98", "#c9ccd3", "#0072B2", "#e3eef7"
TEAL = "#0b6e74"   # node colour on the site

# ------------------------------------------------------------------ svg helpers
def text(x, y, s, size=13, weight=400, fill=INK, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{html.escape(s)}</text>'

def box(x, y, w, h, dashed=False, main=False):
    st = ACC if main else EDGE
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{TINT if main else "none"}" stroke="{st}" '
            f'stroke-width="{2 if main else 1.25}" stroke-dasharray="{"5 4" if dashed else "0"}"/>')

def svg(w, h, title, body, marker="arrow", mcolor=EDGE):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{html.escape(title)}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif" font-size="13">'
            f'<defs><marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M0 0L10 5L0 10z" fill="{mcolor}"/></marker></defs><rect width="{w}" height="{h}" fill="#fff"/>{body}</svg>')

def arrow(d, color=EDGE, width=1.25, dash=None, marker="arrow"):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{" stroke-dasharray=\"%s\"" % dash if dash else ""} marker-end="url(#{marker})"/>'

def line(d, color=EDGE, width=1.25, dash=None):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{" stroke-dasharray=\"%s\"" % dash if dash else ""}/>'

# ------------------------------------------------------------------ figure 3 (drawn here; figures 1 and 2 are files)
def fig_map():
    """Figure 3, in the site map's own visual language and legend: blog metrics left, paper metrics right, name matches
    between. Nodes: filled = has a corresponding metric on the other side, empty = has none. Links on both sides: solid =
    supported on the other side, dashed = not. A selection of the paper's links is drawn (the caption says so)."""
    BL = "#0072B2"
    bx, px = 290, 520
    by = {"current": 110, "power": 160, "charge": 210, "temperature": 260}
    py = {"I": 100, "P": 145, "Q": 190, "T": 235, "V": 280, "R": 325, "t": 370}
    filled_p = {"I", "P", "Q", "T"}
    pname = {"I": "I  current", "P": "P  power", "Q": "Q  charge", "T": "T  temperature", "V": "V  voltage", "R": "R  resistance", "t": "t  time"}
    b = [text(24, 32, "Mapping the blog onto the paper", 15, 600),
         text(bx, 70, "BLOG METRICS", 11.5, 600, QUIET, "end"), text(px, 70, "PAPER METRICS", 11.5, 600, QUIET)]
    def node(x, y, filled):
        return '<circle cx="%s" cy="%s" r="6" fill="%s" stroke="%s" stroke-width="1.6"/>' % (x, y, TEAL if filled else "#fff", TEAL)
    for bn, pk in [("current", "I"), ("power", "P"), ("charge", "Q"), ("temperature", "T")]:
        b.append(line(f"M{bx + 8} {by[bn]} C{bx + 120} {by[bn]} {px - 120} {py[pk]} {px - 8} {py[pk]}", "#9fb8c8", 1.4))
    xb = bx - 112
    def barc(y1, y2, solid):
        xm = xb - min(30 + abs(y1 - y2) * 0.35, 140)
        return line(f"M{xb} {y1} C{xm} {y1} {xm} {y2} {xb} {y2}", BL, 3 if solid else 1.6, None if solid else "5 4")
    b += [barc(by["current"], by["power"], True), barc(by["temperature"], by["power"], False)]
    xp = px + 118
    def parc(a, c, solid):
        y1, y2 = py[a], py[c]; xm = xp + min(30 + abs(y1 - y2) * 0.35, 140)
        return line(f"M{xp} {y1} C{xm} {y1} {xm} {y2} {xp} {y2}", BL, 3 if solid else 1.6, None if solid else "5 4")
    b += [parc("I", "P", True), parc("I", "Q", False), parc("I", "T", False), parc("V", "T", False), parc("Q", "t", False), parc("V", "R", False)]
    for n, y in by.items():
        b += [node(bx, y, True), text(bx - 14, y + 4, n, 13, anchor="end")]
    for k, y in py.items():
        b += [node(px, y, k in filled_p), text(px + 14, y + 4, pname[k], 13)]
    b += [text(xb - 54, (by["current"] + by["power"]) / 2 + 4, "rises with", 11, fill=QUIET, anchor="end"),
          text(xb - 72, (by["temperature"] + by["power"]) / 2 + 30, "decreases as", 11, fill=QUIET, anchor="end")]
    ly = 410
    b.append(text(24, ly, "NODES", 11, 600, QUIET))
    b += [node(90, ly - 4, True), text(102, ly, "has a corresponding blog/paper metric", 12),
          '<polygon points="350,%d 357,%d 350,%d 343,%d" fill="%s"/>' % (ly - 11, ly - 4, ly + 3, ly - 4, TEAL), text(364, ly, "has multiple corresponding metrics (none here)", 12),
          node(90, ly + 18, False), text(102, ly + 22, "has no corresponding blog/paper metric", 12)]
    ly2 = ly + 50
    b.append(text(24, ly2, "EDGES", 11, 600, QUIET))
    b += [line(f"M90 {ly2 - 4}H130", BL, 3), text(140, ly2, "link is supported in the corresponding paper/blog", 12),
          line(f"M90 {ly2 + 18}H130", BL, 1.1), text(140, ly2 + 22, "link is partly supported (none here)", 12),
          line(f"M90 {ly2 + 40}H130", BL, 1.6, "5 4"), text(140, ly2 + 44, "link is not supported in the corresponding paper/blog", 12),
          line(f"M500 {ly2 - 4}H540", "#9fb8c8", 1.4), text(550, ly2, "blog metric to paper metric", 12),
          text(24, ly2 + 72, "Only selected paper links are drawn; Figure 1 shows the full paper network.", 11.5, fill=QUIET)]
    return svg(760, ly2 + 86, "All four blog metrics map to paper metrics. Voltage V, resistance R and elapsed time t are absent from the blog. Current to power is retained; temperature to power is additional to the paper. Selected omitted paper relationships illustrate both metrics named, one metric named, and neither metric named. Figure 1 shows the full paper network.", "".join(b))


def from_file(name, tag):
    s = open(os.path.join(HERE, "figure_files", name), encoding="utf-8").read()
    s = re.sub(r"<\?xml[^>]*>\s*", "", s)
    s = s.replace('id="title"', f'id="{tag}-title"').replace('id="desc"', f'id="{tag}-desc"').replace('aria-labelledby="title desc"', f'aria-labelledby="{tag}-title {tag}-desc"')
    s = re.sub(r'(<svg[^>]*?) width="\d+" height="\d+"', r'\1 width="100%"', s, count=1)
    return s

FIGS = {"fig1_paper_interdependencies.svg": from_file("fig1_paper_interdependencies.svg", "f1"),
        "fig2_blog_extraction.svg": from_file("fig2_blog_extraction.svg", "f2"),
        "fig3_map.svg": fig_map()}

# ------------------------------------------------------------------ the document
CSS = """
:root{--ink:#1f2328;--muted:#6b7380;--line:#e6e8ec;--acc:#0072B2}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:32px 24px 80px}
h1{font-size:26px;letter-spacing:-.01em;margin:0 0 4px}h2{font-size:19px;margin:36px 0 10px;padding-top:12px;border-top:1px solid var(--line)}h3{font-size:15.5px;margin:20px 0 6px}h4{font-size:14.5px;margin:16px 0 4px;color:#333}caption{caption-side:top;text-align:left;font-size:13px;color:var(--muted);padding:0 0 6px}math{font-size:1.05em}blockquote{margin:8px 0 12px;padding-left:14px;border-left:3px solid var(--line)}figure svg{height:auto}.sk-o2{background:rgba(213,94,0,.38)}.sk-o1{background:rgba(213,94,0,.16)}.sk-mid{background:rgba(0,158,115,.18)}.sk-u1{background:rgba(0,114,178,.14)}.sk-u2{background:rgba(0,114,178,.34)}nav.toc{margin:14px 0 8px;padding:10px 16px;border:1px solid var(--line);border-radius:8px}nav.toc p{margin:0 0 4px}nav.toc ul{margin:0;padding-left:0;list-style:none}nav.toc ul ul{padding-left:1.6em}nav.toc li{margin:2px 0}[id]{scroll-margin-top:12px}
.by{color:var(--muted);margin:0 0 20px;font-size:14px}p{margin:0 0 12px}
table{border-collapse:collapse;width:100%;margin:10px 0 16px;font-size:14px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{font-size:12.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.eq{font:15px/1.5 ui-monospace,Menlo,monospace;background:#f6f7f9;border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:8px 0 14px}
figure{margin:18px 0 22px}figure svg{display:block;border:1px solid var(--line);border-radius:8px}figcaption{font-size:13px;color:var(--muted);margin-top:6px}
ol,ul{padding-left:22px}li{margin:3px 0}code{font:13px ui-monospace,Menlo,monospace;background:#f6f7f9;padding:1px 4px;border-radius:4px}
@media print{main{max-width:none;padding:0}figure svg{border:none}h2{page-break-after:avoid}figure{page-break-inside:avoid}}
"""

def fig(name, caption):
    return f'<figure>{FIGS[name]}<figcaption>{caption}</figcaption></figure>'

def band_cells(body):
    """A table cell holding a ratio ("▲ ×2.80") gets the site's band shading: ×2 or more / at most ×0.5 darker, ×1.41–2 and
    ×0.5–0.71 lighter, in between neutral. The mark carries the reading; the shading repeats it."""
    def cls(v):
        return "sk-o2" if v >= 2 else "sk-o1" if v >= 1.41 else "sk-u2" if v <= 0.5 else "sk-u1" if v <= 0.71 else "sk-mid"
    def rep(m):
        return f'<td{m.group(1)} class="{cls(float(m.group(3)))}">{m.group(2)}</td>'
    return re.sub(r'<td([^>]*)>(\s*[▲●▼] ×(\d+(?:\.\d+)?)\s*)</td>', rep, body)

def load_body():
    """The document text lives in body.html (edit that file). A line [[FIG name.svg | caption]] places a figure."""
    raw = open(os.path.join(HERE, "body.html"), encoding="utf-8").read()
    def rep(m): return fig(m.group(1).strip(), m.group(2).strip())
    body = band_cells(re.sub(r"\[\[FIG ([^|\]]+)\|((?:.|\n)*?)\]\]", rep, raw))
    return add_toc(body)

def add_toc(body):
    """A table of contents under the title. Each <h2> is a numbered section (1, 2, ...) unless it has class="nonum"; each <h3>
    under it is numbered 2i, 2ii, ... (two levels; an <h4> is not listed). Numbers are written into the headings too, and
    every heading gets an id."""
    used, items, n, r = set(), [], 0, 0
    def roman(k): return ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"][k - 1]
    def slug(t):
        b = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", t).lower()).strip("-")[:48] or "s"; k, m = b, 2
        while k in used: k, m = f"{b}-{m}", m + 1
        used.add(k); return k
    def plain(s): return html.unescape(re.sub(r"<[^>]+>", "", s))
    def one(m):
        nonlocal n, r
        lvl, attrs, inner = m.group(1), m.group(2) or "", m.group(3); k = slug(inner)
        if lvl == "2":
            if "nonum" in attrs: items.append((2, k, plain(inner))); return f'<h2 id="{k}">{inner}</h2>'
            n, r = n + 1, 0; items.append((2, k, f"{n}. {plain(inner)}")); return f'<h2 id="{k}">{n}. {inner}</h2>'
        if lvl == "3":
            r += 1; num = f"{n}{roman(r)}."; items.append((3, k, f"{num} {plain(inner)}")); return f'<h3 id="{k}">{num} {inner}</h3>'
        return f'<h4 id="{k}">{inner}</h4>'
    body = re.sub(r'<h([234])((?: class="[^"]*")?)>(.*?)</h\1>', one, body, flags=re.S)
    toc, depth = ['<nav class="toc"><p><b>Contents</b></p><ul>'], 2
    for lvl, k, t in items:
        while depth < lvl: toc.append("<ul>"); depth += 1
        while depth > lvl: toc.append("</li></ul>"); depth -= 1
        if toc[-1] not in ("<ul>",) and not toc[-1].startswith('<nav'): toc.append("</li>")
        toc.append(f'<li><a href="#{k}">{html.escape(t)}</a>')
    while depth > 2: toc.append("</li></ul>"); depth -= 1
    toc.append("</li></ul></nav>")
    return body.replace("</h1>", "</h1>" + "".join(toc), 1)

BODY = load_body()

out = os.path.join(HERE, "method.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mapping Technical Artifacts: methods</title><style>{CSS}</style></head><body><main>{BODY}</main></body></html>')
figdir = os.path.join(HERE, "figures"); os.makedirs(figdir, exist_ok=True)
for name, s in FIGS.items():
    with open(os.path.join(figdir, name), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + s)
print("wrote", out, "and", len(FIGS), "figures in", figdir)
