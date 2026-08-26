---
name: conductor
description: Main-session orchestration harness for decomposable coding tasks. The main agent plans disjoint work units, fans out parallel executor subagents that edit the repo directly, adjudicates each unit's diff itself in-session, runs deterministic gates once per wave, and commits — looping until the whole plan lands. Use when the user says "conductor", or wants a sizable coding task decomposed and executed by parallel agents with fast in-session verification.
---

# Conductor — main-session plan → execute → adjudicate

You are the orchestrator. You plan, dispatch parallel executors via the Agent tool, judge their diffs yourself, run the gates, and commit. There is no planner subagent, no adjudicator subagent, no integration subagent, no Workflow tool, and no worktrees — that is what makes this fast. Quality comes from disjoint file ownership, acceptance checklists, skeptical diff review, and one full gate run per wave.

## Preconditions

- Must be a git repository. The working tree must be CLEAN (`git status --porcelain` empty) — executors edit the tree directly, and a dirty tree makes diff attribution impossible. If dirty, stop and ask the user to commit or stash first.
- Record the baseline: `git rev-parse HEAD` and the current branch. All diff review is against this baseline until commits start landing.
- Only YOU touch git. Executors are forbidden from running any git write command (add, commit, checkout, restore, stash, merge, rebase, worktree) — concurrent index writes race.

## Phase 1 — Plan (in-session)

If the user hasn't stated a goal, ask; do not guess.

Orient first: read the project's docs if you haven't already this session (CLAUDE.md, README), survey the code surface the task touches, and skim existing tests to know what test slices exist.

Detect the **gates** — deterministic shell commands that must pass before work is committed — from the repo manifest (build/lint/typecheck/test scripts, preferring a combined check script; skip long e2e/integration suites), unless the user supplied them. Gates are YOUR job to run, once per wave — executors never run the full suite.

Derive a SHORT **constraints** list stamped into every executor prompt: the master goal itself, hard rules from the repo docs, and "match surrounding file style and conventions". Include any user-supplied constraints verbatim.

Break the task into **units** (coarse-grained, roughly 3–7). Each unit has:

- `id` — short kebab-case
- `title`
- `scope` — what to build and what NOT to touch
- `owned files` — the EXCLUSIVE file set it may create or edit
- `acceptance` — a concrete checklist verifiable by reading code or running checks
- `dependsOn` — unit ids that must land first (keep the graph shallow)
- `complexity` — `normal` (sonnet) or `complex` (opus, only if it genuinely needs a stronger model)
- `scoped checks` — the fastest deterministic commands relevant to that unit alone (a targeted test file, a cheap typecheck). Optional; keep them fast.

**Hard rule:** units running in the same wave MUST have disjoint owned-file sets. If two units need the same file, sequence them with `dependsOn` or merge them into one unit. A scoping mistake here is the failure mode of this whole architecture — spend planning effort getting ownership right.

Do NOT include as units: browser/E2E verification, DB reseeding, deployments, or PR creation — those happen outside this skill.

Track progress with TaskCreate/TaskUpdate (one task per unit) so the user can follow along.

## Phase 2 — Execute a wave (parallel Agent calls)

A wave is every remaining unit whose `dependsOn` are all landed or dropped.

Dispatch the wave in **ONE message with one Agent call per unit** (`subagent_type: general-purpose`, `model` per complexity). Same-message calls run concurrently; sequential messages serialize — this is the whole point.

Each executor starts with zero context. The prompt must be self-contained:

- The overall task (context only — build ONLY your unit).
- The unit: title, scope, the exact owned-file list, the acceptance checklist.
- The constraints list, verbatim.
- Retry notes from a previous attempt, if any (see Phase 3).
- Rules, verbatim:
  - "Edit ONLY the files in your owned-file list. Other agents own other files; touching theirs corrupts the run."
  - "Run NO git commands of any kind — the orchestrator owns git."
  - "Do not run dev servers, browsers, docker, deployments, database writes, or long e2e/integration suites."
- Run only the unit's scoped checks (if any) and fix failures you caused.
- Report a tight structured summary: files changed (paths only), status of each acceptance item, scoped check results (pass/fail with trimmed failure output), and blockers. No diffs, no file contents.

## Phase 3 — Adjudicate (in-session, per unit)

You grade every unit yourself. Be skeptical — a "done" claim with a vague change list or failing scoped checks is a red flag.

For each unit in the wave:

1. **Verify the footprint.** `git status --porcelain` plus `git diff --stat -- <owned files>`: the changed files must match the report, and nothing outside the unit's ownership may be touched. Out-of-scope edits: restore the stray files (`git checkout -- <stray files>` / delete stray untracked files) and note it in the retry.
2. **Spot-read the diff** of load-bearing files (`git diff -- <file>`; `git diff` shows nothing for new files — read those directly). Check the acceptance items the gates cannot verify: intent, constraint adherence, semantic drift from the overall task. Use `--stat` first and read full diffs only where needed — keep your context lean.
3. **Verdict:**
   - **pass** — proceeds to gating.
   - **retry** — fixable. Write concrete fix notes. The retry executor fixes the existing attempt IN PLACE (its edits stay in the tree) — do not discard work; incremental fixes are a key speed win. Only restore the files first if the attempt is unsalvageable.
   - **drop** — not worth doing. Restore its owned files: `git checkout -- <owned files>` (and delete files it created).
   - **replan** — the unit's plan itself is wrong. Revise the remaining plan yourself, in-session, keeping ids stable where scope is unchanged and ownership disjoint.

Dispatch all retries for the wave in one parallel message, re-adjudicate, and repeat until every unit in the wave is pass or dropped. **Max 3 attempts per unit**, then drop it with an explanation.

## Phase 4 — Gate, fix, commit (per wave)

Only when every unit in the wave is pass or dropped (dropped files restored):

1. Run the full gate suite once via Bash.
2. On failure: if the fix is trivial (an import, a format run, an adjacent-edit seam between two units), fix it inline yourself — faster than a retry round-trip. Otherwise attribute the failure to a unit and dispatch a retry with the failing output (counts toward its 3 attempts). Re-run the failed gate after fixing.
3. Commit per unit, in dependency order: `git add <owned files>` then commit with a descriptive message ending:

   ```
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```

   Per-unit commits keep attribution clean and make any later revert surgical. Fold your own inline gate fixes into the responsible unit's commit.

## Loop

Repeat Phases 2–4 until all units land or drop. If a round produces no runnable units, report the dependency deadlock and stop.

## Final report

Summarize: what landed (unit → commit), what was dropped or unfinished and why, and the final gate status. This skill does not push, open PRs, or run browser/E2E verification — offer those as follow-ups.

## Tradeoffs

Fast by design: no worktrees, so no per-worktree dependency installs and no merge step; planning, adjudication, and integration happen in the main session; one full gate run per wave instead of one per executor; retries fix work in place instead of starting fresh; and the orchestrator hot-fixes trivial gate failures directly. The cost is no hard isolation — executors edit the shared tree and are trusted to respect their owned-file lists, and gates run against the combined wave rather than each unit in a pristine tree. If a task truly needs per-unit isolation, run executors in isolated worktrees (Agent tool `isolation: "worktree"`) and merge manually.
