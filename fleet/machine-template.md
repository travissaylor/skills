# Machine template

Create `~/.config/fleet/` if it does not exist. Copy the contents of the fenced block below, without the fence, to `~/.config/fleet/<hostname>.md`, using the lowercase short hostname. Fill it in on the machine it describes, then copy the file to every other host. Keep the filled-in copy out of the repo. Replace each line in angle brackets and delete any section that does not apply.

```markdown
# <hostname>

<One line: what the machine is and how it runs T3 Code.> Last checked: <YYYY-MM-DD>.

## Identity

| Fact | Value |
|---|---|
| **Hostname** | `<hostname>` |
| **T3 environment id** | <from ~/.t3/userdata/environment-id> |
| **Tailscale** | <tailnet IP and MagicDNS name, from `tailscale status`> |
| **Linked environments** | <which T3 environments this host links, and the access level> |

## Hardware

- **Model**: <vendor and model>.
- **CPU**: <model, cores and threads, architecture>. Record instruction-set limits, such as no AVX, because prebuilt binaries crash on them.
- **RAM**: <size, plus swap>.
- **Disk**: <drives and volumes>.

## OS and shells

- **OS**: <name, version, build or kernel>.
- **Shells**: <which shell the Bash and PowerShell tools run, and any quoting traps>.
- **sudo or admin**: <what the user can run without a prompt. Agents still ask first.>

## T3 Code

- **Install**: <desktop app, user service, or other>.
- **Server**: <how it starts, the host and port, where server-runtime.json is>.
- **Network**: <how other devices reach it, such as Tailscale Serve or a tunnel>.
- **State and logs**: <T3CODE_HOME, settings.json, log paths>.
- **PATH**: <what PATH agent sessions inherit, and how to refresh it after an install>.

## Agent CLIs

| CLI | Path | Install method | Update |
|---|---|---|---|
| **claude** | | | |
| **codex** | | | |
| **agy** | | | |

## Toolchain

| Tool | Location | Install method |
|---|---|---|
| **node, npm** | | |
| **python, python3** | | |
| **uv, uvx** | | |
| **git, gh** | | |
| **make** | | |
| **rg, jq** | | |

## Skills

- **Repo**: <where ~/projects/skills is cloned, and over HTTPS or SSH>.
- **Links**: <how make install links skills on this OS>.
```

## Commands that collect the facts

| Fact | Linux | macOS | Windows (PowerShell) |
|---|---|---|---|
| Hostname | `hostname` | `hostname` | `hostname` |
| T3 environment id | `cat ~/.t3/userdata/environment-id` | `cat ~/.t3/userdata/environment-id` | `Get-Content ~/.t3/userdata/environment-id` |
| OS version | `cat /etc/os-release` | `sw_vers` | `Get-ComputerInfo OsName,OsBuildNumber` |
| CPU and flags | `lscpu` | `sysctl -n machdep.cpu.brand_string` | `Get-CimInstance Win32_Processor` |
| RAM | `free -h` | `sysctl -n hw.memsize` | `Get-CimInstance Win32_ComputerSystem` |
| Disk | `lsblk` | `df -h /` | `Get-Volume` |
| Tailnet | `tailscale status` | `tailscale status` | `tailscale status` |
