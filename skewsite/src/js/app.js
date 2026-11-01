(function(){
'use strict';
var PAIRS = window.PAIRS || {}, ORDER = window.PAIR_ORDER || [];
var SCOPENAME = {abstract:'abstract', intro:'introduction', prelim:'§2.2–2.3 cost model', body:'body §3–8 + appendices'};
function key(a,b){ return a<b ? a+'|'+b : b+'|'+a; }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function h(tag, cls, html){ var e=document.createElement(tag); if(cls) e.className=cls; if(html!=null) e.innerHTML=html; return e; }
function uniq(arr){ var s={}, o=[]; arr.forEach(function(x){ if(!s[x]){ s[x]=1; o.push(x);} }); return o; }
var DELIMS=[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}];
function ts(node, macros){ if(!window.renderMathInElement) return; renderMathInElement(node,{delimiters:DELIMS, throwOnError:false, strict:'ignore', macros:macros||{}, ignoredTags:['script','noscript','style','textarea','pre','code','template']}); }

// ---------- layer state (shared by the three tabs) ----------
var L = {eq:true, framing:true, prelim:true, body:true};   // all prose scopes on; the layer toggles are gone, the whole paper is always read
// the unit is a paper link; five live cells over (blog names end 1, names end 2, states the link): ✓✓✓ carried, ✓✓✗ dropped link, ✓✗✗ one end named, ✗✗✗ neither end named, ✗✓✓ off-paper link (a blog edge with an end that has no paper metric). Ungrounded and collapsed sit outside the grid.
var STATNAME={rep:'supported in the blog',ung:'unsupported',unl:'not supported: the blog names both',orph:'not supported: the blog names one',abs:'not supported: the blog names neither',none:'not linked'};   // one word, support
var KINDNAME={equation:'equation',prose:'prose',conditional:'conditional (derived from a condition)'};
function pol(x){ return x.polarity==='negated'?'negated':'positive'; }   // only an explicit statement of independence is negated; 'unspecified' (direction not stated) counts as a link
function scopeOn(scope){ if(scope==='abstract'||scope==='intro') return L.framing; if(scope==='prelim') return L.prelim; if(scope==='body') return L.body; return true; }
function proseOn(l){ return scopeOn(l.scope); }

// ---------- lumping dial ----------
// Metrics may be read as one only on semantic similarity of their names, under a threshold the reader sets. The
// scores come from tools/similarity.py (sentence embeddings of label + names; wording only). Grouping is single-linkage:
// every pair scoring at or above the threshold is joined, and joins chain. Links, equations and mappings are never read
// for grouping; they are re-keyed onto the groups afterwards so every count on the page is recomputed under the dial.
var LUMP = {};   // pid -> threshold (1 = no lumping)
var DEFAULT_TAU = 0.70;   // the slider runs fine 1.00 to coarse 0.60 (definitions); the site opens at 0.70
var FILTER = {}; // pid -> {pc: top % of paper metrics by PageRank shown, nb: hide paper metrics no blog metric stands for} (map only)
var DIALN = 0;
function TI(t){ return ' <span class="info" tabindex="0" data-tip="'+esc(t)+'" aria-label="'+esc(t)+'">ⓘ</span>'; }   // short column note
function APPX(t){ return '<p class="small muted">Hover over ⓘ to see what a column means. The full details are on the <a href="method.html#'+t+'">methods page</a>.</p>'; }
var MAPG = {};   // pid -> mapping granularity threshold (1 = by name only)
// a blog metric maps to a paper metric only by name (the paper's name used in its own mentions: alias_used).
// A mapping marked "inferred" is not used. Below 1, a blog metric with no by-name mapping is folded into its nearest paper metric
// (semantic similarity of names, build/similarity/map_<pair>.json) when the score is at or above the threshold; folds are drawn dashed.
function mapP(P, mt){ if(!P.B) return P; var cross=(P.sim&&P.sim.map)||{}, info={total:P.B.length,mapped:0,folded:0,aside:0}, changed=false;
  var B=P.B.map(function(b){ var pre=b.preimage||[], au=b.alias_used||{}, byName=pre.filter(function(k){ return au[k]; });
    if(b.mapping!=='inferred'&&!Object.keys(au).length) byName=pre.slice();   // a by-name node without alias_used keeps its preimage
    var nb=b; if(byName.length!==pre.length){ info.aside+=pre.length-byName.length; nb=Object.assign({},b,{preimage:byName}); if(!byName.length){ delete nb.mapping; delete nb.mapping_note; } else nb.mapping='by name'; if(byName.length<2){ delete nb.preimage_unsure; delete nb.preimage_note; } changed=true; }
    if(!byName.length&&mt<1){ var c=cross[b.id]||{}, best=null; Object.keys(c).forEach(function(k){ if(best===null||c[k]>c[best]) best=k; });
      if(best!==null&&c[best]>=mt){ nb=Object.assign({},nb,{preimage:[best],mapping:'similarity',mapping_note:'Joined by the metric boundary: the most similar paper metric ('+c[best].toFixed(2)+'), not a coder’s mapping.'}); info.folded++; changed=true; } }
    if((nb.preimage||[]).length) info.mapped++; return nb; });
  var out=changed?Object.assign({},P,{B:B}):P; out.mapg=info; return out; }
// PageRank on an undirected graph (damping 0.85; a node with no links spreads its weight evenly); sums to 1
function pagerank(V, adj){ var N=V.length, pr={}, d=0.85; V.forEach(function(v){ pr[v]=1/N; }); for(var it=0;it<100;it++){ var nx={}, dang=0; V.forEach(function(v){ nx[v]=(1-d)/N; if(!(adj[v]||[]).length) dang+=pr[v]; }); V.forEach(function(v){ var nb=adj[v]||[]; nb.forEach(function(w){ nx[w]+=d*pr[v]/nb.length; }); }); V.forEach(function(v){ nx[v]+=d*dang/N; }); pr=nx; } return pr; }
function unionFind(ids, pairs, tau){ var par={}; ids.forEach(function(i){ par[i]=i; }); function f(x){ while(par[x]!==x){ par[x]=par[par[x]]; x=par[x]; } return x; }
  Object.keys(pairs||{}).forEach(function(k){ if(pairs[k]<tau) return; var ab=k.split('|'); if(!(ab[0] in par)||!(ab[1] in par)) return; var a=f(ab[0]), b=f(ab[1]); if(a!==b){ if(ids.indexOf(a)<ids.indexOf(b)) par[b]=a; else par[a]=b; } });
  var map={}, groups={}; ids.forEach(function(i){ var r=f(i); map[i]=r; (groups[r]=groups[r]||[]).push(i); }); return {map:map, groups:groups}; }
function uniqArr(a){ var o=[]; a.forEach(function(x){ if(o.indexOf(x)<0) o.push(x); }); return o; }
function lumpLabel(names){ return names.join(' ⊕ '); }   /* back to every name joined */
function lumpP(P, tau){ if(!(tau<1)||!P.sim||!P.Q) return P; var sim=P.sim;
  // a formula variable is pinned by the paper's notation, not by wording, so a symbol metric never lumps
  var pinned={}; P.Q.forEach(function(q){ if(q.kind==='symbol') pinned[q.key]=1; }); var simP={}; Object.keys(sim.paper||{}).forEach(function(k){ var ab=k.split('|'); if(!pinned[ab[0]]&&!pinned[ab[1]]) simP[k]=sim.paper[k]; });
  var qs=P.Q.map(function(q){ return q.key; }), U=unionFind(qs, simP, tau); var gm=U.map;
  var bs=(P.B||[]).map(function(b){ return b.id; }), V=unionFind(bs, sim.blog, tau); var bm=V.map;
  var Q=[]; var QI={}; P.Q.forEach(function(q){ QI[q.key]=q; });
  Object.keys(U.groups).forEach(function(r){ var mem=U.groups[r]; if(mem.length===1){ Q.push(QI[r]); return; } var q0=QI[r]; var al=[]; var aq={}; mem.forEach(function(k){ (QI[k].aliases||[]).forEach(function(a){ if(al.indexOf(a)<0) al.push(a); }); Object.keys(QI[k].alias_quotes||{}).forEach(function(a){ aq[a]=QI[k].alias_quotes[a]; }); });
    Q.push(Object.assign({}, q0, {label: lumpLabel(mem.map(function(k){ return QI[k].label; })), fullLabel: mem.map(function(k){ return QI[k].label; }).join(' ⊕ '), aliases: al, alias_quotes: aq, lumped: mem.slice()})); });
  var order={}; qs.forEach(function(k,i){ order[k]=i; }); Q.sort(function(a,b){ return order[a.key]-order[b.key]; });
  var labels={}; Object.keys(P.labels||{}).forEach(function(k){ if(gm[k]===k) labels[k]=P.labels[k]; });
  var rels=(P.rels||[]).map(function(r){ return Object.assign({}, r, {vars: uniqArr(r.vars.map(function(v){ return gm[v]||v; })), cond_vars: uniqArr((r.cond_vars||[]).map(function(v){ return gm[v]||v; }))}); });
  var PR=[]; (P.PR||[]).forEach(function(l){ var a=gm[l.a]||l.a, b=gm[l.b]||l.b; if(a===b) return; PR.push(Object.assign({}, l, {a:a, b:b, condition_vars: uniqArr((l.condition_vars||[]).map(function(v){ return gm[v]||v; })).filter(function(v){ return v!==a&&v!==b; })})); });
  var anchors=P.anchors||{paper:{eq:{},quotes:{}},blog:{quotes:{}}}; var bq=Object.assign({}, anchors.blog.quotes||{}); var B=[]; var BI={}; (P.B||[]).forEach(function(b){ BI[b.id]=b; });
  Object.keys(V.groups).forEach(function(r){ var mem=V.groups[r]; var b0=BI[r]; var pre=[]; mem.forEach(function(id){ (BI[id].preimage||[]).forEach(function(k){ var g=gm[k]||k; if(pre.indexOf(g)<0) pre.push(g); }); });
    if(mem.length===1){ B.push(Object.assign({}, b0, {preimage: pre})); return; }
    var ments=[]; var au={}; mem.forEach(function(id){ var bb=BI[id]; (bb.mentions||[{quote:bb.quote}]).forEach(function(m,j){ ments.push({m:m, src:j===0?id:(id+'~'+j)}); }); Object.keys(bb.alias_used||{}).forEach(function(k){ au[gm[k]||k]=bb.alias_used[k]; }); });
    ments.forEach(function(x,i){ var key=i===0?r:(r+'~'+i); if(anchors.blog.quotes[x.src]) bq[key]=anchors.blog.quotes[x.src]; });
    B.push(Object.assign({}, b0, {label: lumpLabel(mem.map(function(id){ return BI[id].label; })), fullLabel: mem.map(function(id){ return BI[id].label; }).join(' ⊕ '), mentions: ments.map(function(x){ return x.m; }), preimage: pre, alias_used: au, lumped: mem.slice(), class: mem.some(function(id){ return BI[id].class==='both'; })?'both':b0.class, mapping: mem.every(function(id){ return BI[id].mapping==='similarity'; })?'similarity':b0.mapping})); });
  var border={}; bs.forEach(function(k,i){ border[k]=i; }); B.sort(function(a,b){ return border[a.id]-border[b.id]; });
  var E=[], seen={}; (P.E||[]).forEach(function(e){ var s0=bm[e.source]||e.source, t0=bm[e.target]||e.target; if(s0===t0) return; var k=s0+'|'+t0; var cv=uniqArr((e.condition_vars||[]).map(function(v){ return bm[v]||v; })).filter(function(v){ return v!==s0&&v!==t0; });
    if(seen[k]){ var e0=E[seen[k]-1]; e0.quotes=uniqArr((e0.quotes||[e0.quote]).concat(e.quotes||[e.quote])); return; } E.push(Object.assign({}, e, {source:s0, target:t0, condition_vars:cv})); seen[k]=E.length; });
  var nP=Object.keys(U.groups).filter(function(r){ return U.groups[r].length>1; }).length, nB=Object.keys(V.groups).filter(function(r){ return V.groups[r].length>1; }).length;
  var alg=P.alg&&P.alg.links?Object.assign({}, P.alg, {links:P.alg.links.map(function(l){ return Object.assign({}, l, {a:gm[l.a]||l.a, b:gm[l.b]||l.b}); }).filter(function(l){ return l.a!==l.b; })}):P.alg;
  return Object.assign({}, P, {Q:Q, labels:labels, rels:rels, alg:alg, PR:PR, B:B, E:E, anchors:Object.assign({}, anchors, {blog:Object.assign({}, anchors.blog, {quotes:bq})}), lump:{tau:tau, paperGroups:nP, blogGroups:nB, paperFrom:P.Q.length, paperTo:Q.length, blogFrom:(P.B||[]).length, blogTo:B.length, model:sim.model}}); }

// ---------- model for a coded pair ----------
function model(P){
  var M = {P:P, Q:P.Q||[], QI:{}, QORDER:[], REL:P.rels||[], PR:P.PR||[], B:P.B||[], BI:{}, E:P.E||[], LBL:P.labels||{}, A:P.anchors||{paper:{eq:{},quotes:{}},blog:{quotes:{}}}};
  M.Q.forEach(function(q){ M.QI[q.key]=q; M.QORDER.push(q.key); });
  M.B.forEach(function(b,i){ b.i=i; M.BI[b.id]=b; });
  // equation links: two metrics are linked when they sit in a common minimal linked group of the reduced equations
  // (P.alg, skewcoder.algebra), or when the model read a statement that is not an equality as making them depend.
  // M.EQX[k] keeps the smallest group (directness). Without a reduction, every pair in one equation is linked.
  M.EQ={}; M.EQX={}; M.ALG=!!(P.alg&&P.alg.links);
  if(M.ALG){ var rid={}; M.REL.forEach(function(r,ri){ rid[r.id]=ri; });
    P.alg.links.forEach(function(l){ if(l.a===l.b) return; var k=key(l.a,l.b), ris=(l.rels||[]).map(function(id){ return rid[id]; }).filter(function(x){ return x!==undefined; }); if(!ris.length) return;
      M.EQ[k]=uniq((M.EQ[k]||[]).concat(ris)); var c=M.EQX[k];
      if(!c) M.EQX[k]={size:l.size, group:l.group, src:l.src, reason:l.reason||'', regime:l.regime||''};
      else { if(l.src==='algebra'&&(c.src!=='algebra'||(l.size&&(!c.size||l.size<c.size)))){ M.EQX[k]={size:l.size, group:l.group, src:'algebra', regime:l.regime||'', alsoModel:c.src==='model'||c.alsoModel}; } else if(l.src!==c.src) c.alsoModel=true; } }); }
  else M.REL.forEach(function(r,ri){ var v=r.vars; for(var i=0;i<v.length;i++) for(var j=i+1;j<v.length;j++){ var k=key(v[i],v[j]); (M.EQ[k]=M.EQ[k]||[]).push(ri); } });
  M.eqHow=function(k){ var x=M.EQX[k]; if(!x) return M.ALG?'':'every pair in one equation'; if(x.src==='model') return 'read by the model as dependent ('+x.reason+')';
    return (x.size?'minimal linked group of '+x.size+': '+x.group.map(function(g){ return M.lbl(g); }).join(', '):'linked through the equations (smallest group larger than '+(P.alg.max_group||6)+')')+(x.regime?' — under: '+x.regime:'')+(x.alsoModel?'; also read by the model':''); };
  M.mapped={}; M.B.forEach(function(b){ (b.preimage||[]).forEach(function(k){ (M.mapped[k]=M.mapped[k]||[]).push(b.id); }); });
  M.orphans=M.QORDER.filter(function(k){ return !M.mapped[k]; });
  // polarity = interdependent vs independent. A negated edge states no link, so it implies no pair. A blog condition naming metric C links C to each end of the edge (through preimages), as on the paper side.
  M.IMP={}; M.E.forEach(function(e,i){ var A=M.BI[e.source].preimage||[], C=M.BI[e.target].preimage||[]; if(pol(e)==='positive') A.forEach(function(a){ C.forEach(function(c){ if(a!==c){ var k=key(a,c); (M.IMP[k]=M.IMP[k]||[]).push(i);} }); });
    (e.condition_vars||[]).forEach(function(cid){ var CV=(M.BI[cid]||{}).preimage||[]; [A,C].forEach(function(side){ side.forEach(function(a){ CV.forEach(function(c){ if(a!==c){ var k=key(a,c); (M.IMP[k]=M.IMP[k]||[]).push(i);} }); }); }); }); });
  M.COLL={}; M.B.forEach(function(b){ var p=b.preimage||[]; for(var i=0;i<p.length;i++) for(var j=i+1;j<p.length;j++){ var k=key(p[i],p[j]); (M.COLL[k]=M.COLL[k]||[]).push(b.id);} });
  M.lbl=function(k){ return M.QI[k]?M.QI[k].label:k; };
  M.tex=function(k){ return M.LBL[k]||M.lbl(k); };
  // the metrics a condition names join the group: {a, b} ∪ condition_vars is a derived group, cited to the conditioned statement; pairs inside it other than a–b get a derived witness (dv).
  M.paperLayer=function(){ var out={}; function ens(k){ return out[k]=out[k]||{eq:[],pr:[],dv:[]}; } if(L.eq) Object.keys(M.EQ).forEach(function(k){ ens(k).eq=M.EQ[k].slice(); });
    M.PR.forEach(function(l,i){ if(!proseOn(l)) return; ens(key(l.a,l.b)).pr.push(i); });
    // a condition metric is linked to each metric of the pair it conditions, never to another condition metric.
    function grp(pair,conds,src,i){ pair.forEach(function(a){ conds.forEach(function(c){ if(a===c||pair.indexOf(c)>=0) return; ens(key(a,c)).dv.push({src:src,i:i}); }); }); }
    M.PR.forEach(function(l,i){ if(!proseOn(l)||!(l.condition_vars||[]).length) return; grp([l.a,l.b],l.condition_vars,'pr',i); });
    if(L.eq) M.REL.forEach(function(r,ri){ if(!(r.cond_vars||[]).length) return; grp(r.vars,r.cond_vars,'eq',ri); });
    return out; };
  M.wit=function(k,PL){ var w=[]; if(!PL[k]) return w; PL[k].eq.forEach(function(ri){ var r=M.REL[ri]; w.push({src:'eq',i:ri,pol:'positive',cond:r.cond||''}); }); PL[k].pr.forEach(function(pi){ var l=M.PR[pi]; if(pol(l)==='positive') w.push({src:'pr',i:pi,pol:'positive',cond:l.condition||''}); }); (PL[k].dv||[]).forEach(function(d){ w.push({src:'dv',i:d.i,pol:'positive',cond:'',via:d.src}); }); return w; };
  // a pair's status compares polarity and condition on both sides. agree = same polarity on both; 'cond' = the blog states it without a condition while the paper's same-polarity statements are all conditional, or the paper also states the opposite polarity (two regimes); 'contra' = the paper states only the opposite polarity.
  // kind of interdependence: (settings count as ordinary metrics) by the strongest source: equation, prose, or only derived from a condition.
  M.kind=function(k,PL){ /* a link to a setting is an ordinary link; no separate kind */ var x=PL[k]; if(!x) return null; if(x.eq.length) return 'equation'; if(x.pr.length) return 'prose'; return 'conditional'; };
  M.status=function(k,PL){ var ab=k.split('|'), linked=M.wit(k,PL).length>0, implied=!!(M.IMP[k]&&M.IMP[k].length); if(linked&&implied) return 'rep'; if(implied) return 'ung'; if(linked&&!M.mapped[ab[0]]&&!M.mapped[ab[1]]) return 'abs'; if(linked&&(!M.mapped[ab[0]]||!M.mapped[ab[1]])) return 'orph'; if(linked) return 'unl'; return 'none'; };
  M.edgeRatio=function(i,PL){ var e=M.E[i], A=M.BI[e.source].preimage||[], C=M.BI[e.target].preimage||[], pairs=[]; A.forEach(function(a){ C.forEach(function(c){ if(a!==c) pairs.push(key(a,c)); }); }); pairs=uniq(pairs); var linked=pairs.filter(function(k){ return !!PL[k]; }); return {pairs:pairs, linked:linked, grey:!(A.length&&C.length)}; };
  M.witness=function(k,PL){ var w=[]; if(PL[k]){ if(PL[k].eq.length) w.push('equation'+(M.eqHow(k)?' ('+M.eqHow(k)+')':'')+': '+PL[k].eq.map(function(ri){ return M.REL[ri].id+' '+M.REL[ri].eq; }).join(', ')); if(PL[k].pr.length) w.push('prose: '+PL[k].pr.map(function(pi){ var l=M.PR[pi]; return l.id+' §'+l.section+(pol(l)==='negated'?' [negated]':'')+(l.condition?' [if '+l.condition+']':''); }).join(', ')); var cw=PL[k].eq.filter(function(ri){ return M.REL[ri].cond; }); if(cw.length) w.push('equation conditions: '+cw.map(function(ri){ return M.REL[ri].id+' if '+M.REL[ri].cond; }).join('; ')); if((PL[k].dv||[]).length) w.push('conditions another interdependence: '+PL[k].dv.map(function(d){ return d.src==='pr'?(M.PR[d.i].id+' ('+M.lbl(M.PR[d.i].a)+'–'+M.lbl(M.PR[d.i].b)+' under '+M.PR[d.i].condition+')'):(M.REL[d.i].id+' (under '+M.REL[d.i].cond+')'); }).join('; ')); }
    if(M.IMP[k]) w.push('blog edge(s): '+M.IMP[k].map(function(i){ var e=M.E[i]; return M.BI[e.source].label+' → '+M.BI[e.target].label+(pol(e)==='negated'?' [negated]':'')+(e.condition?' [if '+e.condition+']':''); }).join('; ')); if(M.COLL[k]) w.push('collapsed inside: '+M.COLL[k].map(function(b){ return M.BI[b].label; }).join(', ')); return w.join(' · '); };
  return M;
}

// ======================================================================
// DOCUMENT VIEWER: the paper or blog rebuilt from source as a list of blocks.
// focus(hits) collapses the document to the blocks that carry a hit, with the
// hidden runs shown as expandable pills; marks sentence spans inside blocks.
// ======================================================================
// inside a highlighted source, the names of the metrics in focus are bold. Matching is the viewer's loose matcher
// (case, hyphen/space, plural); tags and maths spans are left alone so KaTeX still renders. Symbols are bolded in the maths by boldTex.
function boldNames(html, names){ if(!names||!names.words||!names.words.length) return html; var rxs=[], srx=[];
  names.words.forEach(function(w){ var r=looseRe(w); if(r){ rxs.push(new RegExp(r.source,'gi')); return; }
    // a short symbol ("Z_q", "e_1", "N_s"): exact, case-sensitive, with _ / ^ read as a sub/superscript tag or the mark itself
    var e=String(w).trim(); if(!e) return; var body=e.split(/([_^])/).map(function(t,i){ if(i%2) return t==='_'?'(?:_|<sub>)':'(?:\\^|<sup>)'; return t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }).join(''); srx.push(new RegExp('(^|[^A-Za-z0-9])('+body+'(?:</su[bp]>)?)(?![A-Za-z0-9])','g')); });
  if(!rxs.length&&!srx.length) return html;
  var math=html.split(/(\$\$[\s\S]*?\$\$|\$[^$]*\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\])/);   // maths spans are left alone (KaTeX renders them; symbols are bolded by boldTex)
  return math.map(function(seg,i){ if(i%2) return seg;
    var parts=seg.split(/(<[^>]+>)/); seg=parts.map(function(p,j){ if(j%2) return p; rxs.forEach(function(rx){ p=p.replace(rx,function(m0,pre,word){ return pre+'<b class="mfoc">'+word+'</b>'; }); }); return p; }).join('');
    srx.forEach(function(rx){ seg=seg.replace(rx,function(m0,pre,sym){ return pre+'<b class="mfoc">'+sym+'</b>'; }); }); return seg; }).join(''); }
function namesOfQ(M, keys){ var words=[], tex=[]; keys.forEach(function(k){ var q=M.QI[k]; if(!q) return; (q.aliases||[]).forEach(function(a){ if(words.indexOf(a)<0) words.push(a); }); var t=M.LBL[k]; if(t&&t.indexOf('$')>=0) tex.push(t); }); return {words:words, tex:tex}; }
function namesOfB(M, ids){ var words=[]; ids.forEach(function(id){ var b=M.BI[id]; if(!b) return; (b.mentions||[]).forEach(function(m){ if(m.matched&&words.indexOf(m.matched)<0) words.push(m.matched); }); Object.keys(b.alias_used||{}).forEach(function(k){ var w=b.alias_used[k]; if(w&&words.indexOf(w)<0) words.push(w); }); if(!words.length) words.push(b.label); }); return {words:words}; }
function DocViewer(doc, opts){
  opts=opts||{}; var root=h('div','viewer'), tools=h('div','vtools'), scroll=h('div','vscroll docv'), macros=(doc&&doc.macros)||{};
  tools.innerHTML='<span class="vinfo"></span><button type="button" class="vall">Show all</button>'; tools.classList.add('hidden');
  tools.querySelector('.vall').addEventListener('click',function(){ if(api.onClear) api.onClear(); else clear(); });
  root.appendChild(tools); root.appendChild(scroll);
  var BL={}, order=[];
  if(opts.iframe){ var note=h('p','muted small'); note.innerHTML='Shown from <a href="'+esc(opts.iframe)+'" target="_blank" rel="noopener">'+esc(opts.iframe)+'</a>. If it stays blank, the site does not allow embedding: use the link to open it in a new tab.'; scroll.appendChild(note); var f=document.createElement('iframe'); f.src=opts.iframe; f.title=opts.title||'document'; scroll.appendChild(f); }
  else if(doc){
    var box=null, boxEnv=null;
    doc.blocks.forEach(function(b,i){
      var el=h('div','blk t-'+b.type); el.dataset.id=b.id; var crumb=(b.sec&&!(b.env&&b.env.toLowerCase()===String(b.sec).toLowerCase())?'§'+b.sec:'')+(b.env?((b.sec&&b.env.toLowerCase()!==String(b.sec).toLowerCase())?' · ':'')+b.env:'');
      if(b.type==='eq'){ el.innerHTML='<span class="crumb">'+esc(crumb)+'</span><div class="eqbody"></div>'+(b.num?'<span class="eqnum" id="eq-'+b.num+'">('+b.num+')</span>':'');
        if(b.img){ el.querySelector('.eqbody').innerHTML='<img class="eqimg" src="'+esc(b.img)+'" alt="equation ('+b.num+')" title="'+esc(b.tex||'')+'">'; }
        else { try{ katex.render(b.tex, el.querySelector('.eqbody'), {displayMode:true, throwOnError:false, strict:'ignore', macros:macros}); }catch(e){ el.querySelector('.eqbody').textContent=b.tex; } } }
      else if(b.type==='fig'){ el.innerHTML='<span class="crumb">'+esc(crumb)+'</span>'+(b.imgs||[]).map(function(s){ return '<img loading="lazy" src="'+esc(s)+'" alt="Figure '+b.num+'">'; }).join('')+'<div class="pbody"><b>Figure '+b.num+'.</b> '+b.html+(b.note?' <i>('+esc(b.note)+')</i>':'')+'</div>'; ts(el.querySelector('.pbody'),macros); }
      else if(b.type==='table'){ el.innerHTML='<span class="crumb">'+esc(crumb)+'</span><div class="pbody"><b>Table '+b.num+'.</b> '+b.html+'</div><div class="tblwrap"><table class="gl">'+(b.rows||[]).map(function(r,ri){ return '<tr>'+r.map(function(c){ return (ri?'<td>':'<th>')+c+(ri?'</td>':'</th>'); }).join('')+'</tr>'; }).join('')+'</table></div>'; ts(el,macros); }
      else { var tag={h1:'h2',h2:'h3',h3:'h4',h4:'h5'}[b.type]; el.innerHTML='<span class="crumb">'+esc(crumb)+(b.src?' <button type="button" class="origbtn" title="show this passage as it appears on the PDF page">original</button>':'')+'</span>'+(tag?'<'+tag+' class="pbody">'+(b.num?b.num+' ':'')+b.html+'</'+tag+'>':'<div class="pbody">'+(b.type==='li'?'• ':'')+b.html+'</div>'); ts(el.querySelector('.pbody'),macros);
        if(b.src){ el.querySelector('.origbtn').addEventListener('click',function(ev){ ev.stopPropagation(); var o=el.querySelector('.orig'); if(o){ o.remove(); this.textContent='original'; return; } o=h('div','orig'); var w=el.querySelector('.pbody').getBoundingClientRect().width||600;
          b.src.crops.forEach(function(c){ var bw=c.bbox[2]-c.bbox[0], bh=c.bbox[3]-c.bbox[1], sc=(w-8)/bw; var d=h('div','origcrop'); d.style.width=(bw*sc)+'px'; d.style.height=(bh*sc)+'px'; d.style.backgroundImage='url('+b.src.dir+'/page'+c.page+'.jpg)'; d.style.backgroundSize=(b.src.pw*sc)+'px '+(b.src.ph*sc)+'px'; d.style.backgroundPosition=(-c.bbox[0]*sc)+'px '+(-c.bbox[1]*sc)+'px'; d.title='page '+c.page; o.appendChild(d); });
          el.appendChild(o); this.textContent='hide original'; }); } }
      // group consecutive blocks of one theorem/proof/abstract environment in a box
      if(b.env && b.type!=='h1' && b.type!=='h2'){ if(!box||boxEnv!==b.env){ box=h('div','envbox'); box.innerHTML='<div class="envlbl">'+esc(b.env)+'</div>'; scroll.appendChild(box); boxEnv=b.env; } box.appendChild(el); }
      else { box=null; boxEnv=null; scroll.appendChild(el); }
      BL[b.id]={b:b, el:el, i:i}; order.push(b.id);
    });
  }
  function hitsInfo(n){ tools.classList.toggle('hidden',!n); tools.querySelector('.vinfo').textContent=n?n+' passage'+(n===1?'':'s'):''; }
  function clear(){ order.forEach(function(id){ var x=BL[id]; x.el.classList.remove('hit','hit-eq','hit-pr','hit-mn','hit-foc','hid','peek'); if(x.marked){ var pb=x.el.querySelector('.pbody'); if(pb){ pb.innerHTML=x.b.html; ts(pb,macros); } x.marked=false; } if(x.texBold){ try{ katex.render(x.b.tex, x.el.querySelector('.eqbody'), {displayMode:true, throwOnError:false, strict:'ignore', macros:macros}); }catch(e){} x.texBold=false; } });
    Array.prototype.forEach.call(scroll.querySelectorAll('.pill'),function(p){ p.remove(); }); Array.prototype.forEach.call(scroll.querySelectorAll('.envbox.hid'),function(p){ p.classList.remove('hid'); }); hitsInfo(0); scroll.classList.remove('focused'); }
  function applyMarks(x, spans){ var html=x.b.html; var ss=spans.filter(function(s){ return s.start!=null; }).sort(function(a,b){ return a.start-b.start; }); var merged=[];
    ss.forEach(function(s){ var last=merged[merged.length-1]; if(last&&s.start<=last.end){ last.end=Math.max(last.end,s.end); last.cls=last.cls===s.cls?last.cls:'pr'; last.foc=last.foc||s.foc; } else merged.push({start:s.start,end:s.end,cls:s.cls,foc:s.foc,title:s.title}); });
    if(!merged.length) return;
    for(var i=merged.length-1;i>=0;i--){ var m=merged[i]; html=html.slice(0,m.start)+'<mark class="m-'+m.cls+(m.foc?' m-foc':'')+'" title="'+esc(m.title||'')+'">'+boldNames(html.slice(m.start,m.end), focusNames)+'</mark>'+html.slice(m.end); }
    var pb=x.el.querySelector('.pbody'); if(pb){ pb.innerHTML=html; ts(pb,macros); x.marked=true; } }
  var lastHits=null, focusNames=null;
  function boldTex(x){ if(!focusNames||!focusNames.tex||!focusNames.tex.length||x.b.type!=='eq'||x.b.img) return; var tex=x.b.tex||''; var out=tex;
    focusNames.tex.forEach(function(t){ t=String(t).replace(/^\$+|\$+$/g,'').trim(); if(!t) return; var rx; if(/^\\[A-Za-z]+$/.test(t)) rx=new RegExp('(^|[^A-Za-z\\\\])('+t.replace(/\\/g,'\\\\')+')(?![A-Za-z])','g'); else if(/^[A-Za-z]$/.test(t)) rx=new RegExp('(^|[^A-Za-z\\\\])('+t+')(?![A-Za-z])','g'); else rx=new RegExp('(^|[^A-Za-z])('+t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')(?![A-Za-z])','g'); out=out.replace(rx,'$1{\\boldsymbol{$2}}'); });   /* braces: a bare \boldsymbol after ^ or _ is a KaTeX parse error */
    if(out===tex) return; var body=x.el.querySelector('.eqbody'); try{ katex.render(out, body, {displayMode:true, throwOnError:false, strict:'ignore', macros:macros}); x.texBold=true; }catch(e){} }
  function focus(hits, names){ clear(); lastHits=hits; focusNames=names||null; var ids=order.filter(function(id){ return hits[id]; }); if(!ids.length) return;
    ids.forEach(function(id){ var x=BL[id]; applyMarks(x, hits[id]); boldTex(x); x.el.classList.add('hit'); hits[id].forEach(function(hh){ x.el.classList.add('hit-'+hh.cls); if(hh.foc) x.el.classList.add('hit-foc'); }); });
    hitsInfo(ids.length); collapse(); goTo(ids[0]); }
  function collapse(){ scroll.classList.add('focused'); var run=[];
    function flush(){ if(!run.length) return; var first=BL[run[0]], last=BL[run[run.length-1]]; var pill=h('button','pill'); pill.type='button'; var a=first.b.sec||'', b=last.b.sec||'';
      pill.textContent='⋯ '+run.length+' block'+(run.length===1?'':'s')+' hidden'+(a?' ('+(a===b?'§'+a:'§'+a+' – §'+b)+')':'')+' · show'; var ids=run.slice();
      pill.addEventListener('click',function(){ ids.forEach(function(id){ BL[id].el.classList.remove('hid'); var bx=BL[id].el.closest('.envbox'); if(bx) bx.classList.remove('hid'); }); pill.remove(); });
      var anchor=first.el.closest('.envbox')||first.el; anchor.parentNode.insertBefore(pill, anchor); run=[]; }
    order.forEach(function(id){ var x=BL[id]; if(x.el.classList.contains('hit')){ flush(); } else { x.el.classList.add('hid'); run.push(id); } }); flush();
    Array.prototype.forEach.call(scroll.querySelectorAll('.envbox'),function(bx){ if(!bx.querySelector('.blk:not(.hid)')) bx.classList.add('hid'); }); }
  function goTo(id){ var x=BL[id]; if(!x) return;
    if(x.el.classList.contains('hid')){ x.el.classList.remove('hid'); x.el.classList.add('peek'); var bx=x.el.closest('.envbox'); if(bx) bx.classList.remove('hid'); }   // a passage outside the current subset: reveal it, marked
    var top=x.el.getBoundingClientRect().top-scroll.getBoundingClientRect().top+scroll.scrollTop-40; scroll.scrollTo({top:top, behavior:'smooth'}); }
  scroll.addEventListener('click',function(e){ var a=e.target.closest('a.eqref'); if(a&&a.dataset.eq){ e.preventDefault(); var id=opts.eqIndex?opts.eqIndex[a.dataset.eq]:null; if(id) goTo(id); } });
  var api={root:root, clear:clear, focus:focus, goTo:goTo, has:function(id){ return !!BL[id]; }, onClear:null}; return api;
}

function shortLbl(l){ return String(l).replace(/\s*\([^)]*\)/g,'').trim(); }
// long (and lumped) names are clipped on the map and in the matrices; the full name is on hover (title)
function decap(l){ l=String(l); return /^[a-z]{3,}(\s|$|[-,])/.test(l)?l.charAt(0).toUpperCase()+l.slice(1):l; }   // sentence case on both sides of the map: a lowercase first word is capitalised; symbols and short codes untouched
var CLIP=26; function clip(l,n){ l=String(l); n=n||CLIP; return l.length>n?l.slice(0,n-1).replace(/[\s,;:⊕]+$/,'')+'…':l; }
function texOrClip(M,k){ var t=M.LBL[k]; if(t&&t.indexOf('$')>=0) return t; return esc(clip(t||M.lbl(k))); }
function lgLine(cls,label){ return '<span class="lgi"><svg width="44" height="12" viewBox="0 0 44 12" aria-hidden="true"><path class="'+cls+'" d="M2,6 L42,6"/></svg>'+label+'</span>'; }
// one legend for both sides. Nodes: filled / diamond / empty. Edges: solid / thin / dashed (supported / partly / not).
var MB_INFO='Each side’s coder writes a one-line definition of every metric: what is measured, of what, and in what unit. Metrics are compared by how alike their definitions are. At fine, every distinct term is its own metric, and a blog metric matches a paper metric only if the blog uses the paper’s own name. Toward coarse, two metrics on one side whose definitions are alike enough are joined (marked ⊕). A blog metric with no match by name is matched to its most alike paper metric, if the two are alike enough. Symbols never join. The slider runs from 1.00 (fine) to 0.60 (coarse) and opens at 0.70.', NC_INFO='Centrality is PageRank in this side’s own web of links. A metric is central when it is linked to many metrics, or to metrics that are central themselves. The slider hides the metrics below the chosen percentile, along with every line that touches them.';
var THIN_INFO='Only for a link from a diamond node, which stands for several metrics on the other side. The link then covers several pairs, and the other side links some of them but not all.';
var MAPLEG='<div class="unileg"><div class="ulttl">Legend</div><div class="ulrow"><span class="ulh">Nodes</span><span class="nw"><span class="mk mk-var"></span>has a corresponding blog/paper metric</span><span class="nw"><span class="mk mk-coll"></span>has multiple corresponding blog/paper metrics</span><span class="nw"><span class="mk mk-rec"></span>has no corresponding blog/paper metric</span></div>'+
  '<div class="ulrow"><span class="ulh">Edges</span>'+lgLine('lg-solid','link is supported in the corresponding paper/blog')+'<span class="lgi">'+'<svg width="44" height="12" viewBox="0 0 44 12" aria-hidden="true"><path class="lg-thin" d="M2,6 L42,6"/></svg>link is partly supported <span class="info" tabindex="0" role="note" aria-label="'+THIN_INFO+'" data-tip="'+THIN_INFO+'">ⓘ</span></span>'+lgLine('lg-dash','link is not supported in the corresponding paper/blog')+'</div></div>';
function keepRow(list, selector, render){ var box=list.closest('.scol')||list.parentNode; var row=selector?list.querySelector(selector):null; var before=row?row.getBoundingClientRect().top:null; var winY=window.scrollY;
  render(); row=selector?list.querySelector(selector):null;
  if(row&&before!=null){ var after=row.getBoundingClientRect().top; box.scrollTop+= (after-before); } window.scrollTo({top:winY}); }
// hits helpers --------------------------------------------------------
function addHit(hits, id, hit){ if(!id) return; (hits[id]=hits[id]||[]).push(hit); }
function eqHit(M, hits, n, title, foc){ addHit(hits, M.A.paper.eq[String(n)], {cls:'eq', title:title, foc:!!foc}); }
function prHit(M, hits, l, foc){ var a=M.A.paper.quotes[l.id]; if(a) addHit(hits, a.block, {cls:'pr', start:a.start, end:a.end, title:l.id+' §'+l.section+' ['+l.connective+']', foc:!!foc}); }
function blogHit(M, hits, qid, cls, title, foc){ var a=M.A.blog.quotes[qid]; if(a) addHit(hits, a.block, {cls:cls, start:a.start, end:a.end, title:title, foc:!!foc}); }
function blogHitAll(M, hits, b, cls, title, foc){ var n=(b.mentions||[1]).length; for(var i=0;i<n;i++) blogHit(M,hits,i?b.id+'~'+i:b.id,cls,title+(n>1?' (mention '+(i+1)+' of '+n+')':''),foc); }
// name mentions: every passage in which the paper uses one of the metric's own names (its alias table), independent of the
// coded layers. Matched on the block text with tags masked to spaces, so "F<sub>XEB</sub>" matches the alias "FXEB"; single-character
// aliases are skipped (too ambiguous). Shown with a dotted rule and dotted underline; coded sentences keep their own marks.

// mapping evidence: how a blog metric is tied to each paper metric in its preimage, read off the blog text at
// run time. Every name the paper uses for the metric (its alias table, plus the name the coder recorded) is searched in the blog
// under loose matching (case, hyphen/space, plural). Categories: 'same' = the blog uses one of the paper's own names;
// 'explicit' = candidate: one sentence of the blog holds two of the paper's names that are not variants of each other (the
// sentence is quoted so the reader judges whether it states the equivalence); 'inferred' = none of the paper's names occurs, so
// the mapping rests on the LLM coder's reading of the mention sentences; 'none' = empty preimage. Mechanical; no count uses it.
function maskHtml(html){ return html.replace(/<[^>]+>/g,function(t){ return new Array(t.length+1).join(' '); }).replace(/&[a-zA-Z#0-9]+;/g,function(t){ return new Array(t.length+1).join(' '); }); }
function sentBounds(t,s,e){ var a=s; while(a>0){ if(a<s&&/[.!?]/.test(t.charAt(a-1))&&/\s/.test(t.charAt(a))) break; a--; } var b=e; while(b<t.length){ if(/[.!?]/.test(t.charAt(b))&&(b+1>=t.length||/\s/.test(t.charAt(b+1)))){ b++; break; } b++; } while(a<b&&/\s/.test(t.charAt(a))) a++; return [a,b]; }
function looseRe(a){ var a2=String(a).trim(); if(a2.replace(/[_\s()]/g,'').length<3) return null; var E=function(t){ return t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); };
  var words=a2.split(/[\s\-_]+/).filter(Boolean).map(function(w){ var base=w.replace(/[()]/g,''), suf=''; if(base.length>4&&/ies$/i.test(base)){ base=base.slice(0,-3); suf='(?:y|ies)'; } else if(base.length>4&&/es$/i.test(base)){ base=base.slice(0,-2); suf='(?:e|es|s)?'; } else if(base.length>3&&/s$/i.test(base)){ base=base.slice(0,-1); suf='(?:s|es)?'; } else if(base.length>3&&/y$/i.test(base)){ base=base.slice(0,-1); suf='(?:y|ies)'; } else if(base.length>3) suf='(?:s|es)?'; return E(base)+suf; });
  try{ return new RegExp('(^|[^A-Za-z0-9])('+words.join('[\\s\\-]+')+')(?![A-Za-z0-9])','gi'); }catch(e){ return null; } }
function findInDoc(doc, phrase){ var out=[]; var re=looseRe(phrase); if(!re||!doc) return out;
  doc.blocks.forEach(function(b){ if(b.type==='eq'||b.type==='fig'||b.type==='table'||!b.html) return; var masked=maskHtml(b.html); re.lastIndex=0; var m;
    while((m=re.exec(masked))){ var st=m.index+m[1].length, en=st+m[2].length; var sb=sentBounds(masked,st,en); out.push({block:b.id, start:st, end:en, sstart:sb[0], send:sb[1], sentence:masked.slice(sb[0],sb[1]).replace(/\s+/g,' ').trim()}); if(m[0].length===0) re.lastIndex++; } });
  return out; }

// show the evidence for each of a paper metric's names. Each coded name is searched in the rebuilt paper text (same loosened matcher as the blog side); equations are not searched, so a symbol that lives only in equations shows 0 here.
function aliasEvidence(M,q){ var doc=M.P.docs&&M.P.docs.paper; return (q.aliases||[]).map(function(a){ var occ=doc?findInDoc(doc,a):[]; return {a:a, n:occ.length, o:occ[0]||null}; }); }
function aliasHTML(M,q){ var ev=aliasEvidence(M,q); var miss=ev.filter(function(x){ return !x.n; }).length;
  return '<details'+(miss?' open':'')+'><summary>Paper’s names ('+ev.length+(miss?', '+miss+' not found in the text':'')+')</summary><ul class="evlist">'+ev.map(function(x){ return '<li>“'+esc(x.a)+'” — '+(x.n?x.n+' occurrence'+(x.n===1?'':'s')+(x.o?': <span class="occ q" data-pr-block="'+esc(x.o.block)+'">“'+esc(x.o.sentence.length>220?x.o.sentence.slice(0,220)+'…':x.o.sentence)+'”</span>':''):'<b>not found in the rebuilt text</b> (a symbol may live only in equations; a phrase not found is a name the paper does not use)')+'</li>'; }).join('')+'</ul></details>'; }
function nameVariant(a,b){ function st(x){ return x.toLowerCase().split(/[\s\-_()]+/).filter(Boolean).map(function(w){ return w.slice(0,4); }); } var A=st(a), B=st(b); var sh=A.length<=B.length?A:B, lg=A.length<=B.length?B:A; return sh.every(function(w){ return lg.indexOf(w)>=0; }); }
function mapEvidence(M, b, k){ var w=((b.alias_used||{})[k]||'').trim(); var doc=M.P.docs&&M.P.docs.blog; if(!doc) return {cat:'unchecked', w:w, occ:[], names:[]};
  var q=M.QI[k]||{}; var names=[]; [w].concat(q.aliases||[]).forEach(function(a){ a=String(a||'').trim(); if(a&&names.indexOf(a)<0) names.push(a); });
  var found=[]; names.forEach(function(a){ var occ=findInDoc(doc,a); if(occ.length) found.push({name:a, occ:occ}); });
  if(!found.length) return {cat:'inferred', w:w, occ:[], names:[]};
  var ex=null; for(var i=0;i<found.length&&!ex;i++) for(var j=i+1;j<found.length&&!ex;j++){ if(nameVariant(found[i].name,found[j].name)) continue; found[i].occ.forEach(function(o){ if(ex) return; found[j].occ.forEach(function(o2){ if(!ex&&o.block===o2.block&&o.sentence===o2.sentence&&(o2.start>=o.end||o2.end<=o.start)) ex={o:o, a:found[i].name, b:found[j].name}; }); }); }
  var all=[]; found.forEach(function(f){ f.occ.forEach(function(o){ all.push(o); }); }); var fn=found.map(function(f){ return f.name; });
  return ex?{cat:'explicit', w:ex.a, other:ex.b, o:ex.o, occ:all, names:fn}:{cat:'same', w:fn[0], occ:all, names:fn}; }

// ---------- shared: rendered detail for a metric pair ----------
function pairHTML(M, PL, a, b){
  var k=key(a,b), rels=(PL[k]?PL[k].eq:[]), prs=(PL[k]?PL[k].pr:[]);
  var s='<h4>'+M.tex(a)+' &nbsp;↔&nbsp; '+M.tex(b)+' <span class="tag">'+STATNAME[M.status(k,PL)]+'</span>'+(M.kind(k,PL)?' <span class="tag kind-'+M.kind(k,PL)+'">'+KINDNAME[M.kind(k,PL)]+'</span>':'')+'</h4>';
  s+='<p class="muted">'+esc(M.witness(k,PL)||'no witness')+'</p>';
  if(rels.length){ s+='<p><b>Equations</b> (click a number to jump to it in the paper)'+(M.eqHow(k)?' — '+esc(M.eqHow(k)):'')+'</p>'; rels.forEach(function(ri){ var r=M.REL[ri]; s+='<div class="rel"><span class="eqref">'+r.nums.map(function(n){ return '<span class="occ" data-eq="'+n+'">('+n+')</span>'; }).join(' ')+' · '+esc(r.id)+'</span><div style="font-weight:600;margin:.15rem 0">'+r.title+'</div>'+r.html+(r.cond?'<p class="muted">holds under: '+esc(r.cond)+' — established by “'+esc(r.cond_quote)+'” ('+esc(r.cond_where)+')</p>':'')+'</div>'; }); }
  if(prs.length){ s+='<p><b>Sentences</b> (click to jump)</p><ul>'; prs.forEach(function(pi){ var l=M.PR[pi]; s+='<li><span class="occ" data-pr="'+esc(l.id)+'">'+esc(l.id)+' §'+esc(l.section)+'</span> <span class="tag">'+esc(l.scope)+'</span>'+(pol(l)==='negated'?' <span class="tag">states independence (not a link)</span>':'')+' <span class="q">“'+esc(l.quote)+'”</span> <span class="muted">['+esc(l.connective)+']</span>'+(l.condition?'<br><span class="muted">condition: '+esc(l.condition)+' — established by “'+esc(l.condition_quote)+'” ('+esc(l.condition_where)+')</span>':'')+'</li>'; }); s+='</ul>'; }
  var dvs=(PL[k]?PL[k].dv:[])||[]; if(dvs.length){ s+='<p><b>Conditions another interdependence</b> (one of these two metrics is named in a condition on a link of the other)</p><ul>'+dvs.map(function(d){ if(d.src==='pr'){ var l=M.PR[d.i]; return '<li><span class="occ" data-pr="'+esc(l.id)+'">'+esc(l.id)+' §'+esc(l.section)+'</span> the '+esc(M.lbl(l.a)+'–'+M.lbl(l.b))+' link holds under a condition naming this metric — condition: '+esc(l.condition)+' (“'+esc(l.condition_quote)+'”)</li>'; } var r=M.REL[d.i]; return '<li>'+esc(r.id)+' holds under a condition naming this metric: '+esc(r.cond)+' ('+esc(r.cond_where)+')</li>'; }).join('')+'</ul>'; }
  if(!rels.length&&!prs.length&&!dvs.length) s+='<p>The paper does not state this dependence.</p>';
  if(M.IMP[k]) s+='<p><b>Blog edges implying this pair:</b> '+M.IMP[k].map(function(i){ var e=M.E[i]; return esc(M.BI[e.source].label+' → '+M.BI[e.target].label)+(pol(e)==='negated'?' <span class="tag">states independence (not a link)</span>':'')+' (“'+esc(e.quote)+'”)'+(e.condition?' — condition: '+esc(e.condition)+' (“'+esc(e.condition_quote)+'”)':''); }).join('; ')+'</p>';
  return s;
}
function leadsOf(M, ri, vars){ var L=(M.A.paper.leads||{})[M.REL[ri].id]||[]; return L.filter(function(x){ return vars.indexOf(x['var'])>=0; }); }
function leadHits(M, hits, ri, vars){ leadsOf(M,ri,vars).forEach(function(x){ if(x.block) addHit(hits, x.block, {cls:'eq', start:x.start, end:x.end, title:'names '+M.lbl(x['var'])+' for ('+x.eq+')'}); }); }
function pairFocus(M, PL, viewer, a, b){ var k=key(a,b), hits={};
  (PL[k]?PL[k].eq:[]).forEach(function(ri){ M.REL[ri].nums.forEach(function(n){ eqHit(M,hits,n,'('+n+') '+M.REL[ri].id+' — shared by '+M.lbl(a)+' and '+M.lbl(b),true); }); leadHits(M,hits,ri,[a,b]); });
  (PL[k]?PL[k].pr:[]).forEach(function(pi){ prHit(M,hits,M.PR[pi],true); });
  // a link to a setting (an ordinary link) has its source in the conditioned statement and its condition quote; highlight both
  ((PL[k]?PL[k].dv:[])||[]).forEach(function(d){ var c; if(d.src==='pr'){ var l=M.PR[d.i]; prHit(M,hits,l,true); c=M.A.paper.quotes['cond:'+l.id]; if(c) addHit(hits,c.block,{cls:'pr',start:c.start,end:c.end,title:'condition on '+l.id+': '+(l.condition||''),foc:true}); }
    else { var r=M.REL[d.i]; r.nums.forEach(function(n){ eqHit(M,hits,n,'('+n+') '+r.id+' — stated under: '+(r.cond||''),true); }); c=M.A.paper.quotes['cond:'+r.id]; if(c) addHit(hits,c.block,{cls:'pr',start:c.start,end:c.end,title:'condition on '+r.id+': '+(r.cond||''),foc:true}); } });
  viewer.focus(hits, namesOfQ(M,[a,b])); }
function wireOcc(M, node, viewer){ node.addEventListener('click',function(e){ var o=e.target.closest('.occ'); if(!o) return; if(o.dataset.eq){ viewer.goTo(M.A.paper.eq[o.dataset.eq]); } else if(o.dataset.pr){ var a=M.A.paper.quotes[o.dataset.pr]; if(a) viewer.goTo(a.block); } else if(o.dataset.prBlock){ viewer.goTo(o.dataset.prBlock); } else if(o.dataset.bq){ var bq=M.A.blog.quotes[o.dataset.bq]; if(bq) viewer.goTo(bq.block); } }); }

// ======================================================================
// PAPER TAB
// ======================================================================
// a side is missing when an upload left it blank (P.iframe) or a bundle was made from one side only (P.sides)
function hasSide(P,s){ if(P.iframe) return !!P.iframe[s]; return !P.sides||P.sides.indexOf(s)>=0; }
function buildPaperTab(M, ctx){
  var P=M.P, root=h('div');
  if(!hasSide(P,'paper')){ root.appendChild(h('div','msg','<b>No paper given.</b> Only the blog was provided, so only its metrics and interdependencies are shown, and the map is withheld.')); return {root:root, refresh:function(){}, showTab:function(){}}; }
  var viewer=P.iframe?DocViewer(null,{iframe:P.iframe.paper,title:'paper'}):DocViewer(P.docs.paper,{eqIndex:M.A.paper.eq});
  if(P.status!=='coded'){ root.appendChild(h('div','msg','<b>Not yet coded.</b> The paper is rebuilt below so it can be read, but no metrics, equations or sentences have been coded for it under the rules at the bottom. The Trotter pair shows what a coded pair looks like.'));
    var split0=h('div','split'); split0.appendChild(h('div','vcol')).appendChild(viewer.root); split0.appendChild(h('div','scol','<div class="qdetail"><h4>Named metrics</h4><p class="muted">none coded</p></div>')); root.appendChild(split0); return {root:root, refresh:function(){}}; }
  var split=h('div','split'), vcol=h('div','vcol'), scol=h('div','scol');
  vcol.appendChild(srcHead(P.paper,'Paper')); vcol.appendChild(viewer.root); split.appendChild(vcol); split.appendChild(scol);
  var list=h('table','qlist');
  var stabs=h('div','stabs'); stabs.setAttribute('role','tablist'); stabs.innerHTML='<button type="button" role="tab" data-st="metrics" aria-selected="true">Metrics</button><button type="button" role="tab" data-st="matrix" aria-selected="false">Interdependencies</button>'; scol.appendChild(stabs);
  var mpanel=h('div','panel metrics'), mguide=h('div','guide'); mpanel.appendChild(mguide); mguide.appendChild(h('p','muted small','Click a metric to see its sources in the paper, whether an equation (e.g. <mark class="m-eq">F = ma</mark>) or prose (e.g. “<mark class="m-pr">force</mark> is dependent on…”); a sentence that only names it is shaded grey (e.g. “<mark class="m-nm">force</mark> was measured”). Click the metric again to fold it.')); var dl=ctx.makeDial&&ctx.makeDial('paper'); if(dl) mguide.appendChild(dl); var mwrap=h('div','listwrap'); mwrap.appendChild(list); mpanel.appendChild(mwrap); scol.appendChild(mpanel);
  var xpanel=h('div','panel matrix hidden'); xpanel.innerHTML='<div class="guide"><p class="muted small">Click a cell to see where the paper links those two metrics. Click a metric’s name to see all its links. Interactions shown are a function of the metric boundary established on the Metrics tab.</p><div class="mxscale small"><span>no sources</span><span class="bar" aria-hidden="true"></span><span>many sources</span><span class="nrsw" aria-hidden="true"></span><span>hatched = not supported in the blog</span></div></div><div class="mxwrap"><table class="mx" aria-label="Interdependence table"></table></div>'; scol.appendChild(xpanel); root.appendChild(split);
  stabs.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; var t=b.dataset.st; Array.prototype.forEach.call(stabs.querySelectorAll('button'),function(x){ x.setAttribute('aria-selected',x.dataset.st===t?'true':'false'); }); mpanel.classList.toggle('hidden',t!=='metrics'); xpanel.classList.toggle('hidden',t!=='matrix'); });
  syncPane(vcol,scol,viewer); var detailHTML='';
  var mx=xpanel.querySelector('table.mx');
  var PL={}, sel=null, selPair=null;
  function occ(k){ var eqs=L.eq?M.REL.map(function(r,i){return i;}).filter(function(i){ return M.REL[i].vars.indexOf(k)>=0; }):[]; var prs=M.PR.map(function(l,i){return i;}).filter(function(i){ var l=M.PR[i]; return proseOn(l)&&(l.a===k||l.b===k); });
    // a setting's sources are the statements made under it; count and list them too
    var ceq=L.eq?M.REL.map(function(r,i){return i;}).filter(function(i){ return (M.REL[i].cond_vars||[]).indexOf(k)>=0; }):[]; var cpr=M.PR.map(function(l,i){return i;}).filter(function(i){ var l=M.PR[i]; return proseOn(l)&&(l.condition_vars||[]).indexOf(k)>=0; }); return {eq:eqs, pr:prs, ceq:ceq, cpr:cpr}; }
  // a metric exists on its own; the list says where the paper names it, and links are a separate count. No row is greyed for having no link.
  var NAMECNT={}; function nameCount(k){ if(NAMECNT[k]===undefined){ var ev=aliasEvidence(M,M.QI[k]); NAMECNT[k]=ev.reduce(function(a,x){ return a+x.n; },0); } return NAMECNT[k]; }
  function renderList(){ var s='<thead><tr><th rowspan="2">Metric</th><th rowspan="2">Paper’s names</th><th rowspan="2">Named in (sentences)</th><th colspan="2" class="grp">Links it is an end of</th></tr><tr><th>equation</th><th>prose</th></tr></thead><tbody>';
    M.QORDER.forEach(function(k){ var q=M.QI[k], o=occ(k); s+='<tr class="clk'+(sel===k?' sel':'')+'" data-k="'+esc(k)+'"><td>'+M.tex(k)+(q.lumped?' <span class="tag lump" title="'+esc(q.lumped.join(', '))+'">⊕ '+q.lumped.length+'</span>':'')+'</td><td class="al">'+esc(q.aliases.join(' · '))+'</td><td class="num">'+nameCount(k)+'</td><td class="num">'+(o.eq.length+o.ceq.length)+'</td><td class="num">'+(o.pr.length+o.cpr.length)+'</td></tr>';
      if(sel===k) s+='<tr class="exp"><td colspan="5"><div class="qdetail inline">'+detailHTML+'</div></td></tr>'; });
    keepRow(list, sel?'tr.clk[data-k="'+sel+'"]':null, function(){ list.innerHTML=s+'</tbody>'; ts(list); }); }
  function clearSel(){ sel=null; selPair=null; detailHTML=''; viewer.clear(); renderList(); Array.prototype.forEach.call(mx.querySelectorAll('td.sel'),function(td){ td.classList.remove('sel'); }); }
  viewer.onClear=clearSel;
  function qHits(k){ var o=occ(k), hits={}; o.eq.forEach(function(ri){ M.REL[ri].nums.forEach(function(n){ eqHit(M,hits,n,'('+n+') '+M.REL[ri].id); }); leadHits(M,hits,ri,[k]); }); o.pr.forEach(function(pi){ prHit(M,hits,M.PR[pi]); }); (o.cpr||[]).forEach(function(pi){ prHit(M,hits,M.PR[pi]); }); (o.ceq||[]).forEach(function(ri){ M.REL[ri].nums.forEach(function(n){ eqHit(M,hits,n,'('+n+') '+M.REL[ri].id); }); }); return hits; }
  function showQ(k){ sel=k; selPair=null; var q=M.QI[k], o=occ(k); if(ctx.nav) ctx.nav('paper',k);
    var hits=qHits(k); var doc=M.P.docs&&M.P.docs.paper; (q.aliases||[]).forEach(function(a){ (doc?findInDoc(doc,a):[]).forEach(function(oc){ addHit(hits, oc.block, {cls:'nm', start:oc.sstart, end:oc.send, title:'names it: “'+a+'”'}); }); });
    // a name the text search cannot find (a single letter, a subscripted symbol, a name only in a figure
    // caption) falls back to the coder's quoted sentence for it, so every metric shows at least one marked passage
    if(doc&&!Object.keys(hits).some(function(b){ return hits[b].some(function(x){ return x.cls==='nm'; }); })) Object.keys(q.alias_quotes||{}).forEach(function(a){ var qt=String(q.alias_quotes[a]).replace(/\s+/g,' ').trim().toLowerCase().split(/[_^$\\{}]/).sort(function(x,y){ return y.length-x.length; })[0].trim().slice(0,50); if(qt.length<12) return;   /* the longest run free of TeX marks, so T_1 in a quote still finds T<sub>1</sub> */
      doc.blocks.forEach(function(b){ if(!b.html) return; var mk=maskHtml(b.html), low=mk.replace(/\s/g,' ').toLowerCase(), i=low.replace(/ +/g,' ')===low?low.indexOf(qt):-1; if(i<0){ var squash=low.replace(/\s+/g,' '); var j=squash.indexOf(qt); if(j<0) return; i=j; } var sb=sentBounds(mk,i,i+qt.length); addHit(hits,b.id,{cls:'nm',start:sb[0],end:sb[1],title:'names it: “'+a+'” (the coder’s quote)'}); }); }); viewer.focus(hits, namesOfQ(M,[k]));
    var partners={}; Object.keys(PL).forEach(function(x){ var ab=x.split('|'); if(ab.indexOf(k)<0) return; var c=ab[0]===k?ab[1]:ab[0]; partners[c]={eq:PL[x].eq.length, pr:PL[x].pr.length, st:M.status(x,PL)}; });
    var impl=Object.keys(M.IMP).filter(function(x){ return x.split('|').indexOf(k)>=0&&!PL[x]; }).map(function(x){ var ab=x.split('|'); return ab[0]===k?ab[1]:ab[0]; });
    var s='<p>'+esc(q.label)+'. Named in: '+esc(q.named_in)+'.</p>'+aliasHTML(M,q);
    s+='<p><b>Named in</b> '+nameCount(k)+' sentence'+(nameCount(k)===1?'':'s')+' of the paper (highlighted on the left). <b>An end of</b> '+o.eq.length+' numbered equation'+(o.eq.length===1?'':'s')+' and '+o.pr.length+' coded sentence'+(o.pr.length===1?'':'s')+((o.cpr.length||o.ceq.length)?'; <b>is the setting for</b> '+o.cpr.length+' coded sentence'+(o.cpr.length===1?'':'s')+' and '+o.ceq.length+' equation'+(o.ceq.length===1?'':'s')+' (results the paper states under it)':'')+'. The paper on the left is collapsed to those passages; click one below to jump to it.</p>';
    if(o.cpr.length) s+='<details'+(o.cpr.length<=8?' open':'')+'><summary>'+o.cpr.length+' sentence'+(o.cpr.length===1?'':'s')+' stated under it</summary><ul>'+o.cpr.map(function(pi){ var l=M.PR[pi]; var located=!!M.A.paper.quotes[l.id]; return '<li>'+(located?'<span class="occ" data-pr="'+esc(l.id)+'">':'<span>')+esc(l.id)+' §'+esc(l.section)+'</span> '+esc(M.lbl(l.a))+'–'+esc(M.lbl(l.b))+' <span class="muted">under: '+esc(l.condition||'')+'</span>'+(l.condition_quote?' <span class="q">“'+esc(l.condition_quote)+'”</span>':'')+'</li>'; }).join('')+'</ul></details>';
    if(o.ceq.length) s+='<details open><summary>'+o.ceq.length+' equation'+(o.ceq.length===1?'':'s')+' stated under it</summary><ul>'+o.ceq.map(function(ri){ var r=M.REL[ri]; return '<li>'+r.nums.map(function(n){ return '<span class="occ" data-eq="'+n+'">('+n+')</span>'; }).join(' ')+' <span class="muted">'+r.title+' — under: '+esc(r.cond||'')+'</span></li>'; }).join('')+'</ul></details>';
    if(o.eq.length) s+='<details open><summary>'+o.eq.length+' equation'+(o.eq.length===1?'':'s')+'</summary><ul>'+o.eq.map(function(ri){ var r=M.REL[ri]; var L=leadsOf(M,ri,[k]); return '<li>'+r.nums.map(function(n){ return '<span class="occ" data-eq="'+n+'">('+n+')</span>'; }).join(' ')+' <span class="muted">'+r.title+'</span>'+(L.length?'<br><span class="small">named by: '+L.map(function(x){ return '('+x.eq+') '+(x.block?'<span class="occ q" data-pr-block="'+esc(x.block)+'">“'+esc(x.quote)+'”</span>':'<span class="q">“'+esc(x.quote)+'”</span>')+(x.note?' <span class="muted">— '+esc(x.note)+'</span>':''); }).join('; ')+'</span>':'')+'</li>'; }).join('')+'</ul></details>';
    if(o.pr.length) s+='<details'+(o.pr.length<=8?' open':'')+'><summary>'+o.pr.length+' sentence'+(o.pr.length===1?'':'s')+'</summary><ul>'+o.pr.map(function(pi){ var l=M.PR[pi]; var located=!!M.A.paper.quotes[l.id]; return '<li>'+(located?'<span class="occ" data-pr="'+esc(l.id)+'">':'<span>')+esc(l.id)+' §'+esc(l.section)+'</span> <span class="tag">'+esc(l.scope)+'</span> <span class="q">“'+esc(l.quote)+'”</span>'+(located?'':' <span class="muted">(not located in the rebuilt text)</span>')+'</li>'; }).join('')+'</ul></details>';
    detailHTML=s; renderList(); }
  function showPair(a,b){ selPair=[a,b]; pairFocus(M,PL,viewer,a,b); detailHTML='<p><button type="button" class="lnk" data-back="'+esc(a)+'">← back to '+esc(M.lbl(a))+'</button></p>'+pairHTML(M,PL,a,b); renderList();
    Array.prototype.forEach.call(mx.querySelectorAll('td.sel'),function(td){ td.classList.remove('sel'); }); Array.prototype.forEach.call(mx.querySelectorAll('td[data-a="'+a+'"][data-b="'+b+'"],td[data-a="'+b+'"][data-b="'+a+'"]'),function(td){ td.classList.add('sel'); }); }
  list.addEventListener('click',function(e){ var bk=e.target.closest('[data-back]'); if(bk){ showQ(bk.dataset.back); return; }
    var pr=e.target.closest('[data-pair]'); if(pr&&sel){ var on=pr.classList.contains('sel'); Array.prototype.forEach.call(list.querySelectorAll('[data-pair].sel'),function(x){ x.classList.remove('sel'); });
      if(on){ viewer.focus(qHits(sel), namesOfQ(M,[sel])); } else { pr.classList.add('sel'); if(PL[key(sel,pr.dataset.pair)]) pairFocus(M,PL,viewer,sel,pr.dataset.pair); } return; }
    if(e.target.closest('.occ')) return;
    var tr=e.target.closest('tr.clk'); if(!tr) return; if(tr.dataset.k===sel){ var k0=tr.dataset.k; keepRow(list,'tr.clk[data-k="'+k0+'"]',clearSel); } else showQ(tr.dataset.k); });
  wireOcc(M, list, viewer);
  function cnt(x){ return x?x.eq.length+x.pr.length+((x.dv||[]).length):0; }
  function renderMatrix(){ var V=M.QORDER; var mx0=0; Object.keys(PL).forEach(function(k){ mx0=Math.max(mx0,cnt(PL[k])); });
    var s='<thead><tr><th></th>'+V.map(function(k){ return '<th scope="col" class="mh" data-h="'+esc(k)+'" title="'+esc((M.QI[k]||{}).fullLabel||M.lbl(k))+'"><span>'+texOrClip(M,k)+'</span></th>'; }).join('')+'</tr></thead><tbody>';
    // settings' links are ordinary links (no separate scope marking); hatched = the blog does not support the link
    V.forEach(function(a){ s+='<tr><th scope="row" class="mh" data-h="'+esc(a)+'" title="'+esc((M.QI[a]||{}).fullLabel||M.lbl(a))+'"><span>'+texOrClip(M,a)+'</span></th>'+V.map(function(b){ if(a===b) return '<td class="diag"></td>'; var x=PL[key(a,b)]; if(!x) return '<td></td>'; var n=cnt(x), lv=n<=1?1:(n<=3?2:(n<mx0/2?3:4)); var nr=M.status(key(a,b),PL)!=='rep'; return '<td class="has l'+lv+(nr?' nr':'')+'" tabindex="0" role="button" data-a="'+a+'" data-b="'+b+'" title="'+esc(M.lbl(a)+' ↔ '+M.lbl(b)+': '+n+' source'+(n===1?'':'s')+(nr?' · not supported in the blog':' · supported in the blog'))+'" aria-label="'+n+' sources'+(nr?', not supported in the blog':'')+'"></td>'; }).join('')+'</tr>'; });
    mx.innerHTML=s+'</tbody>'; ts(mx); }
  function hlMetric(k){ Array.prototype.forEach.call(mx.querySelectorAll('td.sel,td.hl,th.selh'),function(x){ x.classList.remove('sel','hl','selh'); });
    Array.prototype.forEach.call(mx.querySelectorAll('td[data-a="'+k+'"],td[data-b="'+k+'"]'),function(x){ x.classList.add('hl'); }); Array.prototype.forEach.call(mx.querySelectorAll('th[data-h="'+k+'"]'),function(x){ x.classList.add('selh'); });
    viewer.focus(qHits(k), namesOfQ(M,[k])); }
  function showMatrix(){ var bt=stabs.querySelector('button[data-st="matrix"]'); if(bt) bt.click(); }
  mx.addEventListener('mousedown',function(e){ if(e.target.closest('td.has,th.mh')) e.preventDefault(); });
  mx.addEventListener('click',function(e){ var th=e.target.closest('th.mh'); if(th){ hlMetric(th.dataset.h); return; } var td=e.target.closest('td.has'); if(!td) return; var a=td.dataset.a, b=td.dataset.b; pairFocus(M,PL,viewer,a,b); Array.prototype.forEach.call(mx.querySelectorAll('td.hl,th.selh'),function(x){ x.classList.remove('hl','selh'); }); 
    Array.prototype.forEach.call(mx.querySelectorAll('td.sel'),function(x){ x.classList.remove('sel'); }); Array.prototype.forEach.call(mx.querySelectorAll('td[data-a="'+a+'"][data-b="'+b+'"],td[data-a="'+b+'"][data-b="'+a+'"]'),function(x){ x.classList.add('sel'); }); });
  function refresh(){ PL=M.paperLayer(); renderList(); renderMatrix(); if(selPair) showPair(selPair[0],selPair[1]); else if(sel) showQ(sel); }
  refresh();
  return {root:root, refresh:refresh, selectQ:function(k,o){ showQ(k); if(o&&o.scroll) listToTop(list); },
    matrixMetric:function(k){ showMatrix(); hlMetric(k); var th=mx.querySelector('th[data-h="'+k+'"]'); if(th) th.scrollIntoView({block:'nearest',inline:'nearest'}); },
    matrixPair:function(a,b){ showMatrix(); var td=mx.querySelector('td[data-a="'+a+'"][data-b="'+b+'"]'); if(td){ td.click(); td.scrollIntoView({block:'nearest',inline:'nearest'}); } }};
}

// ======================================================================
// BLOG TAB
// ======================================================================
function buildBlogTab(M, ctx){
  var P=M.P, root=h('div');
  if(!hasSide(P,'blog')){ root.appendChild(h('div','msg','<b>No blog given.</b> Only the paper was provided, so only its metrics and interdependencies are shown, and the map is withheld.')); return {root:root, refresh:function(){}, showTab:function(){}}; }
  var viewer=P.iframe?DocViewer(null,{iframe:P.iframe.blog,title:'blog'}):DocViewer(P.docs.blog,{});
  if(P.status!=='coded'){ root.appendChild(h('div','msg','<b>Not yet coded.</b> The blog text is rebuilt below so it can be read; no metrics or links have been coded for it.'));
    var split0=h('div','split'); split0.appendChild(h('div','vcol')).appendChild(viewer.root); split0.appendChild(h('div','scol','<div class="qdetail"><h4>Blog metrics</h4><p class="muted">none coded</p></div>')); root.appendChild(split0); return {root:root, refresh:function(){}}; }
  var split=h('div','split'), vcol=h('div','vcol'), scol=h('div','scol');
  vcol.appendChild(srcHead(P.blog,'Blog')); vcol.appendChild(viewer.root); split.appendChild(vcol); split.appendChild(scol);
  var list=h('table','qlist');
  var stabs=h('div','stabs'); stabs.setAttribute('role','tablist'); stabs.innerHTML='<button type="button" role="tab" data-st="metrics" aria-selected="true">Metrics</button><button type="button" role="tab" data-st="matrix" aria-selected="false">Interdependencies</button>'; scol.appendChild(stabs);
  var mpanel=h('div','panel metrics'), mguide=h('div','guide'); mpanel.appendChild(mguide); mguide.appendChild(h('p','muted small','Click a metric to see the sentences where the blog names it (e.g. “<mark class="m-pr">30 physical qubits</mark>”). Click the metric again to fold it.')); var dl=ctx.makeDial&&ctx.makeDial('blog'); if(dl) mguide.appendChild(dl); var mwrap=h('div','listwrap'); mwrap.appendChild(list); mpanel.appendChild(mwrap); scol.appendChild(mpanel);
  var xpanel=h('div','panel matrix hidden'); xpanel.innerHTML='<div class="guide"><p class="muted small">Click a cell to see the blog sentence that links those two metrics. Click a metric’s name to see all its links. The shade shows how much of the link the paper supports.</p><div class="mxscale bx small"><span>none supported</span><span class="bar" aria-hidden="true"></span><span>all supported</span><span class="nrsw" aria-hidden="true"></span><span>hatched = not supported in the paper</span></div></div><div class="mxwrap"><table class="mx bx" aria-label="Blog interdependence table"></table></div>'; scol.appendChild(xpanel); root.appendChild(split);
  stabs.addEventListener('click',function(e){ var bt=e.target.closest('button'); if(!bt) return; var t=bt.dataset.st; Array.prototype.forEach.call(stabs.querySelectorAll('button'),function(x){ x.setAttribute('aria-selected',x.dataset.st===t?'true':'false'); }); mpanel.classList.toggle('hidden',t!=='metrics'); xpanel.classList.toggle('hidden',t!=='matrix'); });
  syncPane(vcol,scol,viewer);
  var detailHTML='';
  var mx=xpanel.querySelector('table.mx'); var PL={}, sel=null;
  var EV={}; function ev(b,k){ var id=b.id+'|'+k; if(!EV[id]) EV[id]=mapEvidence(M,b,k); return EV[id]; }
  // the blog list has the paper list's columns (names, sentences naming it, links it is an end of); the other side is left to the map
  var BDOC=M.P.docs&&M.P.docs.blog, BBLK={}; (BDOC?BDOC.blocks:[]).forEach(function(x){ BBLK[x.id]=x; });
  function bNames(b){ var seen={}, out=[]; (b.mentions||[]).forEach(function(m){ var w=(m.matched||'').trim(); if(w&&!/\d/.test(w)&&w.split(/\s+/).length<=4&&!seen[w.toLowerCase()]){ seen[w.toLowerCase()]=1; out.push(w); } }); Object.keys(b.alias_used||{}).forEach(function(k){ var w=(b.alias_used[k]||'').trim(); if(w&&!seen[w.toLowerCase()]){ seen[w.toLowerCase()]=1; out.push(w); } }); return out.length?out:[b.label]; }
  var BNC={}; function bNameCount(b){ if(BNC[b.id]!==undefined) return BNC[b.id]; var set={}; var n=(b.mentions||[1]).length; for(var i=0;i<n;i++){ var an=M.A.blog.quotes[i?b.id+'~'+i:b.id]; if(an&&BBLK[an.block]){ var mk=maskHtml(BBLK[an.block].html), sb=sentBounds(mk,an.start,an.end); set[an.block+'|'+mk.slice(sb[0],sb[1]).replace(/\s+/g,' ').trim()]=1; } }
    bNames(b).forEach(function(w){ if(looseRe(w)&&BDOC) findInDoc(BDOC,w).forEach(function(o){ set[o.block+'|'+o.sentence]=1; }); }); return (BNC[b.id]=Object.keys(set).length); }
  function bLinks(id){ var end=0, cond=0; M.E.forEach(function(e){ if(e.source===id||e.target===id) end++; else if((e.condition_vars||[]).indexOf(id)>=0) cond++; }); return {end:end, cond:cond}; }
  function renderList(){ var s='<thead><tr><th rowspan="2">Metric</th><th rowspan="2">Blog’s names</th><th rowspan="2">Named in (sentences)</th><th colspan="1" class="grp">Links it is an end of</th></tr><tr><th>prose</th></tr></thead><tbody>';
    M.B.forEach(function(b){ var lk=bLinks(b.id); s+='<tr class="clk'+(sel===b.id?' sel':'')+'" data-b="'+esc(b.id)+'"><td>'+esc(b.label)+(b.lumped?' <span class="tag lump" title="'+esc(b.lumped.join(', '))+'">⊕ '+b.lumped.length+'</span>':'')+'</td><td class="al">'+esc(bNames(b).join(' · '))+'</td><td class="num">'+bNameCount(b)+'</td><td class="num">'+(lk.end+lk.cond)+'</td></tr>';
      if(sel===b.id) s+='<tr class="exp"><td colspan="4"><div class="qdetail inline">'+detailHTML+'</div></td></tr>'; });
    keepRow(list, sel?'tr.clk[data-b="'+sel+'"]':null, function(){ list.innerHTML=s+'</tbody>'; ts(list); }); }
  function clearSel(){ sel=null; detailHTML=''; viewer.clear(); renderList(); Array.prototype.forEach.call(mx.querySelectorAll('td.sel'),function(x){ x.classList.remove('sel'); }); }
  viewer.onClear=clearSel;
  function renderMatrix(){ var V=M.B.map(function(b){ return b.id; }); var cell={}; M.E.forEach(function(e,i){ var k=e.source+'|'+e.target; (cell[k]=cell[k]||{es:[],pairs:0,linked:0,grey:false}); var r=M.edgeRatio(i,PL); cell[k].es.push(i); if(r.grey) cell[k].grey=true; else { cell[k].pairs+=r.pairs.length; cell[k].linked+=r.linked.length; } });
    var s='<thead><tr><th></th>'+V.map(function(id){ return '<th scope="col" class="mh" data-h="'+esc(id)+'" title="'+esc(M.BI[id].fullLabel||M.BI[id].label)+'"><span>'+esc(clip(M.BI[id].label))+'</span></th>'; }).join('')+'</tr></thead><tbody>';
    V.forEach(function(a){ s+='<tr><th scope="row" class="mh" data-h="'+esc(a)+'" title="'+esc(M.BI[a].fullLabel||M.BI[a].label)+'"><span>'+esc(clip(M.BI[a].label))+'</span></th>'+V.map(function(b){ if(a===b) return '<td class="diag"></td>'; var x=cell[a+'|'+b]; if(!x) return '<td></td>'; var n=x.es.length, lab=M.BI[a].label+' → '+M.BI[b].label+' ('+n+' sentence'+(n===1?'':'s')+'): ';
        if(x.grey&&!x.pairs) return '<td class="has l1 nr" tabindex="0" role="button" data-a="'+esc(a)+'" data-b="'+esc(b)+'" title="'+esc(lab+'not supported in the paper (an end stands for no paper metric)')+'" aria-label="not supported in the paper"></td>';
        var pct=x.pairs?x.linked/x.pairs:0, lv=x.linked===0?1:(pct<.5?2:(pct<1?3:4)); return '<td class="has l'+lv+(x.linked===0?' nr':'')+'" tabindex="0" role="button" data-a="'+esc(a)+'" data-b="'+esc(b)+'" title="'+esc(lab+'supported '+x.linked+'/'+x.pairs)+'" aria-label="supported '+x.linked+' of '+x.pairs+'"></td>'; }).join('')+'</tr>'; });
    mx.innerHTML=s+'</tbody>'; }
  function showB(id){ sel=id; var b=M.BI[id]; var hits={}; if(ctx.nav) ctx.nav('blog',id); blogHitAll(M,hits,b,'mn',b.label,true); (b.preimage||[]).forEach(function(k){ ev(b,k).occ.forEach(function(o){ addHit(hits,o.block,{cls:'mn',start:o.start,end:o.end,title:'one of the paper’s names for '+M.lbl(k)}); }); }); viewer.focus(hits, namesOfB(M,[id]));
    var pre=b.preimage||[]; var mts=b.mentions||[{quote:b.quote,source:b['class']}]; var s='<p><b>'+mts.length+' mention'+(mts.length===1?'':'s')+'</b>'+'</p><ul class="mentions">'+mts.map(function(mm,i){ var mid=i?id+'~'+i:id; return '<li><span class="tag">'+esc(mm.source||'')+'</span> '+(mm.frame?'<span class="muted">'+esc(mm.frame.split(':')[0])+' “'+esc(mm.matched||'')+'” → '+esc(mm.head||'')+'</span> ':'')+'<span class="q'+(M.A.blog.quotes[mid]?' occ':'')+'" data-bq="'+esc(mid)+'">“'+esc(mm.quote)+'”</span>'+(M.A.blog.quotes[mid]?'':' <span class="muted">(not located)</span>')+'</li>'; }).join('')+'</ul>';
    detailHTML=s; renderList(); }
  list.addEventListener('click',function(e){ var q=e.target.closest('[data-showq]'); if(q&&ctx.showInPaper){ ctx.showInPaper(q.dataset.showq); return; } if(e.target.closest('.occ')) return;
    var tr=e.target.closest('tr.clk'); if(!tr) return; if(tr.dataset.b===sel){ var b0=tr.dataset.b; keepRow(list,'tr.clk[data-b="'+b0+'"]',clearSel); } else showB(tr.dataset.b); });
  wireOcc(M, list, viewer);
  function hlMetric(id){ Array.prototype.forEach.call(mx.querySelectorAll('td.sel,td.hl,th.selh'),function(x){ x.classList.remove('sel','hl','selh'); });
    Array.prototype.forEach.call(mx.querySelectorAll('td[data-a="'+id+'"],td[data-b="'+id+'"]'),function(x){ x.classList.add('hl'); }); Array.prototype.forEach.call(mx.querySelectorAll('th[data-h="'+id+'"]'),function(x){ x.classList.add('selh'); });
    var hits={}; M.E.forEach(function(ed,i){ if(ed.source===id||ed.target===id) blogHit(M,hits,'e'+i,'pr','link',true); }); blogHitAll(M,hits,M.BI[id],'mn',M.BI[id].label); viewer.focus(hits, namesOfB(M,[id])); }
  function showMatrix(){ var bt=stabs.querySelector('button[data-st="matrix"]'); if(bt) bt.click(); }
  mx.addEventListener('mousedown',function(e){ if(e.target.closest('td.has,th.mh')) e.preventDefault(); });
  mx.addEventListener('click',function(e){ var th=e.target.closest('th.mh'); if(th){ hlMetric(th.dataset.h); return; } var td=e.target.closest('td.has'); if(!td) return; Array.prototype.forEach.call(mx.querySelectorAll('td.hl,th.selh'),function(x){ x.classList.remove('hl','selh'); }); var on=td.classList.contains('sel'); Array.prototype.forEach.call(mx.querySelectorAll('td.sel'),function(x){ x.classList.remove('sel'); }); if(on){ viewer.clear(); return; } td.classList.add('sel');
    var a=td.dataset.a, b=td.dataset.b, hits={}; M.E.forEach(function(ed,i){ if(ed.source===a&&ed.target===b) blogHit(M,hits,'e'+i,'pr','link',true); }); blogHitAll(M,hits,M.BI[a],'mn',M.BI[a].label); blogHitAll(M,hits,M.BI[b],'mn',M.BI[b].label); viewer.focus(hits, namesOfB(M,[a,b]));
    sel=null; detailHTML=''; renderList(); });
  function refresh(){ PL=M.paperLayer(); renderList(); renderMatrix(); if(sel) showB(sel); }
  refresh();
  return {root:root, refresh:refresh, selectB:function(id,o){ if(!M.BI[id]) return; showB(id); if(o&&o.scroll) listToTop(list); },
    matrixMetric:function(id){ showMatrix(); hlMetric(id); var th=mx.querySelector('th[data-h="'+id+'"]'); if(th) th.scrollIntoView({block:'nearest',inline:'nearest'}); },
    matrixPair:function(a,b){ showMatrix(); var td=mx.querySelector('td[data-a="'+a+'"][data-b="'+b+'"]'); if(td){ td.click(); td.scrollIntoView({block:'nearest',inline:'nearest'}); } }};
}

// ======================================================================
// MAP TAB (port of the concept-to-concept map)
// ======================================================================
function buildMapTab(M, ctx){
  var P=M.P, root=h('div');
  if(!(hasSide(P,'paper')&&hasSide(P,'blog'))){ root.appendChild(h('div','msg','<b>Map withheld.</b> The map compares a paper with a blog, and only one was given.'));  return {root:root, refresh:function(){}}; }
  if(P.status!=='coded'){ root.appendChild(h('div','msg','<b>Not yet coded.</b> The map needs both sides coded.'));  return {root:root, refresh:function(){}}; }
  var mapbody=h('div'); root.appendChild(mapbody); mapbody.innerHTML='<section class="filterview" aria-label="Filter view"><div class="fv-head"><h3>Filter view</h3></div><div class="fv-grid fv-shared"></div><div class="fv-sides">'+
    '<div class="fv-side fv-side-b"><span class="fv-title">Blog view</span><div class="fv-ctl"><label class="fv-chk"><input type="checkbox" class="fv-sort-b"> sort by node centrality</label><div class="fv-cen"><label for="fvcb-'+ctx.pid+'">filter nodes by centrality <span class="info" tabindex="0" data-tip="'+NC_INFO+'" aria-label="'+NC_INFO+'">ⓘ</span></label><span class="fv-c"><span class="fv-end">all</span><input type="range" class="fv-cen-b" id="fvcb-'+ctx.pid+'" min="0" max="95" step="5"><span class="fv-end">central</span></span><span class="fv-v fv-cv-b"></span></div><div class="fv-inl"><label class="fv-chk"><input type="checkbox" class="fv-nbb"> hide blog metrics not in paper</label><span class="fv-v fv-nbbv"></span></div></div></div>'+
    '<div class="fv-side fv-side-p"><div class="fv-ctl"><label class="fv-chk"><input type="checkbox" class="fv-sort-p"> sort by node centrality</label><div class="fv-cen"><label for="fvcp-'+ctx.pid+'">filter nodes by centrality <span class="info" tabindex="0" data-tip="'+NC_INFO+'" aria-label="'+NC_INFO+'">ⓘ</span></label><span class="fv-c"><span class="fv-end">all</span><input type="range" class="fv-cen-p" id="fvcp-'+ctx.pid+'" min="0" max="95" step="5"><span class="fv-end">central</span></span><span class="fv-v fv-cv-p"></span></div><div class="fv-inl"><label class="fv-chk"><input type="checkbox" class="fv-nb"> hide paper metrics not in blog</label><span class="fv-v fv-nbv"></span></div></div><span class="fv-title">Paper view</span></div>'+
    '</div></section>'+MAPLEG+'<div class="mxwrap" style="padding:0"><svg id="sk2-svg" role="img" aria-label="Map between the blog’s metrics and the paper’s named metrics"></svg></div><nav class="tbltoc small"><b>Tables below:</b> <a data-goto="table-1">1. Metric Salience</a> · <a data-goto="table-2">2. Interdependence Salience</a></nav><div class="qdetail s2-detail"><p class="muted">Click a blog metric, a paper metric, a mapping line, or a blog edge. The detail always names the witness: which blog edge implied a pair, and which equation or sentence links it.</p></div>';
  mapbody.insertBefore(h('div','sec','<h3>Paper-Blog Skew</h3><p class="skewlead">The following tables summarize the decoupling between the network of metrics and interdependencies established in the paper versus the blog. They indicate where the blog’s metrics (<a data-goto="table-1">Table 1</a>) and interdependencies (<a data-goto="table-2">Table 2</a>) are under versus over represented relative to the paper.</p><div class="s2-summary"></div>'), mapbody.querySelector('.s2-detail').nextSibling);
  
  // a contents line under the map; each entry is a real address (#/p/<pair>/map/table-N) and scrolls in place when clicked
  Array.prototype.forEach.call(root.querySelectorAll('.tbltoc a, .skewlead a'),function(x){ x.href='#/p/'+ctx.pid+'/map/'+x.dataset.goto; x.addEventListener('click',function(e){ e.preventDefault(); var hd=root.querySelector('[data-table="'+x.dataset.goto+'"]'); if(hd){ hd.scrollIntoView({block:'start'}); history.replaceState(null,'',x.href); } }); });
  var svg=root.querySelector('#sk2-svg'), NS='http://www.w3.org/2000/svg', B=M.B, E=M.E, QORDER=M.QORDER, BI=M.BI, QI=M.QI;
  var W=1100, rowB=26, rowP=26, top=14, H=top+Math.max(B.length*rowB,QORDER.length*rowP)+20; svg.setAttribute('viewBox','0 0 '+W+' '+H);
  // Filter view. Paper metrics are kept by centrality (top pc% by PageRank on the paper link graph), and optionally only those the
  // blog names (a blog metric stands for them). Hidden nodes keep no row (the map collapses vertically) and every line touching one is hidden; the tables are not filtered.
  // a filter per side. Each side: sort its nodes by centrality (only one side at a time) and keep nodes more central than a percentile
  // (PageRank in that side's own link graph). Paper side also: hide paper metrics not in the blog. Hidden nodes give up their rows; the tables are never filtered.
  var FV=FILTER[ctx.pid]||(FILTER[ctx.pid]={cp:0,cb:0,sort:null,nb:false,nbb:false}); var PL00=M.paperLayer(), adj0={}; QORDER.forEach(function(k){ adj0[k]=[]; }); Object.keys(PL00).forEach(function(k){ if(!M.wit(k,PL00).length) return; var ab=k.split('|'); if(adj0[ab[0]]&&adj0[ab[1]]){ adj0[ab[0]].push(ab[1]); adj0[ab[1]].push(ab[0]); } });
  var adjB={}; B.forEach(function(b){ adjB[b.id]=[]; }); E.forEach(function(e){ if(pol(e)!=='positive'||!adjB[e.source]||!adjB[e.target]||e.source===e.target) return; adjB[e.source].push(e.target); adjB[e.target].push(e.source); });
  var PR0=pagerank(QORDER,adj0), PRB=pagerank(B.map(function(b){ return b.id; }),adjB), HIDP={}, HIDB={};
  function keepN(n,pct){ return Math.max(1,Math.ceil((100-pct)/100*n)); }
  var rankP=QORDER.slice().sort(function(a,b){ return PR0[b]-PR0[a]; }), rankB=B.map(function(b){ return b.id; }).sort(function(a,b){ return PRB[b]-PRB[a]; });
  rankP.forEach(function(k,i){ if(i>=keepN(QORDER.length,FV.cp)) HIDP[k]=1; }); rankB.forEach(function(id,i){ if(i>=keepN(B.length,FV.cb)) HIDB[id]=1; });
  if(FV.nb) QORDER.forEach(function(k){ if(!M.mapped[k]) HIDP[k]=1; }); if(FV.nbb) B.forEach(function(b){ if(!(b.preimage||[]).length) HIDB[b.id]=1; });
  var ordB=FV.sort==='b'?rankB:B.map(function(b){ return b.id; }), ordP=FV.sort==='p'?rankP:QORDER;
  var nVB=B.filter(function(b){ return !HIDB[b.id]; }).length, nVP=QORDER.filter(function(k){ return !HIDP[k]; }).length; H=top+Math.max(nVB*rowB,nVP*rowP,rowP)+20; svg.setAttribute('viewBox','0 0 '+W+' '+H);
  var xB=400, xP=720, posB={}, posP={}; var vi=0; ordB.forEach(function(id){ if(!HIDB[id]) vi++; posB[id]={x:xB,y:top+Math.max(vi-1,0)*rowB+rowB/2}; }); vi=0; ordP.forEach(function(k){ if(!HIDP[k]) vi++; posP[k]={x:xP,y:top+Math.max(vi-1,0)*rowP+rowP/2}; });
  var fvr=root.querySelector('.filterview'), dl=ctx.makeDial&&ctx.makeDial('map',true); if(dl) fvr.querySelector('.fv-shared').appendChild(dl);
  // the side filters sit at the top of the map, each lined up with its own column (blog controls end at the blog nodes, paper controls start at the paper nodes)
  var sides=fvr.querySelector('.fv-sides'); sides.classList.add('onmap'); var mbar=document.createElement('div'); mbar.className='fv-mb'; var shared=fvr.querySelector('.fv-shared'); if(shared){ mbar.appendChild(shared); } svg.parentNode.insertBefore(mbar,svg); fvr.style.display='none';   /* the metric boundary sits between the view panels and the map, centred; the Filter view box is left empty */ var lg=root.querySelector('.unileg'); if(lg){ lg.classList.add('inmap'); sides.insertBefore(lg,sides.querySelector('.fv-side-p')); }   /* the legend sits between the two view panels */ svg.parentNode.insertBefore(mbar,svg); svg.parentNode.insertBefore(sides,svg);   /* metric boundary on top, then the view panels, then the map */
  function alignSides(){ var sw=svg.getBoundingClientRect().width; if(!sw) return; var sc=sw/W, kids=sides.querySelectorAll('.fv-side'); /* both panels left-aligned: the blog panel and the legend take their natural width, the paper panel the rest */ kids[0].style.width=''; if(lg) lg.style.width=''; kids[1].style.marginLeft=''; }
  if(window.ResizeObserver) new ResizeObserver(alignSides).observe(svg); window.addEventListener('resize',alignSides); setTimeout(alignSides,0); setTimeout(alignSides,400);
  var cI={b:root.querySelector('.fv-cen-b'), p:root.querySelector('.fv-cen-p')}, sI={b:root.querySelector('.fv-sort-b'), p:root.querySelector('.fv-sort-p')}, nbI=root.querySelector('.fv-nb'), nbbI=root.querySelector('.fv-nbb');
  cI.b.value=FV.cb; cI.p.value=FV.cp; sI.b.checked=FV.sort==='b'; sI.p.checked=FV.sort==='p'; nbI.checked=!!FV.nb; nbbI.checked=!!FV.nbb;
  function fvTxt(){ root.querySelector('.fv-cv-b').textContent=(+cI.b.value?'>'+cI.b.value+'th %ile · ':'all · ')+keepN(B.length,+cI.b.value)+'/'+B.length;
    root.querySelector('.fv-cv-p').textContent=(+cI.p.value?'>'+cI.p.value+'th %ile · ':'all · ')+keepN(QORDER.length,+cI.p.value)+'/'+QORDER.length;
    root.querySelector('.fv-nbv').textContent=QORDER.filter(function(k){ return !M.mapped[k]; }).length+'/'+QORDER.length; root.querySelector('.fv-nbbv').textContent=B.filter(function(b){ return !(b.preimage||[]).length; }).length+'/'+B.length; }
  fvTxt(); cI.b.addEventListener('input',fvTxt); cI.p.addEventListener('input',fvTxt);
  function fvApply(){ FV.cb=+cI.b.value; FV.cp=+cI.p.value; FV.nb=nbI.checked; FV.nbb=nbbI.checked; ctx.rebuild('map'); } cI.b.addEventListener('change',fvApply); cI.p.addEventListener('change',fvApply); nbI.addEventListener('change',fvApply); nbbI.addEventListener('change',fvApply);
  ['b','p'].forEach(function(w){ sI[w].addEventListener('change',function(){ FV.sort=sI[w].checked?w:null; ctx.rebuild('map'); }); });   // one side sorted at a time
  /* no summary note under the filters */
  // label widths (canvas measure, same font stack as the SVG) so arcs start past the words, not under them
  var cv=document.createElement('canvas').getContext('2d'); cv.font='12.5px "Source Sans 3","Helvetica Neue",Arial,sans-serif';
  function tw(t){ return cv.measureText(t).width; }
  // one fixed start line per column, placed just past the longest label (so every arc leaves from the same x)
  // widths come from the as-coded lists, so the lumping dial moves nothing horizontally (rows only collapse vertically)
  var P0=M.P.orig||M.P, Q0=P0.Q||M.Q, B0=P0.B||M.B, LBL0=P0.labels||M.LBL;
  var wP=Math.max.apply(null,Q0.map(function(q){ var t=LBL0[q.key]; return tw(clip(decap((t&&t.indexOf('$')<0)?t:shortLbl(q.label)))); })), wB=Math.max.apply(null,B0.map(function(b){ return tw(clip(decap(shortLbl(b.label)))); }));
  // a metric on either side that stands for two or more metrics on the other side is drawn as a diamond (whether or not the paper links them)
  var collB={}, collP={}; B.forEach(function(b){ if((b.preimage||[]).length>=2) collB[b.id]=1; }); QORDER.forEach(function(k){ if((M.mapped[k]||[]).length>=2) collP[k]=1; });
  var xEndP={}, xStartB={}; QORDER.forEach(function(k){ xEndP[k]=xP+10+wP+4; }); B.forEach(function(b){ xStartB[b.id]=xB-10-wB-4; });   // all edges start on one vertical line just left of the longest (clipped) label
  var maxX=Math.max.apply(null,QORDER.map(function(k){ return xEndP[k]; })); W=Math.max(W, maxX+160); svg.setAttribute('viewBox','0 0 '+W+' '+H);
  function el(tag,attrs,txt){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(txt!=null) e.textContent=txt; return e; }
  var gRest=el('g'), gPE=el('g'), gBE=el('g'), gMap=el('g'), gB=el('g'), gP=el('g');
  [gRest,gPE,gBE,gMap,gB,gP].forEach(function(g){ svg.appendChild(g); });
  // legend columns follow the dots: the blog legend ends at the blog nodes' x, the paper legend starts at the paper nodes' x
  var legend=root.querySelector('.maplegend');
  function alignLegend(){ if(!legend||!root.offsetParent) return; var sr=svg.getBoundingClientRect(), lr=legend.getBoundingClientRect(); if(!sr.width) return; var sc=sr.width/W, gap=16; var bx=Math.round(sr.left+xB*sc-lr.left+7), px=Math.round(sr.left+xP*sc-lr.left-7); legend.style.columnGap=gap+'px'; legend.style.gridTemplateColumns=bx+'px '+Math.max(40,px-bx-2*gap)+'px 1fr'; }
  if(window.ResizeObserver) new ResizeObserver(alignLegend).observe(svg); window.addEventListener('resize',alignLegend); setTimeout(alignLegend,0); setTimeout(alignLegend,400);
  function arcPath(a,c){ var p=posP[a], q=posP[c]; var dy=Math.abs(p.y-q.y), bulge=Math.min(30+dy*0.35,140); var xm=Math.max(xEndP[a],xEndP[c])+bulge; return 'M'+xEndP[a]+','+p.y+' C'+xm+','+p.y+' '+xm+','+q.y+' '+xEndP[c]+','+q.y; }
  var mapEls=[]; B.forEach(function(b){ (b.preimage||[]).forEach(function(k){ var a=posB[b.id], c=posP[k]; var p=el('path',{d:'M'+(a.x+12)+','+a.y+' C'+(a.x+150)+','+a.y+' '+(c.x-150)+','+c.y+' '+(c.x-12)+','+c.y,'class':'map'+((b.preimage_unsure||b.mapping==='similarity')?' unsure':'')+((HIDB[b.id]||HIDP[k])?' fhide':''),'data-b':b.id,'data-p':k}); gMap.appendChild(p); mapEls.push(p); }); });
  var bedgeEls=[]; E.forEach(function(e,i){ var a=posB[e.source], c=posB[e.target]; var dy=Math.abs(a.y-c.y), bulge=Math.min(30+dy*0.35,140);   /* same curvature as the paper side */ var xm=Math.min(xStartB[e.source],xStartB[e.target])-bulge; var d='M'+xStartB[e.source]+','+a.y+' C'+xm+','+a.y+' '+xm+','+c.y+' '+xStartB[e.target]+','+c.y; var fh=(HIDB[e.source]||HIDB[e.target])?' fhide':''; var p=el('path',{d:d,'class':'bedge2'+fh,'data-e':i}); var hit=el('path',{d:d,'class':'bedgehit'+fh,'data-e':i}); gBE.appendChild(p); gBE.appendChild(hit); bedgeEls.push(p); });
  B.forEach(function(b){ var g=el('g',{'class':'bnode'+((b.preimage||[]).length?'':' nopre')+(collB[b.id]?' coll':'')+(HIDB[b.id]?' fhide':''),'data-b':b.id}); var q=posB[b.id]; g.appendChild(el('title',{},(b.fullLabel||b.label)+(collB[b.id]?' — stands for '+(b.preimage||[]).length+' paper metrics':''))); if(collB[b.id]) g.appendChild(el('polygon',{points:q.x+','+(q.y-7)+' '+(q.x+7)+','+q.y+' '+q.x+','+(q.y+7)+' '+(q.x-7)+','+q.y})); else g.appendChild(el('circle',{cx:q.x,cy:q.y,r:5.5})); g.appendChild(el('text',{x:q.x-10,y:q.y+4,'text-anchor':'end'},clip(decap(shortLbl(b.label))))); gB.appendChild(g); });
  QORDER.forEach(function(k){ var q=QI[k], pos=posP[k]; var g=el('g',{'class':'pnode'+(M.mapped[k]?'':' orphan')+(collP[k]?' coll':'')+(HIDP[k]?' fhide':''),'data-p':k}); g.appendChild(el('title',{},(q.fullLabel||q.label)+(collP[k]?' — '+M.mapped[k].length+' blog metrics map to it':''))); if(collP[k]) g.appendChild(el('polygon',{points:pos.x+','+(pos.y-7)+' '+(pos.x+7)+','+pos.y+' '+pos.x+','+(pos.y+7)+' '+(pos.x-7)+','+pos.y})); else g.appendChild(el('circle',{cx:pos.x,cy:pos.y,r:5.5})); g.appendChild(el('text',{x:pos.x+10,y:pos.y+4},clip(decap((M.LBL[k]&&M.LBL[k].indexOf('$')<0)?M.LBL[k]:shortLbl(q.label))))); gP.appendChild(g); });
  var PL={}, restSel={value:'all',addEventListener:function(){}}, detail=root.querySelector('.s2-detail'); var detail0=detail.innerHTML;   /* every paper link is drawn, as every blog link is */
  function show(x){ detail.innerHTML=x; ts(detail); }
  function drawRest(){ gRest.innerHTML=''; var mode=restSel.value; if(mode==='none') return;
    Object.keys(PL).forEach(function(k){ var ab=k.split('|'); if(!posP[ab[0]]||!posP[ab[1]]||HIDP[ab[0]]||HIDP[ab[1]]) return; var st=M.status(k,PL); if(mode==='mapped'&&(st==='orph'||st==='abs')) return; gRest.appendChild(el('path',{d:arcPath(ab[0],ab[1]),'class':'rest2 st-'+st,'data-k':k})); gRest.appendChild(el('path',{d:arcPath(ab[0],ab[1]),'class':'pedgehit','data-k':k})); });
     }
  function styleEdges(){ E.forEach(function(e,i){ var r=M.edgeRatio(i,PL); bedgeEls[i].setAttribute('class','bedge2 '+(r.grey?'g-grey':(r.linked.length===r.pairs.length?'g-full':(r.linked.length?'g-part':'g-none')))); }); }
  function lbl(k){ return M.lbl(k); }
  function summary(){
    
    root.querySelector('.s2-summary').innerHTML=coverage();
    // counts at the top of the map, one set per side and one for the middle. Degree = links per node, averaged: 2 × links ÷ nodes.
    var nB=B.length, eB=E.filter(function(e){ return pol(e)==='positive'; }).length, nP=QORDER.length, eP=Object.keys(PL).filter(function(k){ return M.wit(k,PL).length>0; }).length, nMap=B.reduce(function(a,b){ return a+(b.preimage||[]).length; },0); function avg(e,n){ return n?(2*e/n).toFixed(1):'–'; }
    var _cb=root.querySelector('.cnt-b'); if(_cb) _cb.textContent=nB+' nodes · '+eB+' edges · average degree '+avg(eB,nB); var _cm=root.querySelector('.cnt-m'); if(_cm) _cm.textContent=nMap+' edges'; var _cp=root.querySelector('.cnt-p'); if(_cp) _cp.textContent=nP+' nodes · '+eP+' edges · average degree '+avg(eP,nP);
  }

  function coverage(){ var adj={}; QORDER.forEach(function(k){ adj[k]=[]; }); Object.keys(PL).forEach(function(k){ if(!M.wit(k,PL).length) return; var ab=k.split('|'); if(adj[ab[0]]&&adj[ab[1]]){ adj[ab[0]].push(ab[1]); adj[ab[1]].push(ab[0]); } });
    // The two tables follow the
    // metric boundary (the view is rebuilt at each setting) and the view filters (a paper metric hidden on the map is hidden here too;
    // shares, p̄ and the evenness test are still computed over all metrics, so hiding a row does not change another row's numbers).
    var nShow=QORDER.filter(function(k){ return !HIDP[k]; }).length;
    return (nShow<QORDER.length?'<p class="small tblshown">Rows shown: '+nShow+' of '+QORDER.length+' paper metrics, as on the map.</p>':'')+salience(adj)+linkSkew(adj); }
  // selective simplification, the metric as the unit. Risk set = the links the paper makes for the metric (D).
  // Coverage = carried ÷ D. Baseline p̄ = the mean of coverage over the metrics the blog names (each metric counts once). Selectivity = coverage ÷ p̄.
  // Evenness test: every named metric keeps each of its links with the same chance p̄, independently (binomial per metric), 2000 draws, seeded;
  // statistic = the spread (sd) of coverage across named metrics.
  function linkSkew(adj){
    var links=Object.keys(PL).filter(function(k){ return M.wit(k,PL).length>0; }).filter(function(k){ var ab=k.split('|'); return M.mapped[ab[0]]||M.mapped[ab[1]]; });
    var car={}; links.forEach(function(k){ if(M.IMP[k]) car[k]=1; });
    var rows=QORDER.filter(function(k){ return (adj[k]||[]).length; }).map(function(k){ var d=adj[k].length, c=adj[k].filter(function(j){ return M.IMP[key(k,j)]; }).length;
      var ung=Object.keys(M.IMP).filter(function(x){ return x.split('|').indexOf(k)>=0&&!M.wit(x,PL).length; }).length; return {k:k,d:d,c:c,ung:ung,named:!!M.mapped[k],cov:c/d}; });
    var nr=rows.filter(function(r){ return r.named; }), sD=nr.reduce(function(a,r){ return a+r.d; },0), sC=nr.reduce(function(a,r){ return a+r.c; },0), pbar=nr.length?nr.reduce(function(a,r){ return a+r.cov; },0)/nr.length:NaN;
    rows.forEach(function(r){ r.exp=r.named?r.d*pbar:NaN; r.sel=r.named&&pbar>0?r.cov/pbar:NaN; });
    rows.sort(function(a,b){ return (b.named-a.named)||((isNaN(b.sel)?-1:b.sel)-(isNaN(a.sel)?-1:a.sel))||b.d-a.d||a.k.localeCompare(b.k); });
    // evenness: sd of coverage across named metrics; null = each named metric keeps each of its D links with chance p̄, independently
    function sdv(xs){ var m=xs.reduce(function(a,b){ return a+b; },0)/xs.length; return Math.sqrt(xs.reduce(function(a,x){ return a+(x-m)*(x-m); },0)/xs.length); }
    var pval=NaN, obs=NaN, NS=2000; if(pbar>0&&pbar<1&&nr.length>1){ obs=sdv(nr.map(function(r){ return r.cov; }));
      var seed=12345; function rnd(){ seed|=0; seed=seed+0x6D2B79F5|0; var t=Math.imul(seed^seed>>>15,1|seed); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }
      var ge=0; for(var s2=0;s2<NS;s2++){ var cv=nr.map(function(r){ var c=0; for(var i=0;i<r.d;i++) if(rnd()<pbar) c++; return c/r.d; }); if(sdv(cv)>=obs-1e-12) ge++; }
      pval=(ge+1)/(NS+1); }
    function cell(r){ if(isNaN(r)) return '<td class="num">–</td>'; var c,m; if(r>=2){ c='sk-o2'; m='▲'; } else if(r>=1.41){ c='sk-o1'; m='▲'; } else if(r>0.71){ c='sk-mid'; m='●'; } else if(r>0.5){ c='sk-u1'; m='▼'; } else { c='sk-u2'; m='▼'; } return '<td class="num '+c+'">'+m+' ×'+r.toFixed(2)+'</td>'; }
    var off={}; E.forEach(function(e){ if(pol(e)!=='positive') return; [e.source,e.target].forEach(function(id){ if(!(BI[id].preimage||[]).length) off[id]=(off[id]||0)+1; }); });
    var verdict=!(pbar>0)?'The blog supports none of the paper’s links for the metrics it names, so there is nothing to compare.':
      'Across the '+nr.length+' metrics the blog names, a typical metric has p̄ = '+(100*pbar).toFixed(1)+'% of its links supported in the blog ('+sC+' of '+sD+' in all). Evenness test: if every metric had the same chance p̄, the spread would be this uneven in '+(100*pval).toFixed(1)+'% of '+NS+' tries (p = '+pval.toFixed(3)+'). '+(pval<0.05?'<b>The spread is wider than even simplification would give: the blog keeps some metrics’ links and drops others’.</b>':'<b>The spread is within what even simplification would give</b> (with this few supported links, the test is weak).');
    return '<h4 class="tblh" data-table="table-2">Table 2. Interdependence Salience</h4><p class="small">This table captures how much a metric’s interdependencies are mentioned in the blog, relative to the average proportion of interdependencies mentioned in the blog for a given metric.</p><p class="small muted">▲ the blog supports more of the metric’s links than is typical; ● about typical; ▼ fewer. The colour repeats the marks. NA: the blog never names the metric, so none of its links could appear.</p>'+APPX('interdependence-salience')+''+
      '<p class="small">'+verdict+'</p>'+
      '<div class="tblwrap"><table class="gl sal"><thead><tr><th>Paper metric</th><th>In blog'+TI('✓ a blog metric matches it. ✗ the blog never names it, so its links could not appear (NA).')+'</th><th>Paper links (D)'+TI('How many links the paper makes for this metric.')+'</th><th>Supported'+TI('Of those links, how many the blog also states.')+'</th><th>Expected'+TI('How many would be supported if this metric had the typical share p̄: D × p̄.')+'</th><th>Share supported'+TI('Supported ÷ D.')+'</th><th>Selectivity'+TI('Share supported ÷ p̄. Above ×1, the blog keeps more of this metric’s links than is typical.')+'</th><th>Unsupported'+TI('Blog links on this metric that the paper does not make. Not counted in the share.')+'</th></tr></thead><tbody>'+
      rows.filter(function(r){ return !HIDP[r.k]; }).map(function(r){ return '<tr'+(r.named?'':' class="muted"')+'><td>'+esc(M.lbl(r.k))+'</td><td>'+(r.named?'✓':'✗')+'</td><td class="num">'+r.d+'</td>'+(r.named?'<td class="num">'+r.c+'</td><td class="num">'+(isNaN(r.exp)?'–':r.exp.toFixed(1))+'</td><td class="num">'+r.c+' of '+r.d+' ('+(100*r.cov).toFixed(0)+'%)</td>'+cell(r.sel)+'<td class="num">'+r.ung+'</td>':'<td class="num">NA</td><td class="num">NA</td><td class="num">NA</td><td class="num">NA</td><td class="num">NA</td>')+'</tr>'; }).join('')+
      Object.keys(off).filter(function(id){ return !HIDB[id]; }).map(function(id){ return '<tr class="muted"><td><i>no paper metric</i> — '+esc(BI[id].label)+'</td><td></td><td></td><td></td><td></td><td class="num" colspan="2">off-paper: '+off[id]+' blog link'+(off[id]>1?'s':'')+'</td><td></td></tr>'; }).join('')+
      '</tbody></table></div>'; }
  function salience(adj){
    // both sides counted in sentences, mechanically. A = distinct paper sentences using any name of the metric; B = distinct blog
    // sentences that are a coded mention of a blog metric standing for it, or that use the words that blog metric was matched on. C = PageRank share.
    var pdoc=M.P.docs&&M.P.docs.paper, bdoc=M.P.docs&&M.P.docs.blog; var BLK={}; (bdoc?bdoc.blocks:[]).forEach(function(b){ BLK[b.id]=b; });
    function sk(block,sentence){ return block+'|'+sentence; }
    // a symbol is counted by its sources, not by occurrences of its character: A's sentences are those using a name of the metric,
    // plus every coded source of it (each numbered equation it is in, each prose link or condition naming it, each attachment sentence).
    var PB={}; (pdoc?pdoc.blocks:[]).forEach(function(b){ PB[b.id]=b; });
    function anchorKey(an){ if(!an||!PB[an.block]||!PB[an.block].html) return null; var mk=maskHtml(PB[an.block].html); var sb=sentBounds(mk,an.start,an.end); return sk(an.block,mk.slice(sb[0],sb[1]).replace(/\s+/g,' ').trim()); }
    var srcs={}; QORDER.forEach(function(k){ srcs[k]={}; }); function addS(k,key){ if(key&&srcs[k]) srcs[k][key]=1; }
    M.REL.forEach(function(r){ r.vars.concat(r.cond_vars||[]).forEach(function(k){ r.nums.forEach(function(n){ addS(k,'eq|'+n); }); addS(k,anchorKey(M.A.paper.quotes['cond:'+r.id])); }); ((M.A.paper.leads||{})[r.id]||[]).forEach(function(x){ if(x.block) addS(x['var'],anchorKey(x)); }); });
    M.PR.forEach(function(l){ var q=anchorKey(M.A.paper.quotes[l.id]), c=anchorKey(M.A.paper.quotes['cond:'+l.id]); [l.a,l.b].forEach(function(k){ addS(k,q); }); (l.condition_vars||[]).forEach(function(k){ addS(k,c||q); }); });
    var ps={}, totP=0, unc=[]; QORDER.forEach(function(k){ var set=srcs[k]; (QI[k].aliases||[]).forEach(function(a){ if(!looseRe(a)) return; findInDoc(pdoc,a).forEach(function(o){ set[sk(o.block,o.sentence)]=1; }); }); var n=Object.keys(set).length; ps[k]=n; totP+=n; });
    function blogSents(b){ var set={}; var n=(b.mentions||[1]).length; for(var i=0;i<n;i++){ var an=M.A.blog.quotes[i?b.id+'~'+i:b.id]; if(an&&BLK[an.block]){ var mk=maskHtml(BLK[an.block].html); var sb=sentBounds(mk,an.start,an.end); set[sk(an.block,mk.slice(sb[0],sb[1]).replace(/\s+/g,' ').trim())]=1; } }
      var words=[]; (b.mentions||[]).forEach(function(m){ if(m.matched&&looseRe(m.matched)&&!/\d/.test(m.matched)) words.push(m.matched); }); Object.keys(b.alias_used||{}).forEach(function(k){ var w=b.alias_used[k]; if(w&&looseRe(w)) words.push(w); });
      words.forEach(function(w){ findInDoc(bdoc,w).forEach(function(o){ set[sk(o.block,o.sentence)]=1; }); }); return set; }
    var bsets={}, allB={}; B.forEach(function(b){ bsets[b.id]=blogSents(b); Object.keys(bsets[b.id]).forEach(function(x){ allB[x]=(allB[x]||0)+1; }); });
    var totB=0; B.forEach(function(b){ totB+=Object.keys(bsets[b.id]).length; });
    var bm={}, bn={}; QORDER.forEach(function(k){ var u={}; (M.mapped[k]||[]).forEach(function(id){ Object.keys(bsets[id]||{}).forEach(function(x){ u[x]=1; }); bn[k]=(bn[k]||[]).concat([M.BI[id].label]); }); bm[k]=Object.keys(u).length; });
    // PageRank on the undirected paper link graph (damping 0.85; a metric with no links spreads its weight evenly), sums to 1
    var V=QORDER, N=V.length, pr={}, d=0.85; V.forEach(function(v){ pr[v]=1/N; });
    for(var it=0;it<100;it++){ var nx={}, dang=0; V.forEach(function(v){ nx[v]=(1-d)/N; if(!(adj[v]||[]).length) dang+=pr[v]; }); V.forEach(function(v){ var nb=adj[v]||[]; nb.forEach(function(w){ nx[w]+=d*pr[v]/nb.length; }); }); V.forEach(function(v){ nx[v]+=d*dang/N; }); pr=nx; }
    function pc(x){ return isNaN(x)?'–':(100*x).toFixed(1)+'%'; }
    function cell(r){ if(r==null||isNaN(r)) return '<td class="num">–</td>'; if(!isFinite(r)) return '<td class="num sk-o2" title="the paper share is 0">▲ ∞</td>';
      var t='×'+r.toFixed(2), c, m; if(r>=2){ c='sk-o2'; m='▲'; } else if(r>=1.41){ c='sk-o1'; m='▲'; } else if(r>0.71){ c='sk-mid'; m='●'; } else if(r>0.5){ c='sk-u1'; m='▼'; } else { c='sk-u2'; m='▼'; }
      return '<td class="num '+c+'">'+m+' '+t+'</td>'; }
    var rows=QORDER.map(function(k){ var A=ps[k]==null?NaN:(totP?ps[k]/totP:NaN), Bs=totB?bm[k]/totB:0, C=pr[k]; return {k:k, A:A, Bs:Bs, C:C, ms:isNaN(A)?NaN:(A>0?Bs/A:(Bs>0?Infinity:NaN)), cs:C>0?Bs/C:NaN}; });
    rows.sort(function(a,b){ function v(x){ return isNaN(x.ms)?-1:(isFinite(x.ms)?x.ms:1e9); } return v(b)-v(a)||b.Bs-a.Bs; });
    var off=B.filter(function(b){ return !(b.preimage||[]).length; });
    var s='<h4 class="tblh" data-table="table-1">Table 1. Metric Salience</h4><p class="small">This table captures how much a metric is mentioned in the blog, relative to its underlying centrality to the paper (both in number of paper mentions, and centrality of that metric node).</p><p class="small muted">▲ the blog gives the metric more weight than the paper does; ● about the same; ▼ less. The colour repeats the marks.</p>'+APPX('metric-salience')+''+
      '<div class="tblwrap"><table class="gl sal"><thead><tr><th>Paper metric</th><th>Paper mentions (A)'+TI('The metric’s share of the paper’s mentions: the sentences that name it, plus its equations and stated links.')+'</th><th>Paper links · PageRank (C)'+TI('How many metrics the paper links it to, and how central it is in the paper’s web of links (PageRank).')+'</th><th>Blog metrics for it'+TI('The blog’s metrics that match this paper metric.')+'</th><th>Blog mentions (B)'+TI('The metric’s share of the blog’s sentences that mention it.')+'</th><th>Mention skew B÷A'+TI('Blog share ÷ paper share. Above ×1, the blog mentions it more than the paper does.')+'</th><th>Centrality skew B÷C'+TI('Blog share ÷ PageRank. Above ×1, the blog mentions it more than its place in the paper suggests.')+'</th></tr></thead><tbody>'+
      rows.filter(function(r){ return !HIDP[r.k]; }).map(function(r){ var k=r.k; return '<tr><td>'+esc(M.lbl(k))+'</td><td class="num">'+(ps[k]==null?'–':ps[k]+' ('+pc(r.A)+')')+'</td><td class="num">'+(adj[k]||[]).length+' · '+pc(r.C)+'</td><td>'+esc((bn[k]||[]).join('; '))+'</td><td class="num">'+bm[k]+' ('+pc(r.Bs)+')</td>'+cell(r.ms)+cell(r.cs)+'</tr>'; }).join('')+
      off.filter(function(b){ return !HIDB[b.id]; }).map(function(b){ var c=Object.keys(bsets[b.id]).length; return '<tr class="muted"><td><i>no paper metric</i></td><td></td><td></td><td>'+esc(b.label)+'</td><td class="num">'+c+' ('+pc(totB?c/totB:NaN)+')</td><td class="num" colspan="2">off-paper</td></tr>'; }).join('')+
      '</tbody></table></div><p class="small muted">In all: '+totP+' paper mentions across '+QORDER.length+' metrics; '+totB+' blog mentions across '+B.length+' blog metrics.</p>';
    return s; }
  function clear(){ if(typeof hidePop==='function') hidePop(); gPE.innerHTML=''; svg.classList.remove('dimrest'); mapEls.forEach(function(p){ p.classList.remove('on','off'); }); bedgeEls.forEach(function(p){ p.classList.remove('on','dim'); }); Array.prototype.forEach.call(svg.querySelectorAll('.bnode,.pnode'),function(g){ g.classList.remove('dim','sel'); }); }
  function parc(a,c,cls){ svg.classList.add('dimrest'); if(HIDP[a]||HIDP[c]||cls==='st-ung') return; gPE.appendChild(el('path',{d:arcPath(a,c),'class':'pedge2 '+cls,'data-k':key(a,c)})); gPE.appendChild(el('path',{d:arcPath(a,c),'class':'pedgehit','data-k':key(a,c)})); }
  // one rule for what a click shows. For the clicked metric's side: its links and the metrics they reach. For the other side: the
  // metrics it corresponds to, their links, and the metrics those reach. Everything else is dimmed. The same rule whichever side is clicked.
  function focus(bset, pset, side, id){ clear(); svg.classList.add('dimrest'); var bOn={}, pOn={};
    bset.forEach(function(b){ bOn[b]=1; }); pset.forEach(function(k){ pOn[k]=1; });
    E.forEach(function(e,i){ var on=bset.indexOf(e.source)>=0||bset.indexOf(e.target)>=0; bedgeEls[i].classList.toggle('on',on); bedgeEls[i].classList.toggle('dim',!on); if(on){ bOn[e.source]=1; bOn[e.target]=1; } });
    pset.forEach(function(k){ Object.keys(PL).forEach(function(x){ var ab=x.split('|'); if(ab.indexOf(k)<0||!M.wit(x,PL).length) return; var c=ab[0]===k?ab[1]:ab[0]; parc(k,c,'st-'+M.status(x,PL)); pOn[c]=1; }); });
    mapEls.forEach(function(p){ var on=bset.indexOf(p.dataset.b)>=0&&pset.indexOf(p.dataset.p)>=0; p.classList.toggle('on',on); p.classList.toggle('off',!on); });
    Array.prototype.forEach.call(svg.querySelectorAll('.bnode'),function(g){ g.classList.toggle('dim',!bOn[g.dataset.b]); g.classList.toggle('sel',side==='b'&&g.dataset.b===id); });
    Array.prototype.forEach.call(svg.querySelectorAll('.pnode'),function(g){ g.classList.toggle('dim',!pOn[g.dataset.p]); g.classList.toggle('sel',side==='p'&&g.dataset.p===id); }); }
  // a paper link is clickable like a blog link: the link, its two metrics, their blog metrics, and the blog links that stand for it
  function selL(k){ clear(); svg.classList.add('dimrest'); var ab=k.split('|'), st=M.status(k,PL); parc(ab[0],ab[1],'st-'+st); var imgs=(M.mapped[ab[0]]||[]).concat(M.mapped[ab[1]]||[]), ed=M.IMP[k]||[];
    Array.prototype.forEach.call(svg.querySelectorAll('.pnode'),function(g){ g.classList.toggle('dim',ab.indexOf(g.dataset.p)<0); });
    Array.prototype.forEach.call(svg.querySelectorAll('.bnode'),function(g){ g.classList.toggle('dim',imgs.indexOf(g.dataset.b)<0); });
    E.forEach(function(e,i){ var on=ed.indexOf(i)>=0; bedgeEls[i].classList.toggle('on',on); bedgeEls[i].classList.toggle('dim',!on); });
    mapEls.forEach(function(p){ var on=ab.indexOf(p.dataset.p)>=0&&imgs.indexOf(p.dataset.b)>=0; p.classList.toggle('on',on); p.classList.toggle('off',!on); });
    var names={rep:'supported: the blog states this link',unl:'not supported: the blog names both metrics but not the link',orph:'not supported: the blog names one of the two',abs:'not supported: the blog names neither'};
    show('<h4>'+esc(lbl(ab[0]))+' ↔ '+esc(lbl(ab[1]))+'</h4><p><b>'+esc(names[st]||st)+'.</b></p><p>'+esc(M.witness(k,PL))+'</p>'); }
  function selP(k){ clear(); Array.prototype.forEach.call(svg.querySelectorAll('.pnode'),function(g){ g.classList.toggle('dim',g.dataset.p!==k); }); svg.querySelector('.pnode[data-p="'+k+'"]').classList.add('sel');
    var imgs=M.mapped[k]||[]; mapEls.forEach(function(p){ p.classList.toggle('on',p.dataset.p===k); p.classList.toggle('off',p.dataset.p!==k); }); Array.prototype.forEach.call(svg.querySelectorAll('.bnode'),function(g){ g.classList.toggle('dim',imgs.indexOf(g.dataset.b)<0); });
    // as when a blog metric is selected: keep the blog links of the metric's blog images, dim the rest
    E.forEach(function(e,i){ var on=imgs.indexOf(e.source)>=0||imgs.indexOf(e.target)>=0; bedgeEls[i].classList.toggle('on',on); bedgeEls[i].classList.toggle('dim',!on); });
    var partners=Object.keys(PL).filter(function(x){ return x.split('|').indexOf(k)>=0; }).map(function(x){ var ab=x.split('|'); return ab[0]===k?ab[1]:ab[0]; });
    var impl=Object.keys(M.IMP).filter(function(x){ return x.split('|').indexOf(k)>=0&&!PL[x]; }).map(function(x){ var ab=x.split('|'); return ab[0]===k?ab[1]:ab[0]; });
    var groups={rep:[],unl:[],orph:[],abs:[]}; partners.forEach(function(c){ var s=M.status(key(k,c),PL); if(groups[s]) groups[s].push(c); parc(k,c,'st-'+s); svg.querySelector('.pnode[data-p="'+c+'"]').classList.remove('dim'); }); impl.forEach(function(c){ parc(k,c,'st-ung'); svg.querySelector('.pnode[data-p="'+c+'"]').classList.remove('dim'); });
    focus(imgs,[k],'p',k);
    var q=QI[k]; var s='<h4>'+esc(q.label)+' <button type="button" class="lnk" data-showq="'+esc(k)+'">show in paper</button></h4><p>Named in: '+esc(q.named_in)+'.</p>'+aliasHTML(M,q)+'<p>Blog metrics mapping to it: '+(imgs.length?imgs.map(function(b){ return esc(BI[b].label)+' (via “'+esc((BI[b].alias_used||{})[k]||'')+'”)'; }).join(' · '):'<b>none — orphaned</b>')+'</p>';
    function list(arr,title){ return '<li><b>'+title+' ('+arr.length+')</b>'+(arr.length?'<ul>'+arr.map(function(c){ return '<li>'+esc(lbl(c))+' — '+esc(M.witness(key(k,c),PL))+'</li>'; }).join('')+'</ul>':'')+'</li>'; }
    show(s+'<ul>'+list(groups.rep,'supported (the blog names both and states the link)')+list(groups.unl,'not supported (the blog names both, never states the link)')+list(groups.orph,'not supported (the blog names this metric but not the partner)')+list(groups.abs,'not supported (the blog names neither)')+list(impl,'unsupported (the blog states a link the paper does not)')+'</ul>'); }
  function selB(id){ clear(); var b=BI[id]; Array.prototype.forEach.call(svg.querySelectorAll('.bnode'),function(g){ g.classList.toggle('dim',g.dataset.b!==id); }); svg.querySelector('.bnode[data-b="'+id+'"]').classList.add('sel');
    mapEls.forEach(function(p){ p.classList.toggle('on',p.dataset.b===id); p.classList.toggle('off',p.dataset.b!==id); }); var pre=b.preimage||[]; Array.prototype.forEach.call(svg.querySelectorAll('.pnode'),function(g){ g.classList.toggle('dim',pre.indexOf(g.dataset.p)<0); });
    E.forEach(function(e,i){ var on=e.source===id||e.target===id; bedgeEls[i].classList.toggle('on',on); bedgeEls[i].classList.toggle('dim',!on); if(on) svg.querySelector('.bnode[data-b="'+(e.source===id?e.target:e.source)+'"]').classList.remove('dim'); });
    focus([id],pre,'b',id);
    var s='<h4>'+esc(b.label)+' <span class="tag">'+esc(b['class'])+'</span> <button type="button" class="lnk" data-showb="'+esc(id)+'">show in blog</button></h4><p class="q">“'+esc(b.quote)+'”</p><p>Preimage: '+(pre.length?pre.map(function(k){ return esc(lbl(k))+' (paper says “'+esc((b.alias_used||{})[k]||'')+'”)'; }).join(' · '):'none')+'</p>'+(b.preimage_note?'<p class="muted">'+(b.preimage_unsure?'<b>Mapping unsure.</b> ':'')+esc(b.preimage_note)+'</p>':'')+(b.recode_note?'<p class="muted">Coding note: '+esc(b.recode_note)+'</p>':'');
    var cl=Object.keys(M.COLL).filter(function(k){ return M.COLL[k].indexOf(id)>=0; }); if(cl.length) s+='<p><b>Collapsed inside this metric:</b> '+cl.map(function(k){ var ab=k.split('|'); return esc(lbl(ab[0])+'↔'+lbl(ab[1]))+(PL[k]?' (linked: '+esc(M.witness(k,PL))+')':' (not linked)'); }).join(' · ')+'</p>';
    var es=E.map(function(e,i){ return i; }).filter(function(i){ return E[i].source===id||E[i].target===id; }); if(es.length) s+='<p><b>Blog edges:</b></p><ul>'+es.map(function(i){ var r=M.edgeRatio(i,PL); return '<li>'+esc(BI[E[i].source].label+' → '+BI[E[i].target].label)+' — '+(r.grey?'off-paper link':'supported '+r.linked.length+'/'+r.pairs.length)+'</li>'; }).join('')+'</ul>'; show(s); }
  function selE(i){ clear(); var e=E[i]; bedgeEls[i].classList.add('on'); bedgeEls.forEach(function(p,j){ if(j!==i) p.classList.add('dim'); }); Array.prototype.forEach.call(svg.querySelectorAll('.bnode'),function(g){ g.classList.toggle('dim',g.dataset.b!==e.source&&g.dataset.b!==e.target); });
    var r=M.edgeRatio(i,PL); var pre=(BI[e.source].preimage||[]).concat(BI[e.target].preimage||[]); Array.prototype.forEach.call(svg.querySelectorAll('.pnode'),function(g){ g.classList.toggle('dim',pre.indexOf(g.dataset.p)<0); }); mapEls.forEach(function(p){ var on=p.dataset.b===e.source||p.dataset.b===e.target; p.classList.toggle('on',on); p.classList.toggle('off',!on); });
    r.pairs.forEach(function(k){ var ab=k.split('|'); parc(ab[0],ab[1],'st-'+M.status(k,PL)); });
    var s='<h4>'+esc(BI[e.source].label)+' → '+esc(BI[e.target].label)+'</h4><p class="q">“'+esc(e.quote)+'”</p>';
    s+=r.grey?'<p>An end has no paper metric, so there is nothing to check.</p>':'<p><b>Supported '+r.linked.length+'/'+r.pairs.length+'.</b></p><ul>'+r.pairs.map(function(k){ var ab=k.split('|'); return '<li>'+esc(lbl(ab[0])+'↔'+lbl(ab[1]))+': '+(PL[k]?'<b>linked</b> — '+esc(M.witness(k,PL)):'<b>not stated in the paper</b>')+'</li>'; }).join('')+'</ul>';
    show(s+(e.paper_counterpart?'<p class="muted">Coding note: '+esc(e.paper_counterpart)+'</p>':'')); }
  svg.addEventListener('click',function(ev){ lastXY=ev; var t=ev.target.closest('.pnode'); if(t){ selP(t.dataset.p); return popNode('p',t.dataset.p); } var b=ev.target.closest('.bnode'); if(b){ selB(b.dataset.b); return popNode('b',b.dataset.b); } var m=ev.target.closest('.map'); if(m){ selP(m.dataset.p); return popNode('p',m.dataset.p); }
    var hh=ev.target.closest('.bedgehit'); if(hh){ selE(+hh.dataset.e); return popEdge('b',+hh.dataset.e); } var pl=ev.target.closest('.pedgehit'); if(pl){ selL(pl.dataset.k); return popEdge('p',pl.dataset.k); } clear(); });
  // no detail panel under the map. A click opens three small chips beside the node, toward the middle of the map: the metric,
  // its interdependencies (the matrix with its row and column bounded), and how many of its links the other text represents.
  var wrap=svg.parentNode, pop=document.createElement('div'), lastXY=null; pop.className='mpop'; pop.hidden=true; wrap.style.position='relative'; wrap.appendChild(pop);
  function hidePop(){ pop.hidden=true; pop.innerHTML=''; }
  function place(px,py,side){ var r=svg.getBoundingClientRect(), w=wrap.getBoundingClientRect(); var x=r.left-w.left+px*r.width/W, y=r.top-w.top+py*r.height/H+wrap.scrollTop;
    pop.style.top=(y-14)+'px'; if(side==='p'){ pop.style.left=(x-14)+'px'; pop.style.transform='translateX(-100%)'; } else if(side==='b'){ pop.style.left=(x+14)+'px'; pop.style.transform='none'; } else { pop.style.left=x+'px'; pop.style.transform='translate(-50%,8px)'; } pop.hidden=false; }
  function chip(go,label,arg){ return '<button type="button" class="chip" data-go="'+go+'" data-arg="'+esc(arg)+'">'+label+' ↗</button>'; }
  function popNode(side,id){ var h='';
    if(side==='p'){ var tot=0, rep=0; Object.keys(PL).forEach(function(x){ if(x.split('|').indexOf(id)<0||!M.wit(x,PL).length) return; tot++; if(M.status(x,PL)==='rep') rep++; });
      h=chip('qp','Metric',id)+chip('mp','Interdependencies',id)+'<span class="chip cnt">'+rep+'/'+tot+' links supported in the blog</span>'; place(posP[id].x,posP[id].y,'p'); }
    else { var tb=0, ok=0; E.forEach(function(e,i){ if(pol(e)!=='positive'||(e.source!==id&&e.target!==id)) return; tb++; var r=M.edgeRatio(i,PL); if(!r.grey&&r.pairs.length&&r.linked.length===r.pairs.length) ok++; });
      h=chip('qb','Metric',id)+chip('mb','Interdependencies',id)+'<span class="chip cnt">'+ok+'/'+tb+' links supported in the paper</span>'; place(posB[id].x,posB[id].y,'b'); }
    pop.innerHTML=h; }
  function popEdge(side,id){ var h;
    if(side==='b'){ var e=E[id], r=M.edgeRatio(id,PL); h=chip('eb','Interdependency',e.source+'|'+e.target)+'<span class="chip cnt">'+(r.grey?'not in the paper (an end stands for no paper metric)':r.linked.length+'/'+r.pairs.length+' paper pairs linked')+'</span>'; }
    else { var ab=id.split('|'); h=chip('ep','Interdependency',id)+'<span class="chip cnt">'+(M.status(id,PL)==='rep'?'supported in the blog':'not supported in the blog')+'</span>'; }
    var r0=svg.getBoundingClientRect(); pop.innerHTML=h; if(lastXY) place((lastXY.clientX-r0.left)*W/r0.width,(lastXY.clientY-r0.top)*H/r0.height,'c'); }
  pop.addEventListener('click',function(e){ var c=e.target.closest('[data-go]'); if(!c) return; var g=c.dataset.go, a=c.dataset.arg;
    if(g==='qp'&&ctx.showInPaper) ctx.showInPaper(a); else if(g==='qb'&&ctx.showInBlog) ctx.showInBlog(a);
    else if(g==='mp'&&ctx.matrixPaper) ctx.matrixPaper(a); else if(g==='mb'&&ctx.matrixBlog) ctx.matrixBlog(a);
    else if(g==='ep'&&ctx.pairPaper){ var ab=a.split('|'); ctx.pairPaper(ab[0],ab[1]); } else if(g==='eb'&&ctx.pairBlog){ var cd=a.split('|'); ctx.pairBlog(cd[0],cd[1]); } });   // a click on empty space resets the view
  detail.addEventListener('click',function(e){ var q=e.target.closest('[data-showq]'); if(q&&ctx.showInPaper) return ctx.showInPaper(q.dataset.showq); var b=e.target.closest('[data-showb]'); if(b&&ctx.showInBlog) return ctx.showInBlog(b.dataset.showb); });
  restSel.addEventListener('change',function(){ drawRest(); });
  function refresh(){ PL=M.paperLayer(); drawRest(); styleEdges(); summary(); }
  refresh();
  return {root:root, refresh:refresh};
}

// ======================================================================
// APP SHELL
// ======================================================================
var app=document.getElementById('app'), VIEWS={}; window.__skew={VIEWS:VIEWS, mapEvidence:mapEvidence, findInDoc:findInDoc};
// a metric reached by a direct link rises to the top of the metrics list's own scroll box (the page itself does not move)
function listToTop(list){ function go(){ var r=list.querySelector('tr.clk.sel'), w=list.closest('.listwrap'); if(!r||!w) return; var th=list.querySelector('thead'); var off=th?th.offsetHeight:0;
  w.scrollTop=Math.max(0, r.offsetTop-off); } go(); setTimeout(go,60); setTimeout(go,450); }
function syncPane(vcol, scol, viewer){ function go(){ if(!scol.offsetParent) return; var top=scol.getBoundingClientRect().top+window.scrollY; var H=Math.max(480, window.innerHeight-top-16); scol.style.height=H+'px'; var extra=0; Array.prototype.forEach.call(vcol.children,function(ch){ if(ch!==viewer.root) extra+=ch.offsetHeight+8; }); viewer.root.style.height=Math.max(420,H-extra)+'px'; } window.addEventListener('resize',go); window.addEventListener('hashchange',function(){ setTimeout(go,0); }); setTimeout(go,0); setTimeout(go,400); return go; }
function srcHead(x,label){ return h('p','srchead','<span class="lb">'+label+'</span> '+srcLink(x)); }
function srcLink(x){ var t=x.title||x.cite||x.url||''; return x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener" title="'+esc(x.cite||'')+'">'+esc(t)+' ↗</a>':esc(t); }
function pairView(pid){ if(VIEWS[pid]) return VIEWS[pid]; var P=PAIRS[pid]; if(!P) return null; var sc=P.scopes||{}; SCOPENAME={abstract:'abstract', intro:'introduction', prelim:sc.prelim||'preliminaries', body:sc.body||'rest of the paper'}; var tau=(LUMP[pid]===undefined)?DEFAULT_TAU:LUMP[pid], mt=tau; /* one slider sets both the within-side collapse and the cross-side fold */ var PM=mapP(P,mt), PL0=lumpP(PM,tau); if(PL0!==P) PL0.orig=P; if(!PL0.mapg) PL0.mapg=PM.mapg; var M=model(PL0); var root=h('div');
  var top=h('div','topbar'); top.innerHTML='<div class="row"><a class="back" href="#/">← all pairs</a><span class="ttl">'+esc(pid)+'</span><a class="howbtn" href="method.html">How this was made</a></div>'+
    '<div class="tabbar" role="tablist"><button role="tab" data-tab="paper">1 · Paper</button><button role="tab" data-tab="blog">2 · Blog</button><button role="tab" data-tab="map">3 · Map</button></div>';
  root.appendChild(top);
  // the metric boundary, fine (left, as coded) to coarse (right). It sits on both Metrics tabs and in
  // the map's Filter view; all copies share LUMP[pid].
  var ctx={};
  function rebuild(tab){ var y=window.scrollY; delete VIEWS[pid]; route(); if(VIEWS[pid]){ VIEWS[pid].showTab(tab); if(VIEWS[pid].afterRebuild) VIEWS[pid].afterRebuild(); } window.scrollTo({top:y}); }
  ctx.rebuild=rebuild; ctx.pid=pid;
  ctx.makeDial=function(tab,compact){ if(!(P.sim&&P.Q&&(Object.keys(P.sim.paper||{}).length||Object.keys(P.sim.blog||{}).length))) return null;   /* no scores: no slider */ var dial=h('div',compact?'fv-cells':'lumpbar'); var lp=PL0.lump||{tau:1,paperGroups:0,blogGroups:0,paperFrom:P.Q.length,paperTo:P.Q.length,blogFrom:(P.B||[]).length,blogTo:(P.B||[]).length,model:P.sim.model}; var did='tb-'+(++DIALN);
    dial.innerHTML=compact?'<label class="fv-l" for="'+did+'">Metric boundary <span class="info" tabindex="0" data-tip="'+MB_INFO+'" aria-label="'+MB_INFO+'">ⓘ</span></label><span class="fv-c"><span class="fv-end">fine</span><input type="range" id="'+did+'" min="0" max="0.4" step="0.01" value="'+(1-tau).toFixed(2)+'" aria-label="metric boundary, fine to coarse"><span class="fv-end">coarse</span></span><span class="fv-v lumpval"></span>':'<label for="'+did+'"><b>Metric boundary</b></label> <span class="small">fine</span><input type="range" id="'+did+'" min="0" max="0.4" step="0.01" value="'+(1-tau).toFixed(2)+'" aria-label="metric boundary, fine to coarse"><span class="small">coarse</span> <span class="lumpval small"></span>'+
      '<p class="muted small">Metrics discerned from prose may not be described using the exact same term throughout the article. Use the slider to relax the boundary of a metric’s terminology from fine (i.e. only an exact match of the term throughout the paper) to coarse (e.g. ‘error rate’ conflates with ‘fidelity’). Terms are joined by how alike their one-line definitions are. Links never join two metrics, and symbols never join. A joined metric is marked ⊕ with the number of terms it holds.</p>';
    var val=dial.querySelector('.lumpval'); function txt(t,l){ return t<1?'similarity ≥ '+t.toFixed(2)+' · paper '+l.paperTo+'/'+l.paperFrom+' · blog '+l.blogTo+'/'+l.blogFrom:'exact terms'; }
    val.textContent=txt(tau,lp); var rng=dial.querySelector('input'); rng.addEventListener('input',function(){ var t=1-parseFloat(rng.value); val.textContent=txt(t,(lumpP(P,t).lump)||lp); });
    rng.addEventListener('change',function(){ LUMP[pid]=Math.round((1-parseFloat(rng.value))*100)/100; rebuild(tab); });
    return dial; };
  var tabs={}; var panels=h('div');
  tabs.paper=buildPaperTab(M,ctx); tabs.blog=buildBlogTab(M,ctx); tabs.map=buildMapTab(M,ctx);
  ['paper','blog','map'].forEach(function(t){ tabs[t].root.id='tab-'+t; tabs[t].root.classList.add('hidden'); panels.appendChild(tabs[t].root); }); root.appendChild(panels);
  function nav(t,id){ var hsh='#/p/'+pid+'/'+t+(id?'/'+encodeURIComponent(id):''); if(location.hash===hsh) return; if(/^#\/p\/[^/]+\/(paper|blog|map)/.test(location.hash||'')) history.pushState(null,'',hsh); else history.replaceState(null,'',hsh); }
  ctx.nav=nav;
  function showTab(t){ ['paper','blog','map'].forEach(function(x){ tabs[x].root.classList.toggle('hidden',x!==t); }); Array.prototype.forEach.call(top.querySelectorAll('[role=tab]'),function(b){ b.setAttribute('aria-selected',b.dataset.tab===t?'true':'false'); }); if((location.hash||'').indexOf('#/p/'+pid+'/'+t)!==0) nav(t); }
  ctx.showInPaper=function(k){ showTab('paper'); window.scrollTo({top:0}); if(tabs.paper.selectQ) tabs.paper.selectQ(k,{scroll:true}); };
  ctx.showInBlog=function(id){ showTab('blog'); window.scrollTo({top:0}); if(tabs.blog.selectB) tabs.blog.selectB(id,{scroll:true}); };
  ctx.matrixPaper=function(k){ showTab('paper'); window.scrollTo({top:0}); if(tabs.paper.matrixMetric) tabs.paper.matrixMetric(k); };
  ctx.matrixBlog=function(id){ showTab('blog'); window.scrollTo({top:0}); if(tabs.blog.matrixMetric) tabs.blog.matrixMetric(id); };
  ctx.pairPaper=function(a,b){ showTab('paper'); window.scrollTo({top:0}); if(tabs.paper.matrixPair) tabs.paper.matrixPair(a,b); };
  ctx.pairBlog=function(a,b){ showTab('blog'); window.scrollTo({top:0}); if(tabs.blog.matrixPair) tabs.blog.matrixPair(a,b); };
  top.querySelector('.tabbar').addEventListener('click',function(e){ var b=e.target.closest('button'); if(b) showTab(b.dataset.tab); });
  VIEWS[pid]={root:root, showTab:showTab, M:M, select:function(t,id){ if(t==='map'&&/^(table-\d+)$/.test(id)){ var moved=false; function onUser(){ moved=true; } window.addEventListener('wheel',onUser,{once:true,passive:true}); window.addEventListener('touchmove',onUser,{once:true,passive:true}); window.addEventListener('mousedown',onUser,{once:true}); var t0=Date.now(), settled=0; (function tick(){ if(moved||Date.now()-t0>10000) return; var hd=tabs.map.root.querySelector('[data-table="'+id+'"]'); if(hd){ var top=hd.getBoundingClientRect().top; if(Math.abs(top)>4){ hd.scrollIntoView({block:'start'}); settled=0; } else settled++; } if(settled<6) setTimeout(tick,200); })(); return; } if(t==='paper'&&tabs.paper.selectQ) tabs.paper.selectQ(id,{scroll:true}); else if(t==='blog'&&tabs.blog.selectB) tabs.blog.selectB(id,{scroll:true}); }}; return VIEWS[pid]; }

function firmOf(x){ return (x&&x.firm)||''; }
function front(){ var f=h('div','front');
  var rows=ORDER.map(function(pid,i){ var P=PAIRS[pid]; var tab=P.paper?'paper':'blog'; function lnk(x){ if(!x) return '<span class="muted">— not given</span>'; var t=x.title||x.cite; return x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener">'+esc(t)+'</a>':esc(t); }
    return '<tr><td class="pid">'+(i+1)+'</td><td><a class="pname" href="#/p/'+esc(pid)+'/'+tab+'">'+esc(pid)+'</a></td><td>'+lnk(P.paper)+'</td><td>'+esc(firmOf(P.paper))+'</td><td>'+lnk(P.blog)+'</td><td>'+esc(firmOf(P.blog))+'</td><td><a class="btn" href="#/p/'+esc(pid)+'/'+tab+'">'+(P.paper&&P.blog?'Compare':'Open')+'</a></td></tr>'; }).join('');
  f.innerHTML='<header><a class="howbtn" href="method.html">How this was made</a><h1>Mapping Technical Artifacts</h1><p class="sub wide">This tool elicits every measurable quantity in a paper or blog (i.e. <b>metrics</b>) and the stated relationships between them (i.e. <b>interdependencies</b>). This reveals the underlying structure of different technical artifacts produced by a firm, <b>enabling organizational researchers to reach deeper into the technical core of an organization than previously possible</b> — to yield insights ranging from strategic communication, to firm positioning, to organizational design.</p></header>'+
    '<div class="listhead"><h2>Sample Quantum Computing Paper-Blog Pairs</h2></div><div class="pairlist"><table class="gl pairs"><colgroup><col style="width:5%"><col style="width:16%"><col style="width:27%"><col style="width:8%"><col style="width:27%"><col style="width:8%"><col style="width:9%"></colgroup><thead><tr><th>ID</th><th>Pair</th><th>Paper</th><th>Firm</th><th>Blog</th><th>Firm</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div>'+(UPLOAD?
    '<h2>Compare your own pair</h2><div class="upload"><p>Enter the url of your own blog and paper (arXiv link preferred) pair. If only one is provided, only one set of metrics and interdependencies will be identified, and the map will be withheld.</p><form><div class="pairlist urlbox"><table class="gl pairs urlform"><colgroup><col style="width:5%"><col style="width:16%"><col style="width:27%"><col style="width:8%"><col style="width:27%"><col style="width:8%"><col style="width:9%"></colgroup><thead><tr><th></th><th>Pair</th><th colspan="2">Paper</th><th colspan="2">Blog</th><th></th></tr></thead><tbody><tr><td></td><td><span class="muted small">your pair</span></td><td colspan="2"><input type="url" name="paper" placeholder="https://arxiv.org/abs/…" aria-label="paper address"></td><td colspan="2"><input type="url" name="blog" placeholder="https://…/blog/…" aria-label="blog address"></td><td><button type="submit" class="btn">Compare</button></td></tr></tbody></table></div></form></div>':'');
  if(UPLOAD) f.querySelector('form').addEventListener('submit',function(e){ e.preventDefault(); var fd=new FormData(e.target); var pu=String(fd.get('paper')||'').trim(), bu=String(fd.get('blog')||'').trim(); if(!pu&&!bu) return;   // one address is enough; the missing side and the map are withheld
    if(PIPE){ submitJob(pu,bu,f); return; }   // a pipeline server is configured (site.json pipeline_url): code the texts
    PAIRS.upload={id:'upload', status:'your pair', short:'', paper:{cite:pu||'(no paper given)', url:pu}, blog:{cite:bu||'(no blog given)', url:bu}, docs:null, iframe:{paper:pu||null, blog:bu||null}}; delete VIEWS.upload; location.hash='#/p/upload/'+(pu?'paper':'blog'); });
  return f; }


// ======================================================================
// RUNNING THE PIPELINE ON A VISITOR'S PAPER / BLOG
// With site.json "pipeline_url", the form sends the links to the skewcoder job server, shows its progress, and opens the
// finished bundle like any sample pair. Without it, the form only shows the two pages (nothing is coded).
// ======================================================================
var PIPE=(window.SITE&&window.SITE.pipeline_url||'').replace(/\/+$/,'');
var UPLOAD=!(window.SITE&&window.SITE.upload===false);   // site.json "upload": false hides "Compare your own pair"
var SET_PREFIX=/^(Method|Model|Regime|Setting|Representation|Task|Input model|Platform|Approximation|Qualifier|Code|Hardware)\s*:\s*/;
function setWord(x){ return x.replace(/\b([Qq])ualifier(s?)\b/g,function(m,q,pl){ return (q==='Q'?'S':'s')+'etting'+pl; }); }
function setWalk(o){ if(Array.isArray(o)) return o.map(setWalk); if(o&&typeof o==='object'){ var r={}; Object.keys(o).forEach(function(k){ if(k!=='qualifier') r[k]=setWalk(o[k]); }); return r; } return typeof o==='string'?setWord(o):o; }
/* the same display rule build.py applies to the sample pairs (scrub_settings): settings are ordinary metrics on the site */
function scrubBundle(b){ ['Q','PR','B','E','rels'].forEach(function(k){ b[k]=setWalk(b[k]||[]); }); b.Q.forEach(function(q){ q.label=q.label.replace(SET_PREFIX,''); }); b.B.forEach(function(x){ x.label=x.label.replace(SET_PREFIX,''); });
  var L={}; Object.keys(b.labels||{}).forEach(function(k){ var v=b.labels[k]; L[k]=typeof v==='string'?setWord(v).replace(SET_PREFIX,''):v; }); b.labels=L; return b; }
function jobBox(f){ var box=f.querySelector('.jobstatus'); if(!box){ box=h('div','jobstatus'); box.setAttribute('role','status'); box.setAttribute('aria-live','polite'); f.querySelector('.upload').appendChild(box); } return box; }
function submitJob(pu,bu,f){ var box=jobBox(f); box.innerHTML='<p>Sending…</p>';
  fetch(PIPE+'/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paper:pu||null,blog:bu||null})}).then(function(r){ return r.json().then(function(j){ return {ok:r.ok,j:j}; }); })
    .then(function(x){ if(!x.ok){ box.innerHTML='<p><b>Not started.</b> '+esc(x.j.error||'the server refused')+'</p>'; return; } location.hash='#/job/'+x.j.id; })
    .catch(function(){ box.innerHTML='<p><b>Not started.</b> The pipeline server could not be reached.</p>'; }); }
function pollJob(jid,f){ var box=jobBox(f), t0=Date.now();
  (function tick(){ if(location.hash!=='#/job/'+jid) return;
    fetch(PIPE+'/jobs/'+encodeURIComponent(jid)).then(function(r){ return r.json(); }).then(function(j){
      if(j.status==='done'){ box.innerHTML='<p><b>Done.</b> Opening…</p>'; return fetch(j.bundle_url).then(function(r){ return r.json(); }).then(function(b){ b=scrubBundle(b); b.id=jid; b.short='your '+(b.sides.length===2?'pair':b.sides[0]); PAIRS[jid]=b; delete VIEWS[jid]; location.hash='#/p/'+jid+'/'+(b.sides.indexOf('paper')>=0?'paper':'blog'); }); }
      var last=(j.log||[]).filter(function(l){ return /\S/.test(l); }).slice(-1)[0]||'';
      box.innerHTML='<p><b>'+(j.status==='failed'?'The run failed.':(j.status==='queued'?'Waiting for a free slot…':'Coding…'))+'</b> '+(j.status==='failed'?esc(j.error||''):'This takes from several minutes to over an hour for a long paper. You can leave this page open, or keep this address and come back.')+'</p>'+
        (last?'<p class="small muted">'+esc(last.slice(0,240))+'</p>':'')+'<p class="small muted">Job '+esc(jid)+' · '+Math.round((Date.now()-t0)/1000)+' s on this page</p>';
      if(j.status!=='failed') setTimeout(tick,5000); })
    .catch(function(){ box.innerHTML='<p><b>The pipeline server could not be reached.</b> Trying again…</p>'; setTimeout(tick,15000); }); })(); }

function route(h){ var m=/^#\/p\/([^/]+)(?:\/(paper|blog|map))?(?:\/([^/]+))?/.exec((typeof h==='string'?h:location.hash)||'');   /* h: the render check passes the address directly (browsers throttle history calls) */ app.innerHTML='';
  if(m&&PAIRS[m[1]]){ var v=pairView(m[1]); app.appendChild(v.root); v.showTab(m[2]||'paper'); if(m[3]) v.select(m[2]||'paper', decodeURIComponent(m[3])); }
  else { var f=front(); app.appendChild(f); var jm=/^#\/job\/([A-Za-z0-9_-]+)$/.exec(location.hash||'');
    if(jm&&PIPE){ pollJob(jm[1],f); setTimeout(function(){ f.querySelector('.upload').scrollIntoView({block:'center'}); },0); }
    else if(location.hash&&location.hash!=='#/') history.replaceState(null,'','#/'); }
  window.scrollTo({top:0}); }
window.__skew=Object.assign(window.__skew||{}, {VIEWS:VIEWS, LUMP:LUMP, lumpP:lumpP, model:model, mapP:mapP, MAPG:MAPG, route:route, scrubBundle:scrubBundle});   // for headless checks only
try{ history.scrollRestoration='manual'; }catch(e){}
window.addEventListener('pageshow',function(){ if(/\/map\/(table-\d+)$/.test(location.hash||'')) route(); });
window.addEventListener('hashchange',route); route();
})();

// the ⓘ notes show at once on hover or keyboard focus (no help cursor, no browser tooltip delay).
(function(){ var tip=null; function el(){ if(!tip){ tip=document.createElement('div'); tip.className='tipbox'; tip.setAttribute('role','tooltip'); document.body.appendChild(tip); } return tip; }
  function show(t){ var x=t.getAttribute('data-tip'); if(!x) return; var b=el(); b.textContent=x; b.style.display='block'; var r=t.getBoundingClientRect(), w=b.offsetWidth, h=b.offsetHeight;
    var left=Math.min(Math.max(8,r.left+r.width/2-w/2),window.innerWidth-w-8), top=r.bottom+6; if(top+h>window.innerHeight-8) top=r.top-h-6; b.style.left=left+'px'; b.style.top=top+'px'; }
  function hide(){ if(tip) tip.style.display='none'; }
  document.addEventListener('mouseover',function(e){ var t=e.target.closest&&e.target.closest('[data-tip]'); if(t) show(t); else hide(); });
  document.addEventListener('focusin',function(e){ var t=e.target.closest&&e.target.closest('[data-tip]'); if(t) show(t); });
  document.addEventListener('focusout',hide); window.addEventListener('scroll',hide,true); })();
