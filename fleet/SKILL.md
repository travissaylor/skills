---
name: fleet
description: Reference for the user's machines (hp-elitebook on Windows 11, travbox on Ubuntu, macbook-pro-m2 on macOS, iphone182 on iOS). Covers OS, CPU instruction-set limits, RAM, disk, how T3 Code is installed and run, T3 environment ids, agent CLIs (claude, codex, agy), and toolchain paths. Read it before probing a machine for facts, installing tools, debugging "Illegal instruction" crashes or PATH problems, or delegating work to another machine.
---

# Fleet

The user runs T3 Code on several machines. Facts about each one live here so agents stop rediscovering them. Read the file for the machine you are on, and the file for any machine you delegate to.

## Find the current machine

Run `hostname`. The name matches a row below and a file in `machines/`.

| Machine | Role | OS | T3 environment id | File |
|---|---|---|---|---|
| **hp-elitebook** | T3 host, daily laptop | Windows 11 Pro | `b93fd775-11bf-48cf-bc2f-151659e60d58` | [machines/hp-elitebook.md](machines/hp-elitebook.md) |
| **travbox** | T3 host, always-on server | Ubuntu Server 24.04 | `d600146b-3da1-4488-b8ff-9bc5448a2c3f` | [machines/travbox.md](machines/travbox.md) |
| **macbook-pro-m2** | T3 host, often offline | macOS | not recorded yet | [machines/macbook-pro-m2.md](machines/macbook-pro-m2.md) |
| **iphone182** | T3 client only | iOS | none, it hosts nothing | none |

All four are on the same Tailscale tailnet. The T3 environment id of the machine you are on is in `~/.t3/userdata/environment-id`.

## Rules that hold on every machine

- **Reach another machine through T3**, not SSH. hp-elitebook links travbox with auto access. Pass the environment id as `target.environmentId` to `delegate_task`, and pass a `target.projectId` from `t3_project_list` on that machine. SSH key auth between machines is not set up.
- **The skills repo** is `github.com/travissaylor/skills`, cloned to `~/projects/skills` on each host. `make install` links every skill into `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills` and `~/.gemini/skills`. Pull, then rerun `make install` after a new skill lands.
- **This skill is linked from `~/projects/skills-main`**, a worktree of the skills repo that tracks the main branch, so it stays installed while `~/projects/skills` is on a feature branch. Refresh it with `git -C ~/projects/skills-main pull`.
- **Global instruction files** `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` on each host only name the machine and point here. Keep facts in this skill, not in those files.
- **Install missing tools** instead of working around them. Then update the machine's file here and commit, so the next agent does not rediscover the gap.
- **Record facts that stay true**: hardware limits, install methods, where things live. Leave out transient state such as free disk space or running PIDs.

## Update this reference

Edit the machine file, run `make check` from the repo root, commit on a branch, and open a PR. A machine that is offline keeps its last verified facts, with the check date in its header.
