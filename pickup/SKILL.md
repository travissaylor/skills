---
name: pickup
description: "Pick up work from the newest handoff document in the shared ~/handoffs store for this project, verify the tree matches it, and continue. Works the same in Claude Code, Codex, and Antigravity, on the machine that wrote the handoff or any peer. Runs when the user invokes /pickup or asks to pick up where the last session left off, at the start of a session that follows a handoff."
argument-hint: "Optional branch or handoff file to pick up, if not the newest"
disable-model-invocation: true
---

# Pickup

**You start where the last session stopped, whichever agent or machine it ran on.** The `handoff` skill wrote a document into `~/handoffs/<project>/` without knowing who would read it, and synced it here. You find it, check that the tree matches it, and get to work. Short on purpose. When there is no handoff, the `recall` skill does the heavy reconstruction instead.

This skill has no agent-specific steps. Every command below is a shell command or a git command, so it runs the same under Claude Code, Codex, and Antigravity. Where the agents differ is only in how they load a skill: Claude Code by its Skill tool, Codex by `$pickup`, Antigravity by reading this file from its skills directory. The document never assumes one of them.

The store script is `../handoff/scripts/handoff.sh` relative to the directory holding this file, so `~/.agents/skills/handoff/scripts/handoff.sh` on a standard install, with identical links under `~/.claude/skills`, `~/.codex/skills`, and `~/.gemini/skills`. Resolve it to an absolute path once. Do not run the relative form from the project root, where `../handoff` does not exist. Call the resolved path with the project root as your working directory, because the script names the project from the cwd. If the handoff skill is not installed, do the same steps by hand: `ls -t ~/handoffs/<project>/` and read the newest file whose `status` is `open`.

1. **Sync first.** From the project root, run the script's `sync` so a document written on another machine arrives before you look. An unreachable peer is a note in your reply, not a stop.
2. **Find the document.** Run the script's `latest`, or `latest --branch <b>` if the user named a branch, or read the file the user named. `status: found` includes the project and document path. `status: empty` reports `0 open handoffs` and exits 0. Say so and offer `recall`. A runtime failure exits 1 and needs investigation before concluding there is no handoff. Use `--all` to list every match, newest first by modification time. Shell callers can add `--path` for paths only, with empty stdout and exit 1 when no document matches. Run `latest --help` for usage.
3. **Read it whole.** Frontmatter and body. The frontmatter says which branch, head, and tree state to expect. `host` and `agent` say where it was written, which tells you whether you are on the same machine, and that is the only place the answer matters.
4. **Bring the tree to the document, then verify.** `git fetch`. If the local tree is clean, check out `branch` (creating it from the remote if needed) and `git pull --ff-only`. That is the normal cross-machine case and is safe, and on the same machine the pull is a no-op. Stop and report instead when the local tree has changes, when the branch has diverged so a fast-forward fails, or when `tree` says `pushed` but the branch is not on the remote at all. Then compare: head is `head` or a descendant of it. If `tree` says `dirty-left-in-place` and `host` is not this machine, the uncommitted work did not travel. Say so plainly. Run the checks in the Pickup block.
5. **Mark it taken.** Run the script's `mark-resumed <file>`. It flips `status` to `resumed`, stamps this host, and syncs, so the next `latest` on any machine does not hand out the same document twice.
6. **Load the suggested skills** the document names, the way this agent loads skills, then begin on the Goal. Do not reopen the Decisions. Ask the user about the Open questions when you reach them, not before.

**Reply** before starting: the document you took, in one line. The verification result, in one line. Any drift between the document and the tree. Then the first action.
