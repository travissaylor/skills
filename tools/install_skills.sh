#!/usr/bin/env bash
# install_skills.sh: symlink every skill in this repo into the skill directories
# of each coding agent on this machine, so Claude Code, Codex, and anything
# that reads ~/.agents/skills all load the same versioned copy.
#
# Usage: tools/install_skills.sh [--dry-run]
#
# Targets: ~/.claude/skills ~/.codex/skills ~/.agents/skills ~/.gemini/skills (SKILL_TARGETS
# overrides, space separated). A link that already points here is left alone.
# Anything else at the target path, a copy or a link elsewhere, is moved to
# ~/.skills-backup/<timestamp>/<target dir name>/<name> before the link is
# made, outside every directory the agents scan, so a stale SKILL.md cannot
# keep loading under the same skill name. Nothing is deleted.
set -u

REPO=$(cd "$(dirname "$0")/.." && pwd)
TARGETS="${SKILL_TARGETS:-$HOME/.claude/skills $HOME/.codex/skills $HOME/.agents/skills $HOME/.gemini/skills}"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_ROOT="${SKILL_BACKUP_ROOT:-$HOME/.skills-backup}"

run() { if [ "$DRY" = 1 ]; then echo "  would: $*"; else "$@"; fi; }

for target in $TARGETS; do
  echo "$target"
  run mkdir -p "$target"
  for skill_md in "$REPO"/*/SKILL.md; do
    dir=$(dirname "$skill_md"); name=$(basename "$dir"); dest="$target/$name"
    if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$dir" ]; then
      echo "  ok      $name"; continue
    fi
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      bdir="$BACKUP_ROOT/$STAMP/$(basename "$(dirname "$target")")-$(basename "$target")"
      echo "  replace $name (moved old to $bdir/$name)"
      run mkdir -p "$bdir"
      run mv "$dest" "$bdir/$name"
    else
      echo "  link    $name"
    fi
    run ln -s "$dir" "$dest"
  done
done
