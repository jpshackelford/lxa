# LXA Repository Knowledge

## Project Overview
LXA (Language eXtension Agent) is a system for building AI agents with specialized tools. Currently implementing a markdown document tool for structural editing of markdown documents.

## Current Implementation Status

### Milestone 1: Parser and Section Model ✅ COMPLETED
- **Location**: `src/tools/markdown/parser.py`
- **Classes**: 
  - `Section` dataclass: Represents markdown sections with hierarchical structure
  - `MarkdownParser` class: Parses markdown documents into section trees
- **Features**:
  - Handles numbered and unnumbered sections
  - Builds hierarchical section trees
  - Detects document titles (H1) and TOC sections
  - Supports section finding by number/title
  - Provides section content extraction
- **Testing**: 20 comprehensive test cases in `tests/tools/markdown/test_parser.py`
- **Quality**: All tests passing, linting clean, type checking passed

### Milestone 2: Section Numbering System ✅ COMPLETED
- **Location**: `src/tools/markdown/numbering.py`
- **Classes**:
  - `NumberingIssue` dataclass: Represents section numbering problems
  - `ValidationResult` dataclass: Contains validation results and recommendations
  - `SectionNumberer` class: Validates, normalizes, and renumbers sections
- **Features**:
  - Validates section numbering consistency
  - Normalizes section numbers to sequential format
  - Renumbers entire documents with proper hierarchy
  - Generates detailed issue reports and recommendations
- **Testing**: 23 comprehensive test cases in `tests/tools/markdown/test_numbering.py`
- **Quality**: All tests passing, full coverage of numbering scenarios

### Milestone 3: OpenHands Tool Integration ✅ COMPLETED
- **Location**: `src/tools/markdown/tool.py`
- **Classes**:
  - `MarkdownAction`: Action class for tool commands
  - `MarkdownObservation`: Observation class for tool results
  - `MarkdownExecutor`: Main tool executor with command routing
- **Commands**:
  - `validate`: Check document structure and numbering
  - `renumber`: Fix section numbering automatically
  - `parse`: Analyze and display document structure
- **Features**:
  - Rich text visualization for actions and observations
  - Comprehensive error handling and validation
  - File I/O with UTF-8 encoding support
  - Detailed result reporting with structured data
- **Testing**: 19 comprehensive test cases in `tests/tools/markdown/test_tool.py`
- **Integration**: 5 integration test cases in `tests/tools/markdown/test_integration.py`

### Key Implementation Details
- **Section Numbering**: Supports both "1. Title" and "1.1 Title" formats
- **Hierarchy**: Only H2+ sections included in tree (H1 treated as document title)
- **TOC Detection**: Case-insensitive matching for "Table of Contents" sections
- **Line Tracking**: Accurate start/end line numbers for each section
- **Content Extraction**: Includes heading and body content with proper formatting
- **Number Formatting**: Level 2 sections get periods (1.), level 3+ don't (1.1)
- **Error Handling**: Graceful handling of file errors, encoding issues, and invalid commands
- **Validation Logic**: Returns warnings for numbering issues, errors for system problems

### Complete Test Suite ✅ ALL PASSING
- **Total Tests**: 62 test cases across all components
- **Parser Tests**: 20 tests covering all parsing functionality
- **Numbering Tests**: 23 tests covering validation, normalization, and renumbering
- **Tool Tests**: 19 tests covering all tool commands and error cases
- **Integration Tests**: 5 tests covering end-to-end workflows
- **Coverage**: All major code paths and edge cases tested
- **Quality**: No mocking used - all tests exercise real functionality

### CI/CD Status ✅ ALL PASSING
- **Linting**: All ruff checks pass (182 issues fixed)
- **Type Checking**: All basedpyright checks pass (2 type errors fixed)
- **Full Test Suite**: All 174 tests across entire project pass
- **Code Quality**: Clean, properly formatted code with no lint violations

## Code Quality Standards
- All code passes `ruff` linting
- Type checking with `basedpyright`
- Comprehensive test coverage with `pytest`
- Clean, minimal code with focused functionality

## Testing Approach
- Unit tests for all parser functionality
- Edge case coverage (empty documents, mixed numbering, etc.)
- Real-world testing with actual design documents
- No mocking - tests real code paths