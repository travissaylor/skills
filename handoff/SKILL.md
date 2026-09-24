---
name: handoff
description: "Write a handoff document for the next agent session into the shared ~/handoffs store, publish the branch so the tree travels with it, and sync the store to peer machines. The document is written for whichever agent and machine picks it up next, so it never needs to know where that is. Runs when the user invokes /handoff or asks to hand this work off, at the end of a stretch of work."
argument-hint: "Optional: what the next session should focus on"
disable-model-invocation: true
---

# Handoff

**You compact this session into a document the next session can act on without you.** You do not know, and do not ask, which agent or machine that session runs on. Claude Code, Codex, or Antigravity, on this laptop or another host, all pick it up the same way: the `pickup` skill takes the newest open document for the project, and the `recall` skill checks the store before mining history. Write for the hardest case, a different agent on a different machine, and every easier case works too.

The document goes into the shared store at `~/handoffs/<project>/`, never the OS temp dir and never the repo. The store syncs to peer machines over rsync.

The failure modes you are writing to prevent: a doc in a temp dir the next machine cannot see, absolute paths that only resolve on this machine, a branch that never left this laptop, and instructions that only one agent understands.

## Finding the script

Every skill directory in this set is installed side by side, so the store script is always `../handoff/scripts/handoff.sh` relative to the directory holding this file. Resolve it to an absolute path once, before anything else: take the directory this SKILL.md was read from, go up one level, then into `handoff/scripts/handoff.sh`. On a standard install that is `~/.agents/skills/handoff/scripts/handoff.sh`, with identical links under `~/.claude/skills`, `~/.codex/skills`, and `~/.gemini/skills`. Never type a placeholder like `<skill-dir>` into a shell, where it becomes a redirection, and never run the relative form from the project root, where `../handoff` does not exist. Call the resolved path with the project root as your working directory, because the script names the project from the cwd. `HANDOFF_PROJECT` overrides the name when you must run it from elsewhere.

1. **Read the argument, if any.** It names the focus of the next session, nothing more. It never names an agent, a host, or a machine. If the user wrote one anyway, treat it as focus text and still write for any destination. With no argument, the focus is whatever this session left unfinished.
2. **Move the tree.** Two separate checks, because a clean tree can still be unpublished. First, `git status`: if the tree is dirty and a remote exists, commit on the current branch with a message starting `wip: handoff`. Always. The next session may be on another machine, and uncommitted work does not travel. Second, publish: run `git fetch` and `git log @{upstream}..HEAD` (or note that no upstream exists). If any commit is not on the remote, or the branch has no upstream, push with `-u`. Do this whether or not you just committed. If there is no remote, say so in the doc and leave the tree alone. Record the outcome in the `tree` field. A branch that only exists here is the single most common reason a handoff fails.
3. **Name the file.** From the project root, run the resolved script with `new <slug>`, where the slug names the work in two to four words. It prints a path that does not yet exist.
4. **Write the document** to the contract below. Paths are relative to the repo root, always. This machine's home directory does not exist on the next one. Do not duplicate content already captured in specs, plans, issues, PRs, commits, or diffs. Point at them by repo-relative path or URL. Redact secrets and personal data. Write it through the `prose` skill.
5. **Sync.** Run the resolved script with `sync`, again from the project root. It pushes to and pulls from every host in `~/handoffs/peers`. An unreachable peer is reported, not fatal. If no peers are listed, tell the user the store is local only and how to add one.
6. **Reply** with the document path, the tree outcome, the sync outcome, and one line telling the user to run `pickup` in whatever session they open next.

## Document contract

Frontmatter first. The script and the `pickup` skill read these fields, so keep the keys exact. `agent` and `host` record where the document was written, which you know. Nothing records where it goes, which you do not.

```
---
project: <repo basename>
branch: <branch>
head: <short sha after the wip commit, if any>
remote: <origin url, or none>
tree: pushed | committed-not-pushed | dirty-left-in-place | clean
written: <UTC timestamp>
host: <hostname>
agent: <claude-code | codex | antigravity | other>
focus: <the argument, verbatim, or omit the key>
status: open
---
```

Then the body, in this order. Cut a section that would be empty, never pad one.

- **Goal.** What the next session is for, in two or three sentences. Lead with the outcome, not the history.
- **State.** Where things stand. One line per thread, each tagged like `recall` does: `[merged #N]`, `[open PR #N]`, `[in flight <branch>]`, `[verified, uncommitted]`, `[planned, not started]`.
- **Pickup.** The exact commands to get working, in a fenced block, written for a fresh clone on another machine: `cd` to the project by its name under the projects directory, `git fetch`, `git checkout <branch>`, `git pull --ff-only`. Then the checks to run first to confirm the tree is as described. A session on this machine runs the same block and the fetch and pull are no-ops, so there is no second version.
- **Decisions.** Choices already made, with the reason, so the next session does not reopen them.
- **Open questions.** Anything the user still has to decide, marked as such.
- **Do not.** Rules learned the hard way in this session that are not yet in CLAUDE.md or AGENTS.md.
- **Verify.** The commands that prove the work is done.
- **Suggested skills.** Skills the next session should load, by name, with one clause each on why. Name them plainly and never by one agent's invocation syntax, since every agent installs the same skill directories and each loads them its own way.
- **Sources.** PRs, issues, tickets, docs, and chat permalinks, each one line.

Nothing in the body may depend on the reader's agent or machine. No tool names that exist in only one agent, no absolute paths, no "on this machine" shortcuts.

## Peers

`~/handoffs/peers` holds one ssh host per line, resolved through `~/.ssh/config`. Sync is symmetric per peer, push then pull, so any machine that can reach any other machine keeps both current. A machine that cannot ssh out still receives whatever its peers push. Run the resolved script with `peers` to see who answers.

## Helper output

Run the resolved script with `--help`, or `<command> --help`, for usage. `latest` reports `status: found`, `project`, and `path`. An empty result reports `status: empty` and `0 open handoffs`, with exit 0. Add `--branch <branch>` to filter and include the branch in the report. Add `--all` to list every match, newest first by modification time. Add `--path` for shell callers that need paths only. In that mode, no match produces empty stdout and exit 1.

Invalid arguments exit 2 before any store changes or peer calls. Runtime failures exit 1. Sync retains its best-effort behavior and exits 2 if any peer is unreachable, including sync after `mark-resumed`.
