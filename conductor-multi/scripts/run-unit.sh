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
# Exit:    0 completed with a JSON object report, 1 execution failure, 2 usage error.
set -u

usage() {
  cat <<'EOF'
Usage: run-unit.sh --backend codex|agy --unit <id> --run-dir <dir> --repo <path>
                   [--model <name>] [--resume <thread-or-conversation-id>]
                   [--stall <secs>] [--max <secs>]

Reads <run-dir>/<unit>.brief.md. Writes result.json, meta.json, and stderr
with the same unit prefix; prints outcome, elapsed time, and artifact paths.
--stall defaults to 600 seconds (Codex only); --max defaults to 3600 seconds.
Timeouts must be positive decimal integers, at most 2147483617 seconds.
--help, -h  Show this help without launching an executor.
Exit codes: 0 completed, 1 execution failure, 2 invalid arguments or setup.
EOF
}

usage_error() {
  printf 'run-unit.sh: %s\nRun run-unit.sh --help for usage.\n' "$1" >&2
  exit 2
}

BACKEND="" UNIT="" RUN_DIR="" REPO="" MODEL="" RESUME=""
STALL=600   # codex only: kill when no new event for this long
MAX=3600    # both: wall-clock ceiling

while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --backend|--unit|--run-dir|--repo|--model|--resume|--stall|--max)
      [ $# -ge 2 ] && [ -n "$2" ] && [[ "$2" != --* ]] || usage_error "$1 requires a value"
      ;;
    *) usage_error "unknown argument: $1" ;;
  esac
  case "$1" in
    --backend) BACKEND="$2"; shift 2 ;;
    --unit)    UNIT="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --repo)    REPO="$2"; shift 2 ;;
    --model)   MODEL="$2"; shift 2 ;;
    --resume)  RESUME="$2"; shift 2 ;;
    --stall)   STALL="$2"; shift 2 ;;
    --max)     MAX="$2"; shift 2 ;;
  esac
done

for v in BACKEND UNIT RUN_DIR REPO; do
  [ -n "${!v}" ] || usage_error "missing --$(printf '%s' "$v" | tr 'A-Z_' 'a-z-')"
done
case "$BACKEND" in codex|agy) ;; *) usage_error "--backend must be codex or agy" ;; esac
for v in STALL MAX; do
  value="${!v}"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] && [ "${#value}" -le 10 ] && [ "$value" -le 2147483617 ] ||
    usage_error "--$(printf '%s' "$v" | tr 'A-Z' 'a-z') must be a positive decimal integer at most 2147483617"
done
command -v "$BACKEND" >/dev/null || usage_error "$BACKEND not on PATH; install it or choose an available backend"
command -v jq >/dev/null || usage_error "jq not on PATH; install jq to read and write executor reports"

SCHEMA="$(cd "$(dirname "$0")/.." && pwd)/result.schema.json"
REPO="$(cd "$REPO" 2>/dev/null && pwd)" || usage_error "--repo must name an accessible directory"
[ -r "$RUN_DIR/$UNIT.brief.md" ] && [ -f "$RUN_DIR/$UNIT.brief.md" ] ||
  usage_error "brief not found or unreadable: $RUN_DIR/$UNIT.brief.md; write it before launching"
RUN_DIR="$(cd "$RUN_DIR" 2>/dev/null && pwd)" || usage_error "--run-dir must name an accessible directory"
BRIEF="$RUN_DIR/$UNIT.brief.md"
RESULT="$RUN_DIR/$UNIT.result.json"
META="$RUN_DIR/$UNIT.meta.json"
EVENTS="$RUN_DIR/$UNIT.events.jsonl"
RAW="$RUN_DIR/$UNIT.raw.json"
STDERR="$RUN_DIR/$UNIT.stderr"
rm -f "$RESULT" "$META"

mtime() {
  local stamp
  if stamp=$(stat -f %m "$1" 2>/dev/null) || stamp=$(stat -c %Y "$1" 2>/dev/null); then
    printf '%s\n' "$stamp"
  else
    echo 0
  fi
}

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
  if ! jq -se 'length == 1 and (.[0] | type == "object")' "$RAW" >/dev/null 2>&1; then
    ERROR=$(jq -n --arg path "$RAW" '"agy response missing or malformed; inspect " + $path')
    [ "$OUTCOME" = "completed" ] && OUTCOME="failed"
  else
    THREAD=$(jq -r '.conversation_id // empty' "$RAW" 2>/dev/null)
    USAGE=$(jq -c '.usage // empty' "$RAW" 2>/dev/null)
    AGY_STATUS=$(jq -r '.status // empty' "$RAW" 2>/dev/null)
    ERROR=$(jq -c '.error // empty' "$RAW" 2>/dev/null)
    if [ "$AGY_STATUS" = "SUCCESS" ] && jq -e '.structured_output != null' "$RAW" >/dev/null 2>&1; then
      jq '.structured_output' "$RAW" > "$RESULT"
    elif [ "$OUTCOME" = "completed" ]; then
      OUTCOME="failed"
      [ -z "$ERROR" ] && ERROR=$(jq -n --arg status "${AGY_STATUS:-none}" '"agy status: " + $status + "; inspect stderr before retrying"')
    fi
  fi
fi

END=$(date +%s)
REASON=""
case "$OUTCOME" in
  timeout) REASON="wall-clock limit exceeded; inspect stderr before retrying with --max" ;;
  stalled) REASON="event stream inactive; inspect stderr before retrying with --stall" ;;
esac
if [ "$OUTCOME" = "completed" ]; then
  if [ "$EXIT" -ne 0 ]; then
    OUTCOME="failed"; REASON="$BACKEND exited with code $EXIT; inspect stderr before retrying"
  elif [ ! -s "$RESULT" ]; then
    OUTCOME="failed"; REASON="result report missing or empty; inspect stderr before retrying"
  elif ! jq -se 'length == 1 and (.[0] | type == "object")' "$RESULT" >/dev/null 2>&1; then
    OUTCOME="failed"; REASON="result report must contain one JSON object; inspect the report before retrying"
  fi
fi
if [ "$OUTCOME" != "completed" ]; then
  if [ -z "$REASON" ]; then
    REASON=$(printf '%s' "${ERROR:-null}" | jq -r 'if type == "object" then .message // . else . end | if . == null then "executor failed; inspect stderr before retrying" elif type == "string" then . else tojson end')
  elif [ -z "${ERROR:-}" ]; then
    ERROR=$(jq -n --arg reason "$REASON" '$reason')
  fi
fi

jq -n \
  --arg backend "$BACKEND" --arg unit "$UNIT" --arg outcome "$OUTCOME" \
  --arg model "$MODEL" --arg thread "${THREAD:-}" --argjson exit "${EXIT:-1}" \
  --argjson seconds "$((END - START))" \
  --argjson usage "${USAGE:-null}" --argjson error "${ERROR:-null}" \
  '{backend:$backend, unit:$unit, outcome:$outcome, exit_code:$exit, model:$model,
    thread_id:$thread, seconds:$seconds, usage:$usage, error:$error}' > "$META"

printf '%s [%s] %s in %ss (thread %s)\n' "$UNIT" "$BACKEND" "$OUTCOME" "$((END - START))" "${THREAD:-none}"
printf 'report: %s\nmeta: %s\nstderr: %s\n' "$RESULT" "$META" "$STDERR"
if [ -n "$REASON" ]; then
  # Keep multiline or verbose backend errors out of the completion summary.
  SUMMARY=$(printf '%s' "$REASON" | jq -Rs 'gsub("[[:cntrl:][:space:]]+"; " ") | if length > 240 then .[:237] + "..." else . end')
  printf 'reason: %s\n' "$SUMMARY"
fi
[ "$OUTCOME" = "completed" ]
