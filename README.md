# Agent Skills

A collection of agent skills for Claude Code.

## Writing

- **prose** — The entry point for anything written for a reader. Merged core of unslop (language), scannable (density + layout), and technical-writing (doc standards); routes to those deep passes when needed. Install all four together.

  ```
  npx skills@latest add travissaylor/skills/prose
  ```

- **unslop** — Deep de-slopping pass: the full 31-pattern catalog of AI tells, applied to an existing draft.

  ```
  npx skills@latest add travissaylor/skills/unslop
  ```

- **scannable** — Deep restructuring pass: semantic density, typographic hierarchy, and ADHD re-orientation for walls of text.

  ```
  npx skills@latest add travissaylor/skills/scannable
  ```

- **technical-writing** — Deep documentation pass: Diátaxis structure, Google developer style, STE instruction rules, Global English syntax.

  ```
  npx skills@latest add travissaylor/skills/technical-writing
  ```

## Context

- **recall** — Reconstruct recent working context from chat history, live state, and the shared record (tickets, docs, memory), then hand back a tight current-state brief.

  ```
  npx skills@latest add travissaylor/skills/recall
  ```

## Planning & Design

- **prd** — Generate structured Product Requirements Documents through an interactive interview with codebase-aware questions.

  ```
  npx skills@latest add travissaylor/skills/prd
  ```

## Architecture & Refactoring

- **improve-codebase-architecture** — Explore a codebase to find architectural improvement opportunities, focusing on testability and module-deepening refactors. Surfaces friction, proposes multiple interface designs, and stores RFCs.

  ```
  npx skills@latest add travissaylor/skills/improve-codebase-architecture
  ```

## Execution

- **conductor** — Main-session orchestration harness for decomposable coding tasks: plan disjoint work units, fan out parallel executor subagents, adjudicate diffs in-session, run gates once per wave, commit. The fast, no-worktree sibling of pea.

  ```
  npx skills@latest add travissaylor/skills/conductor
  ```

- **parallel-execute** — Execute a plan by delegating work to sub-agents, running as many steps as possible in parallel. Builds a dependency graph, fans out independent steps in waves, and verifies results between waves.

  ```
  npx skills@latest add travissaylor/skills/parallel-execute
  ```

- **pea** — Plan → execute → adjudicate harness for decomposable coding tasks. A planner derives work units, executors build them in parallel isolated git worktrees and run deterministic gates, an adjudicator judges each wave against intent, and passing units merge into the integration branch — looping until the whole plan lands.

  ```
  npx skills@latest add travissaylor/skills/pea
  ```
