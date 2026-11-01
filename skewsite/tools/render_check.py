#!/usr/bin/env python3
"""Render check for the built site.

Loads dist/index.html in headless Chrome and, for every pair, clicks through the site the way a reader would:
  - Paper tab: every paper metric. Each shown passage must carry a visible mark (an equation highlight, an orange
    prose source, or a grey naming sentence); a passage shown with no mark is a failure.
  - Blog tab: every blog metric, same test.
  - Map: every node must open its three chips; every paper and blog matrix must render.
  - Any JavaScript error is a failure.
Writes build/render_check.json and prints a summary; exits 1 if anything fails.

    python3 tools/render_check.py            # all pairs
    python3 tools/render_check.py MIC-442_Low2023
    python3 tools/render_check.py other/index.html [pair ...]   # another built page
"""
import json, os, re, subprocess, sys, tempfile, html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

PROBE = r"""<script>
history.pushState=function(){}; history.replaceState=function(){}; window.__e=[]; window.addEventListener('error',function(e){ window.__e.push(String(e.message)); });
function __run(){ var S=window.__skew, out={pairs:{}, errors:[]}, ids=window.PAIR_ORDER||Object.keys(window.PAIRS);
  var want=__WANT__; ids.forEach(function(pid){ if(want.length&&want.indexOf(pid)<0) return; var R={paper:[],blog:[],map:[],counts:{}};
    var P=window.PAIRS[pid], hp=!P.sides||P.sides.indexOf('paper')>=0, hb=!P.sides||P.sides.indexOf('blog')>=0;
    try{ S.route('#/p/'+pid+'/'+(hp?'paper':'blog')); var v=S.VIEWS[pid]; if(!v){ R.map.push('view did not build'); out.pairs[pid]=R; return; } var M=v.M;
      function shown(sel){ var tab=document.querySelector(sel); var blks=tab.querySelectorAll('.docv .blk.hit, .docv .blk[class*="hit-"]'); var bad=[];
        Array.prototype.forEach.call(blks,function(b){ if(b.classList.contains('hid')) return; var ok=b.querySelector('mark')||/hit-eq/.test(b.className)||b.querySelector('.katex'); if(!ok) bad.push(b.dataset.id||b.id||'?'); }); return {n:blks.length,bad:bad}; }
      var np=0; if(hp) M.QORDER.forEach(function(k){ v.select('paper',k); var r=shown('#tab-paper'); np++; if(r.bad.length) R.paper.push(M.lbl(k)+': '+r.bad.length+' passage(s) shown with no mark'); });
      var nb=0; if(hb){ v.showTab('blog'); M.B.forEach(function(b){ v.select('blog',b.id); var r=shown('#tab-blog'); nb++; if(r.bad.length) R.blog.push(b.label+': '+r.bad.length+' passage(s) shown with no mark'); }); }
      var nn=0;
      if(!(hp&&hb)){ /* one side only: the other tab says it was not given, the map is withheld */
        v.showTab('map'); var mm=document.querySelector('#tab-map .msg'); if(!mm||!/Map withheld/.test(mm.textContent)) R.map.push('one-sided pair: the map is not withheld');
        var miss=hp?'blog':'paper'; v.showTab(miss); var ms=document.querySelector('#tab-'+miss+' .msg'); if(!ms||!/not given|No (paper|blog) given/i.test(ms.textContent)) R.map.push('one-sided pair: the '+miss+' tab does not say it was not given');
        var mx=document.querySelector('#tab-'+(hp?'paper':'blog')+' table.mx'); if(!mx||!mx.querySelector('tbody tr')) R.map.push('matrix missing on the '+(hp?'paper':'blog')+' tab');
        R.counts={paper_metrics:np, blog_metrics:nb, map_nodes:0, one_side:(hp?'paper':'blog')}; out.pairs[pid]=R; return; }
      v.showTab('map'); var svg=document.querySelector('#tab-map #sk2-svg');
      Array.prototype.forEach.call(svg.querySelectorAll('.pnode:not(.fhide),.bnode:not(.fhide)'),function(g){ g.dispatchEvent(new MouseEvent('click',{bubbles:true})); nn++; var pop=document.querySelector('#tab-map .mpop'); if(!pop||pop.hidden||pop.querySelectorAll('.chip').length!==3) R.map.push('no chips for '+(g.dataset.p||g.dataset.b)); });
      ['#tab-paper','#tab-blog'].forEach(function(t){ var mx=document.querySelector(t+' table.mx'); if(!mx||!mx.querySelector('tbody tr')) R.map.push('matrix missing on '+t); });
      R.counts={paper_metrics:np, blog_metrics:nb, map_nodes:nn};
    }catch(err){ R.map.push('exception: '+err.message); }
    out.pairs[pid]=R; });
  out.errors=window.__e.slice(); var pre=document.createElement('pre'); pre.id='dumpout'; pre.textContent=JSON.stringify(out); document.body.appendChild(pre); }
// first, the way a reader enters: change the address from the front page and see that the pair opens
setTimeout(function(){ var ids=(window.PAIR_ORDER||Object.keys(window.PAIRS)).filter(function(i){ var P=window.PAIRS[i]; return !P.sides||P.sides.length===2; }); if(!ids.length){ __run(); return; } location.hash='#/p/'+ids[0]+'/map';
  setTimeout(function(){ if(!document.querySelector('#sk2-svg')) window.__e.push('navigation: opening #/p/'+ids[0]+'/map from the front page did not show the pair'); __run(); }, 1500); }, 3000);
</script></body>"""


def main(want):
    page_path = ROOT / "dist" / "index.html"
    if want and want[0].endswith(".html"): page_path = Path(want.pop(0))
    src = page_path.read_text(encoding="utf-8")
    page = src.replace("</body>", PROBE.replace("__WANT__", json.dumps(want)), 1)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f: f.write(page); tmp = f.name
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--window-size=1300,900", "--virtual-time-budget=600000", "--dump-dom", "file://" + tmp],
                       capture_output=True, text=True, timeout=1200)
    m = re.search(r'<pre id="dumpout">(.*?)</pre>', r.stdout, re.S)
    if not m: print("render check: the page did not finish (no report)"); sys.exit(2)
    rep = json.loads(html.unescape(m.group(1))); (ROOT / "build").mkdir(exist_ok=True); (ROOT / "build" / "render_check.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    fails = 0
    for pid, R in rep["pairs"].items():
        n = len(R["paper"]) + len(R["blog"]) + len(R["map"]); fails += n
        print(f"  {pid}: {R.get('counts')} — {n} problem(s)")
        for k in ("paper", "blog", "map"):
            for x in R[k][:8]: print(f"     [{k}] {x}")
            if len(R[k]) > 8: print(f"     [{k}] … {len(R[k]) - 8} more")
    for e in rep["errors"]: print("  JS error:", e)
    fails += len(rep["errors"])
    print(f"render check: {fails} problem(s); report in build/render_check.json"); sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
