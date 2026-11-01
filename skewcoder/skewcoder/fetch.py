"""Make a unit (the input folder every later step reads) from what a user has: an arXiv id or link, a PDF, a blog link or a
saved blog page.

  paper   arXiv id / arxiv.org link  -> the LaTeX source (best: numbered equations survive); a PDF if arXiv has no source
          a PDF file or a PDF link    -> the PDF (equations are kept only as images; see the note written into unit.json)
  blog    a link                      -> the page's HTML, saved as fetched
          an .html file / a .pdf file -> copied as given

  <workspace>/papers/<key>/unit.json + sources/       <workspace>/blogs/<key>/unit.json + sources/

Citation fields come only from the source itself (arXiv's API for an arXiv paper; the page's own title/meta tags for a blog);
whatever cannot be read is left blank, never guessed.
"""
import gzip, io, json, re, shutil, tarfile, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = {"User-Agent": "skewcoder/0.2 (research tool; paper-blog skew)"}
ARXIV_RX = re.compile(r"(?:arxiv\.org/(?:abs|pdf|e-print)/|^arxiv:|^)(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)(?:\.pdf)?$", re.I)


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", ""), r.geturl()


def arxiv_id(s):
    m = ARXIV_RX.search(s.strip()); return m.group(1) if m else None


def slug(s): return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")[:60] or "unit"


def arxiv_meta(aid):
    data, _, _ = get("https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(aid))
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    e = ET.fromstring(data).find("a:entry", ns)
    if e is None or e.find("a:title", ns) is None: return {}
    title = re.sub(r"\s+", " ", e.find("a:title", ns).text or "").strip()
    authors = [re.sub(r"\s+", " ", a.find("a:name", ns).text or "").strip() for a in e.findall("a:author", ns)]
    year = (e.find("a:published", ns).text or "")[:4]
    doi = e.find("x:doi", ns); jref = e.find("x:journal_ref", ns)
    who = ", ".join(authors[:6]) + (" et al." if len(authors) > 6 else "")
    cite = f"{who}, {title}, arXiv:{aid}" + (f"; {jref.text.strip()}" if jref is not None and jref.text else "") + (f" ({year})" if year and jref is None else "")
    return {"title": title, "authors": authors, "year": year, "cite": cite, "doi": doi.text.strip() if doi is not None and doi.text else None,
            "first_author": authors[0].split()[-1] if authors else None}


def main_tex(folder):
    """The file holding \\begin{document}; if several, the one with \\documentclass and the most text."""
    tex = [p for p in folder.rglob("*.tex") if "\\begin{document}" in p.read_text(encoding="utf-8", errors="ignore")]
    if not tex: return None
    tex.sort(key=lambda p: ("\\documentclass" not in p.read_text(encoding="utf-8", errors="ignore"), -p.stat().st_size))
    return tex[0]


def add_paper(workspace, src, key=None):
    W = Path(workspace); aid = arxiv_id(src) if not Path(src).exists() else None
    meta, source, notes = {}, {}, []
    if aid:
        meta = arxiv_meta(aid)
        key = key or slug(f"{meta.get('first_author') or 'arxiv'}{meta.get('year') or ''}") or slug(aid)
        d = W / "papers" / key; (d / "sources").mkdir(parents=True, exist_ok=True)
        data, ctype, _ = get(f"https://arxiv.org/e-print/{aid}")
        if data[:4] == b"%PDF":
            (d / "sources" / "paper.pdf").write_bytes(data); source = {"pdf": "sources/paper.pdf"}; notes.append("arXiv holds only a PDF for this paper: equations are kept as images")
        else:
            raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
            tdir = d / "sources" / "tex"; tdir.mkdir(exist_ok=True)
            try:
                with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
                    safe = [m for m in tf.getmembers() if not (m.name.startswith("/") or ".." in Path(m.name).parts) and (m.isfile() or m.isdir())]
                    tf.extractall(tdir, members=safe)
            except tarfile.ReadError:
                (tdir / "main.tex").write_bytes(raw)      # a single-file submission is the bare .tex, gzipped
            mt = main_tex(tdir)
            if not mt: raise SystemExit(f"arXiv:{aid}: no .tex file with \\begin{{document}} in the source")
            source = {"tex": str(mt.relative_to(d))}
        url = f"https://arxiv.org/abs/{aid}"
    else:
        p = Path(src)
        if p.exists(): data = p.read_bytes(); url = None
        else: data, ctype, url = get(src)
        if data[:4] != b"%PDF": raise SystemExit(f"{src}: not an arXiv id and not a PDF. Give the arXiv id, or the paper as a PDF.")
        key = key or slug(p.stem if p.exists() else Path(urllib.parse.urlparse(src).path).stem)
        d = W / "papers" / key; (d / "sources").mkdir(parents=True, exist_ok=True)
        (d / "sources" / "paper.pdf").write_bytes(data); source = {"pdf": "sources/paper.pdf"}
        notes.append("rebuilt from a PDF: numbered equations are cropped as images and carry no TeX unless sources/equations.json gives it")
    unit = {"kind": "paper", "key": key, "title": meta.get("title", ""), "cite": meta.get("cite", ""), "url": url or "",
            "doi": meta.get("doi"), "source": source, "notes": notes,
            "_doc": "Made by skewcoder fetch. Citation fields come from arXiv's API (arXiv papers) or are blank: fill them by hand from the paper."}
    (d / "unit.json").write_text(json.dumps(unit, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  paper unit {d}: {source}" + (f"; {meta.get('title')}" if meta.get("title") else ""))
    return d


def _meta(html, name):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']*)' % re.escape(name), html, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(name), html, re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def add_blog(workspace, src, key=None, paper=None):
    W = Path(workspace); p = Path(src); url = None
    if p.exists():
        data = p.read_bytes(); ext = p.suffix.lower()
    else:
        data, ctype, url = get(src); ext = ".pdf" if data[:4] == b"%PDF" else ".html"
    key = key or slug(Path(urllib.parse.urlparse(url or str(p)).path.rstrip("/")).name.replace(".html", "") or "blog")
    d = W / "blogs" / key; (d / "sources").mkdir(parents=True, exist_ok=True)
    title = date = author = site = ""
    if ext == ".pdf":
        (d / "sources" / "blog.pdf").write_bytes(data); source = {"pdf": "sources/blog.pdf"}
    else:
        (d / "sources" / "blog.html").write_bytes(data); source = {"html": "sources/blog.html"}
        h = data.decode("utf-8", "ignore")
        title = _meta(h, "og:title") or (re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I).group(1).strip() if re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I) else "")
        date = (_meta(h, "article:published_time") or _meta(h, "date"))[:10]; author = _meta(h, "author"); site = _meta(h, "og:site_name")
        url = url or _meta(h, "og:url")
    cite = ", ".join(x for x in (author, title, site, date) if x)
    unit = {"kind": "blog", "key": key, "title": title, "cite": cite, "url": url or "", "paper": paper, "source": source,
            "_doc": "Made by skewcoder fetch. Citation fields come from the page's own meta tags or are blank. If the saved page runs on "
                    "into other posts, set source.html_stop to the first words of the first block that is not part of this post."}
    (d / "unit.json").write_text(json.dumps(unit, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  blog unit {d}: {source}" + (f"; {title}" if title else ""))
    return d
