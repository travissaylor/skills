# Skill linter

`tools/lint_skills.py` checks every skill in this repo for structural defects and prose defects. It exists because `claude plugin validate . --strict` passes this repo while catching almost nothing: it accepts a skill whose `name` disagrees with its directory, whose links point at missing files, and whose body is full of em dashes and semicolons.

The linter is a static check. It reads files, matches patterns, and prints findings. It makes no model calls and reaches no network.

## Run it

| Command | What it does |
|---|---|
| `make lint` | Prints the full backlog, no baseline filtering. Use it to see the real state. |
| `make lint-ci` | Prints only findings beyond the baseline. This is the commit gate and the CI gate. |
| `make test` | Runs the linter test suite, 60 tests. |
| `make baseline` | Rewrites `tools/lint_baseline.json` from current findings. Run it after a deliberate fix. |
| `make install-hooks` | Points `core.hooksPath` at `.githooks` and marks the pre-commit hook runnable. |
| `make check` | Compile check, then `make test`, then `make lint-ci`. Run it before pushing. |

`make check` is the default target, so bare `make` runs it.

`make lint` exits 1 whenever it finds an error, which it does today, so `make` reports it as a failed target. That is expected. `make lint-ci` is the target that should pass.

Every target is a one line wrapper. The underlying command is `python3 tools/lint_skills.py` with flags.

## What it scans

Skills are every immediate subdirectory of the repo root that holds a `SKILL.md`, skipping dotted directories and `tools`. Prose checks run over every markdown file in the repo, skipping dotted directories, `tools`, and `node_modules`. That is 9 files today: the root `README.md`, seven `SKILL.md` files, and `improve-codebase-architecture/REFERENCE.md`.

Prose checks run on a masked view of each file. Fenced code blocks, blockquotes, inline code spans, and URLs are blanked out first, with line numbers and character offsets preserved. A semicolon inside a code sample is not a finding.

## Flags

    python3 tools/lint_skills.py [PATH] [options]

| Flag | Behavior |
|---|---|
| `PATH` | Repo root to lint. Defaults to the repo holding the script. |
| `--baseline FILE` | Suppress up to the per-key count recorded in FILE. Report the rest. |
| `--write-baseline FILE` | Write current findings to FILE as a baseline, then exit 0. |
| `--format {text,json}` | Output format. `text` is grouped by file, `json` is a flat list of finding objects. |
| `--warnings-as-errors` | Let warnings drive the exit code alongside errors. |
| `--max-words N` | Body word budget for the SK102 check. Default 5000. |
| `--check-installed` | Also emit SK106 for a skill missing a symlink in `~/.claude/skills`. |
| `--only CODES` | Comma-separated finding codes. Report only these. |
| `--quiet` | Print only the summary line. |
| `--timing` | Print elapsed run time to stderr. |

Text output is one line per finding, `path:line: LEVEL CODE message`, sorted by path then line then code. The last line is always the summary, `N errors, M warnings across K files`, where K counts the markdown files scanned, not the files with findings.

Exit codes: `0` clean, `1` findings, `2` bad usage or internal error.

## Finding codes

Codes are frozen. A new check gets a new code, and a retired check leaves its number unused.

### Structure errors

| Code | What it catches |
|---|---|
| SK001 | Frontmatter failed to parse. |
| SK002 | `name` is missing, is not a string, is not kebab-case, or runs over 64 characters. |
| SK003 | `name` does not equal the directory name. |
| SK004 | `description` is missing or is not a string. |
| SK005 | `description` is shorter than 40 characters or longer than 1024. |
| SK006 | A markdown link points at a local file that does not resolve. |
| SK007 | A backticked path-like token points at a file that does not resolve. |
| SK008 | A backticked or bolded cross-skill name has no sibling skill directory. |
| SK009 | A banned pattern: a foreign dotted directory such as `.william/`, a hardcoded `/Users/<name>/` path, or a leftover `TODO` or `FIXME`. |
| SK010 | No skills were discovered under the root. This guards against a linter that silently checks nothing. |

### Structure warnings

| Code | What it catches |
|---|---|
| SK101 | A frontmatter key outside the known set. |
| SK102 | The skill body runs over the word budget set by `--max-words`. |
| SK103 | Two descriptions are more than 60 percent similar, so routing between them is a coin flip. |
| SK104 | A bundled file in the skill directory is never referenced from `SKILL.md`. |
| SK105 | `disable-model-invocation: true` while the description still reads like auto-trigger phrasing, so those phrases can never fire. |
| SK106 | The skill has no entry in `~/.claude/skills`, so it is never dogfooded. Emitted only under `--check-installed`. It depends on one machine's home directory, so it never runs in CI. |

### Prose errors

| Code | What it catches |
|---|---|
| SK201 | An em dash. Use a period or a comma. |
| SK202 | An en dash used as a dash. A numeric range such as `1–5` is allowed. |
| SK203 | A semicolon. Use a period. HTML entities are masked, so `&amp;` is not a hit. |
| SK204 | A plural formed with `(s)`. Write the plural out. |
| SK205 | A slash construction such as `and/or`. Write "a, b, or both". |
| SK208 | A decorative emoji in a heading or a bullet. Arrows are treated as punctuation and allowed. |
| SK209 | A curly quote. Use a straight quote. |

### Prose warnings

| Code | What it catches |
|---|---|
| SK206 | A title-case heading. Two or more capitalized non-proper nouns that are not sentence-initial count as evidence. |
| SK207 | AI vocabulary such as "delve", "crucial", "tapestry". |
| SK210 | A filler phrase such as "in order to" or "it is important to note that". |
| SK211 | Two or more hedges stacked on one line, such as "could potentially". |
| SK212 | An abstract metaphor noun such as "substrate", "flywheel", "north star". |
| SK213 | A fancy word with a plain replacement, such as "utilize" for "use". |

## The baseline

This repo has real findings today: 94 errors and 6 warnings, mostly 53 em dashes and 35 semicolons across the seven skills and the README. Those are genuine defects, and fixing them is a separate job from shipping the linter.

Without a baseline the pre-commit hook would block every commit in the repo from the day it was installed. A hook that always fails gets deleted within a week, and then nothing is checked at all. The baseline records what is already broken so the gate only fires on what a commit adds.

The file is `tools/lint_baseline.json`:

```json
{
  "version": 2,
  "counts": {
    "SK201\tREADME.md\tem dash, use a period or a comma": 7
  }
}
```

Two properties matter:

**Keys carry no line number.** A key is `code`, `path`, and `message`, tab separated. Editing an unrelated paragraph shifts every line below it. If keys held line numbers, that edit would churn the whole baseline and bury the one finding that matters. Without them, the baseline stays still.

**Matching is by count, not by presence.** The baseline allows 7 em dashes in `README.md`. An 8th is reported and fails the gate, even though an em dash in `README.md` is already a recorded violation. Presence matching would let a file accumulate unlimited new copies of a defect it already had.

When the baseline filters a key, it skips the lowest line numbers first, so the findings it does report carry real line numbers you can jump to.

After a deliberate fix, run `make baseline` and commit the regenerated file in the same change. The version field is checked on load. A baseline written by an older linter is rejected with an error telling you to regenerate it, rather than being silently misread.

## Suppression directives

Two HTML comments turn off checks in a file:

```
<!-- lint-skip-file: SK207,SK212 -->
<!-- lint-skip-next-line: SK205 -->
```

`lint-skip-file` may appear anywhere in the file and applies to the whole file. `lint-skip-next-line` applies to the line that follows it. The token `all` suppresses every code.

**The rule: suppress a check only when the file is a legitimate exception, never to hide a defect.**

Three skills carry file-wide suppressions today. `prose`, `unslop`, and `technical-writing` are dictionaries of banned words. They must quote "delve" and "utilize" and "flywheel" to teach an agent to avoid them, so every vocabulary check fires on every rule they define. Each of those three carries:

```
<!-- lint-skip-file: SK207,SK210,SK211,SK212,SK213 -->
```

That list is the word-list codes and nothing else. The punctuation codes SK201 through SK205 are never suppressed this way, in these files or any other. A rule-source file has no reason to contain a real em dash or a real semicolon, and those codes are exactly the backlog the linter exists to report. Suppressing them would make the tool agree with itself while the defects stay.

`technical-writing/SKILL.md` also carries one `lint-skip-next-line: SK205`, on the line where the no-slashes rule quotes `a/b` as the example of what not to write.

## Known gaps

Four defects in the acceptance corpus cannot be caught by static analysis. They are recorded in `tools/fixtures/known_gaps.json` and held under test in `KnownGapsTest`, so the gap is visible instead of forgotten:

| Gap | The defect | What would catch it |
|---|---|---|
| `defect-1-nonexistent-tools` | `conductor/SKILL.md:41` tells the agent to track progress with `TaskCreate` and `TaskUpdate`. Neither tool exists, so the step silently drops on every run. | A registry of valid tool names refreshed from the runtime, plus a check that every tool-looking token resolves against it. |
| `defect-3-half-finished-rfc-conversion` | `improve-codebase-architecture` is half converted from GitHub issue RFCs to Markdown file RFCs. The opening promises issues, the step body writes a file, and `REFERENCE.md` still ships an issue template. | Semantic contradiction detection across a skill and its bundled files, most likely model graded. |
| `defect-5-routing-bypass` | `recall/SKILL.md:33` sends the agent straight to `unslop`, while `prose` states that it is the entry point and the deep passes must not be loaded ahead of it. | The planned `routes-to` frontmatter key, which turns the routing claim into data the linter can check both ways. |
| `defect-6-cross-skill-self-modification` | `technical-writing/SKILL.md:21` instructs the agent to edit another skill's rule list. That is unbounded cross-skill self-modification with no guard on what may be written. | A policy check over write targets, driven by a declared per-skill write scope in frontmatter. |

Each entry states the path, the anchor text, why the linter cannot reach it, and what would. The test suite asserts the anchors still appear at those paths, so a gap entry cannot rot into a stale claim about a file that changed.

## Zero dependencies

The linter imports Python 3 standard library only, and it will stay that way.

It runs inside a pre-commit hook, which means it runs on every developer's machine on every commit. A hook that needs `pip install` fails on the first machine with a different Python, a stale virtualenv, or no network. A hook that fails on a commit that is fine gets disabled, and once it is disabled nobody turns it back on.

The tradeoff is real. There is no YAML parser, so `core.parse_frontmatter` handles only the subset these files use: `key: value` lines with optional quotes, plus inline `[a, b]` lists. Anything else is an SK001 error rather than a silent misparse. That is the correct failure for a check whose job is to be trusted.

## Layout

    tools/lint_skills.py              entry point, fixes sys.path and calls cli.main
    tools/skill_lint/core.py          Finding, Skill, frontmatter parsing, masking, suppressions
    tools/skill_lint/checks_structure.py  SK001 to SK010, SK101 to SK106
    tools/skill_lint/checks_prose.py  SK201 to SK213
    tools/skill_lint/cli.py           flags, output formatting, baseline, exit codes
    tools/test_skill_lint.py          the test suite
    tools/fixtures/cases/             per-check fixture skills
    tools/fixtures/known_gaps.json    the four non-checkable defects
    tools/lint_baseline.json          recorded counts of existing findings

Check modules return `list[Finding]`. They never print, never exit, and never write files. All output and all exit-code logic lives in `cli.py`.
