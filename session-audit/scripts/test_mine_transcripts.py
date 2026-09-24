#!/usr/bin/env python3
"""Fixture test for mine-transcripts.py + verify-findings.py. Run after any edit to either:
    python3 test_mine_transcripts.py
Each assertion pins a bug the first version had or a signal the audit depends on."""
import re
import json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).parent
tmp = Path(tempfile.mkdtemp())
proj = tmp / "projects" / "-Users-x-projects-demo"
(proj / "memory").mkdir(parents=True)
U = dict(input_tokens=10, output_tokens=100, cache_creation_input_tokens=1000, cache_read_input_tokens=5000)


def rec(t, ts, **kw): return dict(type=t, timestamp=f"2026-09-20T10:{ts:02d}:00Z", version="9.9.9", **kw)
def user(ts, text): return rec("user", ts, message=dict(role="user", content=text))
def asst(ts, mid, blocks, skill=None):
    r = rec("assistant", ts, message=dict(id=mid, model="claude-test", usage=U, content=blocks))
    if skill: r["attributionSkill"] = skill
    return r
def tool(tid, name, **inp): return dict(type="tool_use", id=tid, name=name, input=inp)
def result(ts, tid, text, err=False):
    return rec("user", ts, message=dict(role="user", content=[dict(type="tool_result", tool_use_id=tid, content=text, is_error=err)]))


sess = [
    user(0, "run the standup"),
    # one API response split over three lines: usage must count once
    asst(1, "m1", [dict(type="text", text="Loading the skill.")], skill="standup"),
    asst(1, "m1", [tool("t1", "Bash", command="cd /x && notion-cli query --db 1")], skill="standup"),
    asst(1, "m1", [tool("t2", "Bash", command="sleep 60")], skill="standup"),
    result(2, "t1", "Exit code 1\nError: no such column: Date", err=True),
    result(2, "t2", ""),
    asst(3, "m2", [tool("t3", "Read", file_path="/x/big.ts")], skill="standup"),
    result(4, "t3", "x" * 40_000),
    asst(5, "m3", [dict(type="text", text="Done.")], skill="standup"),
    user(6, "that's not what I asked, the Daily is wrong"),
    asst(7, "m4", [tool("t4", "Agent", subagent_type="Explore", model="opus", description="look", prompt="p")]),
    asst(7, "m4", [tool("t5", "mcp__claude_ai_Notion__notion-fetch", id="p", include_transcript=True)]),
    result(8, "t5", "short"),
    result(8, "t4", "ok"),
    user(9, "[Request interrupted by user]"),
    rec("brand-new-type", 10),
]
(proj / "aaaaaaaa-0000-0000-0000-000000000000.jsonl").write_text("\n".join(json.dumps(r) for r in sess))
sub_dir = proj / "aaaaaaaa-0000-0000-0000-000000000000" / "subagents"; sub_dir.mkdir(parents=True)
(sub_dir / "agent-b1.jsonl").write_text(json.dumps(asst(8, "s1", [tool("st1", "Grep", pattern="x")])))
# second subagent: one error per fix metric
(sub_dir / "agent-b2.jsonl").write_text("\n".join(json.dumps(r) for r in [
    asst(8, "s2", [tool("st2", "mcp__claude_ai_Notion__notion-query-data-sources", data={})]),
    result(8, "st2", 'Failed to execute query: no such column: "Date"', err=True),
    asst(9, "s3", [tool("st3", "Read", file_path="/x/digest-01.md")]),
    result(9, "st3", "File content (41717 tokens) exceeds maximum allowed tokens (25000).", err=True),
    asst(9, "s4", [tool("st4", "Bash", command='AB="agent-browser --session x"; $AB open u')]),
    result(9, "st4", "(eval):1: command not found: agent-browser --session x", err=True),
    asst(9, "s5", [tool("st5", "mcp__claude_ai_Notion__notion-fetch", id="p", include_transcript=True)]),
    result(9, "st5", "y" * 40_000)]))
(sub_dir / "agent-b2.meta.json").write_text(json.dumps(dict(agentType="general-purpose", model="sonnet", description="mine")))
(sub_dir / "agent-b1.meta.json").write_text(json.dumps(dict(agentType="Explore", model="opus", description="look")))
# out-of-window session: must not leak into any count
old = [dict(user(0, "old"), timestamp="2026-09-01T10:00:00Z"), dict(asst(1, "o1", [tool("o1t", "Bash", command="psql -c 1")]), timestamp="2026-09-01T10:01:00Z")]
(proj / "bbbbbbbb-0000-0000-0000-000000000000.jsonl").write_text("\n".join(json.dumps(r) for r in old))
(proj / "memory" / "MEMORY.md").write_text("- [A](a.md) — a\n- [Gone](gone.md) — missing\n")
(proj / "memory" / "a.md").write_text("---\nname: a\n---\nx")
(proj / "memory" / "orphan.md").write_text("no frontmatter")

out = tmp / "out"
data = tmp / "data"; data.mkdir()
(data / "metrics.json").write_text(json.dumps([  # config-driven metrics, one per matcher kind
    dict(name="raw_psql", tool="Bash", family="psql"),
    dict(name="notion_no_such_column", tool="query-data-sources", error="no such column"),
    dict(name="read_over_cap", tool="Read", error="exceeds maximum allowed tokens"),
    dict(name="ab_var_split", tool="Bash", error="command not found: agent-browser --session"),
    dict(name="main_transcript_fetches", tool="notion-fetch", input='"include_transcript": true', main_only=True),
]))
(data / "fixes.json").write_text(json.dumps([dict(id="late-fix", shipped="2026-09-25", metric="tool_errors", baseline=99, better="lower")]))
r = subprocess.run([sys.executable, HERE / "mine-transcripts.py", out, "--root", tmp / "projects", "--since", "2026-09-15", "--data", data],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stderr
sig = json.loads((out / "signals.json").read_text()); m = sig["metrics"]; stats = (out / "stats.md").read_text()
digest = (out / "digest-01.md").read_text()
checks = {
    "fix shipped mid-window is flagged unmeasured": "FIX late-fix" in stats and "UNMEASURED" in stats,
    "one session in window": m["sessions"] == 1,
    "out-of-window psql not counted": m.get("raw_psql", 0) == 0,
    "usage deduped by message.id (4 main-thread responses, not 6 lines)": sig["sessions"]["aaaaaaaa"]["tokens"]["output_tokens"] == 400,
    "tool calls = 5 main + 5 sub": m["tool_calls"] == 10,
    "error captured": m["tool_errors"] == 4 and "TOOL! Bash" in digest and "no such column" in digest,
    "blind sleep ≥30s": m["blind_sleeps_30s"] == 1,
    "skill attributed": sig["skills"]["standup"]["api_calls"] == 3 and sig["skills"]["standup"]["errors"] == 1,
    "steer after skill": sig["skills"]["standup"]["steer_after"] == ["aaaaaaaa"] and "USER[steer?]" in digest,
    "interrupt recorded": m["interrupts"] == 1,
    "subagent model from meta.json": m["subagent_opus"] == 1,
    "big result carried cost ranked": "big.ts" in stats.split("## Largest tool results")[1][:400],
    # floor-div by 1M once printed every row as 0.0M
    # digests run ~2 bytes/token; 90KB chunks overflowed Read's 25k-token cap
    "chunk default fits Read cap": int(re.search(r"default (\d+)KB", subprocess.run([sys.executable, HERE / "mine-transcripts.py", "--help"], capture_output=True, text=True).stdout.replace("\n", " ")).group(1)) * 1000 / 2 <= 25_000,
    # Bash "no such column" must not count; only the Notion tool's
    "fix metrics count their errors": m["notion_no_such_column"] == 1 and m["read_over_cap"] == 1 and m["ab_var_split"] == 1 and "notion_no_such_column" in sig["rates"],
    # sub-thread fetch and sub-thread big result must not count
    "main-thread bulk reads counted": m["main_transcript_fetches"] == 1 and m["main_big_results"] == 1,
    "carried cost nonzero": re.search(r"^\s+[1-9]\d*k carried\s+10k tok .*big\.ts", stats, re.M) is not None,
    "schema canary fires": "brand-new-type" in stats,
    "memory hygiene": all(x in stats for x in ("orphan.md` not in MEMORY.md", "orphan.md` has no frontmatter", "missing `gone.md`")),
    "episode grouped under skill": "## standup:" in (out / "episodes-01.md").read_text(),
}
(out / "findings").mkdir()
(out / "findings" / "t.md").write_text("### real\n> aaaaaaaa | Error: no such column: Date\n### fake\n> aaaaaaaa | this line was never in any transcript\n### sloppy\n> aaaaaaaa | Error: no such column: Date\n> aaaaaaaa (stats.md) | anything\n")
v = subprocess.run([sys.executable, HERE / "verify-findings.py", out], capture_output=True, text=True)
checks["verifier keeps real, drops fake"] = v.returncode == 1 and "OK           1 verified sessions  [t] real" in v.stdout and "UNSUPPORTED" in v.stdout and "PARTIAL      1 verified sessions  [t] sloppy" in v.stdout

bad = [k for k, ok in checks.items() if not ok]
for k, ok in checks.items(): print(("PASS " if ok else "FAIL ") + k)
sys.exit(1 if bad else 0)
