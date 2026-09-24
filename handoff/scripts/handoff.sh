#!/usr/bin/env bash
# handoff.sh: the shared store behind the handoff, pickup, and recall skills.
#
# Handoff documents live in ~/handoffs/<project>/<date>-<slug>.md on every
# machine. This script names the directory, finds the newest open document,
# flips a document to resumed, and syncs the store with peer machines over
# rsync. The agent writes the document itself. The script never does.
#
# Usage:
#   handoff.sh dir                        print ~/handoffs/<project>, creating it
#   handoff.sh new <slug>                 print the path for a new document
#   handoff.sh latest [--branch B] [--all] [--path]
#                                        describe newest open document for this project
#   handoff.sh mark-resumed <file>        set status to resumed, then sync
#   handoff.sh sync                       push and pull with every peer, best effort
#   handoff.sh peers                      list peers and whether each answers
#
# Peers: one ssh host per line in ~/handoffs/peers. HANDOFF_PEERS (space
# separated) adds more. Unreachable peers are reported, never fatal.
# Project: basename of the main repository, which is the same from any linked
# worktree, or of the cwd outside a repo, so run this from inside the project.
# HANDOFF_PROJECT overrides the name.
set -u

ROOT="${HANDOFF_ROOT:-$HOME/handoffs}"
PEERS_FILE="$ROOT/peers"
SSH_OPTS="-o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new"

die() { echo "handoff.sh: $*" >&2; exit 1; }

usage() {
  case "${1:-}" in
    dir) echo "Usage: handoff.sh dir"; echo "Print the project store directory, creating it if needed." ;;
    new) echo "Usage: handoff.sh new <slug>"; echo "Print an unused document path. The document is not created." ;;
    latest)
      echo "Usage: handoff.sh latest [--branch <branch>] [--all] [--path]"
      echo "Report status, project, and matching path. Empty results say 0 open handoffs."
      echo "--branch filters by branch. --all returns every match, newest first by mtime."
      echo "--path prints paths only, with empty stdout and exit 1 when none match."
      ;;
    mark-resumed) echo "Usage: handoff.sh mark-resumed <file>"; echo "Set status to resumed, stamp this host and time, then sync." ;;
    sync) echo "Usage: handoff.sh sync"; echo "Push and pull with every peer, best effort." ;;
    peers) echo "Usage: handoff.sh peers"; echo "List peers and whether each answers." ;;
    *)
      echo "Usage: handoff.sh <command> [arguments]"
      echo "Commands: dir, new, latest, mark-resumed, sync, peers"
      echo "Run handoff.sh <command> --help for arguments and output."
      echo "HANDOFF_ROOT sets the store (default: ~/handoffs). HANDOFF_PROJECT overrides the project."
      echo "Peers come from the store's peers file and space-separated HANDOFF_PEERS."
      ;;
  esac
  echo "Exit codes: 0 success, 1 runtime failure or empty --path result, 2 invalid arguments."
  echo "Sync also exits 2 when any peer is unreachable, including after mark-resumed."
}

usage_error() {
  echo "handoff.sh: $*" >&2
  echo "Run handoff.sh${COMMAND:+ $COMMAND} --help for usage." >&2
  exit 2
}

project_name() {
  if [ -n "${HANDOFF_PROJECT:-}" ]; then echo "$HANDOFF_PROJECT"; return; fi
  local common top
  # --git-common-dir points at the main repo's .git even from a linked
  # worktree, so every worktree shares one ~/handoffs/<project>/.
  if common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
    top=$(dirname "$common")
  else
    top=$PWD
  fi
  basename "$top"
}

ensure_root() {
  mkdir -p "$ROOT" || die "cannot create store: $ROOT"
  if [ ! -f "$PEERS_FILE" ]; then
    cat > "$PEERS_FILE" <<'PEERS' || die "cannot create peers file: $PEERS_FILE"
# One ssh host per line. handoff.sh sync pushes to and pulls from each one.
# Hosts come from ~/.ssh/config, so "travbox" here means "Host travbox" there.
PEERS
  fi
}

project_dir() {
  ensure_root || return 1
  local dir="$ROOT/$(project_name)"
  mkdir -p "$dir" || die "cannot create project directory: $dir"
  echo "$dir"
}

list_peers() {
  {
    [ -f "$PEERS_FILE" ] && grep -vE '^\s*(#|$)' "$PEERS_FILE"
    for p in ${HANDOFF_PEERS:-}; do echo "$p"; done
  } | awk 'NF && !seen[$1]++ {print $1}'
}

cmd_dir() { project_dir; }

cmd_new() {
  local slug="${1:-}"
  slug=$(echo "$slug" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')
  [ -n "$slug" ] || usage_error "new: slug must contain a letter or digit"
  local dir; dir=$(project_dir) || return 1
  # Date and minute keep names unique across machines that sync later.
  local path="$dir/$(date +%Y-%m-%d-%H%M)-$slug.md"
  while [ -e "$path" ]; do path="${path%.md}-$(date +%S%N | cut -c1-4).md"; sleep 0.01; done
  echo "$path"
}

fm_value() { # fm_value <file> <key>
  # Read simple scalar fields only from a complete leading frontmatter block.
  awk -v key="$2" '
    {sub(/\r$/, "")}
    NR==1 {if ($0!="---") exit; next}
    $0=="---" {if (found) print value; exit}
    !found && index($0, key ":")==1 {
      value=substr($0, length(key)+2)
      sub(/^[[:space:]]*/, "", value)
      sub(/[[:space:]]*$/, "", value)
      quote=substr(value, 1, 1)
      if ((quote=="\"" || quote==sprintf("%c", 39)) &&
          substr(value, length(value), 1)==quote)
        value=substr(value, 2, length(value)-2)
      found=1
    }
  ' "$1"
}

cmd_latest() {
  local branch="" all=0 path_only=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      --all) all=1; shift ;;
      --path) path_only=1; shift ;;
    esac
  done
  local dir; dir=$(project_dir) || return 1
  local f status file_branch listing=""
  local -a candidates paths=()
  [ -r "$dir" ] && [ -x "$dir" ] || die "cannot read project directory: $dir"
  shopt -s nullglob
  candidates=("$dir"/*.md)
  if [ "${#candidates[@]}" -gt 0 ]; then
    listing=$(ls -td -- "${candidates[@]}") || die "cannot list handoffs in: $dir"
  fi
  # ls -t: newest first by modification time, which survives rsync -a.
  # Read line by line so a path with spaces stays one path.
  while IFS= read -r f; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    status=$(fm_value "$f" status) || die "cannot read handoff: $f"
    [ "$status" = "open" ] || continue
    if [ -n "$branch" ]; then
      file_branch=$(fm_value "$f" branch) || die "cannot read handoff: $f"
      [ "$file_branch" = "$branch" ] || continue
    fi
    paths+=("$f")
    [ "$all" = 1 ] || break
  done <<< "$listing"
  if [ "$path_only" = 1 ]; then
    [ "${#paths[@]}" -gt 0 ] || return 1
    printf '%s\n' "${paths[@]}"
  elif [ "${#paths[@]}" -gt 0 ]; then
    printf 'status: found\nproject: %s\n' "$(project_name)"
    [ -z "$branch" ] || printf 'branch: %s\n' "$branch"
    printf 'path: %s\n' "${paths[@]}"
  else
    printf 'status: empty\nproject: %s\n' "$(project_name)"
    [ -z "$branch" ] || printf 'branch: %s\n' "$branch"
    printf 'message: 0 open handoffs\n'
  fi
}

cmd_mark_resumed() {
  local f="${1:-}"
  [ -f "$f" ] || die "mark-resumed needs an existing file"
  local stamp; stamp="$(hostname -s) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local tmp; tmp=$(mktemp) || die "cannot create temporary file"
  awk -v stamp="$stamp" '
    {sub(/\r$/, "")}
    NR==1 && $0=="---" {infm=1; print; next}
    infm && $0=="---" {print "resumed_on: " stamp; infm=0; print; next}
    infm && /^status:/ {print "status: resumed"; next}
    {print}
  ' "$f" > "$tmp" && mv "$tmp" "$f" || {
    rm -f "$tmp"
    die "cannot mark handoff resumed: $f"
  }
  echo "marked resumed: $f"
  cmd_sync
}

cmd_sync() {
  ensure_root
  local peers; peers=$(list_peers)
  if [ -z "$peers" ]; then
    echo "sync: no peers listed in $PEERS_FILE, store is local only"
    return 0
  fi
  command -v rsync >/dev/null || die "rsync not installed"
  local rc=0
  for p in $peers; do
    # --update keeps whichever side is newer, so a document edited on one
    # machine wins over its stale copy, and new files simply appear.
    if rsync -a --update --timeout=10 --exclude peers -e "ssh $SSH_OPTS" \
         "$ROOT/" "$p:handoffs/" 2>/dev/null &&
       rsync -a --update --timeout=10 --exclude peers -e "ssh $SSH_OPTS" \
         "$p:handoffs/" "$ROOT/" 2>/dev/null; then
      echo "sync: $p ok"
    else
      echo "sync: $p unreachable, skipped"
      rc=2
    fi
  done
  return $rc
}

cmd_peers() {
  ensure_root
  local peers; peers=$(list_peers)
  [ -n "$peers" ] || { echo "no peers in $PEERS_FILE"; return 0; }
  for p in $peers; do
    if ssh $SSH_OPTS "$p" true 2>/dev/null; then echo "$p: reachable"; else echo "$p: unreachable"; fi
  done
}

COMMAND="${1:-}"
case "$COMMAND" in
  ""|--help|-h)
    COMMAND=""
    [ $# -le 1 ] || usage_error "unexpected arguments after help"
    usage; exit 0 ;;
  dir|new|latest|mark-resumed|sync|peers) shift ;;
  *) COMMAND=""; usage_error "unknown command: $1" ;;
esac
if [ $# = 1 ] && { [ "$1" = --help ] || [ "$1" = -h ]; }; then
  usage "$COMMAND"; exit 0
fi
# Validate the complete invocation before creating files or contacting peers.
case "$COMMAND" in
  dir|sync|peers) [ $# = 0 ] || usage_error "$COMMAND: unexpected argument: $1" ;;
  new|mark-resumed)
    [ $# = 1 ] || usage_error "$COMMAND needs exactly one argument"
    [ -n "$1" ] && [[ "$1" != -* ]] || usage_error "$COMMAND: expected a value, got: $1"
    ;;
  latest)
    args=("$@")
    while [ $# -gt 0 ]; do
      case "$1" in
        --branch)
          [ $# -ge 2 ] && [ -n "$2" ] && [[ "$2" != -* ]] || usage_error "latest: --branch needs a branch name"
          shift 2 ;;
        --all|--path) shift ;;
        *) usage_error "latest: unexpected argument: $1" ;;
      esac
    done
    # Bash 3.2 treats an empty array as unset under nounset.
    set -- ${args[@]+"${args[@]}"}
    ;;
esac
"cmd_${COMMAND//-/_}" "$@"
