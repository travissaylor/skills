# macbook-pro-m2

Last checked: 2026-11-13. The machine was offline, so nothing here beyond the tailnet entry is verified.

## Known

- **Tailscale**: `macbook-pro-m2`, 100.110.217.81, macOS.
- **CPU**: Apple M2 according to the device name. That means arm64, so x86-only binaries need Rosetta. Verify with `sysctl -n machdep.cpu.brand_string` and `uname -m`.

## Fill in when it is next online

Collect the same sections the other machine files have, then replace this list:

1. OS version (`sw_vers`), RAM (`sysctl -n hw.memsize`), disk (`df -h /`).
2. How T3 Code runs: desktop app or a launchd service, the HTTP port from `~/.t3/userdata/server-runtime.json`, and the id in `~/.t3/userdata/environment-id`. Add the id to the table in `SKILL.md`.
3. Agent CLIs `claude`, `codex`, `agy`: path, version, install method.
4. Toolchain: node and its manager, python, uv, git, gh, rg, jq, pdftotext, Homebrew.
5. Whether `~/projects/skills` is cloned and linked with `make install`.
