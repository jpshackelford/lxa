"""Markdown document tool for structural editing and formatting."""

from .numbering import NumberingIssue, SectionNumberer, ValidationResult
from .parser import MarkdownParser, ParseResult, Section
from .toc import TOC_TITLES, TocManager, TocRemoveResult, TocUpdateResult, TocValidationResult
from .tool import MarkdownAction, MarkdownDocumentTool, MarkdownObservation

__all__ = [
    "MarkdownParser",
    "ParseResult",
    "Section",
    "SectionNumberer",
    "NumberingIssue",
    "ValidationResult",
    "MarkdownDocumentTool",
    "MarkdownAction",
    "MarkdownObservation",
    "TocManager",
    "TocUpdateResult",
    "TocRemoveResult",
    "TocValidationResult",
    "TOC_TITLES",
]
