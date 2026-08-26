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

## Architecture & Refactoring

- **improve-codebase-architecture** — Explore a codebase to find architectural improvement opportunities, focusing on testability and module-deepening refactors. Surfaces friction, proposes multiple interface designs, and stores RFCs.

  ```
  npx skills@latest add travissaylor/skills/improve-codebase-architecture
  ```

## Execution

- **conductor** — Main-session orchestration harness for decomposable coding tasks: plan disjoint work units, fan out parallel executor subagents, adjudicate diffs in-session, run gates once per wave, commit.

  ```
  npx skills@latest add travissaylor/skills/conductor
  ```
