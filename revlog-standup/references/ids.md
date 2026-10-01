# Revision Log tracking identifiers

All under project page **Drawing Revision Log** `3c1059d49d658114a1a3d1c0533d031a` (Projects DB row).

| Thing | ID / value |
|---|---|
| Tracking System doc | page `3c6059d49d6581d8b303e42018f7713c` |
| Scope Tracker | data source `collection://dc85e411-f134-4b0a-a909-8bca5dfdc99d` |
| Updates | data source `collection://a04d80cd-8253-4236-826d-fb71328b69b2` |
| Hill Moves | data source `collection://cac349d7-44ad-435a-bc41-f180207e1061` |
| Slack channel | `#project-drawing-log` = `C0AKM3X5X7A` |
| Travis Slack user | `U08FMLUHYJ2` |
| Jira epic | `TXT-8416` (cloudId `trunktools.atlassian.net`) |
| Chart generator | `scripts/hill-chart.mjs` (bundled with this skill) |

## Scope Tracker properties
`Name` (title), `Status` (select: Approach chosen, Risks validated, No unknowns, Over the hill, Done, Cut → Q4, Blocked), `Hill position` (number 0–100), `Sequence`, `Size (days)`, `Parent scope` / `Sub-scopes` (self-relation), `Last moved`, `Started`, `Due`, `UAT` (dates, written as `date:<Prop>:start` + `date:<Prop>:is_datetime: 0`), `Jira` (url to the story), `Notes`.

## Scope rows to Jira stories
Read the row's **Jira** property (url). That is the mapping. Sub-scopes inherit the parent's story. Scope page ids are in the Scope Tracker query results. Never hardcode them here.

New scopes: create the row (fill Jira after the story exists), then a Story under TXT-8416 with `additional_fields: {"parent": {"key": "TXT-8416"}, "components": [{"id": "10046"}], "customfield_10001": "20ba82b0-7f52-46f7-9f66-f5b3d931794e"}` (Component TrunkReview, Team TrunkReview), assignee Travis `712020:5943f435-44ee-4002-9620-7e90c8c356b6`. **Ready** (transition 31) is gated by the Definition of Ready: Component, Team, Story Points (`customfield_10028`), Description. An unshaped scope stays in Backlog or Refinement until it has points.

## Updates properties
`Name`, `Type` (Daily | Weekly), `Date`, `Scopes touched` (relation → Scope Tracker), `Posted to` (multi-select: Slack standup, Slack product, Notion only), `Slack permalink` (url).

## Hill Moves properties
`Why` (title), `Scope` (relation), `Date`, `From position`, `To position`, `From status`, `To status`. A terminal row (folded or cut) leaves `To position` and `To status` empty.

## Gather queries (use verbatim)
Date properties are columns `"date:<Prop>:start"` in `WHERE` and `ORDER BY`. Bare `"Date"` or `date("Date")` fails with `no such column: "Date"`.
```sql
SELECT * FROM "collection://dc85e411-f134-4b0a-a909-8bca5dfdc99d" ORDER BY "Sequence"
SELECT * FROM "collection://a04d80cd-8253-4236-826d-fb71328b69b2" WHERE "Type" = 'Daily' ORDER BY "date:Date:start" DESC LIMIT 3
SELECT * FROM "collection://cac349d7-44ad-435a-bc41-f180207e1061" WHERE "date:Date:start" >= '<newest Daily − 1 day, YYYY-MM-DD>' ORDER BY "date:Date:start" DESC
```

## Jira transitions (same ids on every TXT story)
Ready `31` · In Progress `2` · Code Review `51` · Test `61` · Deploy `71` · Done `81` · Discard `91`. Push forward only.

Ladder mapping:
- Started → In Progress.
- PR up → Code Review (automation does it when the ticket is tagged).
- Merged → Test (automation).
- 90 and 95 stay Test (Deploy is unused by this process).
- 100 → Done.

## Notion gotchas
- `update_content` cannot match an image block by its markdown (signed S3 URL). Swap the project-page chart with `replace_content`, re-listing the child `<page url>` and `<database url … data-source-url>` tags verbatim from a fresh fetch. Leave `allow_deleting_content` false.
- Upload a PNG: `notion-create-file-upload` → `curl -F file=@… upload_url` with the returned header → embed `![alt](file-upload://<id>)`.
- SVG → PNG: `AGENT_BROWSER_ALLOW_FILE_ACCESS=1 agent-browser open file://…svg && agent-browser set viewport 1200 560 && agent-browser screenshot out.png` (ImageMagick fails on SVG fonts).
