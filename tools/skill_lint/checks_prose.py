"""Prose checks (SK201-SK213), sourced from unslop and technical-writing.

Every check runs on core.prose_view(), which masks fenced blocks, blockquotes,
inline code, and URLs while preserving offsets, so line numbers stay true.
"""

import re
from pathlib import Path

from .core import Finding, prose_view

# --- Rule data -------------------------------------------------------------

# unslop pattern 7. The source gives no per-word replacement.
AI_VOCAB = [
    "additionally",
    "crucial",
    "delve",
    "enduring",
    "enhance",
    "fostering",
    "garner",
    "interplay",
    "intricate",
    "landscape",
    "pivotal",
    "showcase",
    "tapestry",
    "testament",
    "underscore",
    "vibrant",
]

# unslop pattern 23.
FILLER = {
    "in order to": "to",
    "due to the fact that": "because",
    "it is important to note that": "nothing, delete it",
}

# unslop pattern 24. Fires only when two or more stack on one line.
HEDGES = [
    "arguably",
    "conceivably",
    "could",
    "may",
    "maybe",
    "might",
    "perhaps",
    "possibly",
    "potentially",
    "presumably",
    "seemingly",
]

# unslop pattern 26. Value is the source's replacement, or None when it gives none.
METAPHOR_NOUNS = {
    "substrate": "base",
    "wedge": "add",
    "vector": "way",
    "locus": None,
    "vantage": None,
    "nexus": None,
    "primitive": None,
    "harness": None,
    "surface": None,
    "bedrock": None,
    "scaffolding": None,
    "modality": None,
    "paradigm": None,
    "gold-plating": "more than the job needs",
    "ratchet": "a limit that only tightens",
    "evacuate": "move out",
    "endgame": "the last phase",
    "north star": None,
    "flywheel": None,
}

# unslop pattern 31.
FANCY_WORDS = {
    "utilize": "use",
    "leverage": "use",
    "facilitate": "help",
    "numerous": "many",
    "in the event that": "if",
}

# SK206 allowlist. Proper nouns and acronyms never count as title-case evidence.
PROPER_NOUNS = {
    "global",
    "english",
    "markdown",
    "phase",
    "github",
    "claude",
    "python",
    "json",
    "yaml",
    "readme",
    "rfc",
    "erd",
    "diataxis",
    "diátaxis",
    "google",
    "slack",
    "jira",
    "confluence",
    "notion",
    "datadog",
    "ai",
    "ci",
    "pr",
    "uuid",
    "cli",
    "api",
    "sql",
    "typescript",
}

# Decorative pictographs. Arrows (U+2190-U+21FF) are excluded: they are punctuation here.
EMOJI_RANGES = [
    (0x1F000, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0xFE0F, 0xFE0F),
    (0x2934, 0x2935),
]

CURLY_QUOTES = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
}

# --- Compiled patterns -----------------------------------------------------


def _phrase_re(phrases):
    """Whole-word, case-insensitive alternation. Longest first so phrases win."""
    parts = [re.escape(p).replace(r"\ ", r"\s+") for p in sorted(phrases, key=len, reverse=True)]
    return re.compile(r"(?<![\w-])(" + "|".join(parts) + r")(?![\w-])", re.IGNORECASE)


AI_VOCAB_RE = _phrase_re(AI_VOCAB)
FILLER_RE = _phrase_re(FILLER)
HEDGE_RE = _phrase_re(HEDGES)
METAPHOR_RE = _phrase_re(METAPHOR_NOUNS)
FANCY_RE = _phrase_re(FANCY_WORDS)

BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
PLURAL_S_RE = re.compile(r"[A-Za-z]+\(s\)", re.IGNORECASE)
ENTITY_RE = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
SLASH_RE = re.compile(r"(?<![\w./~-])([A-Za-z][A-Za-z0-9]*)/([A-Za-z][A-Za-z0-9]*)(?![\w./-])")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")

# --- Helpers ---------------------------------------------------------------


def _is_emoji(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in EMOJI_RANGES)


def _rel(path, root):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _finding(code, level, rel_path, line_no, message):
    return Finding(code=code, level=level, path=rel_path, line=line_no, message=message)


def _mask_entities(line):
    """Blank out HTML entities so their trailing semicolon is not a SK203 hit."""
    return ENTITY_RE.sub(lambda m: " " * len(m.group(0)), line)


def _heading_text(line):
    m = HEADING_RE.match(line)
    return m.group(2) if m else None


# --- Per-line checks -------------------------------------------------------


def _check_chars(rel_path, line_no, line, out):
    for _ in range(line.count("—")):
        out.append(_finding("SK201", "error", rel_path, line_no,
                            "em dash, use a period or a comma"))

    for m in re.finditer(r"–", line):
        before = line[m.start() - 1] if m.start() > 0 else ""
        after = line[m.end()] if m.end() < len(line) else ""
        if before.isdigit() and after.isdigit():
            continue  # numeric range, not a dash
        out.append(_finding("SK202", "error", rel_path, line_no,
                            "en dash used as a dash, use a period or a comma"))

    for _ in range(_mask_entities(line).count(";")):
        out.append(_finding("SK203", "error", rel_path, line_no,
                            "semicolon, use a period instead"))

    for m in PLURAL_S_RE.finditer(line):
        out.append(_finding("SK204", "error", rel_path, line_no,
                            '"%s" forms a plural with "(s)", write the plural out'
                            % m.group(0)))

    for m in SLASH_RE.finditer(line):
        if m.group(0).lower() == "and/or":
            fix = 'write "a, b, or both"'
        else:
            fix = 'write "%s, %s, or both"' % (m.group(1), m.group(2))
        out.append(_finding("SK205", "error", rel_path, line_no,
                            '"%s" is a slash construction, %s' % (m.group(0), fix)))

    for ch in line:
        if ch in CURLY_QUOTES:
            out.append(_finding("SK209", "error", rel_path, line_no,
                                "curly quote %s, use %s" % (ch, CURLY_QUOTES[ch])))


def _check_emoji(rel_path, line_no, line, out):
    heading = _heading_text(line)
    is_bullet = BULLET_RE.match(line) is not None
    if heading is None and not is_bullet:
        return
    where = "heading" if heading is not None else "bullet"
    for ch in line:
        if _is_emoji(ch):
            out.append(_finding("SK208", "error", rel_path, line_no,
                                "decorative emoji %s in a %s, remove it" % (ch, where)))


def _check_word_lists(rel_path, line_no, line, out):
    for m in AI_VOCAB_RE.finditer(line):
        out.append(_finding("SK207", "warning", rel_path, line_no,
                            '"%s" is AI vocabulary, use a plain word' % m.group(0)))

    for m in FILLER_RE.finditer(line):
        out.append(_finding("SK210", "warning", rel_path, line_no,
                            '"%s" is filler, use "%s"'
                            % (m.group(0), FILLER[_key(m.group(0), FILLER)])))

    for m in METAPHOR_RE.finditer(line):
        key = _key(m.group(0), METAPHOR_NOUNS)
        plain = METAPHOR_NOUNS[key]
        if plain:
            msg = '"%s" is an abstract metaphor, use "%s"' % (m.group(0), plain)
        else:
            msg = '"%s" is an abstract metaphor, use the concrete word' % m.group(0)
        out.append(_finding("SK212", "warning", rel_path, line_no, msg))

    for m in FANCY_RE.finditer(line):
        plain = FANCY_WORDS[_key(m.group(0), FANCY_WORDS)]
        out.append(_finding("SK213", "warning", rel_path, line_no,
                            '"%s" reads better as "%s"' % (m.group(0), plain)))

    hits = [m.group(0) for m in HEDGE_RE.finditer(line)]
    if len(hits) >= 2:
        out.append(_finding("SK211", "warning", rel_path, line_no,
                            "hedges stack here (%s), one hedge such as \"may\" is enough"
                            % ", ".join('"%s"' % h.lower() for h in hits)))


def _key(matched, table):
    """Map a matched span back to its table key. Whitespace in phrases may vary."""
    flat = re.sub(r"\s+", " ", matched.lower())
    if flat in table:
        return flat
    for k in table:
        if re.sub(r"\s+", " ", k.lower()) == flat:
            return k
    return flat


def _check_title_case(rel_path, line_no, line, out):
    text = _heading_text(line)
    if not text:
        return
    offenders = []
    for m in WORD_RE.finditer(text):
        word = m.group(0)
        if not re.fullmatch(r"[A-Z][a-z]+", word):
            continue  # acronyms and CamelCase carry their own capitalization
        if word.lower() in PROPER_NOUNS:
            continue
        prefix = text[: m.start()].rstrip()
        # Sentence-initial, or opening a clause after punctuation, is not evidence.
        if not prefix or prefix[-1] in ".:!?(—–-“\"'":
            continue
        offenders.append(word)
    if len(offenders) >= 2:
        out.append(_finding("SK206", "warning", rel_path, line_no,
                            'heading "%s" is title case, use sentence case' % text))


# --- Entry point -----------------------------------------------------------


def run(md_paths: list, root: Path) -> list:
    """Return prose findings for every markdown path given. No output, no writes."""
    findings = []
    for path in md_paths:
        p = Path(path)
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel_path = _rel(p, root)
        for i, line in enumerate(prose_view(raw).splitlines(), start=1):
            if not line.strip():
                continue
            _check_chars(rel_path, i, line, findings)
            _check_emoji(rel_path, i, line, findings)
            _check_word_lists(rel_path, i, line, findings)
            _check_title_case(rel_path, i, line, findings)
    return findings
