#!/usr/bin/env python3
"""Run skewcoder from a checkout without installing it: python3 skewcoder.py <command> … (same as `skewcoder <command>`)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from skewcoder.cli import main

if __name__ == "__main__":
    main()
