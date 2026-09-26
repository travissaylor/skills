#!/usr/bin/env python3
"""Distill Google Antigravity CLI (agy) conversations (~/.gemini/antigravity-cli/) into
agy-stats.md, agy-signals.json and digest-agy-NN.md for /session-audit.

Step payloads are schema-less protobuf. A generic wire-format walk recovers the strings we need:
user prompts, tool names, tool args (JSON), and tool results ("The command exited with code N").
Digest blocks start with "## SESSION <id8>" so verify-findings.py checks quotes against them unchanged.
"""
import argparse, json, re, sqlite3, collections, datetime
from pathlib import Path

STEER = re.compile(r"\b(no[,.]|don'?t|do not|instead|stop|not what|wrong|undo|revert|i said|actually|i don'?t want)\b", re.I)

def varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1; r |= (c & 0x7f) << s; s += 7
        if not c & 0x80: return r, i

def walk(b, depth=0, out=None, path=""):
    """Yield (path, kind, value) for every field; strings that decode as printable utf-8 are leaves."""
    if out is None: out = []
    i = 0
    try:
        while i < len(b):
            k, i = varint(b, i); f = k >> 3; wt = k & 7
            if wt == 0: v, i = varint(b, i); out.append((path + str(f), "int", v))
            elif wt == 1: i += 8
            elif wt == 5: i += 4
            elif wt == 2:
                n, i = varint(b, i); s = b[i:i + n]; i += n
                try:
                    t = s.decode("utf-8")
                    if t and (t.isprintable() or "\n" in t or "\t" in t) and not t.startswith("\n"):
                        out.append((path + str(f), "str", t)); continue
                except UnicodeDecodeError: pass
                if depth < 8: walk(s, depth + 1, out, path + str(f) + ".")
            else: break
    except Exception: pass
    return out

def clip(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n] + "…"

def family(cmd):
    c = re.sub(r"^(cd\s+\S+\s*(&&|;)\s*)+", "", cmd.strip())
    c = re.sub(r"^(export\s+\S+=\S+\s*;?\s*|[A-Z_]+=\S+\s+)+", "", c)
    toks = c.split()
    if not toks: return "?"
    if toks[0] in ("git", "gh", "pnpm", "npm", "npx", "docker", "uv", "cargo", "go", "make", "python3", "python", "node", "codex", "agy", "claude") \
            and len(toks) > 1 and not toks[1].startswith("-"): return f"{toks[0]} {toks[1]}"
    return toks[0]

def first_str(fields, prefix, minlen=1):
    for p, k, v in fields:
        if k == "str" and p == prefix and len(v) >= minlen: return v
    return None

def parse_conv(db_path, meta):
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    events = []; n_steps = 0
    for idx, st, status, payload, err in c.execute("select idx, step_type, status, step_payload, error_details from steps order by idx"):
        n_steps += 1
        f = walk(payload or b"")
        secs = next((v for p, k, v in f if k == "int" and p == "5.1.1"), None)
        ts = datetime.datetime.fromtimestamp(secs, datetime.timezone.utc).strftime("%H:%M:%S") if secs else ""
        if err: events.append(("!", clip(err.decode("utf-8", "replace") if isinstance(err, bytes) else str(err), 240), ts, idx))
        if st == 14:  # user message
            txt = first_str(f, "19.2") or first_str(f, "19.3.1") or ""
            events.append(("U", txt, ts, idx))
        elif st == 15:  # model step: thought text + optional tool call
            thought = first_str(f, "20.3", 20)
            name = first_str(f, "20.7.2"); args = first_str(f, "20.7.3")
            if thought: events.append(("A", thought, ts, idx))
            if name: events.append(("call", name, ts, idx, args or ""))
            if not thought and not name:
                longest = sorted([v for p, k, v in f if k == "str" and p.startswith("20.")], key=len)
                if longest: events.append(("A?", longest[-1], ts, idx))
        elif st == 132:  # tool result
            name = first_str(f, "5.4.2") or "?"; args = first_str(f, "5.4.3") or ""
            res = first_str(f, "140.2.1") or ""
            m = re.search(r"exited with code (-?\d+)", res)
            code = int(m.group(1)) if m else None
            cmd = ""
            try: cmd = json.loads(args).get("CommandLine", "") if args.startswith("{") else ""
            except Exception: pass
            events.append(("R", name, ts, idx, cmd, code, res, status))
        else:
            strs = sorted([v for p, k, v in f if k == "str" and len(v) > 20], key=len)
            events.append(("?", f"step_type={st} " + clip(strs[-1] if strs else "", 160), ts, idx))
    return {"id": meta["conversation_id"], "title": meta["title"], "ts": meta["last_modified_time"], "ws": Path(meta["workspace_uris"] or "").name.strip('"]') or "?",
            "status": meta["status"], "parent": meta["parent_conversation_id"], "steps": n_steps, "events": events}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out"); ap.add_argument("--since", required=True); ap.add_argument("--until")
    ap.add_argument("--root", default=str(Path.home() / ".gemini" / "antigravity-cli")); ap.add_argument("--chunk-kb", type=int, default=45)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); root = Path(a.root)
    sc = sqlite3.connect(f"file:{root / 'conversation_summaries.db'}?mode=ro", uri=True); sc.row_factory = sqlite3.Row
    q = "select * from conversation_summaries where last_modified_time >= ? " + ("and last_modified_time < ? " if a.until else "") + "order by last_modified_time"
    rows = sc.execute(q, (a.since, a.until) if a.until else (a.since,)).fetchall()
    convs = []
    for r in rows:
        p = root / "conversations" / f"{r['conversation_id']}.db"
        if p.exists(): convs.append(parse_conv(p, dict(r)))
    n = len(convs); id8 = lambda c: c["id"][:8]

    calls = [(c, e) for c in convs for e in c["events"] if e[0] == "R"]
    tool_sessions = collections.defaultdict(set); tool_calls = collections.Counter()
    for c, e in calls: tool_sessions[e[1]].add(id8(c)); tool_calls[e[1]] += 1
    cmds = [(c, e) for c, e in calls if e[4]]
    errs = [(c, e) for c, e in cmds if e[5] not in (0, None)]
    fam_sessions = collections.defaultdict(set); fam_calls = collections.Counter()
    for c, e in cmds: fam_sessions[family(e[4])].add(id8(c)); fam_calls[family(e[4])] += 1
    err_sig = collections.defaultdict(set)
    for c, e in errs:
        body = e[6].split("Output:", 1)[-1].strip().splitlines()
        err_sig[f"{family(e[4])}: exit {e[5]} {re.sub(r'\\d+', 'N', clip(body[0] if body else '', 90))}"].add(id8(c))
    exact = collections.defaultdict(set)
    for c, e in cmds: exact[clip(e[4], 200)].add(id8(c))
    step_errs = [(c, e) for c in convs for e in c["events"] if e[0] == "!"]
    steer = []
    for c in convs:
        us = [e for e in c["events"] if e[0] == "U"]
        for e in us[1:]:
            if STEER.search(e[1][:300]): steer.append((id8(c), clip(e[1], 160)))
    first_prompts = collections.defaultdict(set)
    for c in convs:
        us = [e for e in c["events"] if e[0] == "U"]
        if us: first_prompts[clip(us[0][1], 90)].add(id8(c))
    per = {id8(c): {"ts": c["ts"], "title": c["title"], "ws": c["ws"], "status": c["status"], "steps": c["steps"],
                    "user_msgs": sum(1 for e in c["events"] if e[0] == "U"), "tool_calls": sum(1 for e in c["events"] if e[0] == "R"),
                    "cmds": sum(1 for e in c["events"] if e[0] == "R" and e[4]), "cmd_errors": sum(1 for e in c["events"] if e[0] == "R" and e[4] and e[5] not in (0, None)),
                    "step_errors": sum(1 for e in c["events"] if e[0] == "!")} for c in convs}
    rates = {"tool_calls": round(len(calls) / n, 2) if n else 0, "cmd_errors": round(len(errs) / n, 2) if n else 0,
             "cmd_error_rate": round(len(errs) / max(1, len(cmds)), 3), "step_errors": round(len(step_errs) / n, 2) if n else 0,
             "steer_candidates": round(len(steer) / n, 2) if n else 0}
    signals = {"tool": "antigravity", "window": [a.since, a.until], "sessions": n, "rates": rates, "tools": {k: sorted(v) for k, v in tool_sessions.items()},
               "error_signatures": {k: sorted(v) for k, v in err_sig.items()}, "families": {k: sorted(v) for k, v in fam_sessions.items()},
               "repeated_exact": {k: sorted(v) for k, v in exact.items() if len(v) >= 3}, "steer_candidates": steer,
               "first_prompts": {k: sorted(v) for k, v in first_prompts.items() if len(v) >= 2}, "sessions_detail": per}
    (out / "agy-signals.json").write_text(json.dumps(signals, indent=1, default=str))

    L = [f"# Antigravity (agy) audit signals: {n} conversations, {a.since} to {a.until or 'now'}",
         "All numbers below are computed, not estimated. Miners must not recount them.",
         "Payloads are protobuf without a schema: token counts and model names are not recoverable, so there is no token table.", ""]
    L += ["## Corpus", f"- conversations in window: {n} (summaries table lists {len(rows)})", f"- workspaces: {collections.Counter(c['ws'] for c in convs).most_common(8)}",
          f"- status: {dict(collections.Counter(c['status'] for c in convs))}", f"- per-session rates: {json.dumps(rates)}",
          f"- steps: {sum(c['steps'] for c in convs)}, tool calls: {len(calls)}, shell commands: {len(cmds)}, failed commands: {len(errs)}, steps with error_details: {len(step_errs)}", ""]
    L += ["## Tools by distinct sessions", *[f"  {len(v):3d} sessions {tool_calls[k]:5d} calls  {k}" for k, v in sorted(tool_sessions.items(), key=lambda kv: -len(kv[1]))]]
    L += ["", "## Command errors by signature (distinct sessions)"]
    for k, v in sorted(err_sig.items(), key=lambda kv: -len(kv[1]))[:40]: L.append(f"  {len(v)} sessions  {k}  [{', '.join(sorted(v)[:4])}]")
    L += ["", "## Step-level errors (error_details column)", *[f"- {id8(c)} step {e[3]}: {e[1]}" for c, e in step_errs[:30]]]
    L += ["", "## Command families by distinct sessions", *[f"  {len(v):3d} sessions {fam_calls[k]:5d} calls  {k}" for k, v in sorted(fam_sessions.items(), key=lambda kv: -len(kv[1]))[:40]]]
    L += ["", "## Exact commands repeated in ≥3 sessions", *[f"  {len(v)} sessions  {k}" for k, v in sorted(signals['repeated_exact'].items(), key=lambda kv: -len(kv[1]))[:30]]]
    L += ["", "## First-prompt fingerprints shared by ≥2 conversations (spawned/batch runs)"]
    for k, v in sorted(signals["first_prompts"].items(), key=lambda kv: -len(kv[1]))[:20]: L.append(f"  {len(v)} sessions  {k}  [{', '.join(sorted(v)[:5])}]")
    L += ["", "## Steer candidates (regex hit on a non-first user message, ~50% precision)", *[f"- {sid} steer? {q}" for sid, q in steer[:30]]]
    L += ["", "## Conversations", "| id | last modified | workspace | title | status | steps | user msgs | tool calls | cmds | cmd errors | step errors |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for sid, p in sorted(per.items(), key=lambda kv: -kv[1]["steps"]):
        L.append(f"| {sid} | {str(p['ts'])[:16]} | {p['ws']} | {clip(p['title'], 40)} | {p['status'].replace('CASCADE_RUN_STATUS_', '')} | {p['steps']} | {p['user_msgs']} | {p['tool_calls']} | {p['cmds']} | {p['cmd_errors']} | {p['step_errors']} |")
    (out / "agy-stats.md").write_text("\n".join(L) + "\n")

    blocks = []
    for c in convs:
        p = per[id8(c)]
        lines = [f"## SESSION {id8(c)} agy {str(c['ts'])[:16]} ws={c['ws']} title={clip(c['title'], 60)} steps={p['steps']} tools={p['tool_calls']} cmd_errors={p['cmd_errors']}"]
        for e in c["events"]:
            if e[0] == "U": lines.append(f"U: {clip(e[1], 500)}")
            elif e[0] in ("A", "A?"): lines.append(f"A: {clip(e[1], 300)}")
            elif e[0] == "call": lines.append(f"call {e[1]}({clip(e[4], 200)})")
            elif e[0] == "R":
                if e[4]: lines.append(f"$ {clip(e[4], 220)} → exit {e[5]}")
                else: lines.append(f"R {e[1]}: {clip(e[6], 160)}")
                if e[5] not in (0, None): lines.append(f"  ! {clip(e[6].split('Output:', 1)[-1], 240)}")
            elif e[0] == "!": lines.append(f"! step {e[3]} error: {e[1]}")
            elif e[0] == "?": lines.append(f"? {e[1]}")
        txt = "\n".join(lines)
        if len(txt) > 60000: txt = txt[:30000] + "\n… [middle of session elided by distiller] …\n" + txt[-28000:]
        blocks.append(txt)
    chunk, size, i, cur = a.chunk_kb * 1024, 0, 1, []
    def flush():
        nonlocal i, cur, size
        if cur: (out / f"digest-agy-{i:02d}.md").write_text("# Antigravity digest (chunk %d)\n\n" % i + "\n\n".join(cur) + "\n"); i += 1; cur = []; size = 0
    for b in blocks:
        if size + len(b) > chunk and cur: flush()
        cur.append(b); size += len(b)
    flush()
    print(f"agy sessions={n} tool_calls={len(calls)} cmds={len(cmds)} errors={len(errs)} steer?={len(steer)} digests={i-1} out={out}")

if __name__ == "__main__": main()
