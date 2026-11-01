"""How one coding session is run. Every backend gets the same thing: a sandbox folder holding only what the coder may read,
a task prompt, the brief (system prompt), and permission to read/write files inside the sandbox and to run `bash check.sh`
(the audit) and nothing else. Every backend returns the same record:

  {"report": <the coder's final text or None>, "model_used": [...], "usage": {...}, "cost_usd": <float or None>,
   "turns": <int>, "error": <str or None>, "raw": {...backend-specific...}}
"""
from .. import config


def get(name=None):
    name = (name or config.backend()).lower()
    if name == "cli":
        from . import claude_cli; return claude_cli
    if name == "api":
        from . import anthropic_api; return anthropic_api
    raise SystemExit(f"unknown backend {name!r}: use cli or api (SKEWCODER_BACKEND)")
