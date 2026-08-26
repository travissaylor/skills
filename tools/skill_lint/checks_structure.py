"""Structural checks: SK001 to SK010 errors, SK101 to SK106 warnings.

Prose and vocabulary rules (SK2xx) live in checks_prose.py.
"""

from __future__ import annotations

import difflib
import itertools
import os
import re
from pathlib import Path

from . import core
from .core import Finding

KNOWN_FM_KEYS = {
    "name",
    "description",
    "disable-model-invocation",
    "allowed-tools",
    "license",
    "metadata",
    "version",
    "routes-to",
    "observable-outcome",
}

DESCRIPTION_MIN = 40
DESCRIPTION_MAX = 1024
NAME_MAX = 64
SIMILARITY_LIMIT = 0.60

_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_LINK_RE = re.compile(r"\]\(([^)\n]*)\)")
_GLOB_CHARS = set("*?[]{}|\\")
_SKIP_LINK_SCHEMES = ("http://", "https://", "ftp://", "mailto:", "tel:", "//")

# Dotted directories that legitimately appear in agent docs. Anything else with a
# leading dot and a slash reads as one person's private tree.
_DOTDIR_ALLOW = {
    "agents",
    "aws",
    "build",
    "cache",
    "changeset",
    "circleci",
    "claude",
    "config",
    "devcontainer",
    "dist",
    "docker",
    "env",
    "git",
    "github",
    "gitlab",
    "husky",
    "idea",
    "local",
    "next",
    "npm",
    "nuxt",
    "output",
    "planning",
    "pnpm",
    "ssh",
    "svelte",
    "turbo",
    "venv",
    "vscode",
    "yarn",
}
_DOTDIR_RE = re.compile(r"(?<![A-Za-z0-9._/~-])\.([a-z][a-z0-9_-]*)/")

# Stand-in usernames in worked examples are not hardcoded personal paths.
_PLACEHOLDER_USERS = {
    "me",
    "name",
    "someone",
    "user",
    "username",
    "you",
    "your-name",
    "yourname",
}
_USERS_PATH_RE = re.compile(r"/Users/([A-Za-z0-9._<>-]+)/")
_MARKER_RE = re.compile(r"\b(TODO|FIXME)\b")

_IDENT_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_ROUTE_VERB_RE = re.compile(
    r"\b(load|loads|loaded|loading|route|routes|routed|routing|invoke|invokes|invoked)\b",
    re.IGNORECASE,
)
_SKILL_WORD_RE = re.compile(r"\bskills?\b", re.IGNORECASE)

_QUOTED_RE = re.compile(r"[\"']([^\"']{4,80})[\"']")
_USE_TRIGGER_RE = re.compile(r"\bUse\s+(?:for|when|if)\b", re.IGNORECASE)


def run(
    skills: list,
    root: Path,
    check_installed: bool = False,
    max_words: int = 5000,
) -> list:
    """Every structural finding for the discovered skills."""
    root = Path(root).resolve()
    findings: list = []

    if not skills:
        return [
            Finding(
                "SK010",
                "error",
                ".",
                0,
                f"no skills discovered under {root.as_posix()}",
            )
        ]

    names = {skill.name for skill in skills}
    for skill in skills:
        findings.extend(_frontmatter_checks(skill, root))
        findings.extend(_link_checks(skill, root))
        findings.extend(_path_checks(skill, root))
        findings.extend(_cross_skill_checks(skill, root, names))
        findings.extend(_banned_checks(skill, root))
        findings.extend(_budget_checks(skill, root, max_words))
        findings.extend(_bundled_checks(skill, root))
        if check_installed:
            findings.extend(_installed_checks(skill, root))
    findings.extend(_similarity_checks(skills, root))
    findings.extend(_banned_outside_skills(skills, root))

    findings.sort(key=lambda f: (f.path, f.line, f.code, f.message))
    return findings


def _banned_outside_skills(skills: list, root: Path) -> list:
    """Banned patterns in repo markdown no skill owns, such as the root README.

    A hardcoded home path or a leftover TODO in the README is the same defect as
    one inside a skill, and the README is where an install line would put it.
    """
    owned = {skill.skill_md.resolve() for skill in skills}
    for skill in skills:
        owned.update(p.resolve() for p in skill.bundled)

    out: list = []
    for path in core.repo_markdown(root):
        if path.resolve() in owned:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        out.extend(_banned_in_text(text, _rel(path, root), root))
    return out


# --- Helpers ------------------------------------------------------------------


def _rel(path: Path, root: Path) -> str:
    """Repo-relative POSIX path, falling back to the absolute path."""
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _quote(value: str, limit: int = 80) -> str:
    """One-line, length-capped echo of the offending text."""
    flat = " ".join(str(value).split())
    if len(flat) > limit:
        flat = flat[: limit - 3] + "..."
    return flat


# --- SK001 to SK005, SK101, SK105 ---------------------------------------------


def _frontmatter_checks(skill, root: Path) -> list:
    path = _rel(skill.skill_md, root)
    out: list = []

    if skill.fm_error:
        return [Finding("SK001", "error", path, 1, f"frontmatter parse failed: {_quote(skill.fm_error)}")]

    fm = skill.frontmatter
    name_line = skill.fm_lines.get("name", 1)
    name = fm.get("name")

    if name is None:
        out.append(Finding("SK002", "error", path, 1, "frontmatter has no name key"))
    elif not isinstance(name, str):
        out.append(
            Finding("SK002", "error", path, name_line, f"name is not a string: {_quote(name)}")
        )
    else:
        if len(name) > NAME_MAX:
            out.append(
                Finding(
                    "SK002",
                    "error",
                    path,
                    name_line,
                    f"name is {len(name)} characters, over the {NAME_MAX} limit: {_quote(name)}",
                )
            )
        elif not _KEBAB_RE.match(name):
            out.append(
                Finding("SK002", "error", path, name_line, f"name is not kebab-case: {_quote(name)}")
            )
        if name != skill.name:
            out.append(
                Finding(
                    "SK003",
                    "error",
                    path,
                    name_line,
                    f"name {_quote(name)} does not match the directory name {skill.name}",
                )
            )

    desc_line = skill.fm_lines.get("description", 1)
    description = fm.get("description")
    if description is None:
        out.append(Finding("SK004", "error", path, 1, "frontmatter has no description key"))
    elif not isinstance(description, str):
        out.append(
            Finding("SK004", "error", path, desc_line, f"description is not a string: {_quote(description)}")
        )
    else:
        size = len(description)
        if size < DESCRIPTION_MIN or size > DESCRIPTION_MAX:
            out.append(
                Finding(
                    "SK005",
                    "error",
                    path,
                    desc_line,
                    f"description is {size} characters, outside {DESCRIPTION_MIN}..{DESCRIPTION_MAX}: "
                    f"{_quote(description, 60)}",
                )
            )

    for key in fm:
        if key not in KNOWN_FM_KEYS:
            out.append(
                Finding(
                    "SK101",
                    "warning",
                    path,
                    skill.fm_lines.get(key, 1),
                    f"unknown frontmatter key {_quote(key)}",
                )
            )

    out.extend(_invocation_checks(skill, path))
    return out


def _invocation_checks(skill, path: str) -> list:
    """SK105: model invocation is off, so trigger phrases in the description can never fire."""
    flag = skill.frontmatter.get("disable-model-invocation")
    if not isinstance(flag, str) or flag.strip().lower() != "true":
        return []
    description = skill.frontmatter.get("description")
    if not isinstance(description, str):
        return []

    phrases = [m.group(1).strip() for m in _QUOTED_RE.finditer(description)]
    if not phrases:
        return []
    if not (_USE_TRIGGER_RE.search(description) or len(phrases) >= 2):
        return []

    shown = ", ".join(f'"{_quote(p, 40)}"' for p in phrases[:3])
    line = skill.fm_lines.get("disable-model-invocation", 1)
    return [
        Finding(
            "SK105",
            "warning",
            path,
            line,
            f"disable-model-invocation is true, so the description trigger phrases never fire: {shown}",
        )
    ]


# --- SK006 --------------------------------------------------------------------


def _link_checks(skill, root: Path) -> list:
    path = _rel(skill.skill_md, root)
    masked = core.mask_blockquotes(core.mask_fenced(skill.text))
    out: list = []

    for match in _LINK_RE.finditer(masked):
        raw = match.group(1).strip()
        target = raw.split()[0] if raw else ""
        target = target.strip("<>")
        if not target or target.startswith("#"):
            continue
        lowered = target.lower()
        if lowered.startswith(_SKIP_LINK_SCHEMES) or "://" in lowered:
            continue
        if target.startswith("/"):
            continue
        local = target.split("#", 1)[0].split("?", 1)[0]
        if not local:
            continue
        if any(ch in _GLOB_CHARS for ch in local) or "<" in local:
            continue
        if _resolves(local, skill.dir, root):
            continue
        out.append(
            Finding(
                "SK006",
                "error",
                path,
                _line_of(masked, match.start()),
                f"link target {_quote(target)} does not resolve to a file",
            )
        )
    return out


def _resolves(target: str, skill_dir: Path, root: Path) -> bool:
    """A reference resolves relative to its own directory or to the repo root."""
    unquoted = target.strip().strip("'\"")
    for base in (skill_dir, root):
        candidate = os.path.join(str(base), unquoted)
        if os.path.lexists(candidate):
            return True
    return False


# --- SK007 --------------------------------------------------------------------


def _path_checks(skill, root: Path) -> list:
    path = _rel(skill.skill_md, root)
    masked = core.mask_blockquotes(skill.text)
    out: list = []

    for line_no, span in core.code_spans(masked):
        token = span.strip()
        if not _is_path_like(token):
            continue
        if _is_banned_token(token):
            continue  # SK009 owns banned paths, do not report them twice
        if _resolves(token, skill.dir, root):
            continue
        out.append(
            Finding(
                "SK007",
                "error",
                path,
                line_no,
                f"backticked path {_quote(token)} does not resolve to a file",
            )
        )
    return out


def _is_path_like(token: str) -> bool:
    """Rule 2 of the spec: only fire on tokens that are unambiguously repo paths."""
    if not token or len(token) > 200:
        return False
    if any(ch.isspace() for ch in token):
        return False
    if any(ch in _GLOB_CHARS for ch in token):
        return False
    if "<" in token or ">" in token:
        return False
    if "://" in token or token.startswith("www."):
        return False
    if token.startswith("/") or token.startswith("~"):
        return False  # absolute and home paths are never repo-relative
    segments = token.split("/")
    if any(seg.isupper() and len(seg) >= 2 for seg in segments):
        return False  # FILE, PATH, and friends are placeholders
    if token.startswith("./") or token.startswith("../"):
        return True
    if "/" not in token:
        return False  # a bare budget.mjs is a worked example, not a reference
    if token.endswith("/"):
        return True
    return bool(re.search(r"\.[A-Za-z0-9]{1,6}$", segments[-1]))


def _is_banned_token(token: str) -> bool:
    if _USERS_PATH_RE.search(token):
        return True
    match = _DOTDIR_RE.search(" " + token)
    return bool(match) and match.group(1) not in _DOTDIR_ALLOW


# --- SK008 --------------------------------------------------------------------


def _cross_skill_checks(skill, root: Path, names: set) -> list:
    path = _rel(skill.skill_md, root)
    masked = core.mask_blockquotes(skill.text)
    lines = masked.split("\n")
    out: list = []
    seen: set = set()

    spans = [(no, text, "`") for no, text in core.code_spans(masked)]
    spans += [(no, text, "**") for no, text in core.bold_spans(masked)]

    for line_no, span, delim in spans:
        token = span.strip()
        if token in names or not _IDENT_RE.match(token) or len(token) > NAME_MAX:
            continue
        line = lines[line_no - 1] if line_no - 1 < len(lines) else ""
        if not _is_skill_reference(line, token, delim):
            continue
        if (line_no, token) in seen:
            continue
        seen.add((line_no, token))
        out.append(
            Finding(
                "SK008",
                "error",
                path,
                line_no,
                f"cross-skill reference {_quote(token)} has no sibling skill directory",
            )
        )
    return out


def _is_skill_reference(line: str, token: str, delim: str) -> bool:
    """Only fire when the line frames the token as a skill, never on free prose."""
    marked = re.escape(delim + token + delim)
    if _SKILL_WORD_RE.search(line):
        if "-" in token:
            return True
        if re.search(marked + r"\s+skills?\b", line, re.IGNORECASE):
            return True
        return bool(re.search(r"\bskills?\b[^`*\n]{0,24}" + marked, line, re.IGNORECASE))
    return "-" in token and bool(_ROUTE_VERB_RE.search(line))


# --- SK009 --------------------------------------------------------------------


def _banned_checks(skill, root: Path) -> list:
    out: list = []
    targets = [skill.skill_md]
    targets += [p for p in skill.bundled if p.suffix == ".md"]

    for target in targets:
        try:
            text = skill.text if target == skill.skill_md else target.read_text(encoding="utf-8")
        except OSError:
            continue
        out.extend(_banned_in_text(text, _rel(target, root), root))
    return out


def _banned_in_text(text: str, path: str, root: Path | None = None) -> list:
    # Not mask_inline_code: the real .william/rfcs/ defect sits inside a backtick span.
    scan = core.mask_urls(core.mask_blockquotes(core.mask_fenced(text)))
    out: list = []

    for match in _DOTDIR_RE.finditer(scan):
        if match.group(1) in _DOTDIR_ALLOW:
            continue
        # A dotted directory that exists here is ours, so docs may name it.
        # Foreign means absent, which is what .william/ is.
        if root is not None and (root / ("." + match.group(1))).is_dir():
            continue
        out.append(
            Finding(
                "SK009",
                "error",
                path,
                _line_of(scan, match.start()),
                f"foreign personal path {_quote(match.group(0))}",
            )
        )

    for match in _USERS_PATH_RE.finditer(scan):
        if match.group(1).strip("<>").lower() in _PLACEHOLDER_USERS:
            continue
        out.append(
            Finding(
                "SK009",
                "error",
                path,
                _line_of(scan, match.start()),
                f"hardcoded home path {_quote(match.group(0))}",
            )
        )

    for match in _MARKER_RE.finditer(scan):
        out.append(
            Finding(
                "SK009",
                "error",
                path,
                _line_of(scan, match.start()),
                f"leftover marker {_quote(match.group(1))}",
            )
        )
    return out


# --- SK102, SK103 -------------------------------------------------------------


def _budget_checks(skill, root: Path, max_words: int) -> list:
    words = len(skill.body.split())
    if words <= max_words:
        return []
    return [
        Finding(
            "SK102",
            "warning",
            _rel(skill.skill_md, root),
            skill.body_offset + 1,
            f"body is {words} words, over the {max_words} word budget",
        )
    ]


def _similarity_checks(skills: list, root: Path) -> list:
    """SK103: near-duplicate descriptions collide at routing time."""
    out: list = []
    for left, right in itertools.combinations(skills, 2):
        a = left.frontmatter.get("description")
        b = right.frontmatter.get("description")
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        if ratio <= SIMILARITY_LIMIT:
            continue
        # Reported once, on the first skill of the pair.
        out.append(
            Finding(
                "SK103",
                "warning",
                _rel(left.skill_md, root),
                left.fm_lines.get("description", 1),
                f"description is {round(ratio * 100)} percent similar to skill {right.name}, "
                "a routing collision",
            )
        )
    return out


# --- SK104, SK106 -------------------------------------------------------------


def _bundled_checks(skill, root: Path) -> list:
    out: list = []
    for bundled in skill.bundled:
        try:
            relative = bundled.resolve().relative_to(skill.dir).as_posix()
        except ValueError:
            relative = bundled.name
        if relative in skill.body or bundled.name in skill.body:
            continue
        out.append(
            Finding(
                "SK104",
                "warning",
                _rel(bundled, root),
                0,
                f"bundled file {_quote(relative)} is never referenced from {skill.name}/SKILL.md",
            )
        )
    return out


def _installed_checks(skill, root: Path) -> list:
    """SK106: opt-in, local only. lexists keeps a dangling symlink counting as installed."""
    target = os.path.join(os.path.expanduser("~/.claude/skills"), skill.name)
    if os.path.lexists(target):
        return []
    return [
        Finding(
            "SK106",
            "warning",
            _rel(skill.skill_md, root),
            skill.fm_lines.get("name", 1),
            f"no entry at ~/.claude/skills/{skill.name}, so the skill is never dogfooded",
        )
    ]
