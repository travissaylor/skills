---
name: conductor-multi
description: Conductor with pluggable executors. The main session plans disjoint work units, then fans each unit out to the executor best suited to it, a Claude subagent, OpenAI Codex CLI, or Google Antigravity CLI (agy), all editing the shared tree in parallel. The orchestrator adjudicates every diff itself, runs gates once per wave, and commits. Use when the user says "conductor-multi", wants Codex or Antigravity to implement parts of a decomposed task, or wants to compare executors on the same plan.
---

# Conductor-multi: one plan, several executors

You are the orchestrator. This skill is the `conductor` loop with one change: each unit names a **backend**. Claude units run through the Agent tool as before. Codex and agy units run as background shell processes launched by `scripts/run-unit.sh`, which feeds them a brief file, pins the sandbox and output flags, enforces timeouts, and writes a report that matches `result.schema.json`. Everything else, planning, ownership, adjudication, gates, and git, stays in this session.

## Preconditions

- Git repository with a CLEAN working tree (`git status --porcelain` empty). Executors edit the tree directly. If dirty, stop and ask the user to commit or stash.
- Record the baseline: `git rev-parse HEAD` and the branch.
- Only YOU touch git. Codex cannot write `.git` inside its sandbox. Agy can, so its brief must forbid it and you must check.
- Check the backends you plan to use exist: `command -v codex agy jq`. Drop a backend that is missing rather than silently substituting.
- Create a run directory for briefs and reports. Use the session scratchpad if one exists, otherwise a temp dir. Never put it inside the repo.

## Phase 1: plan (in-session)

If the user has not stated a goal, ask. Do not guess.

Orient first: read the repo docs (CLAUDE.md, AGENTS.md, README), survey the code the task touches, skim the tests. Note that Codex reads `AGENTS.md` on its own and agy reads the workspace rules, so repo-level conventions that live there need not be repeated in every brief. Anything that lives only in CLAUDE.md must be copied into the constraints list.

Detect the **gates** from the repo manifest, unless the user supplied them: build, lint, typecheck, and test commands. Skip slow e2e and integration suites. You run gates once per wave. Executors never run the full suite.

Derive a SHORT **constraints** list stamped into every brief: the master goal, hard rules from the repo docs, "match surrounding file style and conventions", and any user constraints verbatim.

Break the task into **units** (coarse-grained, roughly 3 to 7). Each unit has:

- `id`: short kebab-case
- `title`
- `scope`: what to build and what NOT to touch
- `owned files`: the EXCLUSIVE file set it may create or edit
- `acceptance`: a concrete checklist verifiable by reading code or running checks
- `dependsOn`: unit ids that must land first. Keep the graph shallow.
- `backend`: `claude`, `codex`, or `agy`
- `model`: optional override. Leave unset to use each CLI's configured default. For Claude, `sonnet` normally, `opus` only when the unit genuinely needs it.
- `scoped checks`: the fastest deterministic commands relevant to this unit alone. Optional. Keep them fast.

**Choosing a backend.** Route by the shape of the unit, not by preference:

- `codex`: bounded implementation with crisp acceptance items and a runnable scoped check. Its sandbox blocks git writes and network, which makes it the safest external executor.
- `agy`: the same shape when the user wants a Gemini model, a second vendor's attempt, or a comparison. Slower and heavier on tokens in testing. No git fence.
- `claude`: units that need repo-wide judgment, ambiguous scope, or heavy reading across files outside their ownership. Also the fallback when a backend is missing.

Honor the user's routing if they gave one ("do the API in codex, the UI in agy").

**Hard rule:** units in the same wave MUST have disjoint owned-file sets, regardless of backend. Sequence or merge units that need the same file. Ownership mistakes are the failure mode of this whole design.

Do NOT include as units: browser or E2E verification, DB reseeding, deployments, or PR creation.

Track progress with a unit table in your messages: one line per unit with backend, attempt count, and status, reposted as verdicts land.

## Phase 2: execute a wave (all backends in one message)

A wave is every remaining unit whose `dependsOn` are all landed or dropped.

Dispatch the whole wave in **ONE message**: one Agent call per Claude unit, and one Bash call with `run_in_background: true` per Codex or agy unit. Same-message calls run concurrently. Sequential messages serialize, which defeats the point.

### Briefs

Write `<run-dir>/<unit-id>.brief.md` for every external unit before launching. The brief is the executor's entire world. It must contain, in this order:

1. **Workspace**: the absolute repo path, stated as "All paths below are relative to this root. Work only inside it." Agy will otherwise work in its own scratch directory and report success.
2. **Task context**: the overall goal in two or three sentences, marked "context only, build ONLY your unit".
3. **Your unit**: title, scope, the exact owned-file list, the acceptance checklist.
4. **Constraints**: the constraints list, verbatim.
5. **Rules**, verbatim:
   - "Edit ONLY the files in your owned-file list. Other agents own other files. Touching theirs corrupts the run."
   - "Run NO git commands of any kind. The orchestrator owns git."
   - "Do not run dev servers, browsers, docker, deployments, database writes, or long e2e or integration suites. Do not install packages."
6. **Scoped checks**: the exact commands, or "none".
7. **Retry notes**, if any (see Phase 3).
8. **Report**: "Your final message must be the JSON report the output schema describes. `files_changed` holds repo-relative paths only. List every acceptance item with `met` true or false. Put trimmed failure output in `checks`. No diffs, no file contents."

Claude units get the same content as the Agent prompt, plus the usual instruction to report a tight structured summary.

### Launching external units

```bash
<skill-dir>/scripts/run-unit.sh --backend codex --unit <id> --run-dir <run-dir> --repo <repo> [--model <name>]
<skill-dir>/scripts/run-unit.sh --backend agy   --unit <id> --run-dir <run-dir> --repo <repo> [--model <name>]
```

Resolve `<skill-dir>` from the path of this SKILL.md. Defaults: 10 minute stall limit (Codex only, based on event-stream activity) and a 60 minute wall-clock ceiling. Override with `--stall` and `--max` for big units.

The script exits when the executor finishes, and Claude Code notifies you of the background completion. Do not poll. While waiting, adjudicate any Claude units that have already reported.

Under the hood, Codex runs `codex exec` with the brief on stdin, `-C <repo>`, `-s workspace-write`, `--json`, and `--output-schema`. Agy runs `agy --print` with `--add-dir <repo>`, `--mode accept-edits`, `--output-format json`, and `--json-schema`. Do not launch either CLI by hand. The flags are the product of testing, and the script also captures thread ids for retries.

## Phase 3: adjudicate (in-session, per unit)

You grade every unit yourself. Be skeptical. A "done" claim with a vague file list, a failed scoped check, or a footprint that disagrees with the report is a red flag.

For each unit in the wave:

1. **Read the report.** External units: `<unit>.meta.json` first (`outcome` is `completed`, `failed`, `stalled`, or `timeout`), then `<unit>.result.json`. A missing result with outcome `failed` means the CLI errored. Read the tail of `<unit>.stderr` and treat it as a retry with the error quoted, unless it is an auth or quota failure, in which case reroute the unit to another backend.
2. **Verify the footprint.** `git status --porcelain` plus `git diff --stat -- <owned files>`. The changed files must match `files_changed`, and nothing outside the unit's ownership may be touched. Out-of-scope edits: restore stray files with `git checkout -- <files>`, delete stray untracked files, and note it in the retry. Agy units get this check every time. It has no sandbox fence.
3. **Spot-read the diff** of load-bearing files (`git diff -- <file>`, and read new files directly). Check the acceptance items gates cannot verify: intent, constraint adherence, semantic drift. Use `--stat` first and read full diffs only where needed.
4. **Verdict:**
   - **pass**: proceeds to gating.
   - **retry**: fixable. Write concrete fix notes. Retries fix the existing attempt IN PLACE. For external units, rewrite the brief with a "Retry notes" section and relaunch with `--resume <thread_id>` from `meta.json`, so the executor keeps its own context. Drop `--resume` if the thread is gone or the attempt is unsalvageable, restoring the files first in that case.
   - **drop**: not worth doing. Restore its owned files and delete files it created.
   - **replan**: the unit's plan is wrong. Revise the remaining plan yourself, keeping ids stable where scope is unchanged and ownership disjoint.
   - **reroute**: the backend is the problem (auth, quota, repeated stalls, consistent misreads of the brief). Restore the files and relaunch on another backend. Counts as an attempt.

Dispatch all retries for the wave in one parallel message, re-adjudicate, and repeat until every unit is pass or dropped. **Max 3 attempts per unit** across all backends, then drop it with an explanation.

## Phase 4: gate, fix, commit (per wave)

Only when every unit in the wave is pass or dropped:

1. Run the full gate suite once via Bash.
2. On failure: if the fix is trivial (an import, a format run, a seam between two units), fix it inline yourself. Otherwise attribute the failure to a unit and dispatch a retry with the failing output. Re-run the failed gate after fixing.
3. Commit per unit, in dependency order: `git add <owned files>` then commit with a descriptive message. Name the executor in the trailer so attribution stays honest:

   ```
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```

   for Claude units, and add `Executed-By: codex` or `Executed-By: agy` for external units. Fold your own inline gate fixes into the responsible unit's commit.

## Loop

Repeat Phases 2 to 4 until all units land or drop. If a round produces no runnable units, report the dependency deadlock and stop.

## Final report

Summarize: what landed (unit, backend, commit), what was dropped, rerouted, or unfinished and why, and the final gate status. Add a per-backend line with attempts, wall-clock seconds, and token usage from the meta files, so the user learns which executor earned its keep. This skill does not push, open PRs, or run browser or E2E verification. Offer those as follow-ups.

## Backend notes

Verified on Codex CLI 0.153 and Antigravity CLI 1.1.26.

- **Codex** reads the brief from stdin, so brief size is not a concern. `workspace-write` makes `.git` read-only and blocks network. A unit that legitimately needs network (rare, and usually a sign it should install nothing) is a Claude unit. `--output-schema` also shapes intermediate messages, which is why the script reads the final-message file rather than the event stream. Retries use `codex exec resume <thread_id>`.
- **Agy** takes the prompt as the value of `--print`, so briefs travel through argv. Keep briefs to a few kilobytes and point at files for anything larger. Without `--add-dir` it edits a private scratch directory and still reports success, so the script always passes it and the brief states the root. Output arrives only when the run ends, so there is no stall detection, only the ceiling. Retries use `--conversation <id>`. Available models include Gemini, Claude, and GPT-OSS variants (`agy models`).
- **Terms.** Antigravity's terms restrict third-party tools driving a subscription login. Using the unmodified CLI from a script is unclarified. The user decides. The sanctioned path is `modelProvider: gemini` with an API key, which limits the model list to Gemini.
- **Cost.** In a trivial side-by-side, agy used roughly four times the tokens and twice the wall-clock of Codex. Treat this as one sample and let the meta files build a real picture.

## Tradeoffs

Same speed profile as `conductor`: no worktrees, no per-worktree installs, no merge step, one gate run per wave, in-place retries. Codex adds a real fence (sandboxed writes, no git) that Claude subagents and agy lack, at the price of a fresh process with zero conversation context per unit, which the brief must make up for. Agy adds vendor diversity and cheap model switching, with no fence and a slower loop. If a task needs hard isolation for every executor, run each unit in its own git worktree (`git worktree add`), pass that path as `--repo`, and merge manually.
