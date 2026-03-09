# Implementation Plan Skill

This skill provides guidance for structuring implementation plans with proper dependency ordering, TDD approach, and demo artifacts.

## Definition of Done

Start every implementation plan with clear definition of done criteria:

```markdown
All tasks require:
- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)
- Passing tests (`make test`)
- [Additional project-specific criteria]
```

### Standard Criteria
Always include these basic quality gates:
- **Lint**: Code follows style guidelines, no formatting issues
- **Type Check**: All type annotations are valid, no type errors
- **Test**: All tests pass, including new tests for added functionality

### Project-Specific Criteria
Add criteria based on project needs:
- **Coverage**: Minimum test coverage percentage (e.g., 90%)
- **Documentation**: API docs, README updates, design docs
- **Performance**: Specific performance benchmarks or load tests
- **Security**: Security scans, vulnerability checks
- **Integration**: End-to-end tests, integration test suites

## Milestone Structure

### Single Milestone Projects
Use a single milestone when:
- Implementation involves fewer than 60 files (code and tests combined)
- Technical complexity is straightforward
- No significant derisking is required
- UX/DX doesn't need early validation

### Multiple Milestone Projects
Split into multiple milestones when:
- More than 60 files will be modified
- Technical complexity requires foundation-first approach
- UX/DX needs early feedback before building dependent features
- Risk mitigation requires incremental delivery

### Milestone Naming
Use descriptive milestone names that indicate the deliverable:
- **Good**: "Core Parser with Error Handling", "Web API with Authentication"
- **Bad**: "Phase 1", "Initial Implementation", "Part A"

## Test-Driven Development (TDD)

### Task-Test Pairing
Each implementation task must be paired with corresponding tests:

**Bad**:
```
- [ ] Implement UserService class
- [ ] Implement UserController class
- [ ] Add integration tests
```

**Good**:
```
- [ ] src/services/user_service.py - UserService with create/read/update methods
- [ ] tests/services/test_user_service.py - Unit tests for UserService operations
- [ ] src/controllers/user_controller.py - UserController with HTTP endpoints
- [ ] tests/controllers/test_user_controller.py - HTTP endpoint tests
```

### Test Categories

#### Unit Tests
- Test individual functions, methods, and classes
- Mock external dependencies
- Fast execution (< 1 second per test file)
- Filename pattern: `test_<module_name>.py`

#### Integration Tests
- Test component interactions
- Use real dependencies when possible
- Moderate execution time (< 10 seconds per test file)
- Filename pattern: `test_<feature_name>_integration.py`

#### End-to-End Tests
- Test complete user workflows
- Use real systems and data
- Longer execution time acceptable
- Filename pattern: `test_<workflow_name>_e2e.py`

### Test Organization
```
tests/
├── unit/
│   ├── services/
│   │   └── test_user_service.py
│   └── models/
│       └── test_user_model.py
├── integration/
│   └── test_api_integration.py
└── e2e/
    └── test_user_workflow_e2e.py
```

## Demo Artifacts

### Purpose
Demo artifacts prove the milestone works and provide usage examples:
- Validate implementation against requirements
- Provide documentation through working examples
- Enable stakeholder feedback on functionality

### Types of Demo Artifacts

#### Executable Scripts
```python
# demo/create_user_demo.py
"""
Demo script showing user creation workflow.
Run: python demo/create_user_demo.py
"""
```

#### Interactive Examples
```markdown
# Demo: User Management API

## Setup
```bash
pip install -r requirements.txt
python -m uvicorn src.main:app --reload
```

## Example Usage
```bash
# Create user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com"}'

# Get user
curl http://localhost:8000/users/1
```
```

#### Configuration Examples
```yaml
# demo/config/example_config.yaml
database:
  host: localhost
  port: 5432
  name: demo_db
  
features:
  user_registration: true
  email_notifications: false
```

### Demo Documentation
Each milestone should include:
```markdown
## Demo

**Goal**: [What this milestone demonstrates]

**Setup**: [How to prepare environment]

**Usage**: [Step-by-step example]

**Expected Output**: [What success looks like]
```

## Dependency Ordering

### Dependency Analysis
For each task, identify dependencies:
1. **Code Dependencies**: Classes, functions, modules used by this task
2. **Data Dependencies**: Database schemas, configuration files needed
3. **Infrastructure Dependencies**: Services, external systems required

### Common Dependency Issues
- Task uses a class defined in a later task
- Task imports a module created in a later task
- Task tests functionality implemented in a later task
- Integration task appears before component tasks

### Dependency Resolution
1. **List all dependencies** for each task
2. **Topological sort** - dependencies must come first
3. **Group related tasks** - keep related functionality together
4. **Validate ordering** - each task's dependencies are satisfied

### Example: Dependency-Ordered Tasks
```
# Correct dependency order:
- [ ] src/models/user.py - User model with validation
- [ ] tests/models/test_user.py - User model unit tests
- [ ] src/services/user_service.py - UserService using User model
- [ ] tests/services/test_user_service.py - UserService unit tests
- [ ] src/controllers/user_controller.py - Controller using UserService
- [ ] tests/controllers/test_user_controller.py - Controller tests

# Incorrect - UserService tests depend on UserService implementation:
- [ ] tests/services/test_user_service.py - UserService tests (WRONG)
- [ ] src/services/user_service.py - UserService implementation
```

## File Path Specifications

### Explicit Paths
Every task must specify exact file paths:

**Bad**: "Add user management functionality"
**Good**: "src/services/user_service.py - UserService class with CRUD operations"

**Bad**: "Create tests for the API"
**Good**: "tests/api/test_user_endpoints.py - HTTP endpoint tests for user CRUD"

### Path Conventions
Follow project conventions:
- Source code: `src/` or project root
- Tests: `tests/` with parallel structure to source
- Documentation: `docs/` or `doc/`
- Configuration: `config/` or project root
- Scripts: `scripts/` or `bin/`

### New Directory Creation
When creating new directory structures, specify in the task:
```
- [ ] src/agents/__init__.py - Package initialization for agents module
- [ ] src/agents/design_agent.py - DesignCompositionAgent implementation
- [ ] tests/agents/__init__.py - Test package initialization
- [ ] tests/agents/test_design_agent.py - DesignCompositionAgent unit tests
```

## Quality Checklist for Implementation Plans

Before finalizing an implementation plan, verify:

### Structure
- [ ] Definition of done at the beginning
- [ ] Clear milestone boundaries with descriptive names
- [ ] Demo artifacts described for each milestone
- [ ] File paths specified for every task

### Dependencies
- [ ] Each task lists what it depends on
- [ ] Dependencies are satisfied by earlier tasks
- [ ] No circular dependencies
- [ ] Related functionality grouped together

### Testing
- [ ] Every implementation task paired with test task
- [ ] Test categories appropriate (unit/integration/e2e)
- [ ] Test file paths follow naming conventions
- [ ] Coverage expectations clear

### Completeness
- [ ] All major components represented
- [ ] Error handling tasks included
- [ ] Integration tasks present
- [ ] Documentation tasks specified

## Examples

### Small Project (Single Milestone)
```markdown
## 4.1 JSON Configuration Parser (M1)

**Goal**: Parse JSON configuration files with validation and type safety.

**Demo**: Run `python demo/config_demo.py` to see parsing of example config files.

All tasks require:
- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)  
- Passing tests (`make test`)

#### 4.1.1 Core Parser
- [ ] src/config/parser.py - JSONConfigParser with load/validate methods
- [ ] tests/config/test_parser.py - Unit tests for parser functionality
- [ ] src/config/schema.py - Configuration schema validation
- [ ] tests/config/test_schema.py - Schema validation tests

#### 4.1.2 Demo and Documentation
- [ ] demo/config_demo.py - Demo script showing parser usage
- [ ] README.md - Update with configuration parser documentation
```

### Large Project (Multiple Milestones)
```markdown
## 4.1 Core Authentication System (M1)

**Goal**: JWT-based authentication with user management.

**Demo**: Run authentication server and create/authenticate users via API.

## 4.2 Authorization and Roles (M2)

**Goal**: Role-based access control for authenticated users.

**Demo**: Show different access levels for admin vs regular users.

## 4.3 Session Management (M3)

**Goal**: Session persistence and cleanup for web application.

**Demo**: Web interface showing login/logout with session state.
```
