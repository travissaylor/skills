#!/usr/bin/env bash
# install_skills.sh: symlink every skill in this repo into the skill directories
# of each coding agent on this machine, so Claude Code, Codex, and anything
# that reads ~/.agents/skills all load the same versioned copy.
#
# Usage: tools/install_skills.sh [--dry-run]
#
# Targets: ~/.claude/skills ~/.codex/skills ~/.agents/skills (SKILL_TARGETS
# overrides, space separated). A link that already points here is left alone.
# Anything else at the target path, a copy or a link elsewhere, is moved to
# <name>.bak-<timestamp> beside it before the link is made. Nothing is deleted.
set -u

REPO=$(cd "$(dirname "$0")/.." && pwd)
TARGETS="${SKILL_TARGETS:-$HOME/.claude/skills $HOME/.codex/skills $HOME/.agents/skills}"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
STAMP=$(date +%Y%m%d-%H%M%S)

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
      echo "  replace $name (moved old to $name.bak-$STAMP)"
      run mv "$dest" "$dest.bak-$STAMP"
    else
      echo "  link    $name"
    fi
    run ln -s "$dir" "$dest"
  done
done
