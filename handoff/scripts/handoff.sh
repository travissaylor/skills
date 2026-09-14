#!/usr/bin/env bash
# handoff.sh: the shared store behind the handoff, resume, and recall skills.
#
# Handoff documents live in ~/handoffs/<project>/<date>-<slug>.md on every
# machine. This script names the directory, finds the newest open document,
# flips a document to resumed, and syncs the store with peer machines over
# rsync. The agent writes the document itself. The script never does.
#
# Usage:
#   handoff.sh dir                        print ~/handoffs/<project>, creating it
#   handoff.sh new <slug>                 print the path for a new document
#   handoff.sh latest [--branch B] [--all] print newest open document for this project
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
  mkdir -p "$ROOT"
  if [ ! -f "$PEERS_FILE" ]; then
    cat > "$PEERS_FILE" <<'PEERS'
# One ssh host per line. handoff.sh sync pushes to and pulls from each one.
# Hosts come from ~/.ssh/config, so "travbox" here means "Host travbox" there.
PEERS
  fi
}

project_dir() {
  ensure_root
  local dir="$ROOT/$(project_name)"
  mkdir -p "$dir"
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
  [ -n "$slug" ] || die "new needs a slug"
  slug=$(echo "$slug" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')
  local dir; dir=$(project_dir)
  # Date and minute keep names unique across machines that sync later.
  local path="$dir/$(date +%Y-%m-%d-%H%M)-$slug.md"
  while [ -e "$path" ]; do path="${path%.md}-$(date +%S%N | cut -c1-4).md"; sleep 0.01; done
  echo "$path"
}

fm_value() { # fm_value <file> <key>
  sed -n '1,/^---$/p' "$1" | sed -n '2,$p' | grep -m1 -E "^$2:" | sed -E "s/^$2:[[:space:]]*//"
}

cmd_latest() {
  local branch="" all=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      --all) all=1; shift ;;
      *) die "latest: unknown flag $1" ;;
    esac
  done
  local dir; dir=$(project_dir)
  local found=0 f name
  # ls -t: newest first by modification time, which survives rsync -a.
  # Read line by line so a path with spaces stays one path.
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    f="$dir/$name"
    [ "$(fm_value "$f" status)" = "open" ] || continue
    if [ -n "$branch" ] && [ "$(fm_value "$f" branch)" != "$branch" ]; then continue; fi
    echo "$f"; found=1
    [ "$all" = 1 ] || break
  done < <(cd "$dir" && ls -t -- *.md 2>/dev/null)
  [ "$found" = 1 ]
}

cmd_mark_resumed() {
  local f="${1:-}"
  [ -f "$f" ] || die "mark-resumed needs an existing file"
  local stamp; stamp="$(hostname -s) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local tmp; tmp=$(mktemp)
  awk -v stamp="$stamp" '
    NR==1 && $0=="---" {infm=1; print; next}
    infm && $0=="---" {print "resumed_on: " stamp; infm=0; print; next}
    infm && /^status:/ {print "status: resumed"; next}
    {print}
  ' "$f" > "$tmp" && mv "$tmp" "$f"
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

case "${1:-}" in
  dir) shift; cmd_dir "$@" ;;
  new) shift; cmd_new "$@" ;;
  latest) shift; cmd_latest "$@" ;;
  mark-resumed) shift; cmd_mark_resumed "$@" ;;
  sync) shift; cmd_sync "$@" ;;
  peers) shift; cmd_peers "$@" ;;
  *) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
