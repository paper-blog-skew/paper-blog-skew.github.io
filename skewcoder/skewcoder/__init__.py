"""skewcoder — code a paper and/or the blog post about it, and map one onto the other.

Six parts, run as subcommands of skewcoder.py:
  text     (a) rebuild a paper or a blog as text blocks           -> <unit>/text/
  metrics  (b) code the metrics of a paper or a blog              -> <unit>/coding/ (LLM, sandboxed, that text only)
  links    (c) code the links between the metrics already coded  -> <unit>/coding/ (LLM; may only join coded metrics)
  map      (d) map a blog's metrics onto its paper's metrics      -> <blog>/coding/blog_metrics.json (LLM; both frozen)
  audit    (e) the validation gates, mechanical                   -> report; exit 1 on failure
The compare step (before/after counts) is not part of this tool; it lives with the site.
"""
__version__ = "1.0.0"
