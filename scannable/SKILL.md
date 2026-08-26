---
name: scannable
description: "Deep restructuring pass: the full semantic-density, typographic-hierarchy, and ADHD re-orientation spec with sources. The `prose` skill carries the everyday core; load this for /scannable or when restructuring a wall of text."
---

# Scannable

Readers scan, they don't read. Eyetracking shows most readers skim in an F-pattern, catching headings, left edges, and the first lines of paragraphs. A reader with ADHD also loses focus mid-page and needs to re-orient from structure alone. Write for that reader: every word earns its place, and the layout answers "where am I, what matters" at a glance.

Two jobs, always together: **density** (more meaning per word) and **hierarchy** (the visual skeleton carries the argument).

## Three tests

Run these on anything longer than a paragraph:

1. **5-second test.** The main point, answer, or ask is findable within 5 seconds of looking at the top.
2. **Left-edge test.** Reading only the headings plus the first 2-3 words of each bullet and paragraph reconstructs the skeleton of the argument.
3. **Re-entry test.** A reader interrupted mid-document can find their place and resume from the structure alone, without rereading from the top.

## Density: more meaning, fewer words

- **Answer first.** The first sentence is the conclusion, answer, or ask. Detail and reasoning follow for readers who want them. Never bury the ask mid-paragraph; it gets its own line.
- **One idea per sentence, one topic per paragraph.** Sentences under ~20 words. Split anything the reader must backtrack to parse.
- **Concrete beats abstract.** The number, the file path, the command, the name. "Cut p99 from 800ms to 90ms", not "significant performance improvements".
- **Match length to decision weight.** If the reader's next action is the same with half the words, cut half the words. A yes/no question deserves a yes/no answer plus one line of why.
- **Name once, reuse exactly.** Define a term, then repeat it verbatim. Synonyms make the reader re-derive that two names are one thing.
- **Never say it twice.** A heading, its first sentence, and a bold label must each add information, not restate each other.

The `unslop` skill owns the language-level catalog (filler, hedging, AI vocabulary). Apply it alongside this one; density here is about information per sentence, not word choice.

## Hierarchy: the layout carries the argument

- **Headings carry the point, and come often.** Descriptive headings every few paragraphs turn F-pattern skimming into layer-cake scanning, where the reader hops heading to heading and drops in only where needed. "Retries mask the real failure", not "Background".
- **Front-load every line.** The first 2-3 words of a heading, bullet, or paragraph carry its keyword. Scanners read the left edge; a bullet that opens with "It is also worth noting that the parser..." hides "parser" from them.
- **Bold is an anchor, not decoration.** Bold only the words a scanner needs to reconstruct the message: decisions, actions, names, numbers. When too much is bold, nothing is.
- **Paragraphs run 1-4 lines.** Past that, split it or restructure it as a list.
- **Lists**: bullets for unordered items, numbers for sequences, parallel grammar throughout, lead word front-loaded. 3-7 items per list; more than that gets grouped under subheadings.
- **Tables** for enumerable comparisons (several items x several attributes). Reasoning stays in prose around the table, not inside cells.
- **White space is structure.** Blank lines separate logical units and give the eye anchor points; W3C lists white space as a cognitive-accessibility pattern in its own right.
- **Code font** for every identifier, path, flag, and command.

## Re-orientation: the ADHD layer

Structure is what lets a distracted reader recover. W3C's cognitive-accessibility guidance is explicit: clear, logical heading structure lets users re-orient after losing focus.

- **Capsule up top.** Anything past one screen opens with a 1-3 line summary of what this is and what the reader should do.
- **Signpost counts.** "Three problems:" then exactly three. The reader tracks progress and knows when they're done.
- **One next action.** End with the single concrete next step, visually isolated. Ten possible actions is zero actions.
- **Chunk in 3-5s.** Groups of 3-5 items are holdable in working memory; bigger sets get subheadings.
- **Sections stand alone.** Don't make section 4 depend on remembering section 2. Repeat the noun across section boundaries instead of "it" or "this".
- **Predictable shape.** Similar documents keep the same section order, so the reader learns the map once. Status updates, reviews, and briefs each get one stable template, not a new structure per instance.

## What this is not

- **Not fragmentation.** An argument that needs connected reasoning stays prose with front-loaded topic sentences. Shredding logic into disconnected bullets forces the reader to rebuild the connections you deleted, which costs more than the words saved.
- **Not decoration.** No emojis as bullets, no bolding for emphasis-feel, no boxes and dividers for their own sake. Every visual element either aids navigation or goes.
- **Not a length cap.** Density means no wasted words, not few words. A complex decision deserves its full supporting detail, laid out so the reader can skip it.

With `technical-writing`: that skill owns document standards (Diátaxis mode, style, STE); this one owns density and layout. They compose. In reference-mode docs, its "be dry and complete" wins over brevity; the layout rules here still apply.

## Worked example

Before:

> I looked into the webhook issue and it seems like there are a few things going on. The retry logic appears to be retrying even in cases where the error is a 4xx which obviously won't succeed on retry, and this is filling up the queue. Additionally I noticed that the timeout is set to 30 seconds which is quite long and might be contributing to the backlog. We should probably consider fixing the retry logic first since that seems to be the main issue, and then maybe look at the timeout afterwards.

After:

> **Webhook backlog: retries on 4xx errors are the cause.** Two findings:
>
> 1. **Retry logic retries 4xx errors**, which never succeed. This fills the queue and is the main issue.
> 2. **Timeout is 30s**, inflating each stuck attempt's cost. Secondary.
>
> Next: fix the 4xx retry check in `webhook-worker`; revisit the timeout only if the backlog persists.

The fixes: conclusion moved to the first line (answer first), findings signposted and numbered (signpost counts), lead words front-loaded and bolded (left-edge test), hedges cut ("seems like", "probably", "maybe"), one isolated next action.

## Sources

- Nielsen Norman Group, [F-shaped pattern of reading](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/), [layer-cake scanning](https://www.nngroup.com/articles/layer-cake-pattern-scanning/), [text scanning patterns](https://www.nngroup.com/articles/text-scanning-patterns-eyetracking/). Fetched 2026-08-20.
- [Federal Plain Language Guidelines](https://digital.gov/guides/plain-language) (plainlanguage.gov): front-load the main message, short sentences, design for scanning. Fetched 2026-08-20.
- W3C WAI cognitive-accessibility patterns: [use white space](https://www.w3.org/WAI/WCAG2/supplemental/patterns/o3p10-whitespace/), [chunk content](https://www.w3.org/WAI/WCAG2/supplemental/patterns/o2p05-chunked-media/), clear structure for attention impairments. Fetched 2026-08-20.
