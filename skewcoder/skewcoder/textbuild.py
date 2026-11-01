#!/usr/bin/env python3
"""Rebuild each pair's paper and blog as a linear list of text blocks, and anchor the coded items to blocks.

Paper  : from the arXiv LaTeX source (pairs.json -> paper.tex). Sections, paragraphs, numbered equations
         (TeX kept for KaTeX), theorem-like environments, lists, figures (captions + converted images), tables.
Blog   : from the saved HTML (blog.html, article container) or, failing that, the blog PDF's text blocks.
Anchors: equation number -> block id; coded quote (paper prose link / blog concept / blog edge) -> block id and
         the character span of the sentence containing it (offsets into the block's html).

Output : build/<pair>_docs.json and dist/figs/<pair>/*.png.  Nothing is guessed: an item that cannot be
         located is listed under "missed".  Run with the research venv (needs PyMuPDF for figures / blog PDFs).
"""
import json, sys, re, unicodedata, html as H
from pathlib import Path

FIG_OUT = None   # set by texts.build_paper(): where converted figures go (Path) — None = do not convert figures
try:
    import fitz
except ImportError:
    fitz = None

# ----------------------------------------------------------------------------- LaTeX helpers
def strip_comments(s):
    out = []
    for line in s.split("\n"):
        i, buf = 0, []
        while i < len(line):
            c = line[i]
            if c == "\\" and i + 1 < len(line):
                buf.append(line[i:i + 2]); i += 2; continue
            if c == "%":
                break
            buf.append(c); i += 1
        if not "".join(buf).strip() and line.lstrip().startswith("%"):
            continue   # a whole-line comment is not a paragraph break
        out.append("".join(buf))
    return "\n".join(out)


def balanced(s, i):
    """s[i] == '{' -> index just past the matching '}'."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\": j += 2; continue
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return j + 1
        j += 1
    return len(s)


def take_arg(s, i):
    """Skip spaces and an optional [..], then read a {..} argument starting at s[i]. Returns (arg, next_index)."""
    j = i
    while j < len(s) and s[j] in " \t\n": j += 1
    if j < len(s) and s[j] == "[":
        k = s.find("]", j); j = k + 1 if k >= 0 else j
        while j < len(s) and s[j] in " \t\n": j += 1
    if j < len(s) and s[j] == "{":
        k = balanced(s, j); return s[j + 1:k - 1], k
    return "", j


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mask_math(s):
    """Replace $...$ / \\(...\\) spans by spaces of equal length (keeps offsets aligned)."""
    out, i = [], 0
    while i < len(s):
        if s.startswith("\\$", i): out.append("\\$"); i += 2; continue
        if s[i] == "$":
            j = s.find("$", i + 1)
            if j < 0: out.append(s[i:]); break
            out.append(" " * (j + 1 - i)); i = j + 1; continue
        out.append(s[i]); i += 1
    return "".join(out)


class Tex2Html:
    """Inline LaTeX -> HTML with $math$ left intact for KaTeX. Reference commands resolve through self.labels."""
    REF_CMDS = {"eq": ("eq:", "({n})"), "thm": ("thm:", "Theorem {n}"), "lem": ("lem:", "Lemma {n}"), "cor": ("cor:", "Corollary {n}"),
                "prop": ("prop:", "Proposition {n}"), "defn": ("defn:", "Definition {n}"), "obs": ("obs:", "Observation {n}"),
                "fig": ("fig:", "Figure {n}"), "tab": ("tab:", "Table {n}"), "sec": ("sec:", "Section {n}"), "append": ("append:", "Appendix {n}")}
    DROP_WITH_ARG = {"label", "ys", "YT", "minh", "blfootnote", "vspace", "hspace", "ot", "sout", "ccsdesc", "keywords", "affiliation", "email",
                     "orcid", "received", "acmConference", "setcopyright", "acmYear", "acmDOI", "acmISBN", "acmPrice", "thispagestyle", "pagestyle",
                     "settopmatter", "renewcommand", "newcommand", "bibliographystyle", "bibliography", "index", "shortauthors", "acmJournal",
                     "acmVolume", "acmNumber", "acmArticle", "acmMonth", "authornote", "authornotemark", "titlenote", "subtitle"}
    DROP_BARE = {"noindent", "centering", "small", "footnotesize", "normalsize", "large", "Large", "medskip", "smallskip", "bigskip", "newpage",
                 "clearpage", "maketitle", "tableofcontents", "appendix", "linebreak", "newline", "hfill", "raggedright", "indent", "par", "qed",
                 "toprule", "midrule", "bottomrule", "hline", "relax", "nonumber", "notag", "allowbreak", "sloppy", "balance", "footnotemark"}
    UNWRAP = {"emph": "em", "textit": "em", "textbf": "b", "texttt": "code", "textsc": "span", "textsf": "span", "textrm": "span", "underline": "u",
              "textsuperscript": "sup", "textsubscript": "sub", "nt": "span", "textcolor2": "span", "mbox": "span", "text": "span", "hbox": "span",
              "textnormal": "span", "textup": "span", "textmd": "span", "uppercase": "span"}

    def __init__(self, labels):
        self.labels = labels

    def ref(self, key):
        return self.labels.get(key)

    def convert(self, s):
        s = s.replace("\\\\", " ")
        out, i, n = [], 0, len(s)
        while i < n:
            c = s[i]
            if c == "$":  # keep math verbatim
                j = s.find("$", i + 1)
                if j < 0: out.append(esc(s[i:])); break
                out.append(s[i:j + 1]); i = j + 1; continue
            if s.startswith("\\(", i):
                j = s.find("\\)", i); j = n if j < 0 else j + 2; out.append("$" + s[i + 2:j - 2] + "$"); i = j; continue
            if c == "\\":
                m = re.match(r"\\([A-Za-z]+)\*?", s[i:])
                if not m:
                    nxt = s[i + 1] if i + 1 < n else ""
                    out.append({"&": "&amp;", "%": "%", "_": "_", "#": "#", "$": "$", "{": "{", "}": "}", ",": " ", " ": " ", ";": " ", "!": "", "-": "", "~": "~", "'": "", "`": "", "^": "", '"': ""}.get(nxt, nxt))
                    i += 2; continue
                cmd = m.group(1); i += len(m.group(0))
                if cmd in self.REF_CMDS:
                    arg, i = take_arg(s, i); pre, fmt = self.REF_CMDS[cmd]
                    num = self.ref(pre + arg.strip())
                    if cmd == "eq" and num is not None: out.append('<a class="eqref" data-eq="%s">(%s)</a>' % (num, num))
                    else: out.append(esc(fmt.format(n=num if num is not None else "?")))
                    continue
                if cmd in ("ref", "cref", "Cref", "eqref", "autoref"):
                    arg, i = take_arg(s, i); keys = [k.strip() for k in arg.split(",")]
                    parts = []
                    for k in keys:
                        num = self.ref(k); kind = k.split(":")[0]
                        name = {"eq": "({n})", "thm": "Theorem {n}", "lem": "Lemma {n}", "cor": "Corollary {n}", "prop": "Proposition {n}", "defn": "Definition {n}",
                                "fig": "Figure {n}", "tab": "Table {n}", "sec": "Section {n}", "append": "Appendix {n}", "obs": "Observation {n}"}.get(kind, "{n}")
                        if kind == "eq" and num is not None: parts.append('<a class="eqref" data-eq="%s">(%s)</a>' % (num, num))
                        else: parts.append(esc(name.format(n=num if num is not None else "?")))
                    out.append(" and ".join(parts)); continue
                if cmd in ("cite", "citep", "citet", "citealp", "citeauthor", "citeyear"):
                    arg, i = take_arg(s, i); out.append('<span class="cite">[' + esc(", ".join(k.strip() for k in arg.split(","))) + ']</span>'); continue
                if cmd == "footnote":
                    arg, i = take_arg(s, i); out.append('<span class="fn">(footnote: ' + self.convert(arg) + ')</span>'); continue
                if cmd == "url":
                    arg, i = take_arg(s, i); out.append('<a href="%s">%s</a>' % (esc(arg), esc(arg))); continue
                if cmd == "href":
                    u, i = take_arg(s, i); t, i = take_arg(s, i); out.append('<a href="%s">%s</a>' % (esc(u), self.convert(t))); continue
                if cmd == "texorpdfstring":
                    a, i = take_arg(s, i); b, i = take_arg(s, i); out.append(self.convert(a)); continue
                if cmd == "textcolor" or cmd == "color":
                    col, i = take_arg(s, i)
                    if cmd == "textcolor": a, i = take_arg(s, i); out.append(self.convert(a))
                    continue
                if cmd in self.UNWRAP:
                    arg, i = take_arg(s, i); tag = self.UNWRAP[cmd]; out.append("<%s>%s</%s>" % (tag, self.convert(arg), tag)); continue
                if cmd in self.DROP_WITH_ARG:
                    arg, i = take_arg(s, i); continue
                if cmd in self.DROP_BARE:
                    continue
                if cmd in ("ldots", "dots", "textellipsis"): out.append("…"); continue
                if cmd in ("textendash",): out.append("–"); continue
                if cmd in ("textemdash",): out.append("—"); continue
                if cmd in ("textquotedblleft",): out.append("“"); continue
                if cmd in ("textquotedblright",): out.append("”"); continue
                if cmd in ("item",): out.append("• "); continue
                if cmd in ("ss",): out.append("ß"); continue
                # accents: \"a \'e \^o handled above as non-letter commands; \o \ae \aa
                if cmd in ("o",): out.append("ø"); continue
                if cmd in ("ae",): out.append("æ"); continue
                # unknown command: if it takes a brace argument, unwrap it; otherwise drop the command name
                j = i
                while j < n and s[j] in " \t\n": j += 1
                if j < n and s[j] == "{":
                    arg, i = take_arg(s, i); out.append(self.convert(arg)); continue
                continue
            if c == "{" or c == "}":
                i += 1; continue
            if c == "~": out.append(" "); i += 1; continue
            if s.startswith("---", i): out.append("—"); i += 3; continue
            if s.startswith("--", i): out.append("–"); i += 2; continue
            if s.startswith("``", i): out.append("“"); i += 2; continue
            if s.startswith("''", i): out.append("”"); i += 2; continue
            if c == "`": out.append("‘"); i += 1; continue
            if c == "'": out.append("’"); i += 1; continue
            out.append(esc(c)); i += 1
        html = "".join(out)
        html = re.sub(r"[ \t\n]+", " ", html).strip()
        return html


# ----------------------------------------------------------------------------- LaTeX -> blocks
THM_ENVS = {"theorem": "Theorem", "lemma": "Lemma", "corollary": "Corollary", "proposition": "Proposition", "definition": "Definition",
            "example": "Example", "observation": "Observation", "remark": "Remark", "claim": "Claim", "conjecture": "Conjecture"}
CUSTOM_THM = {"customthm": "Theorem", "customcor": "Corollary"}


def expand_inputs(tex, base):
    def rep(m):
        f = m.group(1).strip()
        p = base / f
        if not p.suffix: p = p.with_suffix(".tex")
        if p.exists(): return "\n" + strip_comments(p.read_text(encoding="utf-8", errors="ignore")) + "\n"
        return ""
    return re.sub(r"\\(?:input|include)\{([^}]+)\}", rep, tex)


def preamble_macros(tex):
    macros = {}
    for m in re.finditer(r"\\(?:re)?newcommand\*?\{?\\([A-Za-z]+)\}?(?:\[(\d)\])?\{", tex):
        name, nargs = m.group(1), m.group(2)
        end = balanced(tex, m.end() - 1); body = tex[m.end():end - 1]
        if any(x in body for x in ("\\color", "\\textbf", "footnote", "\\hyperref", "\\cref", "\\ref")): continue   # text-mode only
        macros["\\" + name] = body.strip()
    for m in re.finditer(r"\\DeclareMathOperator\*?\{\\([A-Za-z]+)\}\{([^}]*)\}", tex):
        macros["\\" + m.group(1)] = "\\operatorname{" + m.group(2) + "}"
    # commands that KaTeX lacks and the sources use
    macros.setdefault("\\mathds", "\\mathbb{#1}")
    macros.setdefault("\\obot", "\\mathbin{\\circledcirc}")   # custom font symbol in the source; nearest KaTeX glyph
    macros.setdefault("\\bigobot", "\\bigodot")
    return macros


def convert_figure_file(src, out_dir, stem):
    out_dir.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".png":
        dst = out_dir / (stem + ".png"); dst.write_bytes(src.read_bytes()); return dst.name
    if src.suffix.lower() == ".pdf" and fitz:
        dst = out_dir / (stem + ".png"); doc = fitz.open(src); pix = doc[0].get_pixmap(dpi=150); pix.save(dst); return dst.name
    return None


def expand_text_macros(preamble, body):
    """Simple no-argument preamble macros whose body is one word, e.g. \\newcommand{\\CNOT}{{\\ensuremath{\\rm CNOT}}},
    are expanded in the body text so that '\\CNOT s' reads 'CNOT s' instead of losing the word."""
    words = {}
    for m in re.finditer(r"\\(?:newcommand|providecommand|renewcommand)\*?\{\\([A-Za-z]+)\}\{(.*)\}", preamble):
        w = re.sub(r"\\(?:ensuremath|mathrm|textrm|textsc|mathsf|text|rm)\b", "", m.group(2)).replace("{", "").replace("}", "").strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9+\-]*", w): words[m.group(1)] = w
    if not words: return body
    rx = re.compile(r"\\(" + "|".join(sorted(words, key=len, reverse=True)) + r")(?![A-Za-z])(\\ |~)?")
    return rx.sub(lambda mm: words[mm.group(1)] + (" " if mm.group(2) else ""), body)


def tex_to_blocks_core(main_tex, pair_id):
    base = main_tex.parent
    raw = strip_comments(main_tex.read_text(encoding="utf-8", errors="ignore"))
    macros = preamble_macros(raw)
    body = raw.split("\\begin{document}", 1)[1] if "\\begin{document}" in raw else raw
    body = body.split("\\end{document}", 1)[0]
    body = expand_inputs(body, base)
    body = expand_text_macros(raw, body)
    for e in list(THM_ENVS) + list(CUSTOM_THM) + ["proof", "itemize", "enumerate", "description", "abstract"]:
        body = body.replace("\\end{%s}" % e, "\\begin{ENDENV_%s}" % e)   # scope ends become tokens the scanner sees
    title = ""
    tm = re.search(r"\\title\{", raw)
    if tm:
        end = balanced(raw, tm.end() - 1); title = raw[tm.end():end - 1]
    first = min([x for x in (body.find("\\begin{abstract}"), body.find("\\section")) if x >= 0] or [0])
    body = body[first:]
    body = re.sub(r"\\begin\{CCSXML\}.*?\\begin\{ENDENV_CCSXML\}|\\begin\{CCSXML\}.*?\\end\{CCSXML\}", "", body, flags=re.S)

    blocks, labels = [], {}
    counters = {"section": 0, "subsection": 0, "subsubsection": 0, "eq": 0, "figure": 0, "table": 0}
    thm_counters = {}
    state = {"appendix": False, "sec": ""}
    env_stack = []
    pending = []

    def flush():
        txt = "".join(pending); pending.clear()
        if not txt.strip(): return
        for para in re.split(r"\n\s*\n", txt):
            para = para.strip()
            if not para: continue
            if env_stack and env_stack[-1][0] == "list":
                outer = next((e[1] for e in reversed(env_stack) if e[0] in ("thm", "proof", "abstract")), None)
                for it in [x for x in re.split(r"\\item\b", para) if x.strip()]:
                    blocks.append({"type": "li", "raw": it.strip(), "sec": state["sec"], "env": outer})
                continue
            env = next((e[1] for e in reversed(env_stack) if e[0] in ("thm", "proof", "abstract")), None)
            blocks.append({"type": "p", "raw": para, "sec": state["sec"], "env": env})

    pat = re.compile(r"\\(section|subsection|subsubsection|paragraph)(\*?)\s*\{|\\begin\{(\w+\*?)\}|\\\[|\$\$|\\appendix\b|\\label\{([^}]+)\}")
    i, n = 0, len(body)
    while i < n:
        m = pat.search(body, i)
        if not m:
            pending.append(body[i:]); break
        pending.append(body[i:m.start()])
        tok = m.group(0)
        if tok.startswith("\\appendix"):
            flush(); state["appendix"] = True; counters["section"] = 0; i = m.end(); continue
        if m.group(4):
            key = m.group(4).strip()
            if key not in labels:
                last = blocks[-1] if blocks else None
                if env_stack and env_stack[-1][0] == "thm": labels[key] = env_stack[-1][2]
                elif last and last["type"] in ("h1", "h2", "h3") and not "".join(pending).strip(): labels[key] = last.get("num")
            i = m.end(); continue
        if m.group(1):
            flush(); kind, starred = m.group(1), m.group(2) == "*"
            end = balanced(body, m.end() - 1); ttl = body[m.end():end - 1]
            if kind == "paragraph":
                blocks.append({"type": "h4", "raw": ttl, "sec": state["sec"], "env": None, "num": None}); i = end; continue
            secno = (lambda: chr(64 + counters["section"]) if state["appendix"] else str(counters["section"]))
            if not starred:
                if kind == "section": counters["section"] += 1; counters["subsection"] = 0; counters["subsubsection"] = 0; num = secno()
                elif kind == "subsection": counters["subsection"] += 1; counters["subsubsection"] = 0; num = "%s.%d" % (secno(), counters["subsection"])
                else: counters["subsubsection"] += 1; num = "%s.%d.%d" % (secno(), counters["subsection"], counters["subsubsection"])
                state["sec"] = num
            else:
                num = None; state["sec"] = re.sub(r"\\[A-Za-z]+\{?|[{}]", "", ttl).strip()
            blocks.append({"type": {"section": "h1", "subsection": "h2", "subsubsection": "h3"}[kind], "raw": ttl, "sec": state["sec"], "env": None, "num": num})
            lm = re.match(r"\s*\\label\{([^}]+)\}", body[end:])
            if lm: labels[lm.group(1).strip()] = num; end += lm.end()
            i = end; continue
        if tok == "$$":
            # a $$...$$ display is a numbered equation, numbered by order like an equation environment
            flush(); j = body.find("$$", m.end()); counters["eq"] += 1
            blocks.append({"type": "eq", "tex": body[m.end():j].strip(), "num": counters["eq"], "sec": state["sec"], "env": next((e[1] for e in reversed(env_stack) if e[0] in ("thm", "proof", "abstract")), None)}); i = j + 2; continue
        if tok == "\\[":
            flush(); j = body.find("\\]", m.end())
            blocks.append({"type": "eq", "tex": body[m.end():j].strip(), "num": None, "sec": state["sec"], "env": next((e[1] for e in reversed(env_stack) if e[0] in ("thm", "proof", "abstract")), None)}); i = j + 2; continue
        env = m.group(3); i = m.end()
        if env.startswith("ENDENV_"):
            flush(); name = env[7:]
            kind = "list" if name in ("itemize", "enumerate", "description") else ("abstract" if name == "abstract" else ("proof" if name == "proof" else "thm"))
            for k in range(len(env_stack) - 1, -1, -1):
                if env_stack[k][0] == kind: del env_stack[k]; break
            if kind == "abstract" and state["sec"] == "abstract": state["sec"] = "main text"   # text after the abstract and before the first \section
            continue
        endtag = "\\end{%s}" % env
        if env in ("equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*"):
            flush(); j = body.find(endtag, i); tex = body[i:j]; num = None
            if not env.endswith("*"):
                counters["eq"] += 1; num = counters["eq"]
                for lm in re.finditer(r"\\label\{([^}]+)\}", tex): labels[lm.group(1).strip()] = num
            tex = re.sub(r"\\label\{[^}]+\}", "", tex).strip()
            if env.startswith(("align", "eqnarray", "gather")): tex = "\\begin{aligned}" + tex + "\\end{aligned}"
            blocks.append({"type": "eq", "tex": tex, "num": num, "sec": state["sec"], "env": next((e[1] for e in reversed(env_stack) if e[0] in ("thm", "proof", "abstract")), None)}); i = j + len(endtag); continue
        if env == "abstract":
            flush(); blocks.append({"type": "h1", "raw": "Abstract", "sec": "abstract", "env": None, "num": None}); state["sec"] = "abstract"; env_stack.append(("abstract", "Abstract", None)); continue
        if env in THM_ENVS or env in CUSTOM_THM:
            flush()
            if env in CUSTOM_THM:
                arg, i = take_arg(body, i); name = CUSTOM_THM[env]; num = arg.strip()
            else:
                name = THM_ENVS[env]; thm_counters[env] = thm_counters.get(env, 0) + 1; num = str(thm_counters[env])
            label = "%s %s" % (name, num)
            om = re.match(r"\s*\[", body[i:])
            if om:
                k = body.find("]", i + om.end()); label += " (" + body[i + om.end():k].strip() + ")"; i = k + 1
            lm = re.match(r"\s*\\label\{([^}]+)\}", body[i:])
            if lm: labels[lm.group(1).strip()] = num; i += lm.end()
            env_stack.append(("thm", label, num)); continue
        if env == "proof":
            flush(); om = re.match(r"\s*\[", body[i:]); label = "Proof"
            if om:
                k = body.find("]", i + om.end()); label = "Proof (" + body[i + om.end():k].strip() + ")"; i = k + 1
            env_stack.append(("proof", label, None)); continue
        if env in ("itemize", "enumerate", "description"):
            flush(); om = re.match(r"\s*\[[^\]]*\]", body[i:])
            if om: i += om.end()
            env_stack.append(("list", env, None)); continue
        if env in ("figure", "figure*", "wrapfigure", "teaserfigure"):
            flush(); j = body.find(endtag, i); inner = body[i:j]; counters["figure"] += 1
            for lm in re.finditer(r"\\label\{([^}]+)\}", inner): labels[lm.group(1).strip()] = counters["figure"]
            cap = ""; cm = re.search(r"\\caption\{", inner)
            if cm: ce = balanced(inner, cm.end() - 1); cap = inner[cm.end():ce - 1]
            imgs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", inner); files = []
            for k, f in enumerate(imgs):
                src = base / f.strip()
                if not src.exists():
                    cands = list(base.glob(f.strip() + ".*")); src = cands[0] if cands else None
                if src and src.exists():
                    name = convert_figure_file(src, FIG_OUT, "fig%d_%d" % (counters["figure"], k)) if FIG_OUT else None
                    if name: files.append("figs/%s/%s" % (pair_id, name))
            blocks.append({"type": "fig", "raw": cap, "num": counters["figure"], "imgs": files, "note": "" if imgs else "drawn in TikZ in the source; not reproduced", "sec": state["sec"], "env": None}); i = j + len(endtag); continue
        if env in ("table", "table*"):
            flush(); j = body.find(endtag, i); inner = body[i:j]; counters["table"] += 1
            for lm in re.finditer(r"\\label\{([^}]+)\}", inner): labels[lm.group(1).strip()] = counters["table"]
            cap = ""; cm = re.search(r"\\caption\{", inner)
            if cm: ce = balanced(inner, cm.end() - 1); cap = inner[cm.end():ce - 1]
            rows = []; tm_ = re.search(r"\\begin\{tabular\*?\}", inner)
            if tm_:
                k = tm_.end()
                while k < len(inner) and inner[k] in " {":
                    if inner[k] == "{": k = balanced(inner, k)
                    else: k += 1
                te = inner.find("\\end{tabular", k); tab = inner[k:te]
                tab = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|cline\{[^}]*\}|cmidrule(?:\([^)]*\))?\{[^}]*\}|multicolumn\{[^}]*\}\{[^}]*\})", "", tab)
                for r in re.split(r"\\\\", tab):
                    cells = [c.strip() for c in r.split("&")]
                    if any(cells): rows.append(cells)
            blocks.append({"type": "table", "raw": cap, "num": counters["table"], "rows": rows, "sec": state["sec"], "env": None}); i = j + len(endtag); continue
        if env in ("center", "flushleft", "flushright", "small", "footnotesize", "minipage", "sloppypar", "quote", "quotation", "spacing"):
            om = re.match(r"\s*\{[^}]*\}", body[i:])
            if env == "minipage" and om: i += om.end()
            continue
        j = body.find(endtag, i)
        i = (j + len(endtag)) if j >= 0 else n
    flush()
    return blocks, labels, macros, title, body


def escape_math_angles(h):
    """A raw < or > inside inline or display maths ("1\\leq j<k\\leq n") is read by a browser, and by every tag-stripping
    reader of the HTML, as the start of a tag, which swallows the rest of the statement. Escape them inside $...$ / $$...$$ spans only; KaTeX reads the text content, so &lt; reaches it as <."""
    if not h or ("<" not in h and ">" not in h): return h
    def fix(m): return m.group(0).replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\$\$.*?\$\$|\$[^$]*\$", fix, h, flags=re.S)


def finalize_paper(blocks, labels, macros, title):
    conv = Tex2Html(labels)
    out = []
    for k, b in enumerate(blocks):
        o = {"id": "p%d" % k, "type": b["type"], "sec": b.get("sec"), "env": b.get("env"), "num": b.get("num")}
        if b["type"] == "eq":
            o["tex"] = b["tex"]
        elif b["type"] == "fig":
            o["html"] = conv.convert(b["raw"]); o["imgs"] = b["imgs"]; o["note"] = b["note"]
        elif b["type"] == "table":
            o["html"] = conv.convert(b["raw"]); o["rows"] = [[conv.convert(c) for c in r] for r in b["rows"]]
        else:
            o["html"] = conv.convert(b["raw"])
            if not o["html"] and b["type"] != "eq": continue
        if o.get("html"): o["html"] = escape_math_angles(o["html"])
        if o.get("rows"): o["rows"] = [[escape_math_angles(c) for c in r] for r in o["rows"]]
        out.append(o)
    return {"title": conv.convert(title), "macros": macros, "blocks": out}


# ----------------------------------------------------------------------------- blog -> blocks
def html_blog_blocks(html_path):
    """Blog from a saved page. The article container is the first candidate selector holding >=150 words
    (WordPress .entry-content, IBM [class*=post-body], Google research .rich-text, then article/main).
    A container with no <p> (some blogs set a post as one div broken by <br><br>) is split on blank lines."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    art = None
    for sel in (".entry-content", "[class*=post-body]", ".rich-text", "[class*=post__content]", "[class*=article-body]", "article", "main"):
        for cand in soup.select(sel):
            if len(cand.get_text(" ", strip=True).split()) >= 150: art = cand; break
        if art is not None: break
    art = art if art is not None else soup
    for t in art.select("script,style,nav,footer,svg,form,button,table"): t.decompose()
    title = soup.select_one("h1")
    blocks = [{"id": "b0", "type": "h1", "html": esc(title.get_text(" ", strip=True)), "sec": "", "env": None}] if title else []
    k = len(blocks)
    if art.find("p") is None:
        for br in art.find_all("br"): br.replace_with("\n")
        for para in re.split(r"\n\s*\n", art.get_text("", strip=False)):
            txt = re.sub(r"\s+", " ", para).strip()
            if len(txt.split()) < 2: continue
            typ = "h2" if len(txt.split()) <= 6 and not re.search(r"[.!?:]$", txt) else "p"
            blocks.append({"id": "b%d" % k, "type": typ, "html": esc(txt), "sec": "", "env": None}); k += 1
        return {"title": blocks[0]["html"] if blocks else "", "macros": {}, "blocks": blocks}
    for el in art.find_all(["h2", "h3", "h4", "p", "li", "blockquote", "figcaption"]):
        txt = el.get_text(" ", strip=True)
        if not txt: continue
        if el.find_parent(["li"]) and el.name != "li": continue
        typ = {"h2": "h2", "h3": "h3", "h4": "h4", "li": "li", "blockquote": "p", "figcaption": "fig"}.get(el.name, "p")
        blocks.append({"id": "b%d" % k, "type": typ, "html": esc(re.sub(r"\s+", " ", txt)), "sec": "", "env": None}); k += 1
    return {"title": blocks[0]["html"] if blocks else "", "macros": {}, "blocks": blocks}


def pdf_paper_blocks(pdf_path, pid=None):
    """Paper from a journal PDF when no LaTeX source exists (e.g. a Nature article). Column-aware reading
    order; the body font is the family carrying most characters at >= 7.5 pt and only blocks in that family
    (or bold/semibold headings) are kept, so running heads, dates, affiliations, captions and the reference
    list (set smaller) drop out. Equations set as glyph soup are kept as they come; nothing is numbered."""
    doc = fitz.open(pdf_path); raw = []
    eqdir = FIG_OUT
    if eqdir: eqdir.mkdir(parents=True, exist_ok=True)
    for pno, page in enumerate(doc):
        W = page.rect.width
        tblocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0 and any(l["spans"] for l in b["lines"])]
        btext = lambda b: " ".join("".join(s["text"] for s in l["spans"]) for l in b["lines"]).strip()
        # numbered display equations: text extraction scrambles them (sub/superscripts come out as separate
        # blocks, the "(1)" may be followed by a stray exponent), so each is cropped from the page as an image
        # together with every block sharing its vertical band in the same column; paper.equations may add TeX
        consumed, eqitems = set(), []
        for i, b in enumerate(tblocks):
            t = btext(b)
            # an equation block: carries "(N)", is short, and is not a sentence (no word of 4+ letters followed by a stop)
            meq = re.search(r"\((\d+)\)", t)
            if not (meq and len(t.split()) <= 40 and eqdir is not None and not re.search(r"[A-Za-z]{4,}[.,;:]?\s+[A-Za-z]{4,}", t)): continue
            x0, y0, x1, y1 = b["bbox"]; col = 0 if x0 < 0.45 * W else 1
            rect = fitz.Rect(b["bbox"])
            for j, o in enumerate(tblocks):
                if j == i: continue
                ox0, oy0, ox1, oy1 = o["bbox"]
                ocol = 0 if ox0 < 0.45 * W else 1
                overlap = min(y1, oy1) - max(y0, oy0)   # negative = vertical gap; limits of sums/products sit just above
                if ocol == col and overlap > -6 and len(btext(o).split()) <= 12 and not re.search(r"[A-Za-z]{4,}\s+[A-Za-z]{4,}", btext(o)):
                    rect |= fitz.Rect(o["bbox"]); consumed.add(j)
            consumed.add(i)
            num = int(meq.group(1)); pad = 3
            clip = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad) & page.rect
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip, alpha=False)
            fn = f"eq{num}.png"; pix.save(str(eqdir / fn))
            raw.append({"txt": t, "size": 99, "font": "EQIMG", "page": pno, "col": col, "y": y0, "n": 1,
                        "eq": {"num": num, "img": f"figs/{pid}/{fn}"}})
        for i, b in enumerate(tblocks):
            if i in consumed: continue
            spans = [s for l in b["lines"] for s in l["spans"]]
            x0, y0, x1, y1 = b["bbox"]
            wide = (x1 - x0) > 0.55 * W
            col = -1 if wide else (0 if x0 < 0.45 * W else 1)
            # SUB/SUPERSCRIPTS. The PDF stores a subscript as a separate "line" (or a trailing span) with a smaller
            # size, so plain extraction gives "F = 1 XEB" for F_XEB = 1. Lines whose vertical ranges overlap are
            # merged into one visual line, its spans are sorted by x, and small spans become <sub>/<sup> by their
            # vertical offset (markers \x01/\x02 survive escaping and are turned into tags at the end).
            vlines = []
            for l in sorted(b["lines"], key=lambda l: l["bbox"][1]):
                ly0, ly1 = l["bbox"][1], l["bbox"][3]; lc = (ly0 + ly1) / 2
                for v in vlines:
                    if v["y0"] <= lc <= v["y1"] or ly0 <= (v["y0"] + v["y1"]) / 2 <= ly1:
                        v["spans"].extend(l["spans"]); v["y0"] = min(v["y0"], ly0); v["y1"] = max(v["y1"], ly1); break
                else: vlines.append({"y0": ly0, "y1": ly1, "spans": list(l["spans"])})
            vlines.sort(key=lambda v: v["y0"])
            def vtext(v):
                sp = sorted(v["spans"], key=lambda s: s["bbox"][0]); main = [s for s in sp if len(s["text"].strip()) > 1] or sp
                base = max(s["size"] for s in main); mid = sum((s["bbox"][1] + s["bbox"][3]) / 2 * len(s["text"]) for s in main) / max(1, sum(len(s["text"]) for s in main))
                out, prev_x1 = "", None
                for s in sp:
                    t = s["text"]
                    if not t: continue
                    if prev_x1 is not None and s["bbox"][0] - prev_x1 > 2.5 and not out.endswith(" ") and not t.startswith(" "): out += " "
                    if s["size"] < 0.8 * base and t.strip():
                        c = (s["bbox"][1] + s["bbox"][3]) / 2
                        out += ("\x01sub\x02" if c > mid else "\x01sup\x02") + t.strip() + "\x01/\x02"
                    else: out += t
                    prev_x1 = s["bbox"][2]
                return out, min(s["bbox"][0] for s in sp)
            paras, cur = [], []
            for v in vlines:
                ltxt, lx0 = vtext(v)
                indented = lx0 > x0 + 4 and cur and re.search(r"[.!?:\u201d)]\s*$", cur[-1][0])
                if indented: paras.append(cur); cur = []
                cur.append((ltxt, v))
            if cur: paras.append(cur)
            for para in paras:
                psp = [s for _, v in para for s in v["spans"]]
                txt = " ".join(t for t, _ in para)
                txt = re.sub(r"\s+", " ", txt).strip(); txt = re.sub(r"(\w)- (\w)", r"\1\2", txt)
                if not txt: continue
                n = max(1, sum(len(s["text"]) for s in psp))
                size = sum(s["size"] * len(s["text"]) for s in psp) / n
                font = max(set(s["font"] for s in psp), key=lambda f: sum(len(s["text"]) for s in psp if s["font"] == f))
                bb = [min(s["bbox"][0] for s in psp), min(s["bbox"][1] for s in psp), max(s["bbox"][2] for s in psp), max(s["bbox"][3] for s in psp)]
                raw.append({"txt": txt, "size": size, "font": font, "page": pno, "col": col, "y": para[0][1]["y0"], "n": n, "bbox": bb})
        if eqdir is not None:
            # the page itself, so every block can show its original crop ("original" toggle in the viewer)
            fnp = f"page{pno + 1}.jpg"
            if not (eqdir / fnp).exists(): page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(str(eqdir / fnp), jpg_quality=80)
    if not raw: return {"title": "", "macros": {}, "blocks": []}
    fam = lambda f: re.split(r"[-,]", f)[0]
    from collections import Counter
    body_fam = Counter({f: 0 for f in []})
    for it in raw:
        if it["size"] >= 7.5 and "eq" not in it: body_fam[fam(it["font"])] += it["n"]
    body_fam = body_fam.most_common(1)[0][0]
    body_size = Counter()
    for it in raw:
        if fam(it["font"]) == body_fam: body_size[round(it["size"])] += it["n"]
    body_size = body_size.most_common(1)[0][0]
    # reading order: per page, full-width blocks by y, then column 0 by y, then column 1 by y
    raw.sort(key=lambda it: (it["page"], 0 if it["col"] == -1 else 1, it["col"], it["y"]))
    ti = max(range(len(raw)), key=lambda i: raw[i]["size"] if "eq" not in raw[i] else 0)
    title = raw[ti]["txt"]
    items, stop = [], False
    for it in raw:
        if stop and re.match(r"^(Article\s+)?Methods$", it["txt"].strip()):
            stop = False; items.append({"txt": "Methods", "typ": "h2", "page": it["page"], "bbox": it.get("bbox")}); continue
        if re.match(r"^(Article|Letter|Nature\s|\d+\s*\|\s*Nature|https?://|Received:|Accepted:|Published online:|Check for updates)", it["txt"]): continue
        heading = (re.search(r"bold|semibold|black|heavy", it["font"], re.I) or (fam(it["font"]) == body_fam and it["size"] >= body_size + 1)) \
                  and it["size"] >= body_size - 1 and len(it["txt"].split()) <= 12 and not re.search(r"[.]$", it["txt"]) \
                  and len(re.findall(r"[A-Za-z]{2,}", it["txt"])) >= 2
        # Nature layout: main text, "Online content", the reference list, then a "Methods" section, then Data availability /
        # Acknowledgements / Author contributions / ... Reading stops at the first of those headings and resumes at the
        # "Methods" heading (set "Article Methods" at the top of its page), so the Methods text is kept
        if re.match(r"^(References|Online content|Acknowledgements|Author contributions|Competing interests|Additional information|Data availability|Code availability)\b", it["txt"]): stop = True
        if stop: continue
        if it is raw[ti]: continue
        if "eq" in it: items.append({"txt": it["txt"], "typ": "eq", "page": it["page"], "eq": it["eq"]}); continue
        it.setdefault("bbox", None)
        if heading: items.append({"txt": it["txt"], "typ": "h2", "page": it["page"], "bbox": it["bbox"]}); continue
        if fam(it["font"]) != body_fam or it["size"] < body_size - 0.6: continue
        if re.match(r"^\d+\.\s", it["txt"]) and len(it["txt"].split()) < 40: continue
        items.append({"txt": it["txt"], "typ": "p", "page": it["page"], "bbox": it["bbox"]})
    merged = []
    for it in items:
        if merged and it["typ"] == "p" and merged[-1]["typ"] == "p" and not re.search(r"[.!?:\u201d)]$", merged[-1]["txt"]) and it["txt"][:1].islower():
            merged[-1]["txt"] += " " + it["txt"]; merged[-1].setdefault("more", []).append({"page": it["page"], "bbox": it["bbox"]}); continue
        merged.append(it)
    def markup(txt):
        h = esc(txt)
        h = h.replace("\x01sub\x02", "<sub>").replace("\x01sup\x02", "<sup>").replace("\x01/\x02", "</sub>")
        # a </sub> closing a <sup>: fix by scanning
        out, stack, pos = "", [], 0
        for m in re.finditer(r"<sub>|<sup>|</sub>", h):
            out += h[pos:m.start()]; tag = m.group(0)
            if tag == "</sub>": out += "</" + (stack.pop() if stack else "sub") + ">"
            else: stack.append(tag[1:4]); out += tag
            pos = m.end()
        return out + h[pos:]
    PW, PH = doc[0].rect.width, doc[0].rect.height
    blocks = [{"id": "b0", "type": "h1", "html": esc(re.sub(r"[\x01\x02]|sub|sup|/", "", re.sub(r"^Article\s+", "", title)) if "\x01" in title else re.sub(r"^Article\s+", "", title)), "sec": "", "env": None}]
    for k, it in enumerate(merged, 1):
        if it["typ"] == "eq":
            blocks.append({"id": "b%d" % k, "type": "eq", "num": it["eq"]["num"], "img": it["eq"]["img"], "tex": "", "html": "",
                           "sec": "p.%d" % (it["page"] + 1), "env": None, "note": "cropped from the PDF; text extraction gave: " + it["txt"]})
        else:
            src = ([{"page": it["page"] + 1, "bbox": [round(v, 1) for v in it["bbox"]]}] if it.get("bbox") else []) + \
                  [{"page": m["page"] + 1, "bbox": [round(v, 1) for v in m["bbox"]]} for m in it.get("more", []) if m.get("bbox")]
            blocks.append({"id": "b%d" % k, "type": it["typ"], "html": markup(it["txt"]), "sec": "p.%d" % (it["page"] + 1), "env": None,
                           "src": {"dir": f"figs/{pid}", "pw": round(PW, 1), "ph": round(PH, 1), "crops": src} if (src and pid) else None})
    return {"title": re.sub(r"<[^>]+>", "", blocks[0]["html"]), "macros": {}, "blocks": blocks}


def pdf_blog_blocks(pdf_path):
    doc = fitz.open(pdf_path); items = []
    for pno, page in enumerate(doc):
        W, H = page.rect.width, page.rect.height
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0: continue
            spans = [s for l in b["lines"] for s in l["spans"]]
            if not spans: continue
            txt = " ".join("".join(s["text"] for s in l["spans"]) for l in b["lines"])
            txt = re.sub(r"\s+", " ", txt).strip()
            txt = re.sub(r"(\w)- (\w)", r"\1\2", txt)   # line-end hyphenation
            size = sum(s["size"] * len(s["text"]) for s in spans) / max(1, sum(len(s["text"]) for s in spans))
            font = max(set(s["font"] for s in spans), key=lambda f: sum(len(s["text"]) for s in spans if s["font"] == f))
            bold = "Bold" in font
            if size < 9: continue      # page furniture (header/footer/nav) is set small
            items.append({"txt": txt, "size": size, "bold": bold, "page": pno})
    # start at the title (largest bold block), drop short navigation items before it
    if items:
        ti = max(range(len(items)), key=lambda i: items[i]["size"] if items[i]["bold"] else 0)
        items = items[ti:]
    # a paragraph split by a page break: previous block has no sentence end, next starts in lower case
    merged = []
    for it in items:
        if merged and not merged[-1]["bold"] and not it["bold"] and not re.search(r"[.!?:”)]$", merged[-1]["txt"]) and it["txt"][:1].islower():
            merged[-1]["txt"] += " " + it["txt"]; continue
        merged.append(it)
    items = merged
    blocks = []
    for k, it in enumerate(items):
        words = len(it["txt"].split())
        if it["bold"] and it["size"] >= 12: typ = "h1" if k == 0 else "h2"
        elif words <= 3 and not it["bold"]: continue
        else: typ = "p"
        if re.match(r"^(SHARE|Share|Link copied)", it["txt"]): continue
        if typ == "h2" and re.match(r"^(Learn more|Related posts)$", it["txt"]): break   # Microsoft blog trailer
        blocks.append({"id": "b%d" % k, "type": typ, "html": esc(it["txt"]), "sec": "p.%d" % (it["page"] + 1), "env": None})
    return {"title": blocks[0]["html"] if blocks else "", "macros": {}, "blocks": blocks}


# ----------------------------------------------------------------------------- anchoring quotes to blocks
def plain(html):
    """Text of a block html with tags and math masked by spaces (same length), for offset-preserving search."""
    s = mask_math(html)
    s = re.sub(r"<[^>]+>", lambda m: " " * len(m.group(0)), s)
    return s


def norm_quote(q):
    # the coder's text file renders <sub>/<sup> as _ and ^ ("F_XEB"), while the masked HTML reads "F XEB";
    # a quote copied from the text file must still locate, so both marks are read as spaces here.
    q = q.replace("\x0f", "ε").replace("_", " ").replace("^", " ")
    q = unicodedata.normalize("NFKC", q)
    return re.sub(r"\s+", " ", q).strip()


def probes(quote):
    """Search strings, most specific first. Tokens that could be maths (single letters, digits, Greek, symbols)
    break a run, because the LaTeX source has them inside $..$ which the masked text blanks out."""
    q = norm_quote(quote)
    toks = q.split(" ")
    def plain_tok(t):
        core = re.sub(r"^[(\"“‘]+|[)\"”’.,;:!?]+$", "", t)
        return bool(re.fullmatch(r"[A-Za-z]{2,}(?:['’-][A-Za-z]{2,})*", core))
    runs, cur = [], []
    for t in toks:
        if plain_tok(t): cur.append(t)
        else:
            if len(cur) >= 3: runs.append(cur)
            cur = []
    if len(cur) >= 3: runs.append(cur)
    cands = [q]
    for r in sorted(runs, key=len, reverse=True):
        cands.append(" ".join(r))
        if len(r) >= 6: cands.append(" ".join(r[:5])); cands.append(" ".join(r[-5:]))
    out, seen = [], set()
    for p in cands:
        p = re.sub(r"[.,;:!?]+$", "", p.strip().lower())
        if len(p) >= 12 and p not in seen: seen.add(p); out.append(p)
    return out


def sentence_span(text, i, j):
    """Expand [i,j) to the containing sentence in a masked text."""
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", text)]
    start = 0
    for e in ends:
        if e <= i: start = e
        else: break
    end = len(text)
    for e in ends:
        if e >= j: end = e; break
    while start < end and text[start] in " \t": start += 1
    return start, end


def snap(html, pos, forward):
    """Move pos out of any <tag> it falls inside."""
    for m in re.finditer(r"<[^>]+>", html):
        if m.start() < pos < m.end(): return m.end() if forward else m.start()
    return pos


def locate_quote(doc, quote):
    """Locate a coded quote in the rebuilt text. The full quote is tried first, then math-free runs of it (probes()).
    A probe can occur more than once in the paper;
    every occurrence is scored by how many words of the whole quote its sentence contains, and the best wins."""
    qn = norm_quote(quote).lower()
    qtoks = set(re.findall(r"[a-z]{3,}", qn))
    for p in probes(quote):
        full = (p == qn)
        best = None
        for b in doc["blocks"]:
            if b["type"] in ("eq",) or "html" not in b: continue
            t = plain(b["html"]); tl = t.lower()
            # tags are masked to spaces by plain(), so a probe must tolerate runs of whitespace ("the <em>Trotter error</em> bound")
            rx = re.compile(r"\s+".join(re.escape(w) for w in p.split()))
            for m in rx.finditer(tl):
                s, e = sentence_span(t, m.start(), m.end())
                score = sum(1 for w in qtoks if w in tl[s:e])
                # the full quote marks exactly its own span; a math-free fragment marks the sentence it sits in
                if full: s, e = m.start(), m.end()
                if best is None or score > best[0]: best = (score, b, s, e)
        if best:
            score, b, s, e = best
            s = snap(b["html"], s, True); e = snap(b["html"], e, False)
            return {"block": b["id"], "start": s, "end": e, "probe": "full" if p == norm_quote(quote).lower() else p}
    return None


