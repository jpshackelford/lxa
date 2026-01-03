# Process Notes: Working with Agents

I want to talk with you about a way of working with agents that i have found
effective. as we discuss this we will be able to carve up these ideas into a set
of capabilities we can cover in the design document we have been working on.

A new project either needs some exploration to find an appropriate approach and
technology choices that will ground the proposed solution or else a solution and
technology choices are already in mind. This optional exploration phase we could
call a research phase or exploration phase. In it questions are posed by the
user to an llm and the llm provides ideas and explanations that helps the user
learn something about the new domain and available solutions or technologies. As
the human learns the discussion turns to identifying candidate solutions and
identifying trade-offs. The exploration ends as the human decides which of the
candidate solutions becomes the proposed solution and technology choice which
undergirds a new design doc. The exploration content may be captured in its own
document that records key definitions and explanations of the domain, candidate
approaches, selection critera and the selected option. This is seperate from the
design document and its content doesn't ordinarily need to be referenced once
the introduction of the design document is written. (By design document i am
refering to a dcument with a structure such as in
https://gist.githubusercontent.com/jpshackelford/a0cbf2a1f0071619de8595cf2d2ccb79/raw/f0bb93bf4ef669599ecaa5bb09f28584c46fdd31/design-template.md

Once exploration phase is over design phase starts. The design phase is focused
on developing the design document. The design document idenifies the problem and
proposed solution. It defines the user experience (or developer experience in
the case of APIs) of the resulting solution and sketches the key elements of the
technical solution focusing on how the components of the system fit together and
fit with existing systems. (internal consistency and accuracy with regard to
external integrations are the goals at this stage). Once the solution is
envisioned, an implementation plan describes how the system unfolds in series of
milestones. The idea of a milestone is that can be demonstrated and ideally
delivers some increment of real value. It can be safely merged from a feature
branch to main once complete. It includes code, unit tests, integration or
acceptance, documentation, including documented demo flow. A milestone will be
made up of tasks which include test code and implementation code which can be
cleanly commited to a feature branch without breaking a build. So lints and type
checks must pass. Code coverage standards and other quality gates met. The
milestone plan is listed as a checklist that identifies the task goal, the path
the code and test files that will be created or modified for each task. The
tasks are grouped into milestones with milestone goals and demoable capability.

Once the design document is complete it is time to execute the plan: the
execution phase. In this phase an agent familiarizes itself with the
implementation plan and begins working on checklist items. It ensures the
environment is clean, (no uncommitted work, main is checked out and pulled,
tests and lints passing, etc. then creates a feature branch for the milestone
and begins working on tasks in the implementation plan. Once each task is
complete with code and tests passing, lints and typechecks clean, the checklist
item in the implementation plan is marked as complete and the code is committed
and pushed. If no PR for the feature branch has yet been created, a draft PR is
created so that humans can see progress as commits are made. The agent writes an
initial PR description the briefly describes the why of the PR and the scope of
the milestone. The PR description links to the design document rather than
reproducing its detailed content. Ci is checked to be sure the commit was
processed by ci cleanly. If the ci build fails for any reason the agent attempts
to understand why it was not caught by precommit checks. The precommit checks
are enhanced where required so as to reduce liklihood of surpise failures in ci.
Once all of the checklist items are complete for a milestone and ci is clean the
agent updates the PR description with a few focus areas or questiosn for human
reviewers and adds a comment to the PR indicating that it is ready for human
review. Once the human overseeing the agent's work is satisfied with the PR, the
human will change it from draft to ready for review and engage other reviewers.
Once human reviewers are satisified the humans will merge to main. The human
will then ask the agent to proceed to the next milestone. The agent will
checkout main, pull, verify a clean environment create a new feature branch,
etc. for the next milestone's work.

This is the workflow that has worked well for me in the past. I would like to
create tools, skills and agents in long-horizon-agent that help with this
workflow. We can leave exploration phase as work for the furture. I'd like to
focus on design and execution phase with special emphesis on proper completion
of implementation plan tasks (commits) and milestones (feature branches, PRs).

In general I have found that without the tools we need to build, I've seen
agents suffer from omitting quality steps, marking implementation checklist
complete, checking on ci, etc. The software-agent-sdk already has a tool for
managing a task plan. We could use that tool and have it build tasks lists that
include the feature work and the process / quality steps as it starts each task
and for milestone completion or if that tool is inadequate we could build our
own or extend it. Let's try to get as much as we can from existing capabilities.

---

## Design Document Composition Process

A design document typically starts with a document captured from the exploration
phase, from an existing github issue, or in the context of an informal
conversation that is itself an informal exploration. Capturing the the problem
and solution is the place to begin as well as detail about the the proposed user
experience or developer experience in the case of APIs. Then the build out of
the technical solution occurs once a technical direction has been established.
If an agent is asked to create a design doc and no technical approach has been
discussed or else documented in an exploration document, the agent should
susinctly propose and get confirmation from the user that the envisioned
technical direction is correct before writing the technical content. Do not
pause to ask questions if the user has already indicated technical direction in
the conversation or by refering to a document. Technical solution has a number
of components: specific technology choices, such as tools and libraries, general
approach to the problem, and also the code structure of the solution--
components, classes, etc. The design document need not have a specific section
for each of these but all three should be covered. For example the proposed
solution will speak to the overall approach to the problem, external tools and
libraries can be noted in an early section of the technical design and the bulk
of the technical design will walk through the code stucture. Not every class or
function needs to be accounted for, but the main ones so that that document
reviewer can see how the whole solution fits together. The design doc should
have enough detail that one can trace execution from input through to the most
important element of the system that produces the effect that is the solution to
the stated problem in the design doc. It should define key terms and concepts
fundamental to understanding the problem and proposed solution and the technical
design, should illustate user or system interaction in an early section so that
the user has a concrete sense of how the finished solution will work and how a
user or other system will interact with it, and the technical detail should
begin with overview of the system as a whole before elaborating on specific
subcomponents of the design.

You are already familiar with the implementation plan section of the document so
I won't comment further on that.

Sometimes it is helpful to add appendices to the document with additional
background or tables so as to preserve the flow of the main technical design
while providing necessary background or technical detail. Add these only when
necessary.

## Common Issues in Building Design Docs

1. Avoid flowery marketing language in the problem description or solution
   design. Avoid hyperbole. Unadorned facts or beliefs are sufficient. No need
   to sell. We often have to edit for this as LLMs tend to add the marketing
   language and flowery descriptions by default. Keywords like "critical" --
   perhaps you can think of others -- are problematic.

2. Linting markdown is a key part of the process. Probably we should create a
   tool for dealing with markdown that would autofix markdown lint issues,
   rewrap to produce hard line wraps and avoid long lines, and LLM based editing
   for remaining lint errors would be great. Having tools that renumber the
   document after insertions or deletions and also handle promoting or demoting
   sections and renumbering after these operations would save lots of tokens
   that are often burned trying to fix numbering issues.

3. Its important that the milestone plan has a good sense of what to demo for
   each milestone. I often find it helpful to produce a demo script as part of a
   milestone that shows the person doing the milestone demo what to say and what
   code to execute. Alternatively example documents that demonstrate useage of a
   milestones work can show what was accomplished at each milestone.

   If the project is new the first milestone will be about basic infrastructure
   for running tests, linting, defining CI, etc., and putting key parts of the
   base system in place.

   The first part of the implementation plan should have a definition of done
   that presents the quality gates (tests, lints, typechecking, documenting
   functions in the codebase, etc.) and should then present the numbered
   milestones and their steps.

4. Another failure mode is that implemetation plan steps are in the wrong order
   in the sense that a step depends on code that isn't written until a
   subsequent step. It is important to review the plan looking for these kinds
   of mistakes, reordering the implementation plan as necessary.

5. Tests at the end instead of at each step, we want tdd.

6. Implementation plan steps or technical design sections that are very hand
   wavy about security or performance which do not have very specific and
   concrete implementation. These are often appended by an LLM and have to be
   removed. Everything in the doc should be crisply actionable.

## Markdown Tool Requirements

A markdown document tool should support:

- Add and update a TOC (Table of Contents)
- TOC appears before the introduction in an unnumbered "## Table Of Contents"
  section
- Renumber tool should know to omit TOC from numbering
- Move sections: specify section to move and a before/after target position
- Insert sections with unambiguous before/after instruction
- Promote/demote sections (change heading level)
- Rewrap paragraphs to hard line breaks
- Autofix lint issues

The observation returned by the tool after structural changes (insert, delete,
move, promote, demote) should remind the agent to run renumber once all document
structure changes are complete. This guides the agent to batch structural edits
before renumbering rather than renumbering after each change.

There should be a validate command that checks document structural consistency:
- Section numbers are sequential and correctly nested
- TOC matches current headings (if TOC exists)

This should not depend on a dirty flag since it could be invoked in a new
session. The validation inspects the actual document content. A single command
reports on both issues so these aren't separate operations.

TOC commands should be simplified to avoid agent confusion:
- toc update: generates TOC if none exists, updates if one does
- toc remove: removes the TOC section
- depth parameter: controls heading depth included (default 3 for ##, ###, ####)

## Design Composition Agent Workflow

The template and skills are enough for drafting. Use TaskTrackerTool as a review
checklist after drafting, not to track each draft step.

Precheck before drafting:
1. Do we have technical direction? (exploration doc, conversation, explicit)
2. Do we have content for problem statement?
3. Do we have content for proposed solution?

If any missing → ask user for specific missing information before drafting.

Workflow:
1. Precheck: sufficient context?
   → If no: ask user for specific missing information
   → If yes: proceed
2. Draft document using template + skills
3. Review checklist (TaskTrackerTool):
   - No flowery language or hyperbole
   - Problem statement is factual
   - Technical direction confirmed (if was unclear)
   - UX/DX section has concrete examples
   - Technical design traces input to output
   - Definition of done present in implementation plan
   - Each milestone has demo artifacts
   - Each task paired with tests (TDD)
   - Task ordering respects dependencies
   - No hand-wavy sections (all content actionable)
   - Markdown validated and formatted
4. Present to user for feedback
5. Iterate based on feedback

## Milestone Sizing Guidance

A single milestone should involve no more than 60 edited files (code and tests
combined). Multiple milestones are required when:

- More than 60 files
- Technical complexity requires derisking
- UX/DX needs vetting before building on that foundation

Simple projects with few files can be completed in a single milestone. Do not
artificially split simple work.
