"""A small job server so a website can run the pipeline on a paper and/or blog a visitor gives.
Standard library only. Each job runs `skewcoder run` as its own process, one (or SKEWCODER_WORKERS) at a time, and ends in a
bundle the site loads.

  POST /jobs              {"paper": "<arXiv id or link>", "blog": "<link>"}   (either may be missing; not both)
                          -> 202 {"id", "status_url"}
  GET  /jobs/<id>         -> {"id", "status": queued|running|done|failed, "paper", "blog", "created", "log": <last lines>,
                              "bundle_url": <when done>}
  GET  /bundles/<id>/...  the finished bundle (bundle.json, figs/)
  GET  /health            -> {"ok": true, "backend", "queued", "running"}

Settings (environment):
  SKEWCODER_BACKEND / SKEWCODER_MODEL     as for every run (config.py); a public server would use backend api with
                                          ANTHROPIC_API_KEY set on the server only, never in the website
  SKEWCODER_PUBLIC_URL     the address the site reaches this server at (default http://<host>:<port>); figure links use it
  SKEWCODER_ALLOWED_ORIGINS  comma-separated origins allowed to call it from a browser (default: none but localhost)
  SKEWCODER_ACCESS_TOKEN   if set, POST /jobs needs "Authorization: Bearer <token>"
  SKEWCODER_MAX_JOBS_PER_DAY  default 10; SKEWCODER_WORKERS default 1; SKEWCODER_JOB_TIMEOUT seconds per step, default 3600

Inputs from the web are only ever links (http/https) or arXiv ids, never paths on this machine. What a public deployment
still needs (decided later, with the API key): who may submit, a spending cap, and where it runs.
"""
import datetime as dt, json, os, queue, re, secrets, subprocess, sys, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from . import config
from .fetch import arxiv_id

PKG_PARENT = Path(__file__).resolve().parent.parent


def public_host(url):
    """A link a visitor gives must point at a public address: the server never fetches from its own network."""
    import ipaddress, socket, urllib.parse
    host = urllib.parse.urlparse(url).hostname
    if not host: return False
    try: addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except OSError: return False
    return all(ipaddress.ip_address(a.split("%")[0]).is_global for a in addrs)


def ok_source(s, kind):
    if not s: return True
    s = s.strip()
    if re.match(r"^https?://[^\s]+$", s): return public_host(s)
    return kind == "paper" and arxiv_id(s) is not None


class Jobs:
    def __init__(self, W):
        self.W = Path(W).resolve(); self.dir = self.W / "jobs"; self.dir.mkdir(parents=True, exist_ok=True)
        self.q = queue.Queue(); self.lock = threading.Lock(); self.running = 0
        for f in self.dir.glob("*.json"):           # jobs cut off by a restart are marked failed, not rerun silently
            j = json.loads(f.read_text(encoding="utf-8"))
            if j["status"] in ("queued", "running"): j["status"] = "failed"; j["error"] = "server restarted"; self.save(j)

    def save(self, j): (self.dir / f"{j['id']}.json").write_text(json.dumps(j, indent=1, ensure_ascii=False), encoding="utf-8")

    def get(self, jid):
        p = self.dir / f"{jid}.json"
        return json.loads(p.read_text(encoding="utf-8")) if re.fullmatch(r"[A-Za-z0-9_-]+", jid or "") and p.exists() else None

    def today(self):
        d = dt.date.today().isoformat(); return sum(1 for f in self.dir.glob("*.json") if json.loads(f.read_text(encoding="utf-8")).get("created", "").startswith(d))

    def submit(self, paper, blog):
        jid = dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
        j = {"id": jid, "status": "queued", "paper": paper or None, "blog": blog or None, "created": dt.datetime.now().isoformat(timespec="seconds")}
        self.save(j); self.q.put(jid); return j

    def worker(self, public):
        while True:
            jid = self.q.get(); j = self.get(jid); j["status"] = "running"; j["started"] = dt.datetime.now().isoformat(timespec="seconds"); self.save(j)
            with self.lock: self.running += 1
            out = self.W / "bundles" / jid; log = self.dir / f"{jid}.log"
            cmd = [sys.executable, "-m", "skewcoder", "run", "--workspace", str(self.W / "units"), "--out", str(out), "--id", jid,
                   "--fig-base", f"{public}/bundles/{jid}", "--timeout", os.environ.get("SKEWCODER_JOB_TIMEOUT", "3600")]
            if j["paper"]: cmd += ["--paper", j["paper"], "--paper-key", f"paper-{jid}"]
            if j["blog"]: cmd += ["--blog", j["blog"], "--blog-key", f"blog-{jid}"]
            env = dict(os.environ, PYTHONPATH=str(PKG_PARENT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
            with open(log, "w", encoding="utf-8") as lf:
                rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env).returncode
            j = self.get(jid); j["finished"] = dt.datetime.now().isoformat(timespec="seconds")
            if rc == 0 and (out / "bundle.json").exists(): j["status"] = "done"; j["bundle_url"] = f"{public}/bundles/{jid}/bundle.json"
            else: j["status"] = "failed"; j["error"] = f"exit {rc}"
            self.save(j)
            with self.lock: self.running -= 1


def serve(workspace, host="127.0.0.1", port=8765):
    jobs = Jobs(workspace)
    public = os.environ.get("SKEWCODER_PUBLIC_URL", f"http://{host}:{port}").rstrip("/")
    origins = [o.strip() for o in os.environ.get("SKEWCODER_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    token = os.environ.get("SKEWCODER_ACCESS_TOKEN"); cap = int(os.environ.get("SKEWCODER_MAX_JOBS_PER_DAY", "10"))
    for _ in range(int(os.environ.get("SKEWCODER_WORKERS", "1"))): threading.Thread(target=jobs.worker, args=(public,), daemon=True).start()

    class H(BaseHTTPRequestHandler):
        def cors(self):
            o = self.headers.get("Origin", "")
            if o and (o in origins or re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", o) or o == "null"):
                self.send_header("Access-Control-Allow-Origin", o); self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization"); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def reply(self, code, obj=None, body=None, ctype="application/json"):
            data = body if body is not None else json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data))); self.cors(); self.end_headers(); self.wfile.write(data)

        def do_OPTIONS(self): self.send_response(204); self.cors(); self.end_headers()

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/health": return self.reply(200, {"ok": True, "backend": config.backend(), "queued": jobs.q.qsize(), "running": jobs.running})
            m = re.fullmatch(r"/jobs/([A-Za-z0-9_-]+)", path)
            if m:
                j = jobs.get(m.group(1))
                if not j: return self.reply(404, {"error": "no such job"})
                lp = jobs.dir / f"{j['id']}.log"; j = dict(j, log=lp.read_text(encoding="utf-8", errors="replace").splitlines()[-30:] if lp.exists() else [])
                return self.reply(200, j)
            m = re.fullmatch(r"/bundles/([A-Za-z0-9_-]+)/((?:figs/[A-Za-z0-9._-]+/)?[A-Za-z0-9._-]+)", path)
            if m:
                f = (jobs.W / "bundles" / m.group(1) / m.group(2)).resolve()
                if (jobs.W / "bundles") not in f.parents or not f.is_file(): return self.reply(404, {"error": "not found"})
                ct = {".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}.get(f.suffix.lower(), "application/octet-stream")
                return self.reply(200, body=f.read_bytes(), ctype=ct)
            self.reply(404, {"error": "not found"})

        def do_POST(self):
            if self.path.split("?")[0] != "/jobs": return self.reply(404, {"error": "not found"})
            if token and self.headers.get("Authorization", "") != f"Bearer {token}": return self.reply(401, {"error": "not allowed"})
            try: body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 10000)) or b"{}")
            except Exception: return self.reply(400, {"error": "send JSON"})
            paper, blog = (body.get("paper") or "").strip(), (body.get("blog") or "").strip()
            if not (paper or blog): return self.reply(400, {"error": "give a paper, a blog, or both"})
            if not ok_source(paper, "paper") or not ok_source(blog, "blog"): return self.reply(400, {"error": "give links (http/https) or an arXiv id"})
            if jobs.today() >= cap: return self.reply(429, {"error": f"the daily limit of {cap} runs is reached; try tomorrow"})
            j = jobs.submit(paper, blog); self.reply(202, {"id": j["id"], "status_url": f"{public}/jobs/{j['id']}"})

        def log_message(self, fmt, *args): sys.stderr.write("  [server] " + (fmt % args) + "\n")

    print(f"skewcoder server on http://{host}:{port} (public {public}); backend {config.backend()}; workspace {jobs.W}; {cap} jobs/day", flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()
