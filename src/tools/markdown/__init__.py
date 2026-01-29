"""Markdown document tool for structural editing and formatting."""

from .numbering import NumberingIssue, RenumberResult, SectionNumberer, ValidationResult
from .parser import MarkdownParser, ParseResult, Section
from .toc import (
    TocAction,
    TocManager,
    TocRemoveResult,
    TocUpdateResult,
    TocValidationResult,
)
from .tool import MarkdownAction, MarkdownDocumentTool, MarkdownObservation

__all__ = [
    "MarkdownParser",
    "ParseResult",
    "Section",
    "SectionNumberer",
    "NumberingIssue",
    "RenumberResult",
    "ValidationResult",
    "MarkdownDocumentTool",
    "MarkdownAction",
    "MarkdownObservation",
    "TocAction",
    "TocManager",
    "TocUpdateResult",
    "TocRemoveResult",
    "TocValidationResult",
]
