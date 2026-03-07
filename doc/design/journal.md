# Design Composition Agent Implementation Journal

## Task 1: .openhands/microagents/design-composition.md - Workflow, precheck, template

**Date**: 2026-03-07

### Files Created/Modified
- `.openhands/microagents/design-composition.md` - New skill file created

### Task Description
Created the design-composition skill file containing:
- Complete workflow for design document composition (6 steps)
- Environment precheck details with decision table
- Content precheck requirements and questions
- Design template structure
- Review checklist with 14 quality items
- Composition order guidance
- Clarification guidelines

### Implementation Details
The skill file provides comprehensive guidance for the DesignCompositionAgent including:
- Environment setup (git, branches, directories)
- Content validation before drafting
- Structured template for design documents
- Quality review checklist items
- Clear workflow progression

### Lessons Learned
1. **Directory Structure**: Had to create `.openhands/microagents/` directory first
2. **Skill Content**: Based content on the design document sections 3.2.1, ensuring all workflow elements are covered
3. **Template Structure**: Included the standard design document structure as referenced in the design doc
4. **Review Items**: Included all 14 checklist items from the design document

### Potential Gotchas
- Skill files need to be comprehensive since they guide agent behavior
- Template structure must match the expected design document format
- Review checklist items should be actionable and specific


## Task 2: .openhands/microagents/design-style.md - Language rules, forbidden words

**Date**: 2026-03-07

### Files Created/Modified
- `.openhands/microagents/design-style.md` - New skill file created

### Task Description
Created the design-style skill file containing:
- Forbidden words and phrases categorized by type (hyperbolic, misleading, marketing)
- Content rules for avoiding hyperbole, selling language, and ensuring actionability
- Guidelines for defining key terms and maintaining technical traceability
- Rules for handling hand-wavy content with specific examples
- Appendices usage guidelines and writing style rules
- Quality checkers and before/after examples

### Implementation Details
The skill file provides comprehensive style guidance including:
- Extensive list of forbidden words that add no technical value
- Clear content rules with bad/good examples for each principle
- Technical traceability requirements (input-to-output flow)
- Specific guidance on making vague sections concrete
- Quality checking process for final review

### Lessons Learned
1. **Comprehensive Examples**: Including both bad and good examples makes the guidance much clearer
2. **Categorization**: Grouping forbidden words by type (hyperbolic, misleading, marketing) helps understand why they're problematic
3. **Actionable Rules**: Each rule includes specific examples of how to apply it
4. **Quality Process**: Included a systematic checking process for final review

### Potential Gotchas
- The forbidden words list is extensive and may need to be referenced frequently
- Some "forbidden" words might be appropriate in specific technical contexts
- Style rules need to be balanced with readability and natural language flow
