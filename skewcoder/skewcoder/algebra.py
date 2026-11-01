"""The paper's equations reduced mechanically: redundancy, rank, minimal linked groups, directness.

Input: the paper's relations (relations.html) and the coder's formulas for them (equations.json, brief paper_algebra.md).
Equalities are reduced here; statements that are not equalities keep the pairs the coder read off them.

  redundancy   An equality that follows from the earlier ones adds nothing. For polynomial equalities (after clearing
               denominators) the test is ideal membership: the new equation is divided by a Gröbner basis of the
               earlier ones (Buchberger's algorithm, via SymPy) and is redundant when the remainder is zero. An
               equality with exp, log or a trigonometric function cannot be divided this way; for it the test is
               whether it raises the rank below.
  rank         The number of independent relationships: the rank of the system's Jacobian at a generic point of the
               set of values that satisfy every equality (found numerically from a random complex start).
  linked group A set of metrics in which knowing all but one leaves the last with only finitely many possible values,
               whatever the other quantities are. At a generic point this holds exactly when the metrics' differentials,
               restricted to the solution set's tangent space, are linearly dependent. A minimal linked group (a
               circuit of this dependence structure) is one in which every member is needed.
  links        Two metrics are linked when they lie in a common minimal linked group; this is the case exactly when
               they lie in the same connected part of the dependence structure. Directness is the size of the
               smallest minimal linked group the two share (searched up to MAX_GROUP; larger is reported as such).
  regimes      Equations stated under different conditions are not combined into one system: each condition gives
               its own system (the unconditioned equations plus those under that condition). A pair is linked when it
               is linked in some regime; its directness is the smallest over the regimes.
"""
import itertools, json, re, signal
from pathlib import Path
import numpy as np
import sympy as sp

MAX_GROUP = 6            # largest minimal linked group searched for a pair's directness
POLY_TIMEOUT = 20        # seconds allowed for one Gröbner computation
TOL = 1e-8
FUNCS = {"sqrt": sp.sqrt, "exp": sp.exp, "log": sp.log, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "pi": sp.pi, "imag_unit": sp.I}
KINDS = ("equality", "not algebraic")


# ---------------------------------------------------------------- parsing and the coder's check
def parse_expr(s, allowed):
    """A formula string -> SymPy expression over the allowed symbol names only (no other names, no attribute access).
    Every symbol is read as a plain symbol, even when its name is also a SymPy name (I, E, Q, N, S, O, beta …): names are
    swapped for placeholders before parsing and swapped back after. `imag_unit` is the imaginary unit."""
    if not isinstance(s, str) or not s.strip(): raise ValueError("empty formula")
    if re.search(r"__|\bimport\b|\blambda\b|[\[\]{};]|\.\s*[A-Za-z_]", s): raise ValueError(f"not allowed in a formula: {s!r}")
    names = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", s))
    bad = sorted(n for n in names if n not in allowed and n not in FUNCS)
    if bad: raise ValueError(f"unknown symbol(s) {bad}")
    ph = {n: f"zz{i}zz" for i, n in enumerate(sorted(n for n in names if n in allowed))}
    body = re.sub(r"[A-Za-z_][A-Za-z_0-9]*", lambda m: ph.get(m.group(0), m.group(0)), s)
    loc = dict(FUNCS); loc.update({v: sp.Symbol(v) for v in ph.values()})
    e = sp.sympify(body, locals=loc, rational=True)
    return e.xreplace({sp.Symbol(v): sp.Symbol(n) for n, v in ph.items()})


def check(eqdoc, rels, keys):
    """Failures for equations.json against the frozen relations (list of {kind, where, detail})."""
    F = []; fail = lambda k, w, d: F.append({"kind": k, "where": w, "detail": d})
    aux = eqdoc.get("aux") or {}
    for a in aux:
        if a in keys: fail("aux-is-a-metric", a, "an auxiliary symbol may not reuse a metric key")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", a) or a in FUNCS: fail("aux-bad-name", a, "")
    R = {r["id"]: r for r in rels}; seen = set()
    for ent in eqdoc.get("relations") or []:
        rid = ent.get("rel")
        if rid not in R: fail("unknown-relation", str(rid), ""); continue
        seen.add(rid); r = R[rid]; allowed = set(r["vars"]) | set(aux); covered = set()
        for i, s in enumerate(ent.get("statements") or []):
            w = f"{rid}#{i}"
            if s.get("kind") not in KINDS: fail("bad-kind", w, str(s.get("kind"))); continue
            try: n = int(s.get("eq"))
            except Exception: fail("bad-eq", w, str(s.get("eq"))); continue
            if n not in r["nums"]: fail("eq-not-in-relation", w, f"({n}) is not in {r['eq']}")
            covered.add(n)
            if s["kind"] == "equality":
                for side in ("lhs", "rhs"):
                    try: parse_expr(s.get(side), allowed)
                    except Exception as e: fail("formula", f"{w}.{side}", str(e)[:200])
            else:
                if not s.get("reason"): fail("no-reason", w, "a statement that is not an equality needs its reason")
                for p in (s.get("pairs") or []) + (s.get("independent") or []):
                    if not (isinstance(p, list) and len(p) == 2 and all(x in r["vars"] for x in p) and p[0] != p[1]):
                        fail("bad-pair", w, str(p))
        for n in set(r["nums"]) - covered: fail("equation-not-covered", f"{rid} ({n})", "every equation number of the relation needs a statement")
    for rid in set(R) - seen: fail("relation-not-covered", rid, "every relation needs an entry")
    return F


# ---------------------------------------------------------------- numerics
class _Timeout(Exception): pass


def _with_timeout(fn, secs):
    def h(*_): raise _Timeout()
    old = signal.signal(signal.SIGALRM, h); signal.alarm(secs)
    try: return fn()
    finally: signal.alarm(0); signal.signal(signal.SIGALRM, old)


def _poly(expr, syms):
    """numerator of expr as a polynomial over syms with rational coefficients, or None when it is not polynomial."""
    num = sp.numer(sp.together(expr))
    try:
        P = sp.Poly(sp.expand(num), *syms, domain="QQ")
        return P.as_expr()
    except Exception:
        return None


def _point(exprs, syms, seeds=8):
    """A generic point of {exprs = 0}: Gauss–Newton from random complex starts. Returns (values, J) or (None, None)."""
    f = sp.lambdify(syms, exprs, "numpy"); Jx = sp.Matrix(exprs).jacobian(syms); jf = sp.lambdify(syms, Jx, "numpy")
    rng = np.random.default_rng(20261101)
    for _ in range(seeds):
        x = rng.normal(size=len(syms)) + 1j * rng.normal(size=len(syms))
        try:
            with np.errstate(all="ignore"):
                for _ in range(200):
                    F = np.asarray(f(*x), dtype=complex).ravel()
                    if not np.all(np.isfinite(F)): break
                    if np.linalg.norm(F) < 1e-12: break
                    J = np.asarray(jf(*x), dtype=complex).reshape(len(exprs), len(syms))
                    x = x - np.linalg.pinv(J) @ F
                F = np.asarray(f(*x), dtype=complex).ravel()
                if np.all(np.isfinite(F)) and np.linalg.norm(F) < 1e-9:
                    J = np.asarray(jf(*x), dtype=complex).reshape(len(exprs), len(syms))
                    if np.all(np.isfinite(J)): return x, J
        except Exception:
            continue
    return None, None


def _rank(M):
    if M.size == 0: return 0
    s = np.linalg.svd(M, compute_uv=False)
    return int((s > TOL * max(1.0, s[0])).sum())


def _kernel(J):
    u, s, vh = np.linalg.svd(J)
    r = int((s > TOL * max(1.0, s[0] if len(s) else 1.0)).sum())
    return vh[r:].conj().T          # columns span the tangent space (n x (n-r))


# ---------------------------------------------------------------- one system (a regime)
def _system(stmts, metric_keys):
    """stmts: [{rel, eq, expr}] equalities. Returns redundancy flags, rank, and the dependence structure on the metrics."""
    out = {"statements": [], "rank": 0, "components": [], "loops": [], "pairs": {}, "notes": []}
    # connected components of statements through shared symbols (each is reduced on its own)
    syms_of = [sorted(s["expr"].free_symbols, key=str) for s in stmts]
    parent = list(range(len(stmts)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    owner = {}
    for i, ss in enumerate(syms_of):
        for x in ss:
            if x in owner: parent[find(i)] = find(owner[x])
            else: owner[x] = i
    comps = {}
    for i in range(len(stmts)): comps.setdefault(find(i), []).append(i)
    for idx in comps.values():
        idx.sort(key=lambda i: (stmts[i]["eq"], i))
        syms = sorted({x for i in idx for x in syms_of[i]}, key=str)
        exprs = [stmts[i]["expr"] for i in idx]
        # redundancy: Gröbner ideal membership when every equality is polynomial, else rank increase
        polys = [_poly(e, syms) for e in exprs]
        red = [False] * len(idx); method = "groebner" if all(p is not None for p in polys) else "jacobian"
        x, J = _point(exprs, syms)
        if x is None:
            out["notes"].append(f"no solution point found for {sorted({stmts[i]['rel'] for i in idx})}: these equations are kept as stated, every pair of their metrics linked")
            for i in idx:
                out["statements"].append({"rel": stmts[i]["rel"], "eq": stmts[i]["eq"], "redundant": None, "method": "none (no solution point)"})
            mk = [str(s) for s in syms if str(s) in metric_keys]
            for a, b in itertools.combinations(sorted(mk), 2):
                out["pairs"][(a, b)] = {"size": None, "group": None, "rels": sorted({stmts[i]["rel"] for i in idx}), "how": "fallback"}
            continue
        if method == "groebner":
            kept = []
            for j, p in enumerate(polys):
                if kept:
                    try:
                        G = _with_timeout(lambda: sp.groebner(kept, *syms, order="grevlex", domain="QQ"), POLY_TIMEOUT)
                        _, rem = G.reduce(p); red[j] = (sp.expand(rem) == 0)
                    except _Timeout:
                        method = "jacobian"; red = [False] * len(idx); break
                if not red[j]: kept.append(p)
        if method == "jacobian":
            prev = 0
            for j in range(len(idx)):
                r = _rank(J[: j + 1]); red[j] = (r == prev); prev = r
        for j, i in enumerate(idx):
            out["statements"].append({"rel": stmts[i]["rel"], "eq": stmts[i]["eq"], "redundant": bool(red[j]), "method": method})
        rk = _rank(J); out["rank"] += rk
        # dependence structure on the metrics: differentials restricted to the tangent space
        K = _kernel(J)
        mi = [k for k, s in enumerate(syms) if str(s) in metric_keys]
        names = [str(syms[k]) for k in mi]
        V = K[mi, :] if K.size else np.zeros((len(mi), 0))
        cache = {}
        def rk_of(S):
            S = tuple(sorted(S))
            if S not in cache: cache[S] = _rank(V[list(S), :]) if S else 0
            return cache[S]
        loops = [names[t] for t in range(len(mi)) if rk_of([t]) == 0]
        out["loops"] += loops
        # connected parts via fundamental circuits w.r.t. a greedy basis
        basis = []
        for t in range(len(mi)):
            if rk_of(basis + [t]) > len(basis): basis.append(t)
        par = list(range(len(mi)))
        def f2(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        for e in range(len(mi)):
            if e in basis or rk_of([e]) == 0: continue
            # fundamental circuit: basis elements whose removal makes e independent again
            C = [e] + [b for b in basis if rk_of([x for x in basis if x != b] + [e]) == len(basis)]
            for c in C[1:]: par[f2(c)] = f2(e)
        parts = {}
        for t in range(len(mi)):
            if rk_of([t]) == 0: continue
            parts.setdefault(f2(t), []).append(t)
        for P in parts.values():
            if len(P) < 2: continue
            out["components"].append(sorted(names[t] for t in P))
            rels_here = sorted({stmts[i]["rel"] for i in idx})
            for a, b in itertools.combinations(P, 2):
                size, group = None, None
                rest = [t for t in P if t not in (a, b)]
                for s in range(2, min(MAX_GROUP, len(P)) + 1):
                    for extra in itertools.combinations(rest, s - 2):
                        S = [a, b] + list(extra)
                        if rk_of(S) == s - 1 and all(rk_of([x for x in S if x != y]) == s - 1 for y in S):
                            size, group = s, sorted(names[t] for t in S); break
                    if size: break
                # the equations that carry the group: those containing any of its metrics, in this component
                gnames = set(group or [names[a], names[b]])
                wit = sorted({stmts[i]["rel"] for i in idx if gnames & {str(z) for z in syms_of[i]}}) or rels_here
                k = tuple(sorted((names[a], names[b])))
                out["pairs"][k] = {"size": size, "group": group, "rels": wit, "how": "algebra"}
    return out


# ---------------------------------------------------------------- the paper
def analyze(eqdoc, rels, keys):
    """eqdoc: equations.json; rels: parsed relations (id, nums, vars, cond, cond_vars); keys: the paper's metric keys."""
    aux = eqdoc.get("aux") or {}; R = {r["id"]: r for r in rels}
    eqs, model_pairs, indep, cond_of = [], [], [], {}
    for ent in eqdoc.get("relations") or []:
        r = R.get(ent.get("rel"))
        if not r: continue
        cond = (r.get("cond") or "").strip(); cond_of[r["id"]] = cond
        allowed = set(r["vars"]) | set(aux)
        for s in ent.get("statements") or []:
            if s.get("kind") == "equality":
                e = parse_expr(s["lhs"], allowed) - parse_expr(s["rhs"], allowed)
                if e == 0: continue
                eqs.append({"rel": r["id"], "eq": int(s["eq"]), "expr": e, "cond": cond})
            else:
                for a, b in s.get("pairs") or []: model_pairs.append({"a": a, "b": b, "rel": r["id"], "eq": int(s["eq"]), "reason": s.get("reason", "")})
                for a, b in s.get("independent") or []: indep.append({"a": a, "b": b, "rel": r["id"], "eq": int(s["eq"])})
    regimes = sorted({e["cond"] for e in eqs if e["cond"]})
    systems = [("", [e for e in eqs if not e["cond"]])] + [(c, [e for e in eqs if e["cond"] in ("", c)]) for c in regimes]
    links, ranks, stmts_out, notes, comps = {}, {}, {}, [], []
    for c, S in systems:
        if not S: continue
        res = _system(S, set(keys)); ranks[c or "(no condition)"] = res["rank"]; notes += res["notes"]; comps += res["components"]
        for st in res["statements"]:
            k = (st["rel"], st["eq"])
            if k not in stmts_out or (c == "" ): stmts_out[k] = dict(st, regime=c or None)
        for (a, b), v in res["pairs"].items():
            cur = links.get((a, b))
            if cur is None or (v["size"] or 99) < (cur["size"] or 99):
                links[(a, b)] = dict(v, regime=c or None, rels=sorted(set(v["rels"]) | set(cur["rels"] if cur else [])))
            else: cur["rels"] = sorted(set(cur["rels"]) | set(v["rels"]))
    L = [{"a": a, "b": b, "src": "algebra", **v} for (a, b), v in sorted(links.items())]
    for m in model_pairs:
        a, b = sorted((m["a"], m["b"]))
        L.append({"a": a, "b": b, "src": "model", "size": None, "group": None, "rels": [m["rel"]], "reason": m["reason"], "regime": cond_of.get(m["rel"]) or None, "how": "model"})
    n_eq = len(eqs); n_red = sum(1 for v in stmts_out.values() if v.get("redundant"))
    return {"format": "skew-algebra/1", "max_group": MAX_GROUP,
            "counts": {"equalities": n_eq, "redundant": n_red, "not_algebraic": sum(1 for ent in eqdoc.get("relations") or [] for s in ent.get("statements") or [] if s.get("kind") != "equality"),
                       "algebra_links": len(links), "model_links": len(model_pairs), "regimes": len(regimes)},
            "rank": ranks, "statements": [dict(v) for v in stmts_out.values()], "links": L, "independent": indep,
            "groups": sorted({tuple(g) for g in comps}), "notes": notes}


def run_unit(unit_dir):
    """coding/equations.json + coding/relations.html -> coding/algebra.json."""
    from .bundle import parse_relations
    cd = Path(unit_dir) / "coding"
    rels = parse_relations((cd / "relations.html").read_text(encoding="utf-8"))
    keys = [q["key"] for q in json.loads((cd / "paper_quantities.json").read_text(encoding="utf-8"))["paper_quantities"]]
    A = analyze(json.loads((cd / "equations.json").read_text(encoding="utf-8")), rels, keys)
    A["groups"] = [list(g) for g in A["groups"]]
    (cd / "algebra.json").write_text(json.dumps(A, ensure_ascii=False, indent=1), encoding="utf-8")
    c = A["counts"]
    print(f"  {Path(unit_dir).name}: {c['equalities']} equalities ({c['redundant']} redundant), {c['not_algebraic']} not algebraic; "
          f"rank {A['rank']}; {c['algebra_links']} linked pairs by algebra, {c['model_links']} by the model's reading; {len(A['notes'])} note(s)")
    return A
