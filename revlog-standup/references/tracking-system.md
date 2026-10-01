# Tracking System doc, local mirror

Mirror of Notion page `3c6059d49d6581d8b303e42018f7713c` ("Tracking System"), the sections the daily loop needs. **Mirrored 2026-09-28 from page_last_edited_at 2026-09-16T16:21Z. Newest changelog entry 2026-09-16.** Read this instead of fetching the page. Re-fetch and update this file only when: it is Monday, Travis says the process changed, or a source shows a process contradiction. When re-fetching, update the two dates above and the changelog tail below.

## Evidence ladder (position from evidence, with status and Jira)
| Evidence | Position | Status | Jira |
|---|---|---|---|
| Row exists, approach picked | 10 | Approach chosen | Ready |
| Work started (Started date set) | 10–30 | Approach chosen | In Progress |
| Core path works end to end locally | 35 | Risks validated | In Progress |
| Nothing left to learn, only build | 50 | No unknowns | In Progress |
| PR up, CI green | 60 | Over the hill | Code Review (automatic on PR tag) |
| Merged to main, not yet promoted | 80 | Over the hill | Test (automatic on merge) |
| Prod deploy sha includes the merge | 90 | Over the hill | Test |
| UAT session with product or design held (UAT date set) | 95 | Over the hill | Test |
| UAT follow-ups deployed, or sign-off with none | 100 | Done | Done |

Statuses: Approach chosen, Risks validated, No unknowns, Over the hill, Done, Cut → Q4, Blocked (park the project and do not start the next scope). Position 0–100, 50 = crest. Skill proposes from the ladder. Travis overrides in the plan step. Travis's 9/14 rule for Compare from the Log: not over the hill until the model PR is merged. PR-up alone does not earn 60 for that scope.

## Computed lines
- **Progress** (per active scope): expected = working days since Started ÷ Size (days), capped at 100. Actual = hill position. Ahead = actual ≥ expected + 15. Behind = actual ≤ expected − 15. On Track between. Two active scopes → report the worse one.
- **Overall**: remaining = Σ Size × (1 − position/100) over not-Done, not-Cut scopes. slack = working days before the last Due date − remaining. On Track: slack ≥ 0. At Risk: slack < 0 down to 5 days short. Behind: ≥ 5 working days short. Committed P&E dates never change without Daniel.
- Implementation: `scripts/progress.mjs scopes.json [YYYY-MM-DD]`.

## Daily loop (the 8 steps)
1. **Gather.** Window = newest Daily → now (warn if Slack has a newer standup). Sources: commits and branches. PRs with review + CI state. Prod deploy sha per merged PR. Jira transitions on the epic's children. Hill Moves vs Scope Tracker. Slack (project channel, DMs, related threads). Notion meeting notes in window (Meetings relation, then search). Claude sessions. Transcripts are mined by subagents that return findings only.
2. **Gate: scope change.** Any source shows work with no tracker row, or a scope ending or reshaping → stop, run the Scope change loop first.
3. **Gate: hand edits.** Row position ≠ last ledger entry → propose the missing ledger rows. Nothing written until confirmed.
4. **Gate: one scope at a time.** Before apply, count active scopes (Started set, not Done or Cut). More than one is a warning, except a scope at 90 whose only remaining work is the UAT session (scheduled or not). Warning names the scope to finish (lowest Sequence) and proposes pausing the other (Notes line "paused <date> to finish <scope>", said in the Daily). Travis can override.
5. **Plan.** One message: evidence, proposed moves (ladder rung + why), Jira transitions, Daily body. Iterate until **apply**.
6. **Apply.** Scope Tracker rows (Status, Hill position, Last moved. Started on first move. UAT when a session happened), Hill Moves rows, chart regenerated + swapped, Daily with Posted to = Notion only, Jira pushed forward only.
7. **Draft.** Standup in Travis's format per Reporting voice. Today = yesterday's unfinished Today items + branch state. Iterate until **post**.
8. **Post.** Send to #project-drawing-log. Daily flips to Posted to = Slack standup + permalink. No **post** → Daily stays Notion only.

**Reruns:** same-day Daily exists → say so up front, still run every step. Re-apply needs **apply again** (no duplicate ledger rows). Re-post needs **post again** and goes out as a threaded correction.

## Scope change loop
1. Same day, terminal Hill Moves row for the old scope (Done, Cut → Q4, or folded) with the why.
2. Create or re-parent the new scope at Approach chosen, position 10, placeholder done-when, "unshaped" note. Create its Jira story under the epic and set the row's Jira property.
3. Sub-scopes follow the parent. Absorbed rows leave the tracker as child pages of the absorber.
4. Daily names the change in its first line. Weekly carries a "Cuts / reshapes" line.
5. Regenerate the chart.

## Reporting voice (Daniel 1:1, 2026-09-01)
Track in Shape Up terms, report in business terms. Lead with "Completed since last check-in." No hill %, no Shape Up vocabulary outside the tracker. Every update answers "is it going to land?" with milestone status. Confidence and results, not risks. If confidence is genuinely low, say so with the exact plan. Percentages are a self-check (de-risked ≈ 70%, merged + prod-verified ≈ 80–90%).

## Conventions
Scope Tracker is the only source of truth. The chart is a rendering. Jira mirrors one way. Spikes are tasks on the scope they inform. Cut items keep status Cut → Q4 and stay in the tracker. Folded items leave as child pages with a terminal ledger row. One scope in progress (UAT-wait exception above). Standups link Notion scope pages, not Jira. The original Scopes doc is frozen.

## Changelog tail (newest first, as mirrored)
- 2026-09-16: One-scope gate exception widened. A scope at 90 waiting only on UAT no longer counts as active, booked or not.
- 2026-09-10: Overall thresholds. At Risk = more work than days. Behind = ≥ 5 days short.
- 2026-09-10: Scope Tracker gained Jira property, one-scope gate, apply again / post again, --dry-run.
- 2026-09-10: Process rewritten around /revlog-standup. Evidence ladder with UAT rungs, computed lines, Jira one-way mirror.
- 2026-09-01: Reporting voice codified.
