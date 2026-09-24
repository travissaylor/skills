# Miner brief

You are one miner in a session audit of the user's Claude Code history. The orchestrator's prompt gives your role, your files, and your output path. Your findings are leads: a script re-checks every quote and the orchestrator re-checks every claim on the live machine, so precision matters more than volume.

## Inputs

- `stats.md`: computed aggregates. **Every count you need is already in it.** Cite its numbers. Never count lines yourself, because counting over long text is where models go wrong.
- `digest-NN.md`: one block per session, chronological. Line types:
  - `## SESSION <id8> project=… api_calls=… cost_state=$… errors=…` opens a session.
  - `USER[ts]:` is what the user typed. `USER[steer?]` means a regex matched redirect wording (about half are real redirects).
  - `USER SLASH /x` is a slash command. `INTERRUPT` means the user stopped the turn.
  - `SKILL-TURN <name>` means the following assistant turns ran under that skill.
  - `TOOL <name>: <args> (→Nk)` is a call with its result size. `TOOL!` is a call that errored, and the next `ERR:` line is the error.
  - `SUBAGENT <id> type= model= … errors=` is a spawned agent collapsed to a histogram.
  - `LARGE_TOOL_RESULTS:` lists results over 15k chars.
- `episodes.md`: ±5 lines around every error, interrupt, and steer candidate, grouped by the skill that was active.

## Role A: failure classifier (reads `episodes.md` + `stats.md`)

For each skill or tool with repeated episodes, decide what actually went wrong. Read the episode, then assign one friction type:

`misunderstood_request` · `wrong_approach` · `buggy_code` · `user_rejected_action` · `claude_got_blocked` · `user_stopped_early` · `wrong_file_or_location` · `excessive_changes` · `slow_or_verbose` · `tool_failed` · `skill_instruction_gap` (the skill ran but its text sent Claude the wrong way or left a step out) · `not_a_failure` (the regex fired on normal conversation, or the error was expected exploration).

Mark `not_a_failure` freely. A steer that is the user adding scope, or a grep that exits 1 on no match, is not a failure. Then name the root cause in one line and the smallest fix: an edit to the skill (quote the line to change if you can see it), a script, a memory note, or a CLAUDE.md rule.

## Role B: pattern miner (reads one `digest-NN.md` + `stats.md`)

Find what recurs across sessions and could cost fewer tokens or no tokens:

1. **Token sinks.** Whole-file reads of the same big files, huge MCP or Bash results for a narrow question, re-deriving env, URLs, or IDs, Opus subagents doing lookups. Use `stats.md`'s carried-cost ranking: a large result early in a long session costs more than the same result at the end.
2. **Deterministic tooling.** A shell or API sequence with the same shape each time. `stats.md` lists repeated tool sequences: explain what each one is doing and what script would replace it.
3. **Skill candidates or skill fixes.** A multi-step workflow that needs judgment but has the same shape each time, prompts the user retypes in similar words, or an existing skill they have to steer.

## Before proposing, check it doesn't exist

- `ls ~/.claude/skills/` and the likely skill's `scripts/`, then `grep -il "<keyword>" ~/.claude/projects/*/memory/*.md`.
- An existing skill or script that sessions didn't use is itself a finding: say "exists, not reached for".
- Read the followups memory (`ls ~/.claude/projects/*/memory/*session_audit_followups*`) if one exists. A shelved item that recurred goes under the title prefix `STILL SHELVED:`.

## Output format (the verify script parses this, so keep it exact)

Write Markdown to your output path and return the same content. At most 12 findings, most impactful first. Skip one-offs.

```
### <short title>  [type: token | tool | skill | skill-fix | failure]  [friction: <type or ->]
> <session8> | <text copied verbatim from that session's lines, 20+ chars>
> <session8> | <another quote, from a different session where possible>
- **Pattern:** what recurs, citing counts from stats.md
- **Cause:** one line (for failures: the root cause, not the symptom)
- **Fix:** the specific script, skill edit, memory, or rule, with a one-line spec
- **Confidence:** high | medium | low, and what would disprove it
```

Evidence rules:
- Copy quotes character for character from one line, from the text after the line-type prefix. Paraphrased quotes fail verification and the finding is dropped.
- One quote per session, from as many distinct sessions as show the pattern (up to 6).
- If you cannot quote it, do not claim it.
