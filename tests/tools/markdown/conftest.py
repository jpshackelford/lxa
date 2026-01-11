"""Pytest fixtures for markdown tool tests."""

import pytest


@pytest.fixture
def simple_doc() -> str:
    """A simple document with title and two sections."""
    return """# My Document

## 1. Introduction

Content here.

## 2. Methods

Some methods text.
"""


@pytest.fixture
def doc_with_subsections() -> str:
    """A document with nested sections."""
    return """# My Document

## 1. Introduction

This is the introduction.

## 2. Technical Design

### 2.1 Overview

Some overview content.

### 2.2 Details

More details here.

## 3. Implementation

Final section.
"""


@pytest.fixture
def doc_with_toc() -> str:
    """A document with an existing TOC section."""
    return """# My Document

## Table Of Contents

- 1. Introduction
- 2. Technical Design

## 1. Introduction

Content here.

## 2. Technical Design

More content.
"""


@pytest.fixture
def doc_with_deep_nesting() -> str:
    """A document with deeply nested sections."""
    return """# My Document

## 1. Section

### 1.1 Subsection

#### 1.1.1 Sub-subsection

##### 1.1.1.1 Deep section

Content here.
"""


@pytest.fixture
def doc_unnumbered() -> str:
    """A document with unnumbered sections."""
    return """# My Document

## Introduction

Content here.

## Technical Design

### Overview

More content.

## Conclusion

Final thoughts.
"""


@pytest.fixture
def empty_doc() -> str:
    """An empty document."""
    return ""


@pytest.fixture
def doc_title_only() -> str:
    """A document with only a title."""
    return """# My Document

Some introductory text.
"""
