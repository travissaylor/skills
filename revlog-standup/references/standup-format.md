# Standup format (Slack, #project-drawing-log)

Travis's actual format. Reproduce it exactly. Only the content changes.

**Sending through `slack_send_message`** (verified 9/11): the tool converts standard markdown, not mrkdwn. Write `**bold**`, `[text](url)` links, `:white_check_mark:`. A run of "• " lines becomes a list block, and the next bold heading gets swallowed into it as a list continuation, so put a **blank line** between the last Completed bullet and `**Today**` (and before `**Needs/Blockers**`). The rendered result matches the hand-posted format below.

```
*Drawing Log standup - Thurs 9/10*

*Working on: <https://app.notion.com/p/Compare-from-the-Log-3c6059d49d6581a0947ed958b3db012e|Compare from Log>*
*Progress:*  :white_check_mark: *On Track*
*Overall:* :white_check_mark: <https://app.notion.com/p/Drawing-Revision-Log-3c1059d49d658114a1a3d1c0533d031a|On Track>

*Completed Since Last Check-in*
• Sheet history rail is done including updates from feedback
• Initial version of TR comparison from the revision log working
*Today*
• Iterate on compare from log work from yesterday
```

Rules observed across 8/25–9/10:
- Header: `*Drawing Log standup - <Tues|Wed|Thurs|Fri|Mon> M/D*`. Travis writes "Tues" and "Thurs".
- **Working on**: Notion scope page links, joined with ` & ` when two scopes are active. Short display names ("Compare from Log", "Sheet History Rail"). Never Jira links (9/8–9/9 used Jira only because the Notion flow was broken).
- **Progress**: `:white_check_mark: *On Track*` or `*Ahead of schedule*`. Behind uses `:warning:` and comes with the recovery plan in `Needs/Blockers`.
- **Overall**: `:white_check_mark:` + project-page link whose text is the Overall label.
- **Completed Since Last Check-in**: 2–4 bullets. Finished things only, in business language: what a user or the team can now do, what was decided and why it matters. No PR numbers unless Travis adds them, no hill positions, no Shape Up words. A decision counts as completed ("Confirmed through performance testing that … no new database work required").
- **Today**: 1–3 bullets, concrete, starting with a verb.
- `Needs/Blockers`: omitted entirely when there are none (since 9/2). When present, each blocker names the person or thing and the plan to clear it.
- Voice: plain, first person implied, short sentences, no hedging. Confidence and results over risks (Reporting voice, Tracking System doc).
