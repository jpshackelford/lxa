# Design Document Style Guide

This skill defines language and content rules for design documents.

## Forbidden Words and Phrases

Never use these words in design documents:

**Hyperbolic adjectives:**
- "critical", "crucial", "essential", "vital"
- "revolutionary", "game-changing", "cutting-edge"
- "seamless", "robust", "powerful", "elegant"
- "innovative", "next-generation", "state-of-the-art"

**False certainty:**
- "ensures", "guarantees" (unless literally, provably true)
- "always", "never" (unless literally true)
- "perfect", "flawless"

**Minimizing complexity:**
- "simply", "just", "easily", "trivially"
- "straightforward", "obvious"

**Marketing language:**
- "leverage", "synergy", "paradigm"
- "best-in-class", "world-class"
- "enterprise-grade", "production-ready" (unless defining what that means)

## Content Rules

### No Hyperbole

Unadorned facts are sufficient. Compare:

❌ "This revolutionary approach dramatically improves performance"
✅ "This approach reduces latency from 200ms to 50ms"

❌ "The elegant design seamlessly integrates with existing systems"
✅ "The design uses the existing REST API without modifications"

### No Selling

State what it does, not why it's amazing. The reader will judge value.

❌ "This powerful feature enables users to accomplish tasks faster than ever"
✅ "Users complete the workflow in 3 steps instead of 7"

### Be Specific

All content must be crisply actionable. Vague statements waste reader time.

❌ "Error handling will be comprehensive"
✅ "The parser catches malformed JSON and returns ParseError with line number"

## Key Terms and Concepts

- Define terms before using them
- Place definitions early, before they're needed
- If a term has a specific meaning in this context, define it even if common
- Use consistent terminology throughout (don't switch between synonyms)

Example:
```markdown
**Task Agent**: A short-lived sub-agent scoped to completing one checklist item.
Task agents read context from the design doc and journal, implement their
assigned task, then terminate.
```

## Tracing Input to Output

The technical design should allow a reader to trace how input flows through the
system to produce the stated outcome.

**Self-check**: "If I read only the technical design, could I draw a sequence
diagram from user action to system response?"

If not, the design is missing steps. Add them.

## Hand-Wavy Content

Hand-wavy sections make vague claims without implementation detail. These must
be made specific or removed:

| Hand-wavy | Must specify |
|-----------|--------------|
| "Security will be handled appropriately" | What threats? What mitigations? What code? |
| "Performance will be optimized as needed" | What operations? What targets? What techniques? |
| "Error handling will be comprehensive" | What errors? What responses? Where in code? |
| "The system will be extensible" | What extension points? What interfaces? How to extend? |
| "Logging will be added" | What events? What levels? What format? |
| "Tests will be written" | What test types? What coverage? What assertions? |

If a section cannot be made specific, remove it. Placeholder sections that say
"TBD" or "will be determined later" are not acceptable in a design document.

## Appendices

Use appendices to preserve flow of the main technical design while providing
necessary background or reference detail.

**Appropriate for appendices:**
- Reference tables (error codes, configuration options)
- Background explanations of external systems or protocols
- Detailed examples that would interrupt the narrative
- API schemas or data formats

**Not appropriate for appendices:**
- Core design content needed to understand the system
- Implementation details that inform the main design
- Anything the reader must know to evaluate the proposal

If content is needed to understand the design, it belongs in the main body.

## Checklist for Style Review

When reviewing a draft, check each section for:

- [ ] No forbidden words
- [ ] No hyperbole — every claim is factual and verifiable
- [ ] No selling — describes what, not why it's great
- [ ] Specific — no vague or hand-wavy statements
- [ ] Terms defined before use
- [ ] Traceable — can follow input to output
- [ ] Appendices contain only reference material
