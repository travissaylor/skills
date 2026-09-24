---
name: session-audit
description: Audits Claude Code session history (transcripts, memory, skills) for repeated manual work, skills that misfire, tool failures, and token waste, then proposes scripts, skill fixes, and rules ranked by sessions affected. A deterministic distiller does all counting, Sonnet miners classify and explain, and every finding is quote-verified and checked on the live machine before the user sees it. Also re-measures whether earlier audit fixes held. Use when the user says "/session-audit", "audit my sessions", "what am I doing repeatedly", "find pain points in my Claude usage", "where are my tokens going", "did the audit fixes stick", or "let's do the session review again".
---

# /session-audit

Mine session history for work that should be a script, a skill fix, or a rule. Accuracy comes before token savings: a wrong "do today" item costs the user more than a slower audit.

State at load (from the local data dir, never the skill dir):
!`cat ~/.claude/session-audit/state.json 2>/dev/null || echo '{"last_run": null, "note": "first run"}'`

## Why the pipeline has this shape

- **Scripts count, models judge.** Models score under 50% on aggregation at 128K (Oolong, 2025) and 14% on locating the failing step in a trace (Who&When, 2025). So `mine-transcripts.py` computes every number and flags every candidate event. Miners only classify, explain, and propose.
- **Small chunks, one per agent.** Recall drops well before 32K tokens (RULER, NoLiMa). Digests are ~23K tokens and each miner reads one.
- **Quotes or it didn't happen.** Unverified findings from LLMs run ~25% false positives even after filtering (BitsAI-CR), and an adversarial check removes most of the rest (Refute-or-Promote). `verify-findings.py` drops any finding whose quote isn't in the transcript. You then try to refute each survivor on the live machine.

## Checklist

```
- [ ] 0. Window from state, warn if sessions have aged out
- [ ] 1. Test, distill, read stats.md, stop on schema drift
- [ ] 2. Fan out Sonnet miners (Role A per episodes file, Role B per digest)
- [ ] 3. verify-findings.py, drop UNSUPPORTED
- [ ] 4. Refute survivors on the live machine
- [ ] 5. Write the report
- [ ] 6. Walk the tiers with the user
- [ ] 7. Close out: ledger, fixes.json, state, memory
```

## 0. Window

```bash
SA=<this skill's directory>
DATA=~/.claude/session-audit            # local state: never commit it with the skill
OUT=<session scratchpad>/audit
REPORTS=<state.json report_dir, else $DATA/reports>
```

`$DATA` holds `state.json`, `fixes.json`, `metrics.json`, and a `ledger` directory. On a first run it doesn't exist yet: `mkdir -p $DATA/ledger` and audit the last 30 days.

Window = `last_run` to now, unless the user names one. Claude Code deletes transcripts after 30 days (`cleanupPeriodDays`), and `$DATA/ledger/` is the only record older than that. If `last_run` is more than 25 days back, the report's corpus line must say which days were already gone.

## 1. Test, distill, read

Run these. Don't read the scripts.

```bash
python3 $SA/scripts/test_mine_transcripts.py          # must print only PASS lines
python3 $SA/scripts/mine-transcripts.py $OUT --since <last_run> --data $DATA
```

Read `$OUT/stats.md` in full (6K tokens for a week, 12K for a month). It holds the schema canary, the per-session rates, the fix check, and these tables:
- tokens by model
- skill health
- error signatures
- repeated tool sequences
- carried-cost token sinks
- steer and interrupt candidates
- memory hygiene

**If the canary says DRIFT, stop.** The JSONL format is internal to Claude Code and changes between releases. A new record type that is harmless goes in `KNOWN_TYPES`. A missing field (`attributionSkill`, `message.id`, `tool_result`) means some stats are silently zero, so fix the parser and rerun the test before going on.

Never read raw JSONL, digests, or episode files in this session. The miners read those.

## 2. Fan out miners

Send every `Agent` call in one message: `model: sonnet`, `subagent_type: general-purpose`, `run_in_background: true`.

- **Role A, one per `episodes-NN.md`:** "Read `$SA/references/agent-brief.md` and follow it as Role A. Files: `$OUT/stats.md`, `$OUT/episodes-NN.md`. Write findings to `$OUT/findings/A-NN.md` and return the same content."
- **Role B, one per `digest-NN.md`:** the same prompt with Role B, `$OUT/digest-NN.md`, and `$OUT/findings/B-NN.md`.

Wait for the notifications. Don't poll or read task output files. Record each notification's `subagent_tokens` for the close-out.

## 3. Verify evidence

```bash
python3 $SA/scripts/verify-findings.py $OUT
```

Drop every `UNSUPPORTED` finding. For a `PARTIAL` one, keep only the verified sessions. Then merge duplicates across miners. Take counts from `stats.md` or `signals.json`, never from a miner.

## 4. Refute on the live machine

For each finding headed to the report, run the one check most likely to prove it wrong. Each miner names its own "what would disprove it".

- **"Doesn't exist yet"** → `ls` the skill and scripts dirs, and `grep -ril` memory and CLAUDE.md.
- **"Is broken"** → run the script or command once.
- **"Keeps happening"** → check `signals.json` and see whether the sessions fall after the fix date in `fixes.json`.

Anything refuted goes to the report's **Dropped** section with the command that refuted it. Expect to drop a good share of findings. That is the check working, not a failed audit.

## 5. Report

Follow `$SA/references/report-template.md`. Rank by sessions affected. Every "do today" item carries the live check that confirmed it. Write it straight to `$REPORTS/session-audit-<date>.md`, never the scratchpad: the user opens it from there.

## 6. Walk the tiers

Present "Did the last fixes hold" and "Do today" first, then stop. The user answers item by item. Do the ones they pick and verify each one by running the thing, not by rereading the diff. Then move on to skills that misfired, token sinks, tooling, and skill candidates. Most of the later tiers get shelved, and that's expected.

## 7. Close out

1. `cp $OUT/signals.json $DATA/ledger/<today>.json`. The next run diffs against this file.
2. For each fix shipped today that a metric can observe, append `{id, shipped, metric, baseline, better, where}` to `$DATA/fixes.json`. Take `baseline` from this run's `rates`. If no metric can see the fix, add a matcher to `$DATA/metrics.json`: `{name, tool, family?, input?, error?, main_only?}`, where each field is a substring match. Only a metric no matcher can express needs a code change, plus a test assertion. Otherwise the next audit can't tell whether the fix held.
3. Update `$DATA/state.json` with `last_run`, `sessions_covered`, `miner_tokens`, and `report_dir` if the user keeps reports elsewhere.
4. Rewrite the memory `project_session_audit_followups.md` (in the most-used project's memory dir, created on the first run) with what was done and what was shelved, ranked. Update its `MEMORY.md` line.

## Gotchas

- **`steer?` is about 50% precise.** Users redirect in plain words ("I don't like…", "instead of…"), and just as often those words add scope. Never count steers without a Role A verdict.
- **Skill tokens are an upper bound.** A skill owns every turn from its load to the next user message. A `principle-*` or `prose` skill loaded mid-turn gets charged for the whole turn.
- **`cost_state_usd` is a lower bound.** Only some sessions write `cost-state`. Compare runs with the token table and the per-session rates.
- **Propose skills that own a workflow or an artifact type.** A skill whose whole content is wording or register rarely earns its context cost.
- **Memory trims split the file, never delete it.** Split into a current-state file plus a `*_history.md` with `archived:` in its frontmatter.
- **Model and wait rules go in two places:** the skill that misbehaved and a feedback memory, so the rule holds outside the skill.
- **On macOS, proposed scripts must run on bash 3.2:** no `mapfile`, no `declare -A`.

## Files

| File | Use |
|---|---|
| `scripts/mine-transcripts.py` | Execute. Writes `stats.md`, `signals.json`, `digest-NN.md`, and `episodes-NN.md`. `--help` for flags. |
| `scripts/verify-findings.py` | Execute after the miners. Exits 1 if any finding is unsupported. |
| `scripts/test_mine_transcripts.py` | Execute before each run and after editing either script. |
| `references/agent-brief.md` | Miners read it. You don't need to. |
| `references/report-template.md` | Read at step 5. |
| `$DATA/fixes.json`, `metrics.json`, and the ledger | Local, written at close-out. The distiller reads them through `--data`. |
