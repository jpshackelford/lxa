# Sample Project: Calculator Library

## 1. Introduction

### 1.1 Problem Statement

We need a simple calculator library for basic arithmetic operations.

### 1.2 Proposed Solution

Implement a Calculator class with methods for add, subtract, multiply, and divide.

## 2. Technical Design

### 2.1 Calculator Class

A class with static methods for basic arithmetic:

- `add(a, b)` - Returns sum
- `subtract(a, b)` - Returns difference
- `multiply(a, b)` - Returns product
- `divide(a, b)` - Returns quotient (raises on divide by zero)

## 3. Implementation Plan

### 3.1 Core Calculator (M1)

**Goal**: Implement basic arithmetic operations.

**Demo**: Run calculator operations from Python REPL.

#### 3.1.1 Checklist

- [ ] src/calculator.py - Calculator class with add, subtract methods
- [ ] src/calculator.py - Calculator class with multiply, divide methods
- [ ] tests/test_calculator.py - Unit tests for all operations

### 3.2 Advanced Features (M2)

**Goal**: Add advanced operations like power and square root.

**Demo**: Run advanced calculations.

#### 3.2.1 Checklist

- [ ] src/calculator.py - Add power method
- [ ] src/calculator.py - Add sqrt method
- [ ] tests/test_calculator.py - Tests for advanced operations
