# Design Style Skill

This skill provides language and content rules for writing high-quality design documents.

## Forbidden Words and Phrases

Avoid these words and phrases that add no technical value:

### Hyperbolic Language
- "critical", "crucial", "essential", "vital"
- "revolutionary", "game-changing", "cutting-edge"
- "seamless", "robust", "powerful", "elegant"
- "amazing", "fantastic", "incredible", "outstanding"

### Misleading Promises
- "ensures", "guarantees" (unless literally true)
- "simply", "just", "easily" (minimizing complexity)
- "automatically", "magically" (unless describing actual automation)

### Marketing Language
- "best-in-class", "industry-leading", "state-of-the-art"
- "comprehensive", "complete", "full-featured"
- "enterprise-grade", "production-ready" (without specific evidence)

## Content Rules

### No Hyperbole
- Use unadorned facts instead of adjectives
- State what the system does, not why it's amazing
- Let the technical design speak for itself

**Bad**: "Our revolutionary new caching system dramatically improves performance"
**Good**: "The caching system reduces average response time from 200ms to 50ms"

### No Selling
- Focus on functionality, not benefits
- Describe behavior objectively
- Avoid persuasive language

**Bad**: "This elegant solution seamlessly integrates with existing systems"
**Good**: "The API accepts HTTP POST requests and returns JSON responses"

### Crisp Actionability
All content must be actionable for implementers:

**Bad**: "Error handling will be comprehensive"
**Good**: "HTTP 4xx errors return JSON with 'error' field containing user-facing message"

**Bad**: "Security will be handled appropriately"
**Good**: "API keys are validated using constant-time comparison to prevent timing attacks"

## Key Terms and Concepts

### Define Before Use
- Place definitions early in the document
- Define terms before their first substantive use
- Include definitions even for "obvious" terms if they have specific meaning

### Context-Specific Definitions
Even common words may need definition if they have specific meaning:

**Example**: "Repository" in a Git context vs. artifact repository vs. data repository

### Definition Structure
```markdown
**Term**: Brief definition focusing on the specific meaning in this context.
```

## Technical Traceability

### Input-to-Output Flow
The technical design must allow readers to trace how input flows to output:

- Start with user action or external input
- Show each processing step
- End with system response or state change
- Include error paths and edge cases

**Test**: "If I read only the technical design, could I draw a sequence diagram from user action to system response?"

### Missing Steps Detection
Common gaps in technical flow:
- Authentication/authorization steps
- Data validation and transformation
- Error handling and recovery
- State persistence or cleanup

## Hand-Wavy Content

Remove or make specific any vague claims:

### Security Sections
**Bad**: "Security will be handled appropriately"
**Good**: 
- Threats: SQL injection, XSS, CSRF
- Mitigations: Parameterized queries, content security policy, CSRF tokens
- Implementation: Input validation in UserController.validate()

### Performance Sections
**Bad**: "Performance will be optimized as needed"
**Good**:
- Operations: Database queries, file I/O
- Targets: < 200ms API response time, < 10MB memory usage
- Techniques: Connection pooling, query result caching

### Error Handling
**Bad**: "Error handling will be comprehensive"
**Good**:
- Errors: Network timeouts, invalid input, service unavailable
- Responses: HTTP status codes, structured error messages
- Location: ErrorHandler middleware in src/middleware/

### Extensibility
**Bad**: "The system will be extensible"
**Good**:
- Extension points: Plugin interface, configuration hooks
- Interfaces: IDataProcessor, IValidator
- How to extend: Implement interface, register in plugin.json

## Appendices Usage

Use appendices for:
- Reference tables (error codes, configuration options)
- Background on external systems or protocols
- Detailed examples that interrupt main flow

Do NOT use appendices for:
- Core design content
- Essential implementation details
- Critical decision rationale

## Writing Style Guidelines

### Sentence Structure
- Use active voice: "The parser validates input" not "Input is validated by the parser"
- Keep sentences under 25 words when possible
- One main idea per sentence

### Paragraph Structure
- Start with the main point
- Follow with supporting details
- End paragraphs at natural breaks

### Section Organization
- Lead with the most important information
- Group related concepts together
- Use consistent heading levels

## Quality Checkers

Before finalizing, check for:

1. **Forbidden words**: Search document for all items in forbidden list
2. **Vague claims**: Look for "will be", "should be", "might be" without specifics
3. **Missing definitions**: Scan for technical terms used without explanation
4. **Trace gaps**: Follow input-to-output flow, identify missing steps
5. **Hand-wavy sections**: Find claims without implementation details
6. **Marketing language**: Remove promotional or persuasive content

## Examples

### Before and After

**Before:**
"Our innovative authentication system seamlessly integrates with existing infrastructure to provide enterprise-grade security that ensures user data is always protected."

**After:**
"The authentication system validates JWT tokens containing user ID and role. Tokens expire after 24 hours and are signed with RS256 using a private key stored in HashiCorp Vault."

**Before:**
"The powerful API provides comprehensive functionality for all user management needs."

**After:**
"The API provides endpoints for creating users (POST /users), retrieving user data (GET /users/{id}), updating profiles (PUT /users/{id}), and deactivating accounts (DELETE /users/{id})."
