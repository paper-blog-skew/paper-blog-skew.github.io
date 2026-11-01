"""Backend `cli`: the Claude Code CLI run headless inside the sandbox (`claude -p`). Uses whatever account is logged in to
Claude Code on this machine; runs count against that account's usage. Tools allowed: Read, Write, Edit, Glob, Grep and the
single shell command `bash check.sh`; no MCP servers; every other tool call is denied in headless mode."""
import json, os, subprocess


def command(prompt, brief_file, model, max_turns=None):
    cmd = ["claude", "-p", prompt, "--append-system-prompt-file", str(brief_file), "--model", model,
           "--output-format", "json", "--no-session-persistence", "--permission-prompts", "none",
           "--allowedTools", "Read", "Write", "Edit", "Glob", "Grep", "Bash(bash check.sh)",
           "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']   # no MCP servers: a coder needs none
    if max_turns: cmd += ["--max-turns", str(max_turns)]
    return cmd


def run(work, prompt, brief_file, model, timeout=3600, max_turns=None):
    cmd = command(prompt, brief_file, model, max_turns)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}   # allow launching from inside a Claude Code session
    try:
        p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=timeout); out, err = p.stdout, p.stderr
    except FileNotFoundError:
        return {"report": None, "model_used": [], "usage": {}, "cost_usd": None, "turns": 0, "error": "the `claude` CLI is not installed (backend cli); set SKEWCODER_BACKEND=api to use the API", "raw": {}}
    except subprocess.TimeoutExpired as e:
        out, err = (e.stdout or ""), f"timeout after {timeout}s"
        if isinstance(out, bytes): out = out.decode("utf-8", "replace")
    rec = {"command": cmd[:1] + ["<prompt>"] + cmd[3:]}
    try:
        j = json.loads(out)
        return {"report": j.get("result"), "model_used": list((j.get("modelUsage") or {}).keys()), "usage": j.get("modelUsage") or {},
                "cost_usd": j.get("total_cost_usd"), "turns": j.get("num_turns"), "error": "cli reported an error" if j.get("is_error") else None,
                "raw": dict(rec, **{k: j.get(k) for k in ("is_error", "subtype", "num_turns", "duration_ms", "session_id")}, stderr=(err or "")[-2000:])}
    except Exception:
        return {"report": None, "model_used": [], "usage": {}, "cost_usd": None, "turns": None, "error": "no JSON from the CLI",
                "raw": dict(rec, raw_stdout=(out or "")[-4000:], stderr=(err or "")[-4000:])}
