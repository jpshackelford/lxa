Use this template for your designs.


# Title

## 1. Introduction

### 1.1 Problem Statement

Susinctly state the problem and impact of the problem. Avoid flowery or hyperbolic language. Be factual.

### 1.2 Proposed Solution

Susinctly state the design we propose to solve the problem starting with how the beficiary of the design experiences the
benefits of the proposed approach and working toward technical choices that enable it. 

If there are notable limitations or trade-offs made by our design choice, note them briefly in a seperate paragraph. If
limitations are noted, also note why the chosen design is proposed as opposed to alternatives we considered.

## 2. User Interface - OR - New Concepts (Optional Section)

If user-facing functionality, describe the user experience for a specific scenario. Explain the scenario and the steps
the user would take using the new or altered UX. If a CLI show how the user would accomplish tasks using commands and 
their flags and arguments.

If not a user-facing change, describe any new or significanlty altered concepts in the system introduced by the 
proposed changed. Omit the section if the design may easily be understood without illustrations.

## 3. Other Context (Optional Section)

If the proposed change introduces a new technology or technique background on that approach may be included here so that
the implementor does not have to do background reading to understand the design, how to call new third-party libraries or 
APIs, etc.. Include links to material for futher exploration but aim to provide all of the basics needed for the reader to
understand and start work on the proposed solution.

## 4. Technical Design

Describe the design starting from most fundamental concept of the proposal and proceed to explain each part of the
solution in its own subsection. Number subsections as follows:

### 4.1
#### 4.1.1

Ilustrate with code examples, example output, diagrams, etc. Always specify a language for illustrations fenced with
backtics, even for plaintext illustrations.

## 5. Implementation Plan

This section describes the steps required to realize the plan. Include general acceptance criteria like passing lints, and
tests immediately after the heading. Use subsections for milestones each of which could be reviewed as a complete PR with
a given goal and the code and tests required to achieve it. If user facing functionality susinctly describe what we should 
be able to demo with the completed PR. Organize the milestones such that the solution is developed in an iterative and 
incremental way, starting with foundational elements and simplest user-facing functionality that achieves the stated goal 
of the solution and expanding it in future milestones to become more robust, functional, flexible, scalable, etc.
In the sections below, note the path of each implementation and test file. 

Example:

## 5.1 Foundational Types and Classes (M1)

## 5.1.1 Some Subsystem

- [ ] lib/path1/file1.ext
- [ ] test/path1/file1.ext

## 5.1.2 Another Key Step

- [ ] lib/path2/file2.ext
- [ ] test/path2/file2.ext

## 5.2 Simple Command (M2)

Most basic demo of the proposed functionality

## 5.3 New Option for Command (M3)

User can now...



