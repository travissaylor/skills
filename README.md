# Agent Skills

Agent skills for Claude Code, Codex and Antigravity, and the Python tooling that tests them. Most of the repo is Markdown instructions for agents. The three parts below have code, tests and CI behind them, so start there.

## Tested engineering work

- **[session-audit](session-audit/SKILL.md)** mines agent session history for repeated manual work, misfiring skills, tool failures and token waste. Three standard-library distillers parse transcripts from Claude Code (`mine-transcripts.py`), Codex (`mine-codex.py`) and Antigravity (`mine-agy.py`) and compute every count. Sonnet subagents then classify the flagged events, name the patterns and propose fixes, but never count. `verify-findings.py` checks each quote a subagent cites. A quote counts only if it is at least 20 characters long and the whole quote, whitespace-normalized, appears in that session's digest. The script recomputes session counts from verified quotes, marks a finding with none as `UNSUPPORTED` and exits 1, and the skill drops those findings before the report. A fixture test, `session-audit/scripts/test_mine_transcripts.py`, covers the Claude Code distiller and the verifier, and CI runs it.

- **[Skill linter](tools/README.md)** (`tools/skill_lint/`) checks every skill for structural defects such as broken links, unresolved paths and frontmatter that disagrees with its directory, and for prose defects drawn from the writing skills below. It has 30 finding codes, 61 linter tests, a pre-commit hook, and a count-based baseline so the gate fires only on new findings. It uses the Python standard library only and makes no model calls.

- **[CI](.github/workflows/lint.yml)** runs on every push and pull request. On Ubuntu it compiles `tools/`, runs `make test`, and runs the linter against the baseline. `make test` is 79 unit tests (the linter suite plus contract tests for the `handoff` store script and the `conductor-multi` executor launcher, both run against fake CLIs and temporary directories) followed by the session-audit fixture test. On macOS it runs the 13 `handoff` tests again under the system Bash, because that script must work on the Bash 3.2 that ships with macOS.

## Skills

Install one skill with `npx skills@latest add travissaylor/skills/<name>`, or all of them from a clone with `make install`.

### Maintenance

- **session-audit**: Audit Claude Code session history, plus Codex and Antigravity history when present, for repeated manual work, skills that misfire, tool failures, and token waste. A deterministic distiller does all counting, Sonnet miners classify and explain, and every finding is quote-verified and checked on the live machine. Local state (ledger, fixes, custom metrics) lives in `~/.claude/session-audit/`, outside the skill.

  ```
  npx skills@latest add travissaylor/skills/session-audit
  ```

### Execution

- **conductor**: Main-session orchestration for decomposable coding tasks: plan disjoint work units, fan out parallel executor subagents, adjudicate diffs in-session, run gates once per wave, commit.

  ```
  npx skills@latest add travissaylor/skills/conductor
  ```

- **conductor-multi**: Conductor with pluggable executors: each work unit runs on a Claude subagent, OpenAI Codex CLI, or Google Antigravity CLI (agy), launched in parallel by a small script that pins sandbox and output flags. Same in-session adjudication, gates, and commits.

  ```
  npx skills@latest add travissaylor/skills/conductor-multi
  ```

### Context

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

### Writing

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

### Presenting work

- **showcase**: Build a self-contained HTML artifact with diagrams, screenshots, and short text that presents a body of work to someone who was not in the room. Six shapes (work explainer, option comparison, data model and ecosystem fit, PR companion, demo readout, research report), each with a skeleton, plus diagram rules and a render check at desktop and phone width that catch overlapping or clipped labels before publishing. Written around one person's recurring corrections and one company's systems, so treat the specifics as a template.

  ```
  npx skills@latest add travissaylor/skills/showcase
  ```

## Installing from a clone

`make install` symlinks every skill in this repo into `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills`, and `~/.gemini/skills`, so each agent loads the same versioned copy. Anything already at a target path is moved to `~/.skills-backup/<timestamp>/`, never deleted. Run it on each machine after cloning or pulling a skill that was added since.

## Running the skill linter

`tools/lint_skills.py` checks every skill in this repo for structural defects and prose defects. Structure: frontmatter that disagrees with its directory name, links and backticked paths that do not resolve, cross-skill references with no matching directory, hardcoded home paths, leftover markers, and Tailscale addresses in any text file. Prose: em dashes, semicolons, curly quotes, title-case headings, AI vocabulary, filler, and stacked hedging, all drawn from the writing skills above. It is a static check. No model calls, and no third-party dependencies, Python 3 standard library only.

See the full backlog:

```
make lint
```

Install the pre-commit hook, which blocks a commit that adds a new finding:

```
make install-hooks
```

Every finding code, how the baseline works, and the suppression directives are documented in [tools/README.md](tools/README.md).
