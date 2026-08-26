"""Command line front end for the skill linter.

Orchestrates core, checks_structure.run, and checks_prose.run, then formats
results, applies the baseline, and picks the exit code. Owns no checks.
"""

import argparse
import json
import sys
import time
from pathlib import Path


def _default_root() -> Path:
    # tools/skill_lint/cli.py -> tools/skill_lint -> tools -> repo root
    return Path(__file__).resolve().parent.parent.parent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lint_skills.py",
        description="Lint skill directories for structure and prose rules.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PATH",
        help="Repo root to lint. Defaults to the repo containing this script.",
    )
    parser.add_argument(
        "--baseline",
        metavar="FILE",
        help="Suppress up to the per-key count recorded in FILE. Report the rest.",
    )
    parser.add_argument(
        "--write-baseline",
        metavar="FILE",
        help="Write current findings to FILE as a baseline, then exit.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. Text is grouped by file, json is a flat list.",
    )
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Let warnings drive the exit code alongside errors.",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=5000,
        metavar="N",
        help="Body word budget for the SK102 check.",
    )
    parser.add_argument(
        "--check-installed",
        action="store_true",
        help="Also emit SK106 for a skill missing a symlink in the local skills directory.",
    )
    parser.add_argument(
        "--only",
        metavar="CODES",
        help="Comma-separated finding codes. Report only these.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the summary line.",
    )
    parser.add_argument(
        "--timing",
        action="store_true",
        help="Print elapsed run time to stderr.",
    )
    return parser


def _finding_dict(finding) -> dict:
    return {
        "code": finding.code,
        "level": finding.level,
        "path": finding.path,
        "line": finding.line,
        "message": finding.message,
    }


def _print_text(findings) -> None:
    for f in sorted(findings, key=lambda f: (f.path, f.line, f.code)):
        print(f"{f.path}:{f.line}: {f.level.upper()} {f.code} {f.message}")


def _summary_line(findings, file_count: int) -> str:
    errors = sum(1 for f in findings if f.level == "error")
    warnings = sum(1 for f in findings if f.level == "warning")
    return f"{errors} errors, {warnings} warnings across {file_count} files"


BASELINE_VERSION = 2


def _count_by_key(findings) -> dict:
    counts = {}
    for f in findings:
        counts[f.key()] = counts.get(f.key(), 0) + 1
    return counts


def _write_baseline(findings, path: str) -> int:
    counts = _count_by_key(findings)
    payload = {
        "version": BASELINE_VERSION,
        "counts": {k: counts[k] for k in sorted(counts)},
    }
    text = json.dumps(payload, indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8")
    print(f"wrote {len(findings)} findings to {path}")
    return 0


class BaselineFormatError(Exception):
    pass


def _load_baseline_counts(path: str):
    # None signals a missing file, distinct from an empty baseline.
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    version = data.get("version")
    if version != BASELINE_VERSION:
        raise BaselineFormatError(
            f"baseline {path} is version {version!r}, this linter needs version "
            f"{BASELINE_VERSION}. Regenerate it with: make baseline"
        )
    counts = data.get("counts")
    if not isinstance(counts, dict):
        raise BaselineFormatError(
            f"baseline {path} has no counts map. Regenerate it with: make baseline"
        )
    return {str(k): int(v) for k, v in counts.items()}


def _apply_baseline(findings, baseline_counts: dict):
    """Report only the occurrences beyond each key's baseline count.

    Keys carry no line number, so a key can cover many findings. Counting keeps
    line-shift immunity while still catching an extra occurrence.
    """
    by_key = {}
    for f in findings:
        by_key.setdefault(f.key(), []).append(f)

    excess = []
    for key, group in by_key.items():
        allowed = baseline_counts.get(key, 0)
        if len(group) <= allowed:
            continue
        # Skip the oldest lines so the reported findings carry real line numbers.
        excess.extend(sorted(group, key=lambda f: f.line)[allowed:])
    return excess


def _text_by_path(md_paths, root: Path) -> dict:
    result = {}
    for p in md_paths:
        rel = p.resolve().relative_to(root).as_posix()
        result[rel] = p.read_text(encoding="utf-8")
    return result


def _run(args) -> int:
    from . import core, checks_prose, checks_structure

    root = Path(args.path).resolve() if args.path else _default_root()

    skills = core.discover_skills(root)
    md_paths = core.repo_markdown(root)

    findings = []
    findings.extend(
        checks_structure.run(
            skills, root, max_words=args.max_words, check_installed=args.check_installed
        )
    )
    findings.extend(checks_prose.run(md_paths, root))

    findings = core.apply_suppressions(findings, _text_by_path(md_paths, root))

    if args.only:
        codes = {c.strip() for c in args.only.split(",") if c.strip()}
        findings = [f for f in findings if f.code in codes]

    if args.write_baseline:
        return _write_baseline(findings, args.write_baseline)

    if args.baseline:
        try:
            baseline_counts = _load_baseline_counts(args.baseline)
        except BaselineFormatError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if baseline_counts is None:
            print(f"error: baseline file not found: {args.baseline}", file=sys.stderr)
            return 2
        findings = _apply_baseline(findings, baseline_counts)

    if args.format == "json":
        if not args.quiet:
            print(json.dumps([_finding_dict(f) for f in findings], indent=2))
    else:
        if not args.quiet:
            _print_text(findings)
        print(_summary_line(findings, len(md_paths)))

    errors = sum(1 for f in findings if f.level == "error")
    warnings = sum(1 for f in findings if f.level == "warning")
    if errors or (args.warnings_as_errors and warnings):
        return 1
    return 0


def main(argv) -> int:
    start = time.perf_counter()
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 0 on --help, 2 on a bad flag. Keep that split.
        return 0 if exc.code in (0, None) else 2

    try:
        return _run(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if args.timing:
            elapsed = time.perf_counter() - start
            print(f"lint_skills: {elapsed:.3f}s", file=sys.stderr)
