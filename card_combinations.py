"""card_combinations — re-export wrapper for backward compatibility.

Implementation lives in core/. CLI reference docs are in core/cli.py.

Usage:
    python card_combinations.py [options]       # run the CLI
    import card_combinations as cc             # import the full API
"""
from core import *          # noqa: F401,F403  — re-exports Card, FilterSpec, etc.
from core.cli import main   # noqa: F401

if __name__ == "__main__":
    main()
