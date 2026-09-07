#!/usr/bin/env bash
# run-unit.sh: launch one external executor (codex or agy) for one conductor
# unit, normalize its output, and enforce timeouts. The orchestrator launches
# this in the background, one call per unit, and reads the files it writes.
#
# Usage:
#   run-unit.sh --backend codex|agy --unit <id> --run-dir <dir> --repo <path>
#               [--model <name>] [--resume <thread-or-conversation-id>]
#               [--stall <secs>] [--max <secs>]
#
# Reads:   <run-dir>/<unit>.brief.md
# Writes:  <run-dir>/<unit>.result.json   report matching result.schema.json
#          <run-dir>/<unit>.meta.json     backend, outcome, thread id, usage, seconds
#          <run-dir>/<unit>.events.jsonl  codex event stream
#          <run-dir>/<unit>.raw.json      agy response envelope
#          <run-dir>/<unit>.stderr
# Exit:    0 when outcome is "completed" and result.json exists, else 1.
set -u

BACKEND="" UNIT="" RUN_DIR="" REPO="" MODEL="" RESUME=""
STALL=600   # codex only: kill when no new event for this long
MAX=3600    # both: wall-clock ceiling

while [ $# -gt 0 ]; do
  case "$1" in
    --backend) BACKEND="$2"; shift 2 ;;
    --unit)    UNIT="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --repo)    REPO="$2"; shift 2 ;;
    --model)   MODEL="$2"; shift 2 ;;
    --resume)  RESUME="$2"; shift 2 ;;
    --stall)   STALL="$2"; shift 2 ;;
    --max)     MAX="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

for v in BACKEND UNIT RUN_DIR REPO; do
  [ -n "${!v}" ] || { echo "missing --$(echo $v | tr 'A-Z_' 'a-z-')" >&2; exit 2; }
done
case "$BACKEND" in codex|agy) ;; *) echo "backend must be codex or agy" >&2; exit 2 ;; esac
command -v "$BACKEND" >/dev/null || { echo "$BACKEND not on PATH" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

SCHEMA="$(cd "$(dirname "$0")/.." && pwd)/result.schema.json"
REPO="$(cd "$REPO" && pwd)"
mkdir -p "$RUN_DIR"
RUN_DIR="$(cd "$RUN_DIR" && pwd)"
BRIEF="$RUN_DIR/$UNIT.brief.md"
RESULT="$RUN_DIR/$UNIT.result.json"
META="$RUN_DIR/$UNIT.meta.json"
EVENTS="$RUN_DIR/$UNIT.events.jsonl"
RAW="$RUN_DIR/$UNIT.raw.json"
STDERR="$RUN_DIR/$UNIT.stderr"
[ -f "$BRIEF" ] || { echo "brief not found: $BRIEF" >&2; exit 2; }
rm -f "$RESULT" "$META"

mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }

START=$(date +%s)
OUTCOME="completed"

if [ "$BACKEND" = "codex" ]; then
  : > "$EVENTS"
  if [ -n "$RESUME" ]; then
    # resume has no -C or -s flags: run from the repo and pin the sandbox via
    # config override. Prompt goes positional.
    (
      cd "$REPO" && codex exec resume "$RESUME" --json \
        -c 'sandbox_mode="workspace-write"' \
        --output-schema "$SCHEMA" -o "$RESULT" ${MODEL:+-m "$MODEL"} \
        "$(cat "$BRIEF")" < /dev/null > "$EVENTS" 2> "$STDERR"
    ) &
  else
    codex exec - -C "$REPO" -s workspace-write --json \
      --output-schema "$SCHEMA" -o "$RESULT" ${MODEL:+-m "$MODEL"} \
      < "$BRIEF" > "$EVENTS" 2> "$STDERR" &
  fi
  PID=$!
  while kill -0 "$PID" 2>/dev/null; do
    sleep 5
    NOW=$(date +%s)
    if [ $((NOW - START)) -gt "$MAX" ]; then OUTCOME="timeout"; break; fi
    LAST=$(mtime "$EVENTS"); [ "$LAST" -lt "$START" ] && LAST=$START
    if [ $((NOW - LAST)) -gt "$STALL" ]; then OUTCOME="stalled"; break; fi
  done
  if [ "$OUTCOME" != "completed" ]; then
    pkill -TERM -P "$PID" 2>/dev/null; kill -TERM "$PID" 2>/dev/null; sleep 2
    pkill -KILL -P "$PID" 2>/dev/null; kill -KILL "$PID" 2>/dev/null
  fi
  wait "$PID" 2>/dev/null; EXIT=$?
  THREAD=$(jq -r 'select(.type=="thread.started") | .thread_id' "$EVENTS" 2>/dev/null | head -1)
  USAGE=$(jq -c 'select(.type=="turn.completed") | .usage' "$EVENTS" 2>/dev/null | tail -1)
  FAILED=$(jq -c 'select(.type=="turn.failed") | .error // .' "$EVENTS" 2>/dev/null | tail -1)
  [ -n "$FAILED" ] && [ "$OUTCOME" = "completed" ] && OUTCOME="failed"
  ERROR="$FAILED"
else
  # agy: no cwd flag, so cd and pass --add-dir. Prompt must be the flag value.
  # Output arrives only at the end, so only the wall-clock ceiling applies.
  (
    cd "$REPO" && agy --print "$(cat "$BRIEF")" --add-dir "$REPO" \
      --mode accept-edits --output-format json --json-schema "$SCHEMA" \
      ${MODEL:+--model "$MODEL"} ${RESUME:+--conversation "$RESUME"} \
      --print-timeout "${MAX}s" < /dev/null > "$RAW" 2> "$STDERR"
  ) &
  PID=$!
  while kill -0 "$PID" 2>/dev/null; do
    sleep 5
    if [ $(( $(date +%s) - START )) -gt $((MAX + 30)) ]; then OUTCOME="timeout"; break; fi
  done
  if [ "$OUTCOME" != "completed" ]; then
    pkill -TERM -P "$PID" 2>/dev/null; kill -TERM "$PID" 2>/dev/null; sleep 2
    pkill -KILL -P "$PID" 2>/dev/null; kill -KILL "$PID" 2>/dev/null
  fi
  wait "$PID" 2>/dev/null; EXIT=$?
  THREAD=$(jq -r '.conversation_id // empty' "$RAW" 2>/dev/null)
  USAGE=$(jq -c '.usage // empty' "$RAW" 2>/dev/null)
  AGY_STATUS=$(jq -r '.status // empty' "$RAW" 2>/dev/null)
  ERROR=$(jq -c '.error // empty' "$RAW" 2>/dev/null)
  if [ "$AGY_STATUS" = "SUCCESS" ] && jq -e '.structured_output != null' "$RAW" >/dev/null 2>&1; then
    jq '.structured_output' "$RAW" > "$RESULT"
  elif [ "$OUTCOME" = "completed" ]; then
    OUTCOME="failed"; [ -z "$ERROR" ] && ERROR="\"agy status: ${AGY_STATUS:-none}\""
  fi
fi

END=$(date +%s)
[ "$OUTCOME" = "completed" ] && { [ -s "$RESULT" ] && jq -e . "$RESULT" >/dev/null 2>&1 || OUTCOME="failed"; }

jq -n \
  --arg backend "$BACKEND" --arg unit "$UNIT" --arg outcome "$OUTCOME" \
  --arg model "$MODEL" --arg thread "${THREAD:-}" --argjson exit "${EXIT:-1}" \
  --argjson seconds "$((END - START))" \
  --argjson usage "${USAGE:-null}" --argjson error "${ERROR:-null}" \
  '{backend:$backend, unit:$unit, outcome:$outcome, exit_code:$exit, model:$model,
    thread_id:$thread, seconds:$seconds, usage:$usage, error:$error}' > "$META"

echo "$UNIT [$BACKEND] $OUTCOME in $((END - START))s (thread ${THREAD:-none})"
[ "$OUTCOME" = "completed" ]
