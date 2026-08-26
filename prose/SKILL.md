---
name: prose
description: "The one prose skill. Apply before writing anything a person will read: chat responses past a paragraph, docs, PR descriptions, commit messages, Jira/Confluence/Slack/Notion posts, summaries, artifacts. Merged core of unslop (language), scannable (density + layout), and technical-writing (doc standards), conflicts pre-reconciled."
---

<!-- This file is a dictionary of banned words and quotes them as examples. Vocabulary checks are skipped here. Punctuation checks stay live. -->
<!-- lint-skip-file: SK207,SK210,SK211,SK212,SK213 -->

# Prose

The merged core of three deep-pass skills. Apply this to everything written for a reader. Escalate to a deep pass only as routed at the bottom.

## Shape (before writing)

- **Answer first.** First sentence = the conclusion, answer, or ask. Detail after, for readers who want it.
- **Give the ask its own line.** A question or action request stands alone where a scanner lands on it.
- **Match length to decision weight.** Same reader action with half the words means cut half the words.
- **Capsule up top** for anything past one screen: 1-3 lines, what this is and what to do.

## Density

- One idea per sentence, under ~20 words. One topic per paragraph, 1-4 lines.
- Concrete over abstract: the number, path, command, or name. "p99 800ms → 90ms", not "significant improvement".
- Name once, reuse exactly. The second mention repeats the first mention's word.
- Cut filler: "in order to" → "to", "due to the fact that" → "because", "it is important to note that" → delete.
- One hedge max: "could potentially possibly" → "may".

## Language

- **Choose the plain word**: use (not leverage, utilize), key (not crucial, pivotal), dig into (not delve), show (not showcase), because (not due to the fact that). When two words fit, take the shorter, older one.
- **Say "is" and "has".** The parser is..., the repo has... These carry what "serves as", "boasts", and "features" pretend to.
- **Make one claim, once.** "Not just X, but Y" collapses to the Y claim, stated directly.
- **End the sentence where the thought ends.** Periods and commas separate thoughts; a new thought gets a new sentence (this is what em dashes were doing).
- **Open with content.** The first sentence starts the answer. Greetings, "Great question", and "I hope this helps" are deleted on sight.
- **Name the actor**: "the loader parses the file", "the compiler checks the types".
- **Name the real thing**: "the retry queue", not "the flywheel"; "the base image", not "the substrate". The concrete noun for the actual mechanism.

## Layout

- **Headings carry the point**, front-loaded, sentence case: "Retries mask the real failure", not "Background". Frequent enough to hop heading-to-heading.
- **Front-load every line.** First 2-3 words of each bullet and paragraph carry its keyword; scanners read the left edge.
- **Bold the scanner's anchors**: decisions, actions, names, numbers. Each bolded phrase adds information its line hasn't said yet. Sparseness is what makes an anchor visible.
- **Lists**: bullets unordered, numbers for sequence, parallel grammar, 3-7 items. More gets subheadings.
- **Tables** for comparisons; reasoning stays in surrounding prose, not cells.
- **Code font** for every identifier, path, flag, command.
- **Blank lines between logical units** are the page's only decoration. Every other visual element (bold, heading, list) earns its place by aiding navigation.

## Re-orientation (ADHD)

- Signpost counts: "Three problems:" then exactly three.
- One next action, visually isolated at the end.
- Sections stand alone; repeat the noun across section boundaries instead of "it"/"this".
- Similar documents keep the same section order every time.

## Voice

- Vary rhythm. Short sentences land points. Longer ones carry a fact with its condition.
- Have a view where the mode allows it; reference material stays dry.
- Specific over sterile: not "this is concerning" but the concrete unsettling fact.
- **Keep connected reasoning in prose** with front-loaded topic sentences. Bullets are for parallel items; an argument whose steps depend on each other stays as sentences that show the connections.

## Self-audit

Before sending: What makes this obviously AI-generated? Does the left edge alone reconstruct the argument? Is the main point findable in 5 seconds?

## Deep passes (load with the Skill tool when routed)

- **Formal documentation** (README, RFC, ERD, Confluence page, doc set) → load `technical-writing` before drafting. It owns Diátaxis mode selection, Google style, STE, Global English.
- **De-slopping an existing draft** or the user invokes it → load `unslop` for the full 31-pattern catalog.
- **Restructuring a dense wall of text** or the user invokes it → load `scannable` for the full layout and re-orientation spec with sources.

The three deep passes defer to this skill in their descriptions; don't load them ahead of it. This skill is the entry point for prose, and it routes onward.
