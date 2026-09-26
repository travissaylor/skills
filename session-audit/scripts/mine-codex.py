#!/usr/bin/env python3
"""Distill OpenAI Codex CLI rollouts (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl) into
codex-stats.md, codex-signals.json and digest-codex-NN.md for /session-audit.

Digest blocks start with "## SESSION <id8>" so verify-findings.py checks quotes against them unchanged.
All numbers are computed here; miners classify and explain only.
"""
import argparse, json, re, collections, datetime
from pathlib import Path

STEER = re.compile(r"\b(no[,.]|don'?t|do not|instead|stop|not what|wrong|undo|revert|i said|actually|i don'?t want)\b", re.I)
INJECTED = ("<environment_context>", "<user_instructions>", "# AGENTS.md", "<permissions", "<turn_aborted")

def text_of(c):
    if c is None: return ""
    if isinstance(c, str): return c
    if isinstance(c, list): return "\n".join(text_of(x) for x in c)
    if isinstance(c, dict):
        for k in ("text", "input_text", "output_text", "content", "summary_text"):
            if k in c: return text_of(c[k])
        return ""
    return str(c)

def clip(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n] + "…"

def family(cmd):
    c = cmd.strip()
    c = re.sub(r"^(/bin/)?(bash|zsh|sh)\s+-l?c\s+", "", c).strip("'\"")
    c = re.sub(r"^(cd\s+\S+\s*(&&|;)\s*)+", "", c)
    c = re.sub(r"^(export\s+\S+=\S+\s*;?\s*|[A-Z_]+=\S+\s+)+", "", c)
    toks = c.split()
    if not toks: return "?"
    if toks[0] in ("git", "gh", "pnpm", "npm", "npx", "docker", "uv", "cargo", "go", "make", "python3", "python", "node", "codex", "agy", "claude") \
            and len(toks) > 1 and not toks[1].startswith("-"):
        return f"{toks[0]} {toks[1]}"
    return toks[0]

def parse(path):
    s = {"file": str(path), "id": None, "ts": None, "cwd": None, "cli": None, "originator": None, "source": None,
         "model": None, "effort": None, "approval": None, "sandbox": None,
         "events": [], "rs_user": [], "api_calls": 0, "tokens": {}, "turns": 0, "turn_ms": [], "ttft_ms": []}
    thread_usage = {}
    for line in open(path, errors="replace"):
        try: d = json.loads(line)
        except Exception: continue
        t = d.get("type"); p = d.get("payload") or {}; ts = d.get("timestamp")
        if not isinstance(p, dict): continue
        if t == "session_meta":
            s["id"] = p.get("id") or p.get("session_id"); s["ts"] = p.get("timestamp"); s["cwd"] = p.get("cwd")
            s["cli"] = p.get("cli_version"); s["originator"] = p.get("originator"); s["source"] = str(p.get("source"))[:30]
        elif t == "turn_context":
            s["model"] = s["model"] or p.get("model"); s["effort"] = s["effort"] or p.get("effort")
            s["approval"] = s["approval"] or str(p.get("approval_policy"))[:30]; s["sandbox"] = s["sandbox"] or str(p.get("sandbox_policy"))[:40]
        elif t == "token_usage_record":
            s["api_calls"] += 1
            thread_usage[p.get("thread_id")] = p.get("thread_token_usage") or {}
        elif t == "event_msg":
            et = p.get("type")
            if et == "task_started": s["turns"] += 1
            elif et == "task_complete":
                s["turn_ms"].append(p.get("duration_ms") or 0); s["ttft_ms"].append(p.get("time_to_first_token_ms") or 0)
            elif et == "item_completed":
                it = p.get("item") or {}; k = it.get("type")
                dur = (p.get("completed_at_ms") or 0) - (p.get("started_at_ms") or 0)
                if k == "UserMessage": s["events"].append(("U", text_of(it.get("content")), ts))
                elif k == "AgentMessage": s["events"].append(("A", text_of(it.get("content")), ts))
                elif k == "CommandExecution":
                    cmd = it.get("command") or ""
                    if isinstance(cmd, list): cmd = " ".join(map(str, cmd))
                    out = it.get("aggregated_output") or it.get("formatted_output") or it.get("stderr") or ""
                    s["events"].append(("$", cmd, ts, it.get("exit_code"), it.get("status"), text_of(out), dur))
                elif k == "FileChange":
                    ch = it.get("changes") or []
                    paths = [f"{c.get('kind','?')} {c.get('path','?')}" for c in ch if isinstance(c, dict)] if isinstance(ch, list) else [str(ch)[:100]]
                    s["events"].append(("F", "; ".join(paths), ts, it.get("status")))
                elif k == "WebSearch": s["events"].append(("W", str(it.get("query") or ""), ts))
                elif k == "Extension":
                    s["events"].append(("X", clip(json.dumps({kk: it.get(kk) for kk in ("source", "action") if kk in it}), 200), ts))
        elif t == "response_item":
            if p.get("type") == "function_call":
                s["events"].append(("fn", p.get("name") or "?", ts, clip(p.get("arguments") or "", 200)))
            elif p.get("type") == "message" and p.get("role") == "user":
                txt = text_of(p.get("content"))
                if not txt.lstrip().startswith(INJECTED): s["rs_user"].append((txt, ts))
    if not any(e[0] == "U" for e in s["events"]):
        for txt, ts in s["rs_user"]: s["events"].append(("U", txt, ts))
        s["events"].sort(key=lambda e: e[2] or "")
    tot = collections.Counter()
    for tu in thread_usage.values():
        for k, v in (tu or {}).items():
            if isinstance(v, (int, float)): tot[k] += v
    s["tokens"] = dict(tot)
    if not s["id"]:
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path.name)
        s["id"] = m.group(1) if m else path.stem
    if not s["ts"]:
        m = re.search(r"rollout-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})", path.name)
        s["ts"] = m.group(1).replace("T", "T").replace("-", ":", 0) if m else ""
    return s

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out"); ap.add_argument("--since", required=True); ap.add_argument("--until")
    ap.add_argument("--root", default=str(Path.home() / ".codex" / "sessions")); ap.add_argument("--chunk-kb", type=int, default=45)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    files = sorted(Path(a.root).rglob("rollout-*.jsonl"))
    sessions = []
    for f in files:
        m = re.search(r"rollout-(\d{4}-\d{2}-\d{2})", f.name)
        day = m.group(1) if m else ""
        if day < a.since or (a.until and day >= a.until): continue
        sessions.append(parse(f))
    sessions.sort(key=lambda s: s["ts"] or "")
    n = len(sessions)
    id8 = lambda s: (s["id"] or "")[:8]

    # ---- counts
    cmd_events = [(s, e) for s in sessions for e in s["events"] if e[0] == "$"]
    def is_err(e): return e[0] == "$" and ((e[3] not in (0, None)) or e[4] in ("failed", "error"))
    err_events = [(s, e) for s, e in cmd_events if is_err(e)]
    fam_sessions = collections.defaultdict(set); fam_calls = collections.Counter()
    for s, e in cmd_events: fam_sessions[family(e[1])].add(id8(s)); fam_calls[family(e[1])] += 1
    err_sig = collections.defaultdict(set)
    for s, e in err_events:
        first = clip((e[5] or "").strip().splitlines()[0] if (e[5] or "").strip() else "", 90)
        first = re.sub(r"\d+", "N", first)
        err_sig[f"{family(e[1])}: exit {e[3]} {first}"].add(id8(s))
    exact = collections.defaultdict(set)
    for s, e in cmd_events: exact[clip(e[1], 200)].add(id8(s))
    fn_names = collections.Counter(e[1] for s in sessions for e in s["events"] if e[0] == "fn")
    orig = collections.Counter(s["originator"] for s in sessions); models = collections.Counter(s["model"] for s in sessions)
    clis = collections.Counter(s["cli"] for s in sessions)
    cwds = collections.Counter(Path(s["cwd"] or "?").name for s in sessions)
    steer = []
    for s in sessions:
        us = [e for e in s["events"] if e[0] == "U"]
        for e in us[1:]:
            if STEER.search(e[1][:300]): steer.append((id8(s), clip(e[1], 160)))
    tok = collections.Counter()
    for s in sessions:
        for k, v in s["tokens"].items(): tok[k] += v
    first_prompts = collections.defaultdict(set)
    for s in sessions:
        us = [e for e in s["events"] if e[0] == "U"]
        if us: first_prompts[clip(us[0][1], 90)].add(id8(s))
    per = {id8(s): {"ts": s["ts"], "cwd": Path(s["cwd"] or "?").name, "originator": s["originator"], "model": s["model"], "cli": s["cli"],
                    "turns": s["turns"], "cmds": sum(1 for e in s["events"] if e[0] == "$"), "errors": sum(1 for e in s["events"] if is_err(e)),
                    "file_changes": sum(1 for e in s["events"] if e[0] == "F"), "api_calls": s["api_calls"],
                    "user_msgs": sum(1 for e in s["events"] if e[0] == "U"), "tokens": s["tokens"],
                    "turn_ms_max": max(s["turn_ms"] or [0])} for s in sessions}
    rates = {"cmds": round(len(cmd_events) / n, 2) if n else 0, "cmd_errors": round(len(err_events) / n, 2) if n else 0,
             "cmd_error_rate": round(len(err_events) / max(1, len(cmd_events)), 3), "steer_candidates": round(len(steer) / n, 2) if n else 0,
             "turns": round(sum(s["turns"] for s in sessions) / n, 2) if n else 0}
    signals = {"tool": "codex", "window": [a.since, a.until], "sessions": n, "rates": rates, "tokens": dict(tok), "originators": dict(orig),
               "models": dict(models), "cli_versions": dict(clis),
               "error_signatures": {k: sorted(v) for k, v in err_sig.items()}, "families": {k: sorted(v) for k, v in fam_sessions.items()},
               "repeated_exact": {k: sorted(v) for k, v in exact.items() if len(v) >= 3 or sum(1 for s, e in cmd_events if clip(e[1], 200) == k) >= 3},
               "steer_candidates": steer, "first_prompts": {k: sorted(v) for k, v in first_prompts.items() if len(v) >= 2}, "sessions_detail": per}
    (out / "codex-signals.json").write_text(json.dumps(signals, indent=1, default=str))

    # ---- stats.md
    L = [f"# Codex audit signals: {n} sessions, {a.since} to {a.until or 'now'}", "All numbers below are computed, not estimated. Miners must not recount them.", ""]
    L += ["## Corpus", f"- rollout files: {len(files)} total, {n} in window", f"- cli versions: {dict(clis)}", f"- originators: {dict(orig)}",
          f"- models: {dict(models)}", f"- effort: {dict(collections.Counter(s['effort'] for s in sessions))}",
          f"- approval policy: {dict(collections.Counter(s['approval'] for s in sessions))}",
          f"- top cwd: {cwds.most_common(8)}", f"- per-session rates: {json.dumps(rates)}",
          f"- commands: {len(cmd_events)}, failed: {len(err_events)}, file changes: {sum(p['file_changes'] for p in per.values())}, api responses: {sum(p['api_calls'] for p in per.values())}", ""]
    L += ["## Tokens (sum of last thread_token_usage per thread)", "| input | cached input | output | reasoning output | total |", "|---|---|---|---|---|",
          f"| {tok.get('input_tokens',0)//1000}k | {tok.get('cached_input_tokens',0)//1000}k | {tok.get('output_tokens',0)//1000}k | {tok.get('reasoning_output_tokens',0)//1000}k | {tok.get('total_tokens',0)//1000}k |", ""]
    L += ["## Command errors by signature (distinct sessions)"]
    for k, v in sorted(err_sig.items(), key=lambda kv: -len(kv[1]))[:40]: L.append(f"  {len(v)} sessions  {k}  [{', '.join(sorted(v)[:4])}{' +%d' % (len(v)-4) if len(v) > 4 else ''}]")
    L += ["", "## Command families by distinct sessions"]
    for k, v in sorted(fam_sessions.items(), key=lambda kv: -len(kv[1]))[:40]: L.append(f"  {len(v):3d} sessions {fam_calls[k]:5d} calls  {k}")
    L += ["", "## Exact commands repeated (≥3 sessions or ≥3 calls)"]
    for k, v in sorted(signals["repeated_exact"].items(), key=lambda kv: -len(kv[1]))[:30]: L.append(f"  {len(v)} sessions  {k}")
    L += ["", "## Non-shell function calls", *[f"  {c:4d}  {k}" for k, c in fn_names.most_common(20)]]
    L += ["", "## First-prompt fingerprints shared by ≥2 sessions (spawned/batch runs)"]
    for k, v in sorted(signals["first_prompts"].items(), key=lambda kv: -len(kv[1]))[:20]: L.append(f"  {len(v)} sessions  {k}  [{', '.join(sorted(v)[:5])}]")
    L += ["", "## Steer candidates (regex hit on a non-first user message, ~50% precision)"]
    for sid, q in steer[:30]: L.append(f"- {sid} steer? {q}")
    L += ["", "## Sessions", "| id | start | cwd | originator | model | turns | user msgs | cmds | errors | file changes | api | output tok | total tok | longest turn |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for sid, p in sorted(per.items(), key=lambda kv: -(kv[1]["tokens"].get("total_tokens", 0))):
        L.append(f"| {sid} | {str(p['ts'])[:16]} | {p['cwd']} | {p['originator']} | {p['model']} | {p['turns']} | {p['user_msgs']} | {p['cmds']} | {p['errors']} | {p['file_changes']} | {p['api_calls']} | {p['tokens'].get('output_tokens',0)//1000}k | {p['tokens'].get('total_tokens',0)//1000}k | {p['turn_ms_max']//1000}s |")
    (out / "codex-stats.md").write_text("\n".join(L) + "\n")

    # ---- digests
    blocks = []
    for s in sessions:
        p = per[id8(s)]
        hdr = f"## SESSION {id8(s)} codex {str(s['ts'])[:16]} cwd={p['cwd']} originator={p['originator']} model={p['model']} turns={p['turns']} cmds={p['cmds']} errors={p['errors']}"
        lines = [hdr]
        for e in s["events"]:
            if e[0] == "U": lines.append(f"U: {clip(e[1], 500)}")
            elif e[0] == "A": lines.append(f"A: {clip(e[1], 300)}")
            elif e[0] == "$":
                lines.append(f"$ {clip(e[1], 220)} → exit {e[3]} {e[4] or ''} {e[6]//1000 if e[6] else 0}s")
                if is_err(e): lines.append(f"  ! {clip(e[5], 240)}")
            elif e[0] == "F": lines.append(f"F: {clip(e[1], 200)} [{e[3]}]")
            elif e[0] == "W": lines.append(f"W: {clip(e[1], 160)}")
            elif e[0] == "X": lines.append(f"X: {e[1]}")
            elif e[0] == "fn": lines.append(f"fn {e[1]}({e[3]})")
        txt = "\n".join(lines)
        if len(txt) > 60000: txt = txt[:30000] + "\n… [middle of session elided by distiller] …\n" + txt[-28000:]
        blocks.append(txt)
    chunk, size, i, cur = a.chunk_kb * 1024, 0, 1, []
    def flush():
        nonlocal i, cur, size
        if cur: (out / f"digest-codex-{i:02d}.md").write_text("# Codex digest (chunk %d)\n\n" % i + "\n\n".join(cur) + "\n"); i += 1; cur = []; size = 0
    for b in blocks:
        if size + len(b) > chunk and cur: flush()
        cur.append(b); size += len(b)
    flush()
    print(f"codex sessions={n} cmds={len(cmd_events)} errors={len(err_events)} steer?={len(steer)} digests={i-1} out={out}")

if __name__ == "__main__": main()
