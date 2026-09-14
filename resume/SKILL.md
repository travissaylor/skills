---
name: resume
description: "Pick up work from the newest handoff document in the shared ~/handoffs store for this project, verify the tree matches it, and continue. Runs only when the user invokes /resume, at the start of a session that follows a handoff from any agent or machine."
argument-hint: "Optional branch or handoff file to resume, if not the newest"
disable-model-invocation: true
---

# Resume

**You start where the last session stopped, whichever agent or machine it ran on.** The `handoff` skill wrote a document into `~/handoffs/<project>/` and synced it here. You find it, check that the tree matches it, and get to work. Short on purpose. When there is no handoff, the `recall` skill does the heavy reconstruction instead.

The store script lives next to this skill at `../handoff/scripts/handoff.sh`. If the handoff skill is not installed, do the same steps by hand: `ls -t ~/handoffs/<project>/` and read the newest file whose `status` is `open`.

1. **Sync first.** Run `../handoff/scripts/handoff.sh sync` so a document written on another machine arrives before you look. An unreachable peer is a note in your reply, not a stop.
2. **Find the document.** Run `../handoff/scripts/handoff.sh latest`, or `latest --branch <b>` if the user named a branch, or read the file the user named. No open document means no handoff. Say so and offer `recall`.
3. **Read it whole.** Frontmatter and body. The frontmatter says which branch, head, and tree state to expect.
4. **Verify the tree before trusting the doc.** `git fetch`, then compare. Branch checked out and matches `branch`. Head is `head` or a descendant of it. If `tree` says `pushed` and the branch is not on the remote, or the local head is behind, stop and report it instead of guessing. If `tree` says `dirty-left-in-place` and you are on a different machine, the uncommitted work did not travel. Say so plainly. Run the checks in the Resume block.
5. **Mark it taken.** Run `../handoff/scripts/handoff.sh mark-resumed <file>`. It flips `status` to `resumed`, stamps this host, and syncs, so the next `latest` on any machine does not hand out the same document twice.
6. **Load the suggested skills** the document names, then begin on the Goal. Do not reopen the Decisions. Ask the user about the Open questions when you reach them, not before.

**Reply** before starting: the document you took, in one line. The verification result, in one line. Any drift between the document and the tree. Then the first action.
