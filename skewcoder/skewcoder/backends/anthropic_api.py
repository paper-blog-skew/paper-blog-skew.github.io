"""Backend `api`: the same coding session run directly on the Anthropic API (no Claude Code needed), for a server or for
anyone with an API key (ANTHROPIC_API_KEY). The model gets six tools that act only inside the sandbox folder (read, write,
edit, list, grep, and the audit `check.sh`); a path that leaves the sandbox is refused. The loop is the plain agent loop:
send, run the tool calls, send the results back, until the model ends its turn, the turn limit or the time limit is hit.

Prompt caching: one explicit breakpoint on the brief (the static system prompt) plus automatic caching of the growing
conversation, so a long session re-reads its own history at the cached rate.
"""
import fnmatch, json, re, subprocess, time
from pathlib import Path

MAX_TOKENS = 64000
SYSTEM_HEAD = ("You are a careful coder of scientific and corporate texts working inside a sandbox folder. Your tools read and "
               "write files only inside that folder; paths are relative to it. The coding brief follows; follow it exactly.")

TOOLS = [
    {"name": "read_file", "description": "Read a text file in the sandbox. Returns numbered lines. Use offset/limit for long files.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "offset": {"type": "integer", "description": "first line, 1-based"},
                                                       "limit": {"type": "integer", "description": "number of lines (default 2000)"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Create or overwrite a file in the sandbox with the given content.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace an exact string in a sandbox file. old_string must occur exactly once unless replace_all is true.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"},
                                                       "replace_all": {"type": "boolean"}}, "required": ["path", "old_string", "new_string"]}},
    {"name": "list_files", "description": "List sandbox files matching a glob pattern (default: all).",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}}},
    {"name": "grep", "description": "Search sandbox files for a regular expression; returns path:line:text, at most 200 lines.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "description": "file or folder (default: whole sandbox)"},
                                                       "ignore_case": {"type": "boolean"}}, "required": ["pattern"]}},
    {"name": "run_check", "description": "Run the audit on your output files (bash check.sh) and return its report.",
     "input_schema": {"type": "object", "properties": {}}},
]
for t in TOOLS: t["eager_input_streaming"] = True   # large file contents stream as they are written; inputs are validated below


class Sandbox:
    def __init__(self, root): self.root = Path(root).resolve()

    def path(self, p):
        q = (self.root / p).resolve()
        if q != self.root and self.root not in q.parents: raise ValueError(f"{p}: outside the sandbox")
        return q

    def read_file(self, path, offset=1, limit=2000):
        lines = self.path(path).read_text(encoding="utf-8").splitlines(); o = max(1, int(offset or 1)); n = int(limit or 2000)
        out = "\n".join(f"{i:6d}\t{l}" for i, l in enumerate(lines[o - 1:o - 1 + n], o))
        more = len(lines) - (o - 1 + n)
        return out + (f"\n… {more} more lines (use offset)" if more > 0 else "")

    def write_file(self, path, content):
        q = self.path(path); q.parent.mkdir(parents=True, exist_ok=True); q.write_text(content, encoding="utf-8")
        return f"wrote {path} ({len(content)} characters)"

    def edit_file(self, path, old_string, new_string, replace_all=False):
        q = self.path(path); s = q.read_text(encoding="utf-8"); n = s.count(old_string)
        if n == 0: return "error: old_string not found"
        if n > 1 and not replace_all: return f"error: old_string occurs {n} times; give more context or set replace_all"
        q.write_text(s.replace(old_string, new_string) if replace_all else s.replace(old_string, new_string, 1), encoding="utf-8")
        return f"edited {path} ({n if replace_all else 1} replacement(s))"

    def list_files(self, pattern="**/*"):
        fs = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())
        return "\n".join(f for f in fs if fnmatch.fnmatch(f, pattern or "*") or fnmatch.fnmatch(f, "*/" + (pattern or "*"))) or "(none)"

    def grep(self, pattern, path=".", ignore_case=False):
        rx = re.compile(pattern, re.I if ignore_case else 0); base = self.path(path or "."); out = []
        for f in ([base] if base.is_file() else sorted(base.rglob("*"))):
            if not f.is_file(): continue
            try: lines = f.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError: continue
            for i, l in enumerate(lines, 1):
                if rx.search(l): out.append(f"{f.relative_to(self.root)}:{i}:{l[:400]}")
                if len(out) >= 200: return "\n".join(out) + "\n… (stopped at 200)"
        return "\n".join(out) or "(no matches)"

    def run_check(self):
        p = subprocess.run(["bash", "check.sh"], cwd=self.root, capture_output=True, text=True, timeout=900)
        return ((p.stdout or "") + (p.stderr or ""))[-20000:] + f"\n(exit {p.returncode})"


def _call(box, name, args):
    if not isinstance(args, dict): return "error: tool input is not an object"
    need = next((t["input_schema"].get("required", []) for t in TOOLS if t["name"] == name), None)
    if need is None: return f"error: unknown tool {name}"
    bad = [k for k in need if not isinstance(args.get(k), str)]
    if bad: return f"error: missing or invalid {bad}"
    try: return getattr(box, name)(**args)
    except Exception as e: return f"error: {e}"


def run(work, prompt, brief_file, model, timeout=3600, max_turns=None):
    import anthropic
    client = anthropic.Anthropic()
    box = Sandbox(work); t0 = time.time(); max_turns = max_turns or 300
    system = [{"type": "text", "text": SYSTEM_HEAD},
              {"type": "text", "text": Path(brief_file).read_text(encoding="utf-8"), "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": prompt}]
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    models, turns, report, error, max_tok = set(), 0, None, None, MAX_TOKENS
    while True:
        if turns >= max_turns: error = f"turn limit {max_turns} reached"; break
        if time.time() - t0 > timeout: error = f"timeout after {timeout}s"; break
        try:
            with client.messages.stream(model=model, max_tokens=max_tok, system=system, tools=TOOLS, messages=messages,
                                        thinking={"type": "adaptive"}, cache_control={"type": "ephemeral"}) as stream:
                msg = stream.get_final_message()
        except ValueError as e:      # a tool input the parser could not read at all: ask again
            messages.append({"role": "user", "content": f"Your last tool call could not be parsed ({e}). Send it again."}); turns += 1; continue
        except anthropic.APIError as e:
            error = f"API error: {e}"; break
        turns += 1; models.add(msg.model)
        for k in usage: usage[k] += getattr(msg.usage, k, 0) or 0
        if msg.stop_reason == "refusal": error = "the model refused"; break
        uses = [b for b in msg.content if b.type == "tool_use"]
        if msg.stop_reason == "max_tokens" and uses:
            if max_tok < 128000: max_tok = 128000; continue      # a cut-off tool input is never run: retry the turn with more room
            error = "a tool call did not fit in the output limit"; break
        messages.append({"role": "assistant", "content": msg.content})
        if msg.stop_reason == "pause_turn": continue
        if not uses:
            report = "\n".join(b.text for b in msg.content if b.type == "text").strip() or None; break
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": u.id, "content": str(_call(box, u.name, u.input))} for u in uses]})
    return {"report": report, "model_used": sorted(models), "usage": usage, "cost_usd": None, "turns": turns, "error": error,
            "raw": {"seconds": round(time.time() - t0, 1), "tools": [t["name"] for t in TOOLS]}}
