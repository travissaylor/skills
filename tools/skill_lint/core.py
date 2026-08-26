"""Shared foundation for the skill linter: parsing, discovery, masking, suppressions.

Standard library only. No checks live here.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Finding",
    "Skill",
    "parse_frontmatter",
    "discover_skills",
    "repo_markdown",
    "mask_fenced",
    "mask_inline_code",
    "mask_blockquotes",
    "mask_urls",
    "prose_view",
    "code_spans",
    "bold_spans",
    "headings",
    "suppressions",
    "apply_suppressions",
]

SKIP_DIRS = frozenset({"tools", "node_modules"})


# --- Findings -----------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    code: str
    level: str
    path: str
    line: int
    message: str

    def key(self) -> str:
        """Stable identity for baseline matching.

        The line number is deliberately excluded so a baseline survives
        unrelated edits that shift lines.
        """
        return f"{self.code}\t{self.path}\t{self.message}"


# --- Frontmatter --------------------------------------------------------------

_FM_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
_QUOTE_PAIRS = (('"', '"'), ("'", "'"))


def _strip_quotes(value: str) -> str:
    """Strip one matching outer quote pair."""
    if len(value) >= 2:
        for open_q, close_q in _QUOTE_PAIRS:
            if value[0] == open_q and value[-1] == close_q:
                return value[1:-1]
    return value


def parse_frontmatter(text: str) -> tuple[dict, dict, str | None, int]:
    """Parse a leading "---" block of "key: value" lines.

    Returns (values, key_line_numbers, error_or_None, body_offset).
    Values are str with the outer quote pair stripped, or list[str] for the
    inline "[a, b, c]" form. Parse failures are returned as a message, never
    raised.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, {}, 'missing opening "---"', 0

    close_at = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close_at = i
            break
    if close_at < 0:
        return {}, {}, 'missing closing "---"', 0

    values: dict = {}
    key_lines: dict = {}
    error: str | None = None
    for i in range(1, close_at):
        raw = lines[i]
        if not raw.strip():
            continue
        match = _FM_KEY_RE.match(raw)
        if not match:
            if error is None:
                error = f"line {i + 1}: expected \"key: value\", got {raw.strip()!r}"
            continue
        key = match.group(1)
        value = match.group(2).strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            parsed: object = (
                [_strip_quotes(item.strip()) for item in inner.split(",") if item.strip()]
                if inner
                else []
            )
        else:
            parsed = _strip_quotes(value)
        values[key] = parsed
        key_lines[key] = i + 1

    return values, key_lines, error, close_at + 1


# --- Discovery ----------------------------------------------------------------


@dataclass
class Skill:
    name: str
    dir: Path
    skill_md: Path
    text: str
    frontmatter: dict
    fm_lines: dict
    fm_error: str | None
    body: str
    body_offset: int
    bundled: list


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _bundled_files(skill_dir: Path) -> list:
    """Every file under skill_dir except SKILL.md, skipping dotted directories."""
    found: list = []
    for dirpath, dirnames, filenames in os.walk(skill_dir):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = Path(dirpath) / name
            if path.name == "SKILL.md" and path.parent == skill_dir:
                continue
            found.append(path)
    return found


def discover_skills(root: Path) -> list[Skill]:
    """Every immediate subdirectory of root holding a SKILL.md, sorted by name."""
    root = Path(root)
    skills: list[Skill] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = _read(skill_md)
        values, key_lines, error, body_offset = parse_frontmatter(text)
        body = "\n".join(text.split("\n")[body_offset:])
        skills.append(
            Skill(
                name=entry.name,
                dir=entry.resolve(),
                skill_md=skill_md.resolve(),
                text=text,
                frontmatter=values,
                fm_lines=key_lines,
                fm_error=error,
                body=body,
                body_offset=body_offset,
                bundled=_bundled_files(entry.resolve()),
            )
        )
    return skills


def repo_markdown(root: Path) -> list[Path]:
    """Every *.md in the repo, skipping dotted dirs, "tools", and "node_modules"."""
    root = Path(root).resolve()
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS
        ]
        for name in filenames:
            if name.endswith(".md") and not name.startswith("."):
                found.append(Path(dirpath) / name)
    return sorted(found)


# --- Masking ------------------------------------------------------------------
#
# Every helper returns a string of the same length with the same number of
# newlines. Masked characters become spaces so line and column numbers computed
# on the masked text stay true to the original.

_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_BLOCKQUOTE_RE = re.compile(r"^[ \t]*>")
_LINK_TARGET_RE = re.compile(r"\]\(([^)\n]*)\)")
_BARE_URL_RE = re.compile(r"(?:https?://|ftp://|mailto:|www\.)[^\s<>()\[\]\"'`]+")
_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_SKIP_FILE_RE = re.compile(r"<!--\s*lint-skip-file:\s*([^>]*?)\s*-->")
_SKIP_NEXT_RE = re.compile(r"<!--\s*lint-skip-next-line:\s*([^>]*?)\s*-->")


def _spaces(match: re.Match) -> str:
    return " " * (match.end() - match.start())


def mask_fenced(text: str) -> str:
    """Blank out ``` and ~~~ blocks, fence lines included."""
    lines = text.split("\n")
    out = []
    fence_char = ""
    fence_len = 0
    for line in lines:
        match = _FENCE_RE.match(line)
        if fence_char:
            out.append(" " * len(line))
            if (
                match
                and match.group(1)[0] == fence_char
                and len(match.group(1)) >= fence_len
                and not match.group(2).strip()
            ):
                fence_char = ""
                fence_len = 0
            continue
        if match:
            fence_char = match.group(1)[0]
            fence_len = len(match.group(1))
            out.append(" " * len(line))
            continue
        out.append(line)
    return "\n".join(out)


def _backtick_spans(line: str) -> list:
    """(start, end, inner_start, inner_end) for each balanced backtick run."""
    spans = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] != "`":
            i += 1
            continue
        j = i
        while j < n and line[j] == "`":
            j += 1
        run = j - i
        k = j
        closed = False
        while k < n:
            if line[k] == "`":
                m = k
                while m < n and line[m] == "`":
                    m += 1
                if m - k == run:
                    spans.append((i, m, j, k))
                    i = m
                    closed = True
                    break
                k = m
            else:
                k += 1
        if not closed:
            i = j
    return spans


def mask_inline_code(text: str) -> str:
    """Blank out `...` spans, backticks included."""
    out = []
    for line in text.split("\n"):
        spans = _backtick_spans(line)
        if not spans:
            out.append(line)
            continue
        chars = list(line)
        for start, end, _, _ in spans:
            for x in range(start, end):
                chars[x] = " "
        out.append("".join(chars))
    return "\n".join(out)


def mask_blockquotes(text: str) -> str:
    """Blank out lines starting with optional whitespace then ">"."""
    return "\n".join(
        " " * len(line) if _BLOCKQUOTE_RE.match(line) else line
        for line in text.split("\n")
    )


def mask_urls(text: str) -> str:
    """Blank out bare URLs and the target half of []() links."""

    def link(match: re.Match) -> str:
        return "](" + " " * len(match.group(1)) + ")"

    return _BARE_URL_RE.sub(_spaces, _LINK_TARGET_RE.sub(link, text))


def prose_view(text: str) -> str:
    """The text with fences, blockquotes, inline code, and URLs blanked out."""
    return mask_urls(mask_inline_code(mask_blockquotes(mask_fenced(text))))


def code_spans(text: str) -> list:
    """(line_no, inner_text) for every `...` span outside fenced blocks.

    inner_text excludes the surrounding backticks.
    """
    spans = []
    for idx, line in enumerate(mask_fenced(text).split("\n"), start=1):
        for _, _, inner_start, inner_end in _backtick_spans(line):
            spans.append((idx, line[inner_start:inner_end]))
    return spans


def bold_spans(text: str) -> list:
    """(line_no, inner_text) for every **...** span, fenced blocks masked.

    inner_text excludes the surrounding asterisks.
    """
    spans = []
    for idx, line in enumerate(mask_fenced(text).split("\n"), start=1):
        for match in _BOLD_RE.finditer(line):
            spans.append((idx, match.group(1)))
    return spans


def headings(text: str) -> list:
    """(line_no, level, heading_text) for ATX headings, fenced blocks masked."""
    found = []
    for idx, line in enumerate(mask_fenced(text).split("\n"), start=1):
        match = _HEADING_RE.match(line)
        if match:
            found.append((idx, len(match.group(1)), match.group(2).strip()))
    return found


# --- Suppressions -------------------------------------------------------------


def _codes(raw: str) -> set:
    return {token.strip() for token in raw.split(",") if token.strip()}


def suppressions(text: str) -> tuple[set, dict]:
    """Parse lint-skip directives out of raw file text.

    Returns (file_wide_codes, line_to_codes). The token "all" means every code.
    """
    file_wide: set = set()
    by_line: dict = {}
    for idx, line in enumerate(text.split("\n"), start=1):
        for match in _SKIP_FILE_RE.finditer(line):
            file_wide |= _codes(match.group(1))
        for match in _SKIP_NEXT_RE.finditer(line):
            by_line.setdefault(idx + 1, set()).update(_codes(match.group(1)))
    return file_wide, by_line


def apply_suppressions(findings: list, text_by_path: dict) -> list:
    """Drop findings whose code is suppressed for their path and line."""
    cache: dict = {}
    kept = []
    for finding in findings:
        text = text_by_path.get(finding.path)
        if text is None:
            kept.append(finding)
            continue
        if finding.path not in cache:
            cache[finding.path] = suppressions(text)
        file_wide, by_line = cache[finding.path]
        if finding.code in file_wide or "all" in file_wide:
            continue
        line_codes = by_line.get(finding.line)
        if line_codes and (finding.code in line_codes or "all" in line_codes):
            continue
        kept.append(finding)
    return kept
