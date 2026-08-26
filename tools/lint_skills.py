#!/usr/bin/env python3
"""Entry point. Fixes sys.path so skill_lint imports from any cwd."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_lint import cli

if __name__ == "__main__":
    sys.exit(cli.main(sys.argv[1:]))
