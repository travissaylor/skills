#!/usr/bin/env python3
"""Distill Claude Code session JSONL into digests + deterministic signals for /session-audit.

Outputs in OUT: stats.md (read in-session), signals.json (ledger + verify input),
digest-NN.md and episodes-NN.md (read by miner agents).

The JSONL format is internal to Claude Code and changes between releases. The schema
canary at the top of stats.md reports drift instead of silently undercounting.
"""
import argparse, collections, datetime, json, os, re, sys
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("out", help="output directory")
ap.add_argument("--since", help="sessions starting on/after YYYY-MM-DD")
ap.add_argument("--until", help="sessions starting before YYYY-MM-DD")
ap.add_argument("--project", help="substring filter on the project dir name")
ap.add_argument("--chunk-kb", type=int, default=45, help="digest/episode chunk size (default 45KB ≈ 22k tokens at ~2 bytes/token; Read caps at 25k)")
ap.add_argument("--min-sessions", type=int, default=3, help="min distinct sessions for a repeated-sequence candidate")
ap.add_argument("--root", help="projects dir to read (default ~/.claude/projects; tests pass a fixture)")
ap.add_argument("--data", help="local audit data dir holding ledger/, fixes.json, metrics.json (e.g. ~/.claude/session-audit)")
args = ap.parse_args()

HOME = str(Path.home())
HOME_SLUG = "-" + HOME.strip("/").replace("/", "-") + "-"  # ~/.claude/projects dir names start with this
ROOT = Path(args.root) if args.root else Path(HOME) / ".claude/projects"
OUT = Path(args.out); OUT.mkdir(parents=True, exist_ok=True)
SINCE, UNTIL = args.since or "", args.until or "9999"
BIG = 15_000  # chars; a tool result this size is a token-sink candidate
KNOWN_TYPES = {"user", "assistant", "system", "attachment", "summary", "mode", "last-prompt", "atis-latch",
               "file-history-snapshot", "file-history-delta", "queue-operation", "cost-state", "custom-title", "ai-title",
               "tag", "agent-name", "permission-mode", "pr-link", "frame-link", "artifact-comment-monitor",
               "artifact-autoreact-ledger"}
GENERIC_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "Grep", "Glob", "ToolSearch", "TodoWrite", "NotebookEdit"}
TRIVIAL_SHAPES = {"ls", "echo", "pwd", "true", "wc", "head", "tail", "cat", "sed -n", "grep", "sort", "uniq", "awk",
                  "cut", "tr", "xargs", "find", "jq", "python3", "date", "which", "test", "["}
STEER_RE = re.compile(
    r"\b(still (not|broken|wrong|showing|failing|seeing|getting|happening|there)|didn'?t work|doesn'?t work|"
    r"not working|isn'?t working|that'?s (not|wrong)|not what i|instead of|i don'?t (want|like|think|see)|"
    r"why (did|is|are|does) (you|it|this|that)|you (missed|forgot|didn'?t|skipped)|revert|undo|i said|"
    r"too (long|verbose|much|wordy)|shorter|wrong|broke|regress)", re.I)
INTERRUPT_RE = re.compile(r"\[Request interrupted by user[^\]]*\]")
SCRATCH_RE = re.compile(r"/private/tmp/claude-\d+/[^/\s]+/[0-9a-f-]{36}/scratchpad")
SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")


def norm_path(s):
    return SCRATCH_RE.sub("$SCRATCH", s).replace(HOME, "~")


def one_line(s, n):
    return norm_path(s[:n * 2]).replace("\n", " ⏎ ")[:n]


def compact_input(name, inp):
    if not isinstance(inp, dict): return one_line(str(inp), 160)
    if name == "Bash": return one_line(inp.get("command") or "", 220)
    if name in ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit"): return norm_path(inp.get("file_path", ""))
    if name == "Grep": return f"pattern={inp.get('pattern', '')[:60]} path={norm_path(inp.get('path', ''))}"
    if name == "Glob": return f"{inp.get('pattern', '')} in {norm_path(inp.get('path', ''))}"
    if name == "Agent": return f"type={inp.get('subagent_type')} model={inp.get('model')} desc={inp.get('description')} prompt_len={len(inp.get('prompt') or '')}"
    if name == "Skill": return f"{inp.get('skill')} {inp.get('args') or ''}"[:120]
    if name == "Workflow": return f"name={inp.get('name')} script_len={len(inp.get('script') or '')}"
    if name == "AskUserQuestion": return "; ".join(q.get("question", "")[:80] for q in inp.get("questions", []))
    return one_line(json.dumps(inp), 160)


def result_text(b):
    c = b.get("content")
    if isinstance(c, str): return c
    return "\n".join(x.get("text", "") for x in (c or []) if isinstance(x, dict) and x.get("type") == "text")


def text_of(content):
    if isinstance(content, str): return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", re.S)
QUOTED_RE = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
ERRLINE_RE = re.compile(r"(error|not found|no such|denied|failed|fatal|traceback|bad substitution|cannot|unknown|invalid|exceeds|timed? ?out)", re.I)


def err_signature(tool, err):
    """Stable key for grouping errors: the error line itself, digits and quoted values masked."""
    m = re.search(r'message\\?"\s*:\s*\\?"([^"\\]{8,})', err)
    line = m.group(1) if m else next((l for l in err.split(" ⏎ ") if ERRLINE_RE.search(l)), err.split(" ⏎ ")[0])
    sig = re.sub(r"\d+", "N", QUOTED_RE.sub("Q", line.strip()))[:90]
    return sig


def bash_shapes(cmd):
    """'cd x && FOO=1 git push -f | tee' -> ['git push', 'tee']: the command family, not its args."""
    out = []
    cmd = QUOTED_RE.sub("Q", HEREDOC_RE.sub("", cmd))
    for seg in re.split(r"\s*(?:&&|\|\||;|\||\n)\s*", cmd.strip()):
        seg = re.sub(r"^(?:[A-Z_][A-Z0-9_]*=\S+\s+)+", "", seg.strip())
        toks = seg.split()
        if not toks or toks[0] in ("cd", "then", "do", "done", "fi", "else", "Q") or not re.match(r"^[\w./~$-]", toks[0]): continue
        head = toks[0].split("/")[-1]
        sub = toks[1] if len(toks) > 1 and re.match(r"^[a-z][a-z:-]*$", toks[1]) else ""
        out.append(f"{head} {sub}".strip() if head not in ("echo", "cat", "sleep") else head)
    return out


def usage_tokens(u):
    return {k: u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}


# ---------- per-file parse ----------
schema = dict(unknown_types=collections.Counter(), files=0, assistant_records=0, unique_msgs=0,
              records_with_skill_attr=0, tool_results=0, cost_state_sessions=0)


def parse(path: Path):
    """One transcript -> ordered events + deduped usage. Assistant content blocks from one API
    response are separate lines sharing message.id and usage; keep one usage per id."""
    s = dict(events=[], usage={}, msg_skill={}, msg_model={}, msg_pos={}, tools={}, cost=None,
             first=None, last=None, api_errors=0, truncations=0, max_turns=0, version=None)
    schema["files"] += 1
    ev = s["events"]
    with open(path) as f:
        for line in f:
            try: r = json.loads(line)
            except ValueError: continue
            t = r.get("type")
            if t not in KNOWN_TYPES: schema["unknown_types"][t] += 1
            ts = r.get("timestamp")
            if ts: s["first"] = s["first"] or ts; s["last"] = ts
            s["version"] = r.get("version") or s["version"]
            if t == "cost-state": s["cost"] = r
            elif t == "system":
                if r.get("subtype") == "api_error": s["api_errors"] += 1
            elif t == "attachment":
                at = (r.get("attachment") or {}).get("type")
                if at == "read_truncation_notice": s["truncations"] += 1
                elif at == "max_turns_reached": s["max_turns"] += 1
            elif t == "assistant":
                schema["assistant_records"] += 1
                m = r.get("message") or {}
                mid = m.get("id") or r.get("uuid")
                skill = r.get("attributionSkill")
                if skill: schema["records_with_skill_attr"] += 1
                if mid not in s["usage"]:
                    s["msg_pos"][mid] = len(ev)
                    ev.append(("api", mid, skill))
                s["usage"][mid] = usage_tokens(m.get("usage") or {})
                s["msg_skill"][mid] = skill or s["msg_skill"].get(mid)
                s["msg_model"][mid] = m.get("model")
                for b in m.get("content") or []:
                    if not isinstance(b, dict): continue
                    if b.get("type") == "tool_use":
                        name, inp = b.get("name", ""), b.get("input") or {}
                        s["tools"][b.get("id")] = dict(name=name, inp=inp, arg=compact_input(name, inp),
                                                       skill=skill, pos=len(ev), err=None, rlen=0)
                        ev.append(("tool", b.get("id"), skill))
                    elif b.get("type") == "text":
                        tx = (b.get("text") or "").strip()
                        if tx: ev.append(("say", one_line(tx, 160), skill))
            elif t == "user" and not r.get("isMeta"):
                content = (r.get("message") or {}).get("content")
                if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                    for b in content:
                        if not (isinstance(b, dict) and b.get("type") == "tool_result"): continue
                        schema["tool_results"] += 1
                        tu = s["tools"].get(b.get("tool_use_id"))
                        if not tu: continue
                        txt = result_text(b)
                        tu["rlen"] = len(txt)
                        if b.get("is_error"): tu["err"] = one_line(txt.strip(), 600) or "(empty error)"
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "text" and INTERRUPT_RE.search(b.get("text", "")):
                            ev.append(("interrupt", INTERRUPT_RE.search(b["text"]).group(0), None))
                    continue
                txt = text_of(content).strip()
                if not txt: continue
                m = re.search(r"<command-name>/?([\w:.-]+)</command-name>", txt)
                if m: ev.append(("slash", m.group(1), None)); continue
                if INTERRUPT_RE.search(txt): ev.append(("interrupt", INTERRUPT_RE.search(txt).group(0), None)); continue
                if txt.startswith("<"): continue
                ev.append(("user", txt, ts))
    schema["unique_msgs"] += len(s["usage"])
    return s


def sub_meta(p: Path):
    try: return json.loads(p.with_suffix(".meta.json").read_text())
    except (OSError, ValueError): return {}


def api_calls_after(s, pos):
    return sum(1 for p in s["msg_pos"].values() if p > pos)


# ---------- collect ----------
sessions = []
for proj_dir in sorted(ROOT.iterdir()):
    if not proj_dir.is_dir() or (args.project and args.project not in proj_dir.name): continue
    project = re.sub(r"^(.+)-worktrees-\1-", "wt:", proj_dir.name.replace(HOME_SLUG, "").replace("projects-", "", 1))
    for sess in sorted(proj_dir.glob("*.jsonl")):
        if SINCE and datetime.date.fromtimestamp(sess.stat().st_mtime).isoformat() < SINCE: continue
        s = parse(sess)
        if not (SINCE <= (s["first"] or "")[:10] < UNTIL): continue
        if not any(e[0] in ("user", "slash") for e in s["events"]): continue
        s.update(id=sess.stem[:8], project=project, raw_kb=sess.stat().st_size // 1024, subs=[])
        if s["cost"]: schema["cost_state_sessions"] += 1
        for sp in sorted((proj_dir / sess.stem / "subagents").glob("*.jsonl")) if (proj_dir / sess.stem).is_dir() else []:
            sub = parse(sp); sub.update(id=sp.stem.replace("agent-", "")[:8], meta=sub_meta(sp))
            s["subs"].append(sub)
        sessions.append(s)
sessions.sort(key=lambda s: s["first"] or "")
if not sessions: sys.exit(f"no sessions in window since={SINCE or 'all'} until={args.until or 'now'}")

# ---------- aggregate ----------
C = collections.Counter
agg = dict(tools=C(), mcp=C(), skills_tool=C(), slash=C(), files_read=C(), files_read_sessions=collections.defaultdict(set),
           bash_full=C(), shape_sessions=collections.defaultdict(set), shape_calls=C(), ngram_sessions=collections.defaultdict(set),
           err_sig=collections.defaultdict(set), err_tool=C(), model_tokens=collections.defaultdict(C), sub_models=C(),
           sub_types=C())
skill = collections.defaultdict(lambda: dict(sessions=set(), runs=0, api_calls=0, tokens=C(), tool_calls=0, errors=0,
                                             steer_after=[], interrupt_after=[]))
big_results, flails, steers, interrupts, per_session = [], [], [], [], []
metrics = C()


DATA = Path(args.data).expanduser() if args.data else None
CUSTOM = json.loads((DATA / "metrics.json").read_text()) if DATA and (DATA / "metrics.json").exists() else []


def custom_match(cm, tu, is_sub):
    """metrics.json entry: name + any of tool, family (Bash command family), input, error (substrings), main_only."""
    name = tu["name"]
    if cm.get("main_only") and is_sub: return False
    if "tool" in cm and not (name == cm["tool"] or (name.startswith("mcp__") and cm["tool"] in name)): return False
    if "family" in cm and cm["family"] not in bash_shapes(tu["inp"].get("command") or ""): return False
    if "input" in cm and cm["input"] not in json.dumps(tu["inp"]): return False
    if "error" in cm and cm["error"] not in (tu["err"] or ""): return False
    return True


def fold_usage(s, into):
    for mid, u in s["usage"].items():
        into[s["msg_model"].get(mid) or "?"].update(u)


def tool_counts(s, sid, is_sub):
    for tid, tu in s["tools"].items():
        name = tu["name"]; agg["tools"][name] += 1; metrics["tool_calls"] += 1
        if name.startswith("mcp__"): agg["mcp"][name] += 1
        if tu["err"]:
            metrics["tool_errors"] += 1; agg["err_tool"][name] += 1
            key = name
            if name == "Bash":
                sh = [x for x in bash_shapes(tu["inp"].get("command") or "") if x not in TRIVIAL_SHAPES]
                key = f"Bash[{sh[0] if sh else 'shell'}]"
            agg["err_sig"][(key, err_signature(name, tu["err"]))].add(sid)
        if tu["rlen"] > BIG:
            carried = tu["rlen"] // 4 * api_calls_after(s, tu["pos"])
            big_results.append((carried, tu["rlen"], name, tu["arg"][:110], sid + ("/sub" if is_sub else "")))
            if not is_sub: metrics["main_big_results"] += 1
        for cm in CUSTOM:
            if custom_match(cm, tu, is_sub): metrics[cm["name"]] += 1
        if name == "Bash":
            cmd = tu["inp"].get("command") or ""
            agg["bash_full"][norm_path(cmd.strip())[:200]] += 1
            for sh in bash_shapes(cmd):
                agg["shape_calls"][sh] += 1; agg["shape_sessions"][sh].add(sid)
                if sh == "sleep":
                    n = re.search(r"\bsleep\s+(\d+)", cmd)
                    if n and int(n.group(1)) >= 30: metrics["blind_sleeps_30s"] += 1
            if re.search(r"(cat|tail|head|less)\b[^|]*tasks/[^\s]*\.output", cmd): metrics["task_output_reads"] += 1
        elif name == "Read":
            fp = norm_path(tu["inp"].get("file_path", "")); agg["files_read"][fp] += 1; agg["files_read_sessions"][fp].add(sid)
        elif name == "Skill": agg["skills_tool"][tu["inp"].get("skill", "")] += 1


def step_key(tu):
    n = tu["name"]
    if n == "Bash":
        sh = [x for x in bash_shapes(tu["inp"].get("command") or "") if x not in TRIVIAL_SHAPES]
        return "$ " + sh[0] if sh else None
    if n in GENERIC_TOOLS: return None
    if n.startswith("mcp__"): return n.split("__")[-1]
    if n == "Skill": return "skill:" + str(tu["inp"].get("skill"))
    return n


for s in sessions:
    sid = s["id"]
    fold_usage(s, agg["model_tokens"])
    tool_counts(s, sid, False)
    for sub in s["subs"]:
        fold_usage(sub, agg["model_tokens"]); tool_counts(sub, sid, True)
        mm = sub["meta"]; agg["sub_models"][mm.get("model") or "inherit"] += 1; agg["sub_types"][mm.get("agentType") or "?"] += 1
    # ordered walk of the main thread: skill runs, steer/interrupt after, error flails, n-grams
    ev, tools = s["events"], s["tools"]
    run_skill, last_run_skill, steps, errs_by_tool, user_turns = None, None, [], collections.defaultdict(list), 0
    for i, e in enumerate(ev):
        kind = e[0]
        if kind == "api":
            sk = s["msg_skill"].get(e[1])
            if sk:
                st = skill[sk]; st["api_calls"] += 1; st["tokens"].update(s["usage"][e[1]]); st["sessions"].add(sid)
                if sk != run_skill: st["runs"] += 1
                last_run_skill = sk
            run_skill = sk
        elif kind == "tool":
            tu = tools[e[1]]
            if tu["skill"]:
                skill[tu["skill"]]["tool_calls"] += 1
                if tu["err"]: skill[tu["skill"]]["errors"] += 1
            k = step_key(tu)
            if k: steps.append(k)
            if tu["err"]:
                errs_by_tool[tu["name"]].append(i)
                recent = [p for p in errs_by_tool[tu["name"]] if i - p <= 12]
                if len(recent) == 3: flails.append((sid, tu["name"], tu["arg"][:100], tu["err"][:120]))
        elif kind in ("user", "slash", "interrupt"):
            if kind == "slash": agg["slash"][e[1]] += 1
            if kind == "user":
                user_turns += 1; metrics["user_msgs"] += 1
                if user_turns > 1 and STEER_RE.search(e[1]):
                    steers.append((sid, e[1][:160].replace("\n", " "), last_run_skill))
                    if last_run_skill: skill[last_run_skill]["steer_after"].append(sid)
            if kind == "interrupt":
                interrupts.append((sid, e[1], last_run_skill))
                if last_run_skill: skill[last_run_skill]["interrupt_after"].append(sid)
            run_skill = last_run_skill = None
    for n in (3, 4):
        for j in range(len(steps) - n + 1):
            g = tuple(steps[j:j + n])
            if len(set(g)) > 1: agg["ngram_sessions"][g].add(sid)
    tot = C(); [tot.update(u) for u in s["usage"].values()]
    subtot = C(); [subtot.update(u) for sub in s["subs"] for u in sub["usage"].values()]
    cost = (s["cost"] or {}).get("totalCostUSD")
    per_session.append(dict(id=sid, project=s["project"], start=(s["first"] or "")[:16], raw_kb=s["raw_kb"],
                            api_calls=len(s["usage"]), subagents=len(s["subs"]), tokens=dict(tot), sub_tokens=dict(subtot),
                            cost_state_usd=round(cost, 2) if cost else None, tool_calls=len(tools),
                            errors=sum(1 for t in tools.values() if t["err"]), skills=sorted({x for x in s["msg_skill"].values() if x})))

metrics["sessions"] = len(sessions)
metrics["interrupts"] = len(interrupts); metrics["steer_candidates"] = len(steers); metrics["error_flails"] = len(flails)
metrics["sleep_segments"] = agg["shape_calls"]["sleep"]
opus = sum(v for k, v in agg["sub_models"].items() if "opus" in k)
cheap = sum(v for k, v in agg["sub_models"].items() if "sonnet" in k or "haiku" in k)
metrics["subagent_opus"], metrics["subagent_cheap"], metrics["subagent_inherit"] = opus, cheap, agg["sub_models"]["inherit"]
metrics["cost_state_usd"] = round(sum(p["cost_state_usd"] or 0 for p in per_session), 2)
metrics["big_results"] = len(big_results)
N = max(len(sessions), 1)
rates = {k: round(metrics[k] / N, 2) for k in ["tool_errors", "blind_sleeps_30s", "sleep_segments", "task_output_reads",
                                              "interrupts", "steer_candidates", "big_results", "main_big_results",
                                              "cost_state_usd"] + [cm["name"] for cm in CUSTOM]}
rates["subagent_opus_share"] = round(opus / max(opus + cheap + metrics["subagent_inherit"], 1), 2)
rates["tool_error_rate"] = round(metrics["tool_errors"] / max(metrics["tool_calls"], 1), 3)

# ---------- memory + skill hygiene (deterministic) ----------
hygiene = []
for md in sorted(ROOT.glob("*/memory")):
    proj = md.parent.name.replace(HOME_SLUG, "")
    idx = md / "MEMORY.md"
    files = {p.name: p for p in md.glob("*.md") if p.name != "MEMORY.md"}
    for name, p in files.items():
        head = p.read_text(errors="ignore")[:800]
        if p.stat().st_size > 20_000 and "archived:" not in head and "ARCHIVE" not in head:
            hygiene.append(f"{proj}: memory `{name}` is {p.stat().st_size // 1024}KB (loaded whole when recalled)")
        if not head.startswith("---"): hygiene.append(f"{proj}: memory `{name}` has no frontmatter")
    if idx.exists():
        it = idx.read_text(errors="ignore")
        if len(it) > 25_000 or it.count("\n") > 200:
            hygiene.append(f"{proj}: MEMORY.md is {len(it) // 1024}KB/{it.count(chr(10))} lines; only the first 200 lines / 25KB load")
        linked = set(re.findall(r"\(([\w./-]+\.md)\)", it))
        for n in sorted(set(files) - linked): hygiene.append(f"{proj}: `{n}` not in MEMORY.md index")
        for n in sorted(l for l in linked if "/" not in l and l not in files): hygiene.append(f"{proj}: index links missing `{n}`")
installed = sorted(p.parent.name for p in (Path(HOME) / ".claude/skills").glob("*/SKILL.md")) + \
            sorted(p.stem for p in (Path(HOME) / ".claude/commands").glob("*.md"))
used = set(skill) | set(agg["skills_tool"]) | set(agg["slash"])
unused_all = [n for n in installed if n not in used]
fam = C(n.split("-")[0] for n in unused_all)
unused = sorted({f"{n.split('-')[0]}-* ({fam[n.split('-')[0]]})" if fam[n.split("-")[0]] > 3 else n for n in unused_all})

# ---------- ledger + fix checks ----------
first, last = sessions[0]["first"][:10], sessions[-1]["first"][:10]
ledger_lines = []
if DATA:
    L = DATA / "ledger"
    prior = sorted(L.glob("20*.json"))
    prior = [p for p in prior if json.loads(p.read_text()).get("window", {}).get("since") != SINCE] or prior
    if prior:
        prev = json.loads(prior[-1].read_text())
        pr = prev.get("rates", {})
        ledger_lines.append(f"vs {prior[-1].stem} ({prev.get('metrics', {}).get('sessions')} sessions):")
        for k, v in rates.items():
            if k in pr: ledger_lines.append(f"- {k}: {pr[k]} → {v}")
    fx = DATA / "fixes.json"
    if fx.exists():
        for f in json.loads(fx.read_text()):
            cur = rates.get(f["metric"])
            if cur is None: ledger_lines.append(f"- FIX {f['id']}: metric `{f['metric']}` not computed"); continue
            better = cur < f["baseline"] if f.get("better", "lower") == "lower" else cur > f["baseline"]
            verdict = "holding" if better else "NOT HOLDING"
            if f["shipped"] > first:  # sessions before the ship date dilute the rate
                verdict += f" (UNMEASURED: window starts {first}, before the ship date; rerun with --since {f['shipped']})"
            ledger_lines.append(f"- FIX {f['id']} (shipped {f['shipped']}): {f['metric']} baseline {f['baseline']} → now {cur}: {verdict}")

# ---------- digests ----------
def render(s):
    out, cur_skill, prev_line, rep = [], None, None, 0
    def emit(l):
        nonlocal prev_line, rep
        if l == prev_line: rep += 1; return
        if rep: out.append(f"    (×{rep + 1})")
        out.append(l); prev_line, rep = l, 0
    user_turns = 0
    for e in s["events"]:
        kind = e[0]
        if kind == "api":
            sk = s["msg_skill"].get(e[1])
            if sk and sk != cur_skill: emit(f"  SKILL-TURN {sk}")
            cur_skill = sk
        elif kind == "tool":
            tu = s["tools"][e[1]]
            if tu["name"] == "ToolSearch": continue
            size = f" (→{tu['rlen'] // 1000}k)" if tu["rlen"] > 5000 else ""
            arg = tu["arg"]
            if tu["name"] == "Bash" and not tu["err"] and all(x in TRIVIAL_SHAPES for x in bash_shapes(tu["inp"].get("command") or "")):
                arg = arg[:90]  # read-only exploration: the family matters, the full args rarely do
            emit(f"  TOOL{'!' if tu['err'] else ''} {tu['name']}: {arg}{size}")
            if tu["err"]: emit(f"    ERR: {err_signature(tu['name'], tu['err'])}")
        elif kind == "say": emit(f"  ASSISTANT: {e[1]}")
        elif kind == "slash": emit(f"  USER SLASH /{e[1]}"); cur_skill = None
        elif kind == "interrupt": emit(f"  INTERRUPT {e[1]}"); cur_skill = None
        elif kind == "user":
            user_turns += 1
            flag = "[steer?]" if user_turns > 1 and STEER_RE.search(e[1]) else ""
            emit(f"  USER{flag}[{(e[2] or '')[:16]}]: {one_line(e[1], 500)}"); cur_skill = None
    if rep: out.append(f"    (×{rep + 1})")
    for sub in s["subs"]:
        mm = sub["meta"]; tc = C(t["name"] for t in sub["tools"].values())
        errs = [t for t in sub["tools"].values() if t["err"]]
        tok = sum(u["output_tokens"] + u["cache_creation_input_tokens"] + u["input_tokens"] for u in sub["usage"].values())
        out.append(f"  SUBAGENT {sub['id']} type={mm.get('agentType')} model={mm.get('model') or 'inherit'} desc={one_line(mm.get('description') or '', 60)} "
                   f"calls={len(sub['usage'])} new_tokens={tok // 1000}k errors={len(errs)} | " + " ".join(f"{k}x{v}" for k, v in tc.most_common(6)))
        for t in errs[:3]: out.append(f"    sub ERR {t['name']}: {t['arg'][:80]} → {t['err'][:100]}")
    big = sorted(((t["rlen"], t["name"], t["arg"]) for t in s["tools"].values() if t["rlen"] > BIG), reverse=True)[:6]
    if big: out.append("  LARGE_TOOL_RESULTS: " + "; ".join(f"{n // 1000}k {nm} {a[:70]}" for n, nm, a in big))
    return out


idx, chunk, size, digest_of = 0, [], 0, {}
def flush():
    global idx, chunk, size
    if chunk: idx += 1; (OUT / f"digest-{idx:02d}.md").write_text("\n".join(chunk))
    chunk, size = [], 0
for s, ps in zip(sessions, per_session):
    t = ps["tokens"]
    block = (f"\n## SESSION {s['id']} project={s['project']} start={ps['start']} raw={s['raw_kb']}KB api_calls={ps['api_calls']} "
             f"out_tokens={t.get('output_tokens', 0) // 1000}k cost_state=${ps['cost_state_usd']} subagents={len(s['subs'])} errors={ps['errors']}\n"
             + "\n".join(render(s)) + "\n")
    if size + len(block) > args.chunk_kb * 1000 and chunk: flush()
    chunk.append(block); size += len(block); digest_of[s["id"]] = idx + 1
flush()

# episodes: windows around failures, grouped by the skill active at the time
def benign(tu):
    """grep/ls/sed exiting non-zero with no message: normal exploration, not a failure."""
    return tu["name"] == "Bash" and err_signature("Bash", tu["err"]) == "Exit code N" and \
        all(x in TRIVIAL_SHAPES for x in bash_shapes(tu["inp"].get("command") or ""))


episodes, benign_skipped = collections.defaultdict(list), 0
for s in sessions:
    lines = render(s)
    benign_args = {f"  TOOL! Bash: {t['arg'][:90]}" for t in s["tools"].values() if t["err"] and benign(t)}
    for i, l in enumerate(lines):
        if l in benign_args or any(l.startswith(b) for b in benign_args if len(b) > 20 and l.startswith("  TOOL! Bash")):
            benign_skipped += 1; continue
        if l.startswith(("  TOOL!", "  INTERRUPT")) or l.startswith("  USER[steer?]"):
            owner = None
            for x in reversed(lines[:i]):  # nearest turn marker above; a user line first means no skill owned it
                if x.startswith("  SKILL-TURN"): owner = x.split()[-1]; break
                if x.startswith(("  USER", "  INTERRUPT")): break
            episodes[owner or "(no skill)"].append((s["id"], "\n".join(lines[max(0, i - 5):i + 3])))
for old_ep in OUT.glob("episodes*.md"): old_ep.unlink()
ep_idx, ep_buf = 0, (f"# Failure episodes (±5 lines around each error, interrupt, or steer candidate), grouped by active skill\n"
                     f"{benign_skipped} benign errors skipped (read-only shell commands exiting non-zero with no message).\n")
for owner, eps in sorted(episodes.items(), key=lambda kv: -len(kv[1])):
    header = f"\n## {owner}: {len(eps)} episodes in {len({e[0] for e in eps})} sessions\n"
    ep_buf += header
    for sid, txt in eps:
        item = f"\n### {sid}\n{txt}\n"
        if len(ep_buf) + len(item) > args.chunk_kb * 1000:  # split between episodes, never inside one
            ep_idx += 1; (OUT / f"episodes-{ep_idx:02d}.md").write_text(ep_buf)
            ep_buf = header.replace(":", " (cont.):", 1)
        ep_buf += item
ep_idx += 1; (OUT / f"episodes-{ep_idx:02d}.md").write_text(ep_buf)

# ---------- stats.md ----------
def top(c, n): return "\n".join(f"{v:6d}  {k}" for k, v in c.most_common(n))
def sess_list(ss, n=6): ss = sorted(ss); return ", ".join(ss[:n]) + (f" +{len(ss) - n}" if len(ss) > n else "")
drift = []
if schema["unknown_types"]: drift.append(f"unknown record types {dict(schema['unknown_types'])}")
if schema["assistant_records"] and not schema["records_with_skill_attr"]: drift.append("no attributionSkill fields: per-skill stats are empty")
if schema["assistant_records"] and schema["unique_msgs"] == schema["assistant_records"]: drift.append("no multi-line API responses: check usage dedupe still needed")
if schema["tool_results"] == 0: drift.append("no tool_result blocks parsed")
versions = C(s["version"] for s in sessions)
mt = agg["model_tokens"]
tok_rows = "\n".join(f"| {m} | {u['input_tokens'] // 1000:,}k | {u['output_tokens'] // 1000:,}k | {u['cache_creation_input_tokens'] // 1_000_000:,}M | {u['cache_read_input_tokens'] // 1_000_000:,}M |"
                     for m, u in sorted(mt.items(), key=lambda kv: -kv[1]["output_tokens"]))
sk_rows = "\n".join(
    f"| {n} | {len(st['sessions'])} | {st['runs']} | {st['api_calls']} | {st['tokens']['output_tokens'] // 1000}k | {st['tool_calls']} | {st['errors']} | "
    f"{len(st['steer_after'])} | {len(st['interrupt_after'])} |"
    for n, st in sorted(skill.items(), key=lambda kv: -kv[1]["api_calls"]))
ngrams = sorted(((len(v), k) for k, v in agg["ngram_sessions"].items() if len(v) >= args.min_sessions), reverse=True)
seen, ng_lines = [], []
for n, g in ngrams:  # drop 3-grams contained in an equally common 4-gram
    if any(set(g) <= set(h) and m >= n for m, h in seen): continue
    seen.append((n, g)); ng_lines.append(f"{n:4d} sessions  {' → '.join(g)}  [{sess_list(agg['ngram_sessions'][g], 4)}]")
    if len(ng_lines) >= 40: break
err_lines = [f"{len(ss):3d} sessions  {tool}: {sig}  [{sess_list(ss, 4)}]" for (tool, sig), ss in
             sorted(agg["err_sig"].items(), key=lambda kv: -len(kv[1])) if len(ss) >= 1][:30]
big_results.sort(reverse=True)
stats = f"""# Session audit signals: {len(sessions)} sessions, {first} to {last}
All numbers below are computed, not estimated. Miners must not recount them.

## Schema canary
Claude Code versions: {dict(versions.most_common(4))}
Assistant records {schema['assistant_records']} → unique API responses {schema['unique_msgs']} (usage deduped by message.id). Sessions with cost-state: {schema['cost_state_sessions']}/{len(sessions)}.
{('DRIFT: ' + '; '.join(drift)) if drift else 'No drift detected.'}

## Red flags (verify before reporting)
- per-session rates: {json.dumps(rates)}
- blind waits: {metrics['blind_sleeps_30s']} `sleep ≥30s`, {metrics['task_output_reads']} reads of tasks/*.output
- subagent models: opus {opus}, sonnet/haiku {cheap}, inherit {metrics['subagent_inherit']}
- custom metrics ({DATA / 'metrics.json' if DATA else 'none'}): {json.dumps({cm['name']: metrics[cm['name']] for cm in CUSTOM}) if CUSTOM else 'none defined'}
- error flails (3+ errors from one tool within 12 events): {len(flails)}
- hygiene: {len(hygiene)} issues (below)

## Trend vs last audit and shipped fixes
{chr(10).join(ledger_lines) or '(no --data dir given or no prior ledger entry)'}

## Tokens by model (deduped; main + subagents)
| model | input | output | cache write | cache read |
|---|---|---|---|---|
{tok_rows}
cost-state total (as recorded by Claude Code): ${metrics['cost_state_usd']}

## Skill health (turn-scoped: a skill owns the assistant turns from its load until the next user message; tokens are an upper bound for skills loaded mid-turn)
| skill | sessions | runs | api calls | output tok | tool calls | tool errors | steer? after | interrupted after |
|---|---|---|---|---|---|---|---|---|
{sk_rows}
Installed but unused in window: {', '.join(unused) or 'none'}

## Tool errors by signature (distinct sessions)
{chr(10).join(err_lines) or 'none'}

## Error flails: session, tool, last args → error
{chr(10).join(f'- {a} {b}: `{c}` → {d}' for a, b, c, d in flails[:25]) or 'none'}

## Repeated tool sequences (non-trivial steps, ≥{args.min_sessions} sessions): automation candidates
{chr(10).join(ng_lines) or 'none'}

## Bash command families by distinct sessions
{chr(10).join(f"{len(v):4d} sessions {agg['shape_calls'][k]:5d} calls  {k}" for k, v in sorted(agg['shape_sessions'].items(), key=lambda kv: -len(kv[1]))[:50])}

## Largest tool results, ranked by carried cost (≈tokens × later API calls in that thread)
{chr(10).join(f"{c // 1000:6d}k carried {n // 4000:4d}k tok {nm:10s} {a}  [{sid}]" for c, n, nm, a, sid in big_results[:40])}

## Interrupts and steer candidates (steer? is a regex hit, ~50% precision: read the episode before counting it)
{chr(10).join(f'- {a} INTERRUPT after skill={c}' for a, b, c in interrupts) or '- no interrupts'}
{chr(10).join(f'- {a} steer? after skill={c}: {b}' for a, b, c in steers[:60])}

## Memory and skill hygiene
{chr(10).join('- ' + h for h in hygiene) or 'clean'}

## Sessions by cost
{chr(10).join(f"- {p['id']} {p['start']} {p['project']}: ${p['cost_state_usd']} api={p['api_calls']} out={p['tokens'].get('output_tokens', 0) // 1000}k subagents={p['subagents']} errors={p['errors']} skills={','.join(p['skills'])}" for p in sorted(per_session, key=lambda p: -(p['cost_state_usd'] or 0))[:25])}

## Tool counts
{top(agg['tools'], 30)}

## Slash commands / Skill tool calls
{top(agg['slash'], 25)}
{top(agg['skills_tool'], 25)}

## Subagent types
{top(agg['sub_types'], 15)}

## Exact Bash commands repeated ≥3 times
{chr(10).join(f"{v:5d}  {k}" for k, v in agg['bash_full'].most_common(60) if v >= 3)}

## Files read in the most sessions
{chr(10).join(f"{len(v):4d} sessions {agg['files_read'][k]:4d} reads  {k}" for k, v in sorted(agg['files_read_sessions'].items(), key=lambda kv: -len(kv[1]))[:30])}
"""
(OUT / "stats.md").write_text(stats)
signals = dict(window=dict(since=SINCE or first, until=args.until or last, first=first, last=last), metrics=dict(metrics), rates=rates,
               schema={k: (dict(v) if isinstance(v, C) else v) for k, v in schema.items()},
               sessions={p["id"]: dict(p, digest=digest_of[p["id"]]) for p in per_session},
               skills={n: dict(sessions=sorted(st["sessions"]), runs=st["runs"], api_calls=st["api_calls"], tokens=dict(st["tokens"]),
                               tool_calls=st["tool_calls"], errors=st["errors"], steer_after=st["steer_after"],
                               interrupt_after=st["interrupt_after"]) for n, st in skill.items()},
               hygiene=hygiene, unused_skills=unused_all)
(OUT / "signals.json").write_text(json.dumps(signals, indent=1, default=list))
print(f"sessions={len(sessions)} digests={idx} episodes={ep_idx} tool_calls={metrics['tool_calls']} errors={metrics['tool_errors']} "
      f"steer?={len(steers)} interrupts={len(interrupts)} drift={'YES' if drift else 'no'} out={OUT}")
