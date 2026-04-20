---
name: parallel-execute
description: Execute a plan by delegating work to sub-agents, running as many steps as possible in parallel. Use when the user wants a plan carried out via sub-agents with maximum parallelism, or says "execute in parallel", "fan this out", "delegate this plan".
---

Execute the plan by delegating work to sub-agents via the Agent tool. Maximize parallelism.

## Process

1. **Identify the plan.** If the user hasn't named one, ask which plan (a file, a recent message, a TODO list). Do not guess.
2. **Build a dependency graph.** For each step, ask: does this step *need* output from a prior step, or just happen after it? "After" is not a dependency. Group independent steps into waves.
3. **Fan out each wave.** Send ONE message containing multiple `Agent` tool calls — one per independent step. Tool calls in the same message run concurrently; tool calls in separate messages run serially. This is the whole point — do not skip it.
4. **Wait for the wave, then continue.** After a wave returns, verify results (don't trust summaries blindly — spot-check files the agents claim to have changed), then dispatch the next wave.

## Writing sub-agent prompts

Each sub-agent starts with zero context from this conversation. Every prompt must be self-contained:

- State the goal and why it matters.
- Include exact file paths, line numbers, and the specific change required.
- Say whether you want code changes or just research.
- If you need a short report, say so ("report in under 200 words").
- Pick `subagent_type` deliberately: `Explore` for read-only research, `general-purpose` for code changes, a specialized agent when one fits.

## When NOT to parallelize

- Steps that edit the same file (conflicts).
- Steps where step N's output determines step N+1's approach.
- Destructive or shared-state actions (DB migrations, pushes, deploys) — do these yourself, serially, after confirming with the user.

## Default posture

Bias toward more parallelism, smaller sub-tasks, and self-contained prompts. If you catch yourself making sequential `Agent` calls for work that could have run in one message, stop and re-dispatch as a single parallel batch.
