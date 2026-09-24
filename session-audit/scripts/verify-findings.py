#!/usr/bin/env python3
"""Check every miner finding's evidence against the digests before it can reach the report.

A finding is a `### ` heading in findings/*.md. Its evidence lines look like
    > <session8> | <text copied verbatim from that session's digest or episode lines>
A quote counts only if it appears (whitespace-normalized, ≥20 chars) in that session's block.
Session counts are recomputed from verified quotes; the miner's own counts are ignored.

usage: verify-findings.py OUT        (reads OUT/findings/*.md, OUT/digest-*.md, OUT/episodes-*.md)
exit 1 if any finding has zero verified quotes.
"""
import re, sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
ws = lambda s: re.sub(r"\s+", " ", s).strip()

corpus = {}  # session8 -> normalized text of its digest block + episodes
for p in sorted(OUT.glob("digest-*.md")):
    for block in p.read_text().split("\n## SESSION ")[1:]:
        corpus[block[:8]] = corpus.get(block[:8], "") + ws(block)
for ep in sorted(OUT.glob("episodes-*.md")):
    for block in ep.read_text().split("\n### ")[1:]:
        corpus[block[:8]] = corpus.get(block[:8], "") + " " + ws(block)
if not corpus: sys.exit(f"no digests under {OUT}")

EVID = re.compile(r"^>\s*([0-9a-f]{8})\s*\|\s*(.+)$")
failed, rows = 0, []
for f in sorted((OUT / "findings").glob("*.md")):
    title, quotes = None, []
    def close():
        global failed
        if title is None: return
        ok = [(s, q) for s, q in quotes if len(ws(q)) >= 20 and ws(q).strip("`") in corpus.get(s, "")]
        bad = [(s, q) for s, q in quotes if (s, q) not in ok]
        sessions = sorted({s for s, _ in ok})
        verdict = "OK" if ok and not bad else ("PARTIAL" if ok else "UNSUPPORTED")
        failed += verdict == "UNSUPPORTED"
        rows.append(f"{verdict:11s} {len(sessions):2d} verified sessions  [{f.stem}] {title}")
        for s, q in bad: rows.append(f"            ✗ {s} | {q[:110]}")
    for line in f.read_text().splitlines():
        if line.startswith("### "):
            close(); title, quotes = line[4:].strip(), []
        elif (m := EVID.match(line.strip())):
            quotes.append((m.group(1), m.group(2).strip()))
        elif line.startswith(">") and title is not None:
            quotes.append(("malformed", line[1:].strip()))  # not `> <session8> | quote`: counts against the finding
    close()

print("\n".join(rows) or "no findings parsed: check the evidence format")
print(f"\n{len([r for r in rows if not r.startswith(' ')])} findings, {failed} unsupported. "
      "Drop UNSUPPORTED; for PARTIAL, report only the verified sessions.")
sys.exit(1 if failed else 0)
