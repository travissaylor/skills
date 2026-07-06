---
name: pea
description: Plan → execute → adjudicate harness for decomposable coding tasks. A planner derives work units, executors build them in parallel isolated git worktrees and run deterministic gates, an adjudicator judges each wave against intent, and passing units merge into the integration branch — looping until the whole plan lands. Use when the user says "pea", or wants a sizable coding task decomposed and executed by parallel agents with verification.
---

# Pea — plan → execute → adjudicate

This skill runs the bundled workflow script `pea.js`, which lives in the same directory as this SKILL.md. It requires the Workflow tool (multi-agent orchestration) and a git repository.

## How to run it

1. **Resolve the script path.** Find the absolute path of `pea.js` next to this SKILL.md (typically `~/.claude/skills/pea/pea.js` for a user install, or `<project>/.claude/skills/pea/pea.js` for a project install).

2. **Build args from the user's request:**
   - `task` (required, string) — the goal. If the user hasn't stated one, ask; do not guess.
   - `paths` (optional, string[]) — scope hints for the planner's survey.
   - `gates` (optional, string[]) — shell commands every executor must pass. Omit to let the planner detect them from the repo manifest. Pass explicitly when CI has steps the manifest scripts don't cover (e.g. a separate format check).
   - `constraints` (optional, string[]) — non-negotiable rules stamped into every executor prompt. Omit to let the planner derive them from the repo's docs.
   - `budget` (optional, number) — token cap; defaults to 200k.

3. **Invoke the Workflow tool** with `{ scriptPath: "<absolute path to pea.js>", args: { ... } }`. Pass args as real JSON values, not a JSON-encoded string.

4. **Report the result.** The workflow returns `{ merged, dropped, unfinished, rounds, tokensSpentApprox }`. Summarize what landed on the integration branch, what was dropped or left unfinished and why, and the approximate token spend.

## Preconditions and caveats

- Run it from the branch you want work merged into — the current branch is the integration branch.
- The working tree should be clean; executors work in isolated worktrees, but the integration agent merges into the root repo.
- The workflow does not push, open PRs, or run browser/E2E verification — do those afterwards.
- To resume after a pause or failure, re-invoke Workflow with the same `scriptPath` plus `resumeFromRunId` from the original run.
