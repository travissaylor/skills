# hp-elitebook

Windows 11 laptop that runs the T3 Code desktop app. Last checked: 2026-11-13.

## Identity

| Fact | Value |
|---|---|
| **Hostname** | `hp-elitebook` |
| **T3 environment id** | `b93fd775-11bf-48cf-bc2f-151659e60d58` |
| **Tailscale** | 100.98.92.60 |
| **Linked environments** | travbox, with auto access |

## Hardware

- **Model**: HP EliteBook 640 14 inch G11.
- **CPU**: Intel Core Ultra 7 165U, 12 cores and 14 threads, x86-64. It has **AVX and AVX2 but no AVX-512**, so prebuilt x86-64 binaries run here.
- **RAM**: 32 GB.
- **Disk**: one 512 GB Samsung NVMe SSD, a single `C:` volume.

## OS and shells

- **OS**: Windows 11 Pro 26H2, build 26300. WSL is not installed.
- **Bash tool** runs Git Bash. **PowerShell tool** runs Windows PowerShell 5.1 (`powershell.exe`).
- **PowerShell 7.7** (`pwsh`) is installed as an MSIX package from winget `Microsoft.PowerShell`. Its alias is `%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`. Prefer `pwsh -NoProfile -File script.ps1` for any script longer than one line.
- **Quoting traps** in 5.1 cause most shell errors here:
  - 5.1 has no `&&` or `||`. Run `A`, then `if ($?) { B }` on the next line.
  - A `powershell -Command "..."` string passed from Git Bash goes through bash first, so bash expands every `$_` and `$var` inside double quotes. Use the PowerShell tool, or single-quote the whole command.
  - `2>&1` on a native exe turns stderr lines into error records and sets `$?` to false.

## T3 Code

- **Install**: desktop app "T3 Code (Beta)", an Electron app installed per user at `%LOCALAPPDATA%\Programs\t3code`. It updates itself.
- **Server**: runs inside the app, not as a Windows service, so it is up only while the app is open. It listens on `127.0.0.1:3773`. `~/.t3/userdata/server-runtime.json` records the live port, PID and server version.
- **CLI**: `~/.t3/bin/t3.cmd` runs the app's bundled server CLI. `~/.t3/bin` is on the user PATH.
- **State**: `T3CODE_HOME` is `~/.t3`. Settings are in `~/.t3/userdata/settings.json`, and logs are in `~/.t3/userdata/logs`.
- **Managed tools**: T3 downloads its own copies into `~/.t3/tools`: `codex`, `antigravity-acp`, `cloudflared` and `chrome-headless-shell`. The T3 Codex provider uses the managed `codex` (`setupMode: managed`). The T3 Claude provider uses `~/.local/bin/claude.exe` (`binaryPath` in settings). These copies are not on PATH and are separate from the CLIs below.
- **Stale PATH**: agent sessions inherit the PATH the app had at launch. **Fully quit and relaunch T3 after installing a tool.** In a session that predates an install, reload PATH from the registry:

  ```powershell
  $env:Path = @([Environment]::GetEnvironmentVariable('Path','Machine'), [Environment]::GetEnvironmentVariable('Path','User')) -join [IO.Path]::PathSeparator
  ```

## Agent CLIs

| CLI | Path | Install method | Update |
|---|---|---|---|
| **claude** | `~/.local/bin/claude.exe` | Native Claude Code installer | Self-updates |
| **codex** | `%LOCALAPPDATA%\mise\shims\codex.exe` | `npm install -g @openai/codex` under mise node | Reinstall after mise switches node versions, then `mise reshim` |
| **agy** | `%LOCALAPPDATA%\agy\bin\agy.exe` | `irm https://antigravity.google/cli/install.ps1 \| iex` | Self-updates in the background |

agy signs in through the browser on first run and stores the session in Windows Credential Manager.

## Toolchain

Every tool below is installed per user, so none needs admin rights.

| Tool | Location | Install method |
|---|---|---|
| **node, npm** | `%LOCALAPPDATA%\mise\shims` | mise, `node = "lts"` in `~/.config/mise/config.toml` |
| **mise** | `%LOCALAPPDATA%\Microsoft\WinGet\Packages\jdx.mise_*` | winget `jdx.mise` |
| **python, python3, pip** | `%LOCALAPPDATA%\Programs\Python\Python312` | winget `Python.Python.3.12` (3.12) |
| **py** launcher | `%LOCALAPPDATA%\Programs\Python\Launcher` | Comes with Python |
| **uv, uvx** | `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*` | winget `astral-sh.uv` |
| **git** | `C:\Program Files\Git` | Git for Windows. Global `user.name` and `user.email` are set. |
| **gh** | `C:\Program Files\GitHub CLI` | GitHub CLI installer |
| **rg** | WinGet package dir | winget `BurntSushi.ripgrep.MSVC` |
| **jq** | WinGet package dir | winget `jqlang.jq` |
| **pdftotext** and other poppler tools | WinGet package dir | winget `oschwartz10612.Poppler` |
| **tailscale** | `C:\Program Files\Tailscale` | Tailscale installer |

`python3.exe` is a copy of `python.exe` in the Python312 folder. The python.org installer ships no `python3.exe`, so without the copy `python3` resolves to the Microsoft Store stub in `WindowsApps`. A Python upgrade needs the copy again.

## Skills

- **Repo**: `~/projects/skills`, cloned over HTTPS.
- **Links**: each skill is a directory junction from `~/.claude/skills`, `~/.codex/skills` and `~/.agents/skills` into the repo.
