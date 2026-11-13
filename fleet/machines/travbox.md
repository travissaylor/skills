# travbox

Always-on Ubuntu mini PC that runs T3 Code as a user service. Last checked: 2026-11-13.

## Identity

| Fact | Value |
|---|---|
| **Hostname** | `travbox` |
| **T3 environment id** | `d600146b-3da1-4488-b8ff-9bc5448a2c3f` |
| **Tailscale** | 100.87.243.95, MagicDNS `travbox.pipefish-smelt.ts.net` |
| **Reach it from hp-elitebook** | A T3 linked environment with auto access. SSH key auth is not set up. |

## Hardware

- **Model**: CHUWI HeroBox mini PC, bare metal.
- **CPU**: Intel Celeron J4125, 4 cores and 4 threads, x86-64.
- **RAM**: 8 GB, plus a 7.5 GB swap partition.
- **Disk**: one 256 GB Netac SATA SSD. `/` (including `/home`) is a 178 GB partition. An unmounted 51 GB partition is left over from Windows.

### No AVX on this CPU

The J4125 tops out at **SSE4.2**. It has `aes` and `sha_ni`, and it has **no AVX, AVX2 or AVX-512**. Any binary built for x86-64-v3 or higher dies with `Illegal instruction` (SIGILL). Known cases:

- **vite 8** and its native deps crash, so projects here pin **vite 7** and **@vitejs/plugin-react 5**.
- **T3's Antigravity provider** cannot run here, because its `antigravity-acp` server needs AVX. The standalone `agy` CLI does run.

When a prebuilt binary crashes with SIGILL, look for a baseline or `x86-64-v2` build, an older version, or build from source. Check flags with `grep -o -w 'avx2\?' /proc/cpuinfo | sort -u`.

## OS

- **OS**: Ubuntu Server 24.04 LTS (noble), kernel 6.8 generic.
- **sudo**: passwordless for the user. Ask the user before running sudo anyway.
- **Python packaging**: the system Python enforces PEP 668, so `pip install` into it fails with `externally-managed-environment`. Use `uv`, `pipx`, or a venv.

## T3 Code

- **Service**: the systemd user unit `t3code.service` in `~/.config/systemd/user/`. It is enabled, `Restart=always`, and linger is on, so it runs without a login.
- **Launch chain**: `ExecStart` points at `~/.t3/runtime/versions/0.1.3/t3 __service-launcher`. That launcher starts `t3 serve` from the newest version directory. Find the newest with:

  ```bash
  ls -d ~/.t3/runtime/versions/*/t3 | sort -V | tail -1
  ```

- **Network**: the drop-in `t3code.service.d/10-remote-access.conf` sets `T3CODE_HOST=127.0.0.1` and `T3CODE_PORT=3773`. Tailscale Serve proxies `https://travbox.pipefish-smelt.ts.net` (tailnet only) to that port. The service also runs a `cloudflared` tunnel from `~/.t3/tools/cloudflared`.
- **State**: `T3CODE_HOME` is `~/.t3`. Settings are in `~/.t3/userdata/settings.json`. The service log is `~/.t3/userdata/logs/boot-service.log`.
- **Sessions**: each agent session runs in its own systemd scope under `app-t3code-agents-*.slice`.
- **PATH**: the service process has the bare systemd PATH, but T3 gives agent sessions the login-shell PATH. Sessions see `~/.local/bin`, nvm's node and `~/.bun/bin` first. Restart the service (`systemctl --user restart t3code`) after changing shell profiles.
- **Logs and control**: `systemctl --user status t3code`, `journalctl --user -u t3code`.

## Agent CLIs

All three live in `~/.local/bin`, and none comes from npm.

| CLI | Install method | Update |
|---|---|---|
| **claude** | Native Claude Code installer. The link resolves to `~/.local/share/claude/versions/<version>`. | Self-updates |
| **codex** | Codex standalone installer. The link resolves to `~/.codex/packages/standalone/current`. | Standalone installer |
| **agy** | `curl -fsSL https://antigravity.google/cli/install.sh \| bash`. The binary is a single file, and its data is in `~/.gemini/antigravity-cli/`. | `agy update`, and it self-updates in the background |

## Toolchain

| Tool | Location | Install method |
|---|---|---|
| **node, npm, pnpm** | `~/.nvm/versions/node/<version>/bin` | nvm. v22 is the default and v26 is also installed. pnpm is an npm global. |
| **bun** | `~/.bun/bin` | bun installer |
| **python, python3** | `/usr/bin` | apt `python3` plus `python-is-python3` (3.12) |
| **pip, pip3, venv** | `/usr/bin` | apt `python3-pip`, `python3-venv` |
| **pipx** | `/usr/bin/pipx` | apt `pipx` |
| **uv, uvx** | `~/.local/bin` | Astral installer |
| **pdftotext** and other poppler tools | `/usr/bin` | apt `poppler-utils` |
| **rg** | `/usr/bin/rg` | apt `ripgrep` |
| **jq, git, make, gcc, curl** | `/usr/bin` | apt |
| **gh** | `/usr/bin/gh` | apt, from the `cli.github.com` repo |
| **docker** | `/usr/bin/docker` | apt, from Docker's repo |
| **tailscale** | `/usr/bin/tailscale` | apt, from Tailscale's repo |

`nvm` is a shell function from `~/.bashrc`, so a non-interactive shell does not have the `nvm` command. Node itself is on PATH.

## Skills

- **Repo**: `/home/travis/projects/skills`, cloned over SSH.
- **Links**: `make install` symlinks each skill into `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills` and `~/.gemini/skills`.
