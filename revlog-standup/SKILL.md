---
name: revlog-standup
description: Daily standup loop for the Drawing Revision Log project. Gathers evidence since the last check-in (git, PRs, prod deploy sha, Jira, Slack, Notion meetings, Claude sessions), proposes Scope Tracker moves and a Daily entry for approval ("apply"), then drafts the Slack standup in Travis's format for approval ("post"). Use when Travis says /revlog-standup, "standup", "daily update", or wants the revision log tracker updated. Accepts --dry-run.
argument-hint: "[--dry-run]"
---

# /revlog-standup

The Tracking System doc (`3c6059d49d6581d8b303e42018f7713c`, https://app.notion.com/p/3c6059d49d6581d8b303e42018f7713c) is the process of record. This skill executes its **Daily standup** loop. If the doc and this file disagree, the doc wins. Fix the skill and log it in the doc's changelog.

Read `references/ids.md` first for every identifier and property name. Read `references/standup-format.md` before drafting. Confirm words gate all writes: **apply** (Notion + Jira) and **post** (Slack). On a rerun they become **apply again** and **post again**. Anything else is conversation.

**`--dry-run`**: run every step below, produce the plan and the standup draft, and write nothing. No Notion, no Jira, no chart swap, no Slack. Say "DRY RUN" at the top of every message. Where a step says "write", print what would be written instead.

## 0. Orient

1. Read `references/tracking-system.md` (local mirror of the Tracking System doc: ladder, computed lines, gates, voice). Do **not** fetch the Notion page on an ordinary run. It is about 40k chars. Fetch it and refresh the mirror only on Mondays, when Travis says the process changed, or when evidence contradicts the mirror. Do not paraphrase the process back to Travis.
2. Query the three data sources (SQL mode): Scope Tracker (all rows, all properties, where the `Jira` url property is the scope to story mapping), Updates (newest 3 Daily rows, with `Posted to` and `Slack permalink`), Hill Moves (rows dated on or after the newest Daily minus 1 day).
3. **Window** = newest Daily's Date → now. Read the Slack channel (`slack_read_channel`, `C0AKM3X5X7A`, limit 30) and find Travis's newest standup. If it is newer than the newest Daily, warn: "Slack has a standup on X with no Daily. I'll include that gap in the window."
4. **Rerun detection.** If today already has a Daily, open with a banner: "Today's tracking was already applied at <time>" and, if `Posted to` includes Slack standup or a permalink exists, "and the standup was already posted: <permalink>". Still run every step. The window for a rerun is the previous Daily → now, so today's earlier evidence is re-evaluated, and proposed moves are diffed against ledger rows already dated today.

## 1. Gather

Run in parallel where possible. Keep raw output out of the conversation. Summarize.

- **Git / PRs**: run `git fetch origin main`, then `git log origin/main --since=<window start> --author=Travis --format='%h %ad %s' --date=short`, then `gh pr list --author @me --state all --search "updated:>=<window start>" --json number,title,state,mergedAt,mergeCommit,headRefName,reviewDecision,statusCheckRollup`, then `git for-each-ref --sort=-committerdate refs/heads` for local branches touched in the window. For each active branch run `git rev-list --count origin/main..<branch>` and check whether it exists on origin.
- **Prod deploy**: `scripts/prod-deploy-sha.sh <merge commits of PRs merged in window or still below 90>`. "Deployed" for both services is the 90 rung.
- **Jira**: `searchJiraIssuesUsingJql` with `parent = TXT-8416 ORDER BY key`, fields summary,status,duedate,updated. Match stories to rows through the row's `Jira` property. Note stories whose status moved in the window and any status behind the tracker (ladder mapping in ids.md). A row with an empty `Jira` property is itself a finding: propose creating the story.
- **Ledger vs tracker**: for each Scope Tracker row, compare Hill position and Status to its newest Hill Moves row. A mismatch is a hand edit → the step 3 gate.
- **Slack**: the channel read from step 0 (all messages in window, including replies to Travis's standups. Use `slack_read_thread` on any with replies). `slack_search_public_and_private` **twice, not three times**: `("revision log" OR "drawing log") after:<window start>` (one call. Results over about 40k chars mean the window is too wide, so narrow with `in:#project-drawing-log` before reading), and `from:<@U08FMLUHYJ2> after:<window start>` in DMs (`channel_types: im,mpim`). Skip `slack_read_thread` on threads whose parent is already in the window results. Decisions from Greg, Nick, Daniel, Jason count as evidence.
- **Notion meetings**: query the Meetings relation via the data-source query already run in step 2 where possible. Fetch the project page only if the relation is not in that result. Never re-fetch a meeting note whose last_edited is older than the newest Daily. Run `notion-search` (`query_type: internal`, `sort: last_edited`) for "revision log" and "drawing log" limited to the window, and include the Daniel 1:1 if it falls in the window. Hand the list to a Sonnet subagent (`model: sonnet`) per `references/session-mining.md` (meeting section). Do not read transcripts yourself. Skip the spawn when no meeting falls in the window.
- **Claude sessions**: `scripts/recent-sessions.sh "<window start>"` → one Sonnet subagent (`model: sonnet`) per `references/session-mining.md`. Do not read the JSONL yourself. Skip the spawn entirely when the file list is empty.

## 2. Gate: scope change (hard stop)

Trigger when any source shows: work on something with no Scope Tracker row, a scope ended, split, merged, or reshaped, or a transcript decision that changes what a scope is. If triggered:

1. Say so in one paragraph: what changed, which rows, which evidence.
2. Propose the **Scope change** loop from the doc as a concrete plan: terminal Hill Moves rows for the old scopes (Done / Cut → Q4 / folded, with why), new or re-parented rows at Approach chosen, position 10, placeholder done-when body, Notes marking it unshaped, a Jira story under TXT-8416 (ids.md) with its url written to the row's `Jira` property. New stories sit in Backlog until Component, Team, Story Points, and Description are set. Say so.
3. Stop. Write nothing else until Travis says **apply** to this plan (dry-run: print the plan and continue as if applied). Then continue with the tracker now matching reality.

## 3. Gate: hand edits

If a row's position or status differs from its newest ledger row, list the differences and propose the missing Hill Moves rows (date = row's Last moved, why drafted from the evidence). Wait for **apply** before writing them. This plan can be folded into the step 5 plan if Travis prefers. Ask in one line.

## 4. Gate: one scope at a time (warning)

After the proposed moves are drafted, count scopes that would be **active**: `Started` set, status not Done or Cut → Q4. Exclude any scope at position 90 with no `UAT` date whose only remaining work is the UAT session, scheduled or not (doc changelog 2026-09-16). If more than one remains:

- Name the scope to finish: lowest `Sequence` among them.
- Propose putting the others down: position unchanged, Notes gets "paused <date> to finish <scope>", and the Daily's first line says so.
- Print this as a **WIP warning** block inside the plan. Travis can accept the pause (it becomes part of apply) or override with a one-line reason, which goes into the Daily.

## 5. Plan

One message, in this order:

1. **Evidence**: 4–8 bullets, one per finding that matters. Cite the source type (PR #, Slack, meeting, session).
2. **Proposed moves**: a table: Scope · From → To (position, status) · Ladder rung · Why (one sentence, the future Hill Moves title). Include Started and UAT date sets. A day with no moves says so and proposes a "held" Daily.
3. **WIP warning**: from gate 4, or "one scope active: <name>".
4. **Jira**: transitions to push (forward only, skipping ones the PR automation already made), and any story to create.
5. **Daily body**: the Notion entry as it will be written. The first line names any scope change or pause. Then what happened in hill terms, decisions, blockers, next. 80–200 words. Title `Daily <dash> <Weekday M/D>: <hook>`, where `<dash>` is a real em dash character, matching the existing Daily titles.
6. Ask: "Say **apply**, or tell me what to change." On a rerun ask instead: "Today's tracking was already applied. Are you sure you want to update it? Say **apply again**, or tell me what to change." Dry-run: "DRY RUN, nothing will be written. Continue to the standup draft?"

Iterate until the confirm word.

## 6. Apply

Skipped entirely in dry-run (print "DRY RUN: would write …" per item instead). In this order, then confirm each landed:

1. Scope Tracker rows: `Status`, `Hill position`, `Last moved` (today, or the evidence date if backfilling), `Started` on a row's first move off 10, `UAT` when a product or design session happened, `Notes` for pauses. `update_properties` per row.
2. Hill Moves rows: one per move, `create-pages` in a single call. Never duplicate a row already dated today for the same scope and to-position.
3. Chart: write `{asOf, scopes:[{name, position, status}]}` for all top-level rows (no `Parent scope`), run `node scripts/hill-chart.mjs in.json > chart.svg`, render to PNG with agent-browser (ids.md), upload (`notion-create-file-upload` + curl), then `replace_content` the project page with the new `file-upload://` image and the child page and database tags copied verbatim from a fresh fetch. Look at the PNG once to confirm it rendered.
4. Daily: create in Updates with `Type: Daily`, `Date: today`, `Scopes touched`, `Posted to: ["Notion only"]`, body from the plan. On a rerun, `replace_content` today's Daily and update its properties. Keep its `Posted to` and permalink if already posted.
5. Jira: `transitionJiraIssue` per planned transition (ids in ids.md). `createJiraIssue` for new scopes, then write the url to the row's `Jira` property. If Jira rejects for missing DOR fields, report it and move on.
6. Report: one line per artifact with its URL.

## 7. Draft the standup

Compute Progress and Overall: write `[{name,status,position,size,started,due}]` for all rows to a temp file and run `node scripts/progress.mjs scopes.json`. Use the labels it returns. Show Travis the numbers behind them in one line so he can override.

Build **Today** from: yesterday's Daily or standup "Today" items not evidenced as finished, plus the current branch state (unpushed commits → "push and open PR", open PR → "address review", etc.). Mark it as derived.

Write the message per `references/standup-format.md` and the Reporting voice section of the doc. Show it in a code block, then: "Say **post**, or tell me what to change." On a rerun where the standup was already posted: "Today's standup is already posted (<permalink>). Are you sure you want to post a correction? Say **post again** to send it as a threaded reply under the original, or tell me what to change." Dry-run: show the draft and stop with "DRY RUN, not posted." Never send without the confirm word.

## 8. Post

1. `slack_send_message` to `C0AKM3X5X7A` with the final text (mrkdwn). For **post again**, send it as a reply in the original standup's thread (`thread_ts` = the permalink's ts), prefixed `*Correction:*`. The skill never edits an existing Slack message.
2. Build the permalink: `https://trunk-tools.slack.com/archives/C0AKM3X5X7A/p<ts with the dot removed>`.
3. Update today's Daily: `Posted to: ["Slack standup"]`, `Slack permalink` (first post only. A correction is noted in the Daily body instead).
4. Reply with the permalink and the Daily URL. Done.

## Rules

- Notion is the source of truth. Jira is a one-way mirror keyed by each row's `Jira` property. Never move a story backward.
- One scope at a time. The skill warns. Travis decides.
- Track in Shape Up terms, report in business terms. Hill positions and scope names never appear in the Slack text.
- Subagents read transcripts. The main session never does.
- Reruns are idempotent and explicit: same Daily, no duplicate ledger rows, chart regenerated harmlessly, and nothing rewritten or re-sent without **apply again** / **post again**.
- Dry-run writes nothing, ever.
- Travis's inputs are corrections plus the confirm words. Do not ask him to fill in fields you can derive.
- If the process needs to change, change the Tracking System doc first (and its changelog), then this skill, then `~/.claude/projects/-Users-travissaylor-projects-trunk-tools/memory/reference_revision_log_tracking.md`.
