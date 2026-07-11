export const meta = {
  name: "pea",
  description:
    "Generic plan → execute → adjudicate harness: Fable plans work units from args.task, executors build them in isolated worktrees and run the gates, one Fable adjudicator per wave judges intent, loop until the whole plan passes",
  whenToUse:
    "Any decomposable coding task. Pass args: { task: string, paths?: string[], gates?: string[], constraints?: string[], budget?: number }",
  phases: [
    {
      title: "Plan",
      detail:
        "Fable planner derives work units, acceptance checklists, complexity flags, constraints, gates",
      model: "fable",
    },
    {
      title: "Execute",
      detail:
        "one executor per unit in isolated worktrees, runs the gates, returns tight structured summaries",
    },
    {
      title: "Adjudicate",
      detail: "one Fable adjudicator per wave judges what the gates cannot",
      model: "fable",
    },
    {
      title: "Integrate",
      detail: "merge passing unit branches into the integration branch",
    },
  ],
};

// The Workflow runtime can deliver args as a JSON string; without this
// guard args.task is undefined and every run exits at the gate below.
if (typeof args === "string") {
  try {
    args = JSON.parse(args);
  } catch {
    args = { task: args };
  }
}

if (!args || typeof args.task !== "string" || !args.task.trim()) {
  log("No task provided — nothing to plan. Re-run with args.task set.");
  return {
    error:
      "Missing args.task. Invoke this workflow with args shaped as: " +
      '{ task: "<the goal>", paths?: ["<scope hints>"], gates?: ["<shell checks per unit>"], ' +
      'constraints?: ["<non-negotiables>"], budget?: <token cap> }',
  };
}

const TASK = args.task.trim();
const PATHS = Array.isArray(args.paths)
  ? args.paths.filter((p) => typeof p === "string" && p.trim())
  : [];
const SUPPLIED_GATES = Array.isArray(args.gates)
  ? args.gates.filter((g) => typeof g === "string" && g.trim())
  : [];
const SUPPLIED_CONSTRAINTS = Array.isArray(args.constraints)
  ? args.constraints.filter((c) => typeof c === "string" && c.trim())
  : [];
const BUDGET_CAP =
  typeof args.budget === "number" && args.budget > 0 ? args.budget : 200000;

const PLAN_SCHEMA = {
  type: "object",
  required: ["constraints", "gates", "units"],
  properties: {
    constraints: {
      type: "array",
      items: { type: "string" },
      description: "non-negotiable rules stamped into every executor prompt",
    },
    gates: {
      type: "array",
      items: { type: "string" },
      description: "shell commands every executor must run and pass",
    },
    units: {
      type: "array",
      items: {
        type: "object",
        required: [
          "id",
          "title",
          "scope",
          "acceptance",
          "dependsOn",
          "complexity",
        ],
        properties: {
          id: { type: "string", description: "short kebab-case id" },
          title: { type: "string" },
          scope: {
            type: "string",
            description:
              "what to change, which files/modules, and what NOT to touch",
          },
          files: { type: "array", items: { type: "string" } },
          acceptance: {
            type: "array",
            items: { type: "string" },
            description:
              "concrete checklist items verifiable by reading code / running the gates",
          },
          dependsOn: {
            type: "array",
            items: { type: "string" },
            description: "unit ids that must be merged first",
          },
          complexity: { enum: ["normal", "complex"] },
          checks: {
            type: "array",
            items: { type: "string" },
            description:
              "optional unit-specific shell checks (e.g. a scoped test slice) run in addition to the gates",
          },
        },
      },
    },
  },
};

const EXEC_SCHEMA = {
  type: "object",
  required: [
    "unit_id",
    "status",
    "branch",
    "worktree_path",
    "changes",
    "gates",
  ],
  properties: {
    unit_id: { type: "string" },
    status: { enum: ["done", "blocked"] },
    branch: { type: "string" },
    worktree_path: { type: "string" },
    changes: { type: "array", maxItems: 5, items: { type: "string" } },
    gates: {
      type: "array",
      items: {
        type: "object",
        required: ["command", "result"],
        properties: {
          command: { type: "string" },
          result: { enum: ["pass", "fail", "skipped"] },
          failures: {
            type: "string",
            description:
              "empty unless fail/skipped; then the failing output (trimmed) or the reason skipped",
          },
        },
      },
    },
    blockers: { type: "string" },
  },
};

const VERDICT_SCHEMA = {
  type: "object",
  required: ["verdicts"],
  properties: {
    verdicts: {
      type: "array",
      items: {
        type: "object",
        required: ["unit_id", "verdict", "notes"],
        properties: {
          unit_id: { type: "string" },
          verdict: { enum: ["pass", "retry", "replan", "drop"] },
          notes: {
            type: "string",
            description:
              "for retry: concrete fix instructions; for replan/drop: why",
          },
        },
      },
    },
  },
};

const MERGE_SCHEMA = {
  type: "object",
  required: ["merged", "failed"],
  properties: {
    merged: { type: "array", items: { type: "string" } },
    failed: {
      type: "array",
      items: {
        type: "object",
        required: ["unit_id", "reason"],
        properties: { unit_id: { type: "string" }, reason: { type: "string" } },
      },
    },
  },
};

phase("Plan");
const plannerPrompt = `You are the PLANNER for the task below, working in the repository at your current working directory. You plan only — make NO file edits.

TASK: ${TASK}
${PATHS.length ? "\nSCOPE HINT — start your survey from these paths (not necessarily exhaustive):\n" + PATHS.map((p) => "- " + p).join("\n") + "\n" : ""}
Orient first: note the current branch (git branch --show-current) — that is the integration branch all work merges back into. Read the project's own docs if present (CLAUDE.md, README, contributing or plan docs relevant to this task), then survey the code surface the task touches. Skim existing tests to know what test slices exist.

Produce:
1. constraints — a SHORT list of NON-NEGOTIABLE rules stamped into every executor prompt. ${SUPPLIED_CONSTRAINTS.length ? "The user supplied these; include them VERBATIM and add only rules you discover in the repo docs/code that executors could otherwise violate:\n" + SUPPLIED_CONSTRAINTS.map((c) => "- " + c).join("\n") : 'None were supplied — derive them at runtime from the task, the repo\'s stated rules (e.g. CLAUDE.md hard rules), and invariants you can see in the code. Always include the master goal itself as the first constraint, plus "match surrounding file style and conventions".'}
2. gates — deterministic shell commands every executor runs in its worktree and must pass. ${SUPPLIED_GATES.length ? "The user supplied these; echo them VERBATIM:\n" + SUPPLIED_GATES.map((g) => "- " + g).join("\n") : "None were supplied — detect them: read package.json (or the repo's equivalent manifest) and use its scripts for build/lint/typecheck/test with the repo's package manager (prefer a combined check script if one exists; skip long-running e2e/integration suites). If no manifest exists, propose whatever deterministic checks fit the repo, or an empty list."}
3. units — an ordered list of INDEPENDENT work units (coarse-grained; aim for roughly 3-7; units running in the same wave MUST touch disjoint files). For each: id, title, scope (files + what to build + what not to touch), a concrete checklist-style acceptance list for that unit, dependsOn (unit ids that must land first — keep the graph shallow), complexity ('complex' only if it genuinely needs a stronger model), and optional checks (unit-specific shell checks such as a scoped test slice, run in addition to the gates).

Do NOT include as units: browser-level E2E verification, database reseeding, deployments, or PR creation — those happen outside this workflow.

Return only the structured plan.`;

const plan = await agent(plannerPrompt, {
  model: "fable",
  effort: "high",
  schema: PLAN_SCHEMA,
  label: "planner",
  phase: "Plan",
});
if (!plan) return { error: "Planner unavailable — no plan produced." };
let constraints = SUPPLIED_CONSTRAINTS.length
  ? SUPPLIED_CONSTRAINTS
  : plan.constraints || [];
let gates = SUPPLIED_GATES.length ? SUPPLIED_GATES : plan.gates || [];
let remaining = plan.units;
log(
  `Plan: ${remaining.length} units — ${remaining.map((u) => u.id).join(", ")}; gates: ${gates.join(" | ") || "(none)"}`,
);

const passed = new Set();
const dropped = [];
const notes = {}; // unit_id -> adjudicator/merge notes for retries
const prevAttempt = {}; // unit_id -> worktree path of failed attempt
let round = 0;

function execPrompt(u) {
  const unitChecks = (u.checks || []).filter(Boolean);
  const allChecks = gates.concat(unitChecks);
  return `You are an EXECUTOR for one work unit of a larger task. You are in an ISOLATED git worktree — work ONLY inside your CWD, never in the root repository.

THE OVERALL TASK (for context only — build ONLY your unit): ${TASK}

Setup first:
1. git checkout -B pea/${u.id}-r${round}
2. If dependencies are not already installed in this worktree, install them with the repo's package manager (use its offline/cached mode when available).

Orient by reading only what your unit needs: the project's docs (CLAUDE.md / README if present) and the files in your scope.

NON-NEGOTIABLE CONSTRAINTS (violating any = failure):
${constraints.map((c) => "- " + c).join("\n")}

YOUR UNIT: ${u.id} — ${u.title}
SCOPE: ${u.scope}
${u.files && u.files.length ? "FILES: " + u.files.join(", ") : ""}
ACCEPTANCE CHECKLIST (satisfy every item):
${u.acceptance.map((a) => "- " + a).join("\n")}
${notes[u.id] ? "\nADJUDICATOR NOTES FROM YOUR PREVIOUS ATTEMPT (address these):\n" + notes[u.id] + (prevAttempt[u.id] ? "\nPrevious attempt worktree (read-only, may help): " + prevAttempt[u.id] : "") : ""}

Stay strictly inside your scope — other executors own other files; touching theirs causes merge conflicts.

When done, run these gates IN YOUR WORKTREE and report each one's result honestly (mark a gate 'skipped' only if it genuinely does not apply, and say why):
${allChecks.length ? allChecks.map((g) => "- " + g).join("\n") : "- (no gates defined — state that in your report and self-verify against the acceptance checklist instead)"}
Also run any tests covering files you added or changed. Fix failures you caused. RESOURCE RULES: do NOT run dev servers, browsers, docker, deployments, or database writes; do not run long e2e/integration suites unless listed as a gate.

Commit ALL your work on your branch with a descriptive message ending with:
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Report worktree_path as the output of \`git rev-parse --show-toplevel\` and unit_id as "${u.id}". Return ONLY the tight structured summary — no diffs, no file contents.`;
}

while (remaining.length) {
  const spent = budget.spent();
  if (spent > BUDGET_CAP) {
    log(
      `Budget guard hit (${Math.round(spent / 1000)}k spent, cap ${Math.round(BUDGET_CAP / 1000)}k) — stopping with ${remaining.length} units unfinished`,
    );
    break;
  }
  round++;
  const wave = remaining.filter((u) =>
    (u.dependsOn || []).every((d) => passed.has(d) || dropped.includes(d)),
  );
  if (!wave.length) {
    log("No runnable units — dependency deadlock; stopping");
    break;
  }
  log(
    `Round ${round}: executing ${wave.map((u) => u.id).join(", ")} (${Math.round(spent / 1000)}k tokens spent)`,
  );

  const results = (
    await parallel(
      wave.map(
        (u) => () =>
          agent(execPrompt(u), {
            model: u.complexity === "complex" ? "opus" : "sonnet",
            isolation: "worktree",
            schema: EXEC_SCHEMA,
            label: `exec:${u.id}`,
            phase: "Execute",
          }).then((r) => r && { ...r, unit_id: u.id }),
      ),
    )
  ).filter(Boolean);

  for (const u of wave) {
    if (!results.find((r) => r.unit_id === u.id))
      notes[u.id] =
        (notes[u.id] || "") +
        "\n[previous executor died or was skipped — start fresh]";
  }
  if (!results.length) continue;

  const adjPrompt = `You are the ADJUDICATOR for round ${round} of this task. Executors never grade their own work — you do.

THE OVERALL TASK: ${TASK}

THE PLAN FOR THIS WAVE (constraints + units with acceptance checklists):
${JSON.stringify({ constraints, gates, units: plan.units.filter((u) => wave.some((w) => w.id === u.id)) }, null, 1)}

EXECUTOR STRUCTURED SUMMARIES for this wave (their branches/worktrees are listed; you MAY spot-read specific files in a worktree if a summary is ambiguous, but do NOT review full diffs):
${JSON.stringify(results, null, 1)}

Judge ONLY what the deterministic gates cannot: did each change satisfy the unit's intent and every acceptance item; does it honor every non-negotiable constraint; is there semantic drift from the overall task? Be skeptical of "done" claims with failing or skipped gates or vague change lists. Verdict per unit:
- pass — merge it
- retry — fixable by re-executing; notes MUST contain concrete instructions
- replan — the unit's plan itself is wrong; explain why
- drop — not worth doing; explain why
A unit reporting any failing gate cannot be 'pass'.`;

  const adj = await agent(adjPrompt, {
    model: "fable",
    effort: "high",
    schema: VERDICT_SCHEMA,
    label: `adjudicate-r${round}`,
    phase: "Adjudicate",
  });
  const verdicts = adj
    ? adj.verdicts
    : results.map((r) => ({
        unit_id: r.unit_id,
        verdict: "retry",
        notes: "adjudicator unavailable",
      }));

  const byId = Object.fromEntries(results.map((r) => [r.unit_id, r]));
  const passing = verdicts
    .filter((v) => v.verdict === "pass" && byId[v.unit_id])
    .map((v) => byId[v.unit_id]);

  if (passing.length) {
    const mergeRes = await agent(
      `You are the INTEGRATION agent, running in the ROOT repository (your CWD — you are NOT in a worktree; confirm with git rev-parse --show-toplevel). The integration branch is whatever git branch --show-current reports — do NOT switch branches. Merge these unit branches into it IN THIS ORDER:
${passing.map((p) => `- unit ${p.unit_id}: branch ${p.branch} (worktree ${p.worktree_path})`).join("\n")}

For each, in order: \`git merge --no-ff ${"<branch>"} -m "merge <unit>: <short title>"\`. If a merge conflicts, resolve ONLY if trivial (imports/adjacent disjoint edits); otherwise \`git merge --abort\` and report that unit as failed with the conflicting files as the reason, then continue with the next branch. After each SUCCESSFUL merge: \`git worktree remove --force <worktree_path>\` and \`git branch -D <branch>\`. Do NOT push, do NOT run builds or tests, do NOT touch anything else in the repo. Return the structured result.`,
      {
        model: "sonnet",
        schema: MERGE_SCHEMA,
        label: `integrate-r${round}`,
        phase: "Integrate",
      },
    );

    const merged = mergeRes ? mergeRes.merged : [];
    for (const id of merged) {
      passed.add(id);
      log(`✓ merged ${id}`);
    }
    for (const f of mergeRes
      ? mergeRes.failed
      : passing.map((p) => ({
          unit_id: p.unit_id,
          reason: "integration agent unavailable",
        }))) {
      notes[f.unit_id] =
        (notes[f.unit_id] || "") +
        `\n[merge failed: ${f.reason} — rebase your work on the integration branch's current HEAD]`;
      prevAttempt[f.unit_id] = byId[f.unit_id].worktree_path;
    }
  }

  for (const v of verdicts) {
    if (v.verdict === "retry") {
      notes[v.unit_id] = (notes[v.unit_id] || "") + "\n" + v.notes;
      if (byId[v.unit_id])
        prevAttempt[v.unit_id] = byId[v.unit_id].worktree_path;
      log(`↻ retry ${v.unit_id}: ${v.notes.slice(0, 120)}`);
    }
    if (v.verdict === "drop") {
      dropped.push(v.unit_id);
      log(`✗ dropped ${v.unit_id}: ${v.notes.slice(0, 120)}`);
    }
  }
  remaining = remaining.filter(
    (u) => !passed.has(u.id) && !dropped.includes(u.id),
  );

  const replans = verdicts.filter((v) => v.verdict === "replan");
  if (replans.length && remaining.length) {
    log(`Re-planning: ${replans.map((v) => v.unit_id).join(", ")}`);
    const rev = await agent(
      `You are the PLANNER revising the plan for this task (repository at your CWD). Plan only — no edits.
THE OVERALL TASK: ${TASK}
Current constraints: ${JSON.stringify(constraints)}
Current gates: ${JSON.stringify(gates)}
Units already merged into the integration branch: ${JSON.stringify([...passed])}. Dropped: ${JSON.stringify(dropped)}.
Remaining units: ${JSON.stringify(remaining, null, 1)}
The adjudicator flagged these as mis-planned: ${JSON.stringify(replans, null, 1)}
Executor summaries this round: ${JSON.stringify(results, null, 1)}
Re-read the relevant docs and current code as needed, then return a REVISED full plan for the remaining work only (same schema; keep unit ids stable where scope is unchanged; same-wave units must touch disjoint files; do not include already-merged units; echo the gates${SUPPLIED_CONSTRAINTS.length ? " and the user-supplied constraints" : ""} unchanged).`,
      {
        model: "fable",
        effort: "high",
        schema: PLAN_SCHEMA,
        label: `replan-r${round}`,
        phase: "Plan",
      },
    );
    if (rev) {
      if (
        !SUPPLIED_CONSTRAINTS.length &&
        rev.constraints &&
        rev.constraints.length
      )
        constraints = rev.constraints;
      remaining = rev.units.filter(
        (u) => !passed.has(u.id) && !dropped.includes(u.id),
      );
      for (const u of remaining)
        if (!plan.units.find((p) => p.id === u.id)) plan.units.push(u);
        else plan.units[plan.units.findIndex((p) => p.id === u.id)] = u;
    }
  }
}

return {
  task: TASK,
  merged: [...passed],
  dropped,
  unfinished: remaining.map((u) => ({
    id: u.id,
    lastNotes: (notes[u.id] || "").slice(-300),
  })),
  rounds: round,
  tokensSpentApprox: budget.spent(),
};
