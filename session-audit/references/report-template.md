# Session audit report template

Write the report to `$REPORTS/session-audit-<YYYY-MM-DD>.md` and paste the same content in chat. Keep the section order fixed so audits compare across runs.

```
# Session audit: <from> to <to>

Corpus: N sessions, N prompts, N tool calls, $N recorded cost (cost-state present in K/N sessions). <If last_run is >25 days back: "Sessions before <date> were already auto-deleted.">
Method: distiller v2 → M digests + E episode files. A Sonnet miners (T tokens total). F findings raised, V quote-verified, L survived the live check.

## Did the last fixes hold
| Fix | Metric (per session) | Baseline → now | Verdict |
(copied from the stats.md "Trend" block. A NOT HOLDING row goes to "Do today".)

## Do today (each verified live)
1. <fix>. <evidence: sessions, count from stats.md>. Check: `<command you ran>` → <what it showed>.

## Skills that misfired
| Skill | Runs / sessions | Errors, steers, interrupts | Friction type | Root cause | Fix |

## Token sinks
| Pattern | Evidence (count from stats.md, session ids) | Fix |

## Deterministic tooling (zero LLM), ranked by sessions that reinvented it
1. <script name + args>. <what it replaces, N sessions>.

## Skill candidates
- <name>: <workflow shape>, <N sessions>.

## Dropped
- <finding>: <why: unsupported quote / already handled (name the file) / refuted by `<command>`>

## Carried over (still shelved)
- <item> (shelved <date>, recurred in N sessions this window, or "not seen")
```

Rules:
- Every count comes from `stats.md` or `signals.json`, never from a miner.
- Every item lists session ids, and every "do today" item lists the live check that confirmed it.
- No effort estimates.
- The "Dropped" section is required. It shows the verification did work, and it is what keeps a wrong item from resurfacing next run.
