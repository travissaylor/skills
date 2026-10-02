---
name: showcase
description: Build an artifact that presents a body of work with visuals. A self-contained HTML page with diagrams, screenshots, and short text, for someone who was not in the room (another engineer, product, the ML team, a reviewer). Covers the six shapes Travis asks for (work explainer, option comparison, data-model + ecosystem fit, PR companion, demo readout, research report) and bakes in the fixes he has asked for on every one (no overlapping diagram text, visuals over paragraphs, generic names, enough context to skip the repo). Use when Travis says "create an artifact that…", "bring it all together with visuals", "companion artifact for the PR", "compare the two options", "visualize the data model", "help me plan the demo", or "does this artifact still hold true".
---

# /showcase

Not a prose skill. `prose` handles wording. This skill handles **what the page is, what goes on it, and the checks that stop the 5-6 fix rounds** that every artifact of this kind went through before (overlap, cut-off text, too many words, fixture names, missing context).

## 0. Load the right helpers, then pick the shape

Always load artifact-design first (page contract, tokens, dark mode, phone width). Then per content: artifact-diagramming for any diagram, dataviz for any chart or stat.

A **diff-ordered reviewer walkthrough** belongs to pr-walkthrough instead. A PR *companion* (screenshots + short explanations) belongs here.

| Shape | Travis's words | Skeleton |
|---|---|---|
| **Work explainer** | "bring it all together in one artifact… for another engineer" | What shipped (1 screen) → How it fits the ecosystem (diagram) → How it works (one section per mechanism, diagram or screenshot each) → What is not done, what is next |
| **Option comparison or decision** | "compare plan 1 to current state", "compare the 2 options" | Decision up top (bold) → Current state vs option, side by side (diagram pair or table) → What changes for users, data, and code → Why not the other (one line each) → Open questions |
| **Data model + ecosystem fit** | "visualize the whole data model", "how it fits into the ecosystem" | ER diagram of the touched models only → Where it sits among the 3 stores and services (boxes and arrows, named) → The 2-3 facts that drive the design, each as a visual → Read and write paths |
| **PR companion** | "companion artifact… screenshots of the updates and small explanation" | Before and after per screen (screenshot pair + 2 lines) → What to click to see it → Link back to the PR. Link the artifact from the PR body References |
| **Demo readout or plan** | "help me plan what to show", "what I should present" | Audience + the one thing they should take away → Flow of 4-7 stops, each: what to show, what to say, the URL or fixture → Fallbacks → Follow-ups to offer |
| **Research report** | "deep research… report artifact explaining and diagramming what you find" | Answer first → Evidence sections, each with one figure → Recommendation → Method and sources at the end |

State the shape and audience in one line before building. If unsure between two, ask once.

## 1. Content rules (his corrections, in order of frequency)

1. **Visual where text explains a relationship.** "The 'Two facts drive every decision' section could use some visuals instead of just text about the relationships." Any section describing how A relates to B, a before and after, or a flow gets a figure first and at most three lines of text.
2. **Cut the words.** "'The Idea' section is too many words." Per section: a heading that carries the point, one lead sentence, then bullets or a figure. No paragraph over three lines.
3. **Generic names, not his local env.** "Instead of using things from my local env, use more general ones that better represent exactly what they are." Sheets, sets, projects, and users are `Sheet A-101`, `Bulletin 3`, `Project A`, `Reviewer`. Use real customer or fixture names only when the artifact is about that data.
4. **Ecosystem fit must actually show the ecosystem.** "'Ecosystem fit' doesn't actually show it in the broader ecosystem." A fit diagram names the neighbouring systems (txt DB, LES, EDS and RAG, PMS, Prefect, Kafka) and draws the arrows the feature adds or changes, highlighted against the ones that exist.
5. **Self-contained context.** "Give enough context of the whole ecosystem that I don't need to go and look up specifics." Define every internal noun on first use with a phrase. Link the source (PR, Notion, Confluence) rather than restating it.
6. **Interactive before and after when a mechanism changes.** A toggle or slider that switches the same diagram between old and new beats two static pictures. Plain JS, no libraries.
7. **Metadata hierarchy, not stat cards.** "I don't like the stat cards." Use a definition list or a compact table with the primary number visually larger. Follow dataviz for anything numeric.
8. **No plans, no history.** What is true now and why. Decisions taken, not the debate, unless the shape is a decision doc.

## 2. Diagram rules (the overlap bug, every time)

Overlapping labels, missing spaces between words, and cut-off text have been reported on four separate artifacts. Cause each time: text placed by guessed width in inline SVG.

- Size boxes from text, not the reverse: pad width = `ch` count × 0.62em + 24px, height per line 1.4em. Wrap manually at ~28 characters. Never rely on SVG to wrap.
- Use `text-anchor="middle"` with an explicit `x` at box centre, `dominant-baseline="middle"`. One `<text>` per line, no `<tspan>` kerning tricks.
- Arrows leave from box edges, never centres. Label arrows above the midpoint with a background-colored halo rect behind the text.
- Minimum font 12px at 100% zoom, 14px for anything the reader must act on.
- Colors from `:root` tokens only, with the dark-mode redefinitions that artifact-design requires. Test both themes.
- **Render check before publishing**: open the file in agent-browser (a plain `file://` open in a throwaway session is fine), `screenshot` once at 1280 wide and once at 390 wide, `Read` both, and look specifically for overlap, clipping, and words run together. Fix, then re-shoot once. This single check is what the old sessions skipped.

## 3. Publish

- Publish private by default with the `Artifact` tool. Say the URL and one line: "Share-ready. Say the word and I'll link it from the PR or Notion page."
- **PR companion**: after he shares it, put the link under `## References` in the PR body. Paste the template sections, because `gh pr edit --body` bypasses the template.
- **Notion**: when he asks to attach it, add the link to the page's body, not as a comment.
- Keep the source HTML in the session scratchpad and name it after the shape (`showcase-<slug>.html`) so a later session can republish to the same URL.

## 4. "Does this artifact still hold true?"

Read the artifact with `Artifact read`, list every factual claim that names code, a table, an endpoint, a flag, or a decision, check each against main or the memory file, and answer with a table: claim, still true or changed or gone, what changed. Offer to republish with the fixes. Do not silently republish.

## Pre-publish checklist (do all, once)

1. Audience and takeaway stated in the first screen?
2. Every relationship section has a figure? Any paragraph over three lines?
3. Any local fixture, customer, or environment name that should be generic?
4. Ecosystem diagram names the real neighbouring systems and highlights the new arrows?
5. Both screenshots (1280 and 390) checked for overlap, clipping, run-together words, dark mode?
6. Links to PRs and pages instead of restated content?
