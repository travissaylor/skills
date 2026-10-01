# Mining Claude session transcripts (subagent brief)

Transcripts are JSONL, often 1–10 MB. Never cat a whole file into the main session. Spawn one Sonnet subagent (`model: sonnet`, `subagent_type: general-purpose`. The recipe below is concrete enough that Opus adds nothing) with the file list from `scripts/recent-sessions.sh` and this extraction recipe. It returns findings only.

Extraction (user turns + assistant text, no tool payloads):
```bash
jq -r 'select(.type=="user" or .type=="assistant")
  | [.timestamp, .type, (.message.content | if type=="string" then . else (map(select(.type=="text")|.text)|join(" ")) end)]
  | @tsv' FILE | cut -c1-600
```

Ask the subagent for, per working day in the window:
1. What was worked on and finished (PRs opened or merged, features, decisions) with session id + timestamp.
2. Decisions and rationale, quoting short key phrases.
3. Anything that changes scope shape: a scope dropped, split, merged, reshaped, or work on something with no Scope Tracker row. Name the scope rows involved.
4. UAT, design review, or product review sessions that happened.
5. Open questions, blockers, unfinished work, and the state of the current branch (commits ahead, pushed?, PR?).
Cap the report at about 1,200 words.

Meeting transcripts: same pattern. Subagent fetches each Notion meeting note with `include_transcript: true` and reports only decisions, scope-shape signals, UAT mentions, and action items for Travis.
