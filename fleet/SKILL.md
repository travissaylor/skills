---
name: fleet
description: Reference for the user's machines (hp-elitebook on Windows 11, travbox on Ubuntu, macbook-pro-m2 on macOS, iphone182 on iOS). Covers OS, CPU instruction-set limits, RAM, disk, how T3 Code is installed and run, T3 environment ids, agent CLIs (claude, codex, agy), and toolchain paths. Read it before probing a machine for facts, installing tools, debugging "Illegal instruction" crashes or PATH problems, or delegating work to another machine.
---

# Fleet

The user runs T3 Code on several machines. Facts about each one are written down so agents stop rediscovering them. This skill holds the rules and the file layout. The facts themselves live in local files outside the repo, because they include network addresses, environment ids and host setup that do not belong in a public repo.

## Find the machine files

The machine files are in `~/.config/fleet/`, one per host, named `<hostname>.md` in lowercase. Each host keeps a copy of every machine's file, so an agent can read about a machine it is about to delegate to.

1. Run `hostname` and lowercase the result. Windows reports `HP-EliteBook`, which maps to `hp-elitebook.md`.
2. Read `~/.config/fleet/<hostname>.md` for the machine you are on.
3. Before delegating, read the file for the target machine too.

| Machine | Role | OS | Local file |
|---|---|---|---|
| **hp-elitebook** | T3 host, daily laptop | Windows 11 Pro | `~/.config/fleet/hp-elitebook.md` |
| **travbox** | T3 host, always-on server | Ubuntu Server 24.04 | `~/.config/fleet/travbox.md` |
| **macbook-pro-m2** | T3 host, often offline | macOS | `~/.config/fleet/macbook-pro-m2.md` |
| **iphone182** | T3 client only | iOS | none, it hosts nothing |

The T3 environment id of the machine you are on is also in `~/.t3/userdata/environment-id`.

**If a file is missing**, say so, then ask the user to copy it from another host. If the machine is new, copy [machine-template.md](machine-template.md) to `~/.config/fleet/<hostname>.md` and fill it in from the machine itself.

## Rules that hold on every machine

- **Reach another machine through T3**, not SSH. Pass the target's environment id from its machine file as `target.environmentId` to `delegate_task`, and pass a `target.projectId` from `t3_project_list` on that machine.
- **The skills repo** is `github.com/travissaylor/skills`, cloned to `~/projects/skills` on each host. `make install` links every skill into `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills` and `~/.gemini/skills`. Pull, then rerun `make install` after a new skill lands.
- **This skill is linked from `~/projects/skills-main`**, a worktree of the skills repo that tracks the main branch, so it stays installed while `~/projects/skills` is on a feature branch. Refresh it with `git -C ~/projects/skills-main pull`.
- **Global instruction files** `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` on each host only name the machine and point here. Keep facts in the machine files, not in those files.
- **Install missing tools** instead of working around them. Then update the machine's file, so the next agent does not rediscover the gap.
- **Record facts that stay true**: hardware limits, install methods, where things live. Leave out transient state such as free disk space or running PIDs.

## Update a machine file

Edit `~/.config/fleet/<hostname>.md` and update the date in its header. A machine that is offline keeps its last verified facts. Then copy the changed file to the other hosts, or commit and push if `~/.config/fleet` is a git repo, so every host reads the same facts.

Never copy a machine file into this repo. The repo is public. Change [machine-template.md](machine-template.md) or this file only for structure that applies to every machine, then run `make check` from the repo root, commit on a branch, and open a PR.
