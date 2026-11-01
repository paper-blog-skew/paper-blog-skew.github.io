"""Part (a): build the text of one unit (a paper or a blog) and write it in the three forms the other parts read.

<unit>/unit.json  says what the unit is:
  {"kind": "paper", "key": "Arute2019", "title": "...", "cite": "...", "source": {"tex": "sources/main.tex"}}
  {"kind": "paper", "key": "Kim2023",   ..., "source": {"pdf": "sources/paper.pdf", "equations": "sources/equations.json"}}
  {"kind": "blog",  "key": "GOO-185",   ..., "source": {"html": "sources/blog.html", "html_stop": "Posted by"}}
  {"kind": "blog",  "key": "MIC-442",   ..., "source": {"pdf": "sources/blog.pdf"}}
Paths are relative to the unit folder.

Writes <unit>/text/docs.json (blocks with HTML/TeX, what the site shows), text.md (one block per line with block ids,
what the coder reads) and text.json (same blocks, for the audit); figures under <unit>/text/figs/.
"""
import html as H, json, re, sys
from pathlib import Path
from . import textbuild as TB


def load_unit(unit_dir):
    unit_dir = Path(unit_dir).resolve()
    u = json.loads((unit_dir / "unit.json").read_text(encoding="utf-8"))
    u["_dir"] = unit_dir
    return u


def build(unit_dir):
    u = load_unit(unit_dir); d = u["_dir"]; src = u["source"]; out_dir = d / "text"; out_dir.mkdir(exist_ok=True)
    TB.FIG_OUT = out_dir / "figs"
    if u["kind"] == "paper":
        if src.get("tex"):
            blocks, labels, macros, title, _ = TB.tex_to_blocks_core(d / src["tex"], u["key"])
            doc = TB.finalize_paper(blocks, labels, macros, title); doc["labels"] = labels
        else:
            if TB.fitz is None: sys.exit("PyMuPDF (fitz) is needed to read a PDF")
            doc = TB.pdf_paper_blocks(d / src["pdf"], u["key"])
            if src.get("equations"):
                # a paper rebuilt from a PDF has no numbered equations; a hand transcription (provenance in its _doc)
                # replaces the glyph-soup block with a numbered equation block
                eqs = json.loads((d / src["equations"]).read_text(encoding="utf-8"))["equations"]
                bynum = {b["num"]: b for b in doc["blocks"] if b["type"] == "eq"}
                for e in eqs:
                    b = bynum.get(e["num"])
                    if not b: sys.exit(f"{u['key']}: equations file names equation ({e['num']}) which the PDF reader did not find")
                    b["tex"] = e["tex"]; b["note"] = "image cropped from the PDF; TeX transcribed by hand"
        doc = cut_appendices(doc, u)
    else:
        if src.get("html"):
            doc = TB.html_blog_blocks(d / src["html"])
            if src.get("html_stop"):
                keep = []
                for b in doc["blocks"]:
                    if H.unescape(re.sub(r"<[^>]+>", "", b.get("html", ""))).strip().startswith(src["html_stop"]): break
                    keep.append(b)
                doc["blocks"] = keep
        else:
            if TB.fitz is None: sys.exit("PyMuPDF (fitz) is needed to read a PDF")
            doc = TB.pdf_blog_blocks(d / src["pdf"])
    (out_dir / "docs.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    (out_dir / "text.json").write_text(json.dumps({"title": u.get("title"), "cite": u.get("cite"), "blocks": doc["blocks"]}, ensure_ascii=False), encoding="utf-8")
    (out_dir / "text.md").write_text(render(doc, u.get("title") or doc.get("title", "")), encoding="utf-8")
    kinds = {}
    for b in doc["blocks"]: kinds[b["type"]] = kinds.get(b["type"], 0) + 1
    neq = sum(1 for b in doc["blocks"] if b["type"] == "eq" and b.get("num"))
    print(f"  {u['kind']} {u['key']}: {len(doc['blocks'])} blocks {kinds}, numbered equations {neq} -> {out_dir}")
    return doc


APPX_HEAD = re.compile(r"^\s*(appendix|appendices|supplementary|supplemental)\b", re.I)


def cut_appendices(doc, u):
    """a paper is coded without its appendices. Every block from the first
    appendix block on is cut before any later step reads the text: the first block whose section is a lettered appendix
    section (A, B.2, ...) or a heading that starts "Appendix" / "Supplementary". unit.json may set "appendix_from"
    (a block id) to fix the start by hand, or "keep_appendices": true to keep them. The cut is recorded in docs.json."""
    if u.get("keep_appendices"): doc["appendix_cut"] = {"kept": True}; return doc
    blocks = doc["blocks"]; start = None
    for i, b in enumerate(blocks):
        sec = str(b.get("sec") or ""); head = plain(b.get("html", "")) if b["type"] in ("h1", "h2", "h3") else ""
        if (u.get("appendix_from") and b["id"] == u["appendix_from"]) or (not u.get("appendix_from") and (re.match(r"^[A-Z](\.\d+)*$", sec) or APPX_HEAD.match(head))):
            start = i; break
    if start is None: doc["appendix_cut"] = {"found": False}; return doc
    gone = blocks[start:]; doc["blocks"] = blocks[:start]
    doc["appendix_cut"] = {"from": gone[0]["id"], "section": gone[0].get("sec"), "blocks_cut": len(gone),
                           "equations_cut": [b.get("num") for b in gone if b["type"] == "eq" and b.get("num")]}
    print(f"  {u['key']}: appendices cut from block {gone[0]['id']} (section {gone[0].get('sec')}): {len(gone)} blocks")
    return doc


def plain(h):
    t = re.sub(r"<sub>(.*?)</sub>", r"_\1", h); t = re.sub(r"<sup>(.*?)</sup>", r"^\1", t)
    t = re.sub(r"<[^>]+>", " ", t); t = H.unescape(t)
    return re.sub(r"[ \t]+", " ", t).strip()


def render(doc, title):
    lines = [f"# {title}", "", "One block per line. `[b12]` is the block id; `(p)` paragraph, `(h1/h2/h3)` heading, `(eq N)` numbered equation",
             "(its TeX follows), `(fig)`/`(table)` caption, `(li)` list item. `sec` gives the section the block sits in where the source states one.", ""]
    for b in doc["blocks"]:
        t = b["type"]; sec = b.get("sec") or ""
        if t == "eq":
            tex = b.get("tex") or ""; note = b.get("note") or ""
            lines.append(f"[{b['id']}] (eq {b.get('num', '?')}) sec={sec}  $$ {tex} $$" + (f"   — {plain(note)}" if note and not tex else ""))
        elif t in ("h1", "h2", "h3"):
            lines.append(f"[{b['id']}] ({t}) sec={sec}  {'#' * (int(t[1]) + 1)} {plain(b.get('html', ''))}")
        else:
            lines.append(f"[{b['id']}] ({t}) sec={sec}  {plain(b.get('html', ''))}")
    return "\n".join(lines) + "\n"


def load_doc(unit_dir):
    p = Path(unit_dir) / "text" / "docs.json"
    if not p.exists(): sys.exit(f"{unit_dir}: no text yet — run `skewcoder.py text {unit_dir}` first")
    return json.loads(p.read_text(encoding="utf-8"))
