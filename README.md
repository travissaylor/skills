# Agent Skills

A collection of agent skills for Claude Code.

## Writing

- **prose**: The entry point for anything written for a reader. Merged core of unslop (language), scannable (density + layout), and technical-writing (doc standards). Routes to those deep passes when needed. Install all four together.

  ```
  npx skills@latest add travissaylor/skills/prose
  ```

- **unslop**: Deep de-slopping pass: the full 31-pattern catalog of AI tells, applied to an existing draft.

  ```
  npx skills@latest add travissaylor/skills/unslop
  ```

- **scannable**: Deep restructuring pass: semantic density, typographic hierarchy, and ADHD re-orientation for walls of text.

  ```
  npx skills@latest add travissaylor/skills/scannable
  ```

- **technical-writing**: Deep documentation pass: Diátaxis structure, Google developer style, STE instruction rules, Global English syntax.

  ```
  npx skills@latest add travissaylor/skills/technical-writing
  ```

## Context

- **recall**: Reconstruct recent working context from chat history, live state, and the shared record (tickets, docs, memory), then hand back a tight current-state brief.

  ```
  npx skills@latest add travissaylor/skills/recall
  ```

## Execution

- **conductor**: Main-session orchestration for decomposable coding tasks: plan disjoint work units, fan out parallel executor subagents, adjudicate diffs in-session, run gates once per wave, commit.

  ```
  npx skills@latest add travissaylor/skills/conductor
  ```

## Skill linter

`tools/lint_skills.py` checks every skill in this repo for structural defects and prose defects. Structure: frontmatter that disagrees with its directory name, links and backticked paths that do not resolve, cross-skill references with no matching directory, hardcoded home paths, leftover markers. Prose: em dashes, semicolons, curly quotes, title-case headings, AI vocabulary, filler, and stacked hedging, all drawn from the writing skills above. It is a static check. No model calls, and no third-party dependencies, Python 3 standard library only.

See the full backlog:

```
make lint
```

Install the pre-commit hook, which blocks a commit that adds a new finding:

```
make install-hooks
```

Every finding code, how the baseline works, and the suppression directives are documented in [tools/README.md](tools/README.md).
