---
name: handoff
description: "Write a handoff document for the next agent session, whichever agent or machine runs it, into the shared ~/handoffs store, move the working tree with it, and sync the store to peer machines. Runs only when the user invokes /handoff, at the end of a stretch of work."
argument-hint: "Where the work goes next (codex, travbox, claude) and what the next session will focus on"
disable-model-invocation: true
---

# Handoff

**You compact this session into a document the next session can act on without you, from any agent on any machine.** The document goes into the shared store at `~/handoffs/<project>/`, never the OS temp dir and never the repo. The store syncs to peer machines over rsync. The `resume` skill picks it up on the other side, and the `recall` skill checks the store before mining history.

The failure modes you are writing to prevent: a doc in a temp dir the next machine cannot see, absolute paths that only resolve on this machine, and a branch that never left this laptop.

1. **Read the argument.** It names the destination (`codex`, `travbox`, `claude`, or a host) and the focus of the next session. Tailor the resume block to the destination. With no argument, assume another machine may pick the work up and write for that case.
2. **Move the tree.** Run `git status`. If the tree is dirty and a remote exists, commit on the current branch with a message starting `wip: handoff` and push it. If the argument says the next session runs on this machine, skip the commit and say so in the doc. If there is no remote, say so in the doc and leave the tree alone. Record the outcome in the `tree` field. A branch that only exists here is the single most common reason a handoff fails.
3. **Name the file.** Run `<skill-dir>/scripts/handoff.sh new <slug>`, where the slug names the work in two to four words. It prints the path. Create the directory if the script says it did not exist.
4. **Write the document** to the contract below. Paths are relative to the repo root, always. This machine's home directory does not exist on the next one. Do not duplicate content already captured in specs, plans, issues, PRs, commits, or diffs. Point at them by repo-relative path or URL. Redact secrets and personal data. Write it through the `prose` skill.
5. **Sync.** Run `<skill-dir>/scripts/handoff.sh sync`. It pushes to and pulls from every host in `~/handoffs/peers`. An unreachable peer is reported, not fatal. If no peers are listed, tell the user the store is local only and how to add one.
6. **Reply** with the document path, the tree outcome, the sync outcome, and the one-line command the next session runs.

## Document contract

Frontmatter first. The script and the `resume` skill read these fields, so keep the keys exact.

```
---
project: <repo basename>
branch: <branch>
head: <short sha after the wip commit, if any>
remote: <origin url, or none>
tree: pushed | committed-not-pushed | dirty-left-in-place | clean
written: <UTC timestamp>
host: <hostname>
agent: <claude-code | codex | other>
target: <the argument, verbatim>
status: open
---
```

Then the body, in this order. Cut a section that would be empty, never pad one.

- **Goal.** What the next session is for, in two or three sentences. Lead with the outcome, not the history.
- **State.** Where things stand. One line per thread, each tagged like `recall` does: `[merged #N]`, `[open PR #N]`, `[in flight <branch>]`, `[verified, uncommitted]`, `[planned, not started]`.
- **Resume.** The exact commands to get working, in a fenced block. For another machine: `cd` to the project by its name under the projects directory, `git fetch`, `git checkout <branch>`, `git pull`. For the same machine: the branch to check out. Then the checks to run first to confirm the tree is as described.
- **Decisions.** Choices already made, with the reason, so the next session does not reopen them.
- **Open questions.** Anything the user still has to decide, marked as such.
- **Do not.** Rules learned the hard way in this session that are not yet in CLAUDE.md or AGENTS.md.
- **Verify.** The commands that prove the work is done.
- **Suggested skills.** Skills the next session should load, by name, with one clause each on why. Name them plainly. Claude Code loads them with the Skill tool, Codex by `$name`.
- **Sources.** PRs, issues, tickets, docs, and chat permalinks, each one line.

## Peers

`~/handoffs/peers` holds one ssh host per line, resolved through `~/.ssh/config`. Sync is symmetric per peer, push then pull, so any machine that can reach any other machine keeps both current. A machine that cannot ssh out still receives whatever its peers push. Run `<skill-dir>/scripts/handoff.sh peers` to see who answers.
