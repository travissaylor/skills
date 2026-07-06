# Agent Skills

A collection of agent skills for Claude Code.

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

- **parallel-execute** — Execute a plan by delegating work to sub-agents, running as many steps as possible in parallel. Builds a dependency graph, fans out independent steps in waves, and verifies results between waves.

  ```
  npx skills@latest add travissaylor/skills/parallel-execute
  ```

- **pea** — Plan → execute → adjudicate harness for decomposable coding tasks. A planner derives work units, executors build them in parallel isolated git worktrees and run deterministic gates, an adjudicator judges each wave against intent, and passing units merge into the integration branch — looping until the whole plan lands.

  ```
  npx skills@latest add travissaylor/skills/pea
  ```
