#!/usr/bin/env bash
# Lists Claude Code main-session transcripts (not subagent files) for trunk-tools
# projects modified since a date, newest last. Feed the list to the session-mining subagent.
# Usage: recent-sessions.sh YYYY-MM-DD[THH:MM]
set -euo pipefail
since=${1:?since date required}
find ~/.claude/projects -path '*trunk-tools*' -name '*.jsonl' -not -path '*/subagents/*' \
  -newermt "$since" -size +20k -print0 |
  while IFS= read -r -d '' f; do
    printf '%s\t%sk\t%s\n' "$(stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$f")" "$(du -k "$f" | cut -f1)" "$f"
  done | sort
