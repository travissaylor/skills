# PRD Section Structure

Generate the PRD with these sections in order.

## 1. Introduction/Overview

Brief description of the feature and the problem it solves. 2-3 sentences max.

## 2. Goals

Specific, measurable objectives as a bullet list.

## 3. User Stories

Each story needs:

- **Title:** Short descriptive name (e.g., `US-001: Add priority field to database`)
- **Description:** "As a [user], I want [feature] so that [benefit]"
- **Acceptance Criteria:** Verifiable checklist of what "done" means

Format:

```markdown
### US-001: [Title]

**Description:** As a [user], I want [feature] so that [benefit].

**Acceptance Criteria:**

- [ ] Specific verifiable criterion
- [ ] Another criterion
- [ ] Typecheck/lint passes
```

**Rules:**
- Each story should be small enough to implement in one focused session
- Acceptance criteria must be verifiable, not vague. "Works correctly" is bad. "Button shows confirmation dialog before deleting" is good.

## 4. Functional Requirements

Numbered list of specific functionalities:

- "FR-1: The system must allow users to..."
- "FR-2: When a user clicks X, the system must..."

Be explicit and unambiguous. Each requirement should be independently testable.

## 5. Non-Goals (Out of Scope)

What this feature will NOT include. Critical for managing scope. Be specific -- "No email notifications" is better than "Notifications are out of scope."

## 6. Edge Cases & Error Handling

Document known edge cases and expected behavior:

- What happens with invalid input?
- What if a dependent service is unavailable?
- What are the boundary conditions?

## 7. Technical Considerations (Optional)

- Known constraints or dependencies
- Integration points with existing systems
- Performance requirements
- Relevant existing code or patterns to reuse

## 8. Success Metrics

How will success be measured? Use concrete metrics:

- "Reduce time to complete X by 50%"
- "Zero unhandled errors in the new flow"

## 9. Open Questions

Remaining questions or areas needing clarification. It's okay to ship a PRD with open questions -- they flag what still needs discussion.

---

## Writing Guidelines

The PRD reader may be a junior developer or AI agent. Therefore:

- Be explicit and unambiguous
- Avoid jargon or explain it
- Provide enough detail to understand purpose and core logic
- Number requirements for easy reference
- Use concrete examples where helpful

If the feature changes existing documented behavior, consider adding a user story or acceptance criterion for updating `CLAUDE.md` or relevant docs.

## Output Format

- **Format:** Markdown (`.md`)
- **Location:** User-given path, default to `.william/prds/`
- **Filename:** `<feature-name>.md` (kebab-case)
