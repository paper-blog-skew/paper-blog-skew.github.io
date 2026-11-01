"""Settings read from the environment, so the same code runs on a laptop, on a server and in a test.

  SKEWCODER_BACKEND   cli (default) | api
                      cli: the Claude Code CLI (`claude -p`) on whatever account is logged in to it.
                      api: the Anthropic API directly; needs ANTHROPIC_API_KEY.
  SKEWCODER_MODEL     the model for every coding step. Default: "opus" for the CLI (its alias), "claude-opus-5-5" for the API.
  SKEWCODER_EMBED_MODEL  sentence-transformer used for the similarity scores (default sentence-transformers/all-mpnet-base-v2).
Any of these, and ANTHROPIC_API_KEY, may be put in a .env file (see load_env_file); .env.example shows the form.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_env_file(path=None):
    """Secrets (ANTHROPIC_API_KEY) live in a file on the machine that runs the pipeline, never in the code or the site:
    SKEWCODER_ENV_FILE, else ~/.config/skewcoder/.env, else <repo>/.env. Lines KEY=value; a variable already set in the
    environment wins. Keep the key outside any synced or shared folder (a Dropbox folder shared with others would copy it to
    them); <repo>/.env is in .gitignore so it is never committed, but it is not hidden from a synced folder."""
    cands = [os.environ.get("SKEWCODER_ENV_FILE"), Path.home() / ".config" / "skewcoder" / ".env", REPO / ".env"]
    p = next((Path(c).expanduser() for c in cands if c and Path(c).expanduser().is_file()), None)
    if p is None: return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); k = k.strip().removeprefix("export ").strip()
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))


load_env_file()
CLI_ALIASES = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-4-5-20251001", "fable": "claude-fable-5-1"}


def backend():
    return os.environ.get("SKEWCODER_BACKEND", "cli").lower()


def model(explicit=None):
    m = explicit or os.environ.get("SKEWCODER_MODEL")
    if backend() == "api": return CLI_ALIASES.get(m or "opus", m)
    return m or "opus"


def embed_model():
    return os.environ.get("SKEWCODER_EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")
