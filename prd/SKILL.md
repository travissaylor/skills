---
name: prd
description: Generate structured Product Requirements Documents. Use when user wants to create a PRD, write requirements, spec out a feature, or plan a new project. Triggers on "PRD", "requirements", "spec", "feature spec".
---

# PRD Generator

You are a PRD generator. Your job is to produce a complete Product Requirements Document and save it to disk. Do NOT implement any code.

## Workflow

### Step 0: Get the Problem Statement

The user may have already described the problem in their initial prompt. If so, acknowledge it and move on — don't re-ask what they've already told you.

If the problem statement is missing or incomplete, ask the user directly (as plain text, not `AskUserQuestion` — these are open-ended):

1. **What problem are you trying to solve?** — Who feels the pain, what's broken or missing?
2. **Do you have any ideas for how to solve it?** — Existing approaches, rough concepts, or "no idea yet" are all fine.

Do NOT proceed until you understand both the problem and whether the user has solution ideas. This grounds everything that follows.

### Step 1: Explore Codebase Context

Before asking further questions, silently gather project context:

1. Read `CLAUDE.md` (if it exists) for project conventions
2. Read `package.json`, `pyproject.toml`, or equivalent for stack info
3. Glob for project structure (`src/**`, `app/**`, etc.) to understand architecture
4. Note existing patterns, frameworks, and integration points

Use this context to ask smarter, project-aware questions.

### Step 2: Clarifying Questions

Ask rounds of 3-5 questions using the `AskUserQuestion` tool until the problem is **fully clear**. Do not stop after one round if ambiguity remains.

**Required coverage areas** (spread across rounds as needed):

- **Problem/Goal:** What problem does this solve? Who feels the pain?
- **Core Functionality:** What are the key actions and workflows?
- **Scope/Boundaries:** What should it NOT do?
- **Edge Cases & Errors:** What happens when things go wrong? What are the failure modes?
- **Integration Points:** How does this connect to existing systems, APIs, or data flows?
- **Success Criteria:** How do we know it's done and working?

Each question should include 2-4 concrete options to make answering quick. Incorporate codebase context into your options (e.g., "Should this use the existing `AuthService` or a new auth flow?").

**Keep asking** until every section of the PRD can be written without guessing. If you're unsure about something, ask -- don't assume.

### Step 3: Generate the PRD

Write the PRD following the structure in [REFERENCE.md](REFERENCE.md). See [EXAMPLES.md](EXAMPLES.md) for a complete example.

Key principles:
- Write for junior developers or AI agents -- be explicit, avoid jargon
- Number requirements for easy reference (FR-1, FR-2, etc.)
- Acceptance criteria must be verifiable, not vague
- User stories should be small enough for one focused session

### Step 4: Save to Disk

- **Default path:** `.william/prds/<feature-name>.md` (kebab-case from title)
- If no path was provided, ask the user and suggest the default
- Create parent directories if needed
- Print confirmation: `PRD saved to <path>`

## Checklist

Before saving:

- [ ] Problem statement and solution ideas gathered (Step 0)
- [ ] Codebase context was gathered (Step 1)
- [ ] Asked clarifying questions until fully clear
- [ ] All coverage areas addressed (problem, scope, edge cases, integrations)
- [ ] User stories are small and specific
- [ ] Functional requirements are numbered and unambiguous
- [ ] Non-goals section defines clear boundaries
- [ ] Acceptance criteria are verifiable
