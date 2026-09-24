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

Three skills that carry a session across agents (Claude Code, Codex, Antigravity) and machines. Handoff documents live in `~/handoffs/<project>/` and sync between machines over rsync, so the same file is there whichever agent picks it up. The writing side never needs to know where the work goes next. The reading side, `pickup` or `recall`, works the same in any agent on any peer. Install all three together.

- **handoff**: Write a handoff document into the shared store, commit and push the branch so the tree travels too, and sync to peer machines. Written for any agent on any machine, so it takes no destination. Ships the store script the other two use.

  ```
  npx skills@latest add travissaylor/skills/handoff
  ```

- **pickup**: Sync the store, take the newest open handoff for this project, verify the tree matches it, mark it taken, and start. The fast path after a handoff, in whichever agent and on whichever machine the next session opens. Named `pickup` because `/resume` is already a built-in command in Claude Code.

  ```
  npx skills@latest add travissaylor/skills/pickup
  ```

- **recall**: Reconstruct recent working context from Claude Code, Codex, and Antigravity chat history, live state, and the shared record (tickets, docs, memory), then hand back a tight current-state brief. Checks the handoff store first. The fallback when no handoff exists.

  ```
  npx skills@latest add travissaylor/skills/recall
  ```

To sync between machines, list each peer's ssh host name in `~/handoffs/peers`, one per line. The first run of the store script creates the file.

## Execution

- **conductor**: Main-session orchestration for decomposable coding tasks: plan disjoint work units, fan out parallel executor subagents, adjudicate diffs in-session, run gates once per wave, commit.

  ```
  npx skills@latest add travissaylor/skills/conductor
  ```

- **conductor-multi**: Conductor with pluggable executors: each work unit runs on a Claude subagent, OpenAI Codex CLI, or Google Antigravity CLI (agy), launched in parallel by a small script that pins sandbox and output flags. Same in-session adjudication, gates, and commits.

  ```
  npx skills@latest add travissaylor/skills/conductor-multi
  ```

## Installing from a clone

`make install` symlinks every skill in this repo into `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills`, and `~/.gemini/skills`, so each agent loads the same versioned copy. Anything already at a target path is moved aside with a `.bak-<timestamp>` suffix, never deleted. Run it on each machine after cloning or pulling a skill that was added since.

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
