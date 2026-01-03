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

### Key Implementation Details
- **Section Numbering**: Supports both "1. Title" and "1.1 Title" formats
- **Hierarchy**: Only H2+ sections included in tree (H1 treated as document title)
- **TOC Detection**: Case-insensitive matching for "Table of Contents" sections
- **Line Tracking**: Accurate start/end line numbers for each section
- **Content Extraction**: Includes heading and body content with proper formatting

### Next Steps
1. Implement `MarkdownTool` class with OpenHands integration
2. Add command implementations (validate, toc, renumber, etc.)
3. Update package exports and documentation

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