# Tool Integration Strategies for AI Coding Agents

## A Comparative Study Using Markdown Document Editing

**Status**: Draft  
**Authors**: [TBD]  
**Last Updated**: 2025-03-07

---

## 1. Research Context

### 1.1 The Broader Question

As AI coding agents become more sophisticated, a fundamental question emerges:

> **How should we extend agent capabilities with specialized tools?**

The OpenHands Software Agent SDK provides a framework for building native,
integrated tools with structured input/output. But is this integration overhead
worthwhile compared to simpler approaches like providing CLI utilities?

This experiment uses markdown document editing as a concrete test case to
investigate tool integration strategies for AI agents.

### 1.2 Why This Matters

The answer has practical implications for:

1. **Tool developers**: Should I build an SDK tool or a CLI wrapper?
2. **Agent framework designers**: What tool integration features matter most?
3. **Cost optimization**: Which approach minimizes tokens/cost?
4. **Reliability**: Which approach produces fewer errors?

### 1.3 The Hypothesis Space

| Hypothesis | Description |
|------------|-------------|
| **H1** | SDK-native tools outperform CLI tools due to structured I/O and discoverability |
| **H2** | CLI tools match SDK tools — the capability matters, not the integration |
| **H3** | CLI tools outperform SDK tools due to composability and flexibility |
| **H4** | Both tool approaches significantly outperform no-tool baselines |

We expect H4 to hold regardless, with the interesting question being H1 vs H2 vs H3.

---

## 2. Experimental Design

### 2.1 Conditions

We compare three conditions using identical underlying capabilities:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CONDITIONS                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  CONDITION A: BASELINE (No Specialized Tools)                       │
│  ┌─────────────────────────────────────────┐                       │
│  │  Agent has:                             │                       │
│  │  • file_editor (view, edit, create)     │                       │
│  │  • bash (shell commands)                │                       │
│  │                                         │                       │
│  │  Must: Manually parse and edit markdown │                       │
│  └─────────────────────────────────────────┘                       │
│                                                                     │
│  CONDITION B: SDK-NATIVE TOOL                                       │
│  ┌─────────────────────────────────────────┐                       │
│  │  Agent has:                             │                       │
│  │  • file_editor                          │                       │
│  │  • bash                                 │                       │
│  │  • MarkdownDocumentTool (SDK-native)    │ ← Structured I/O      │
│  │                                         │                       │
│  │  Usage: tool.run(command="renumber",    │                       │
│  │              file="doc.md")             │                       │
│  └─────────────────────────────────────────┘                       │
│                                                                     │
│  CONDITION C: CLI TOOL (Equivalent Capabilities)                    │
│  ┌─────────────────────────────────────────┐                       │
│  │  Agent has:                             │                       │
│  │  • file_editor                          │                       │
│  │  • bash + `md-tool` CLI in PATH         │ ← String I/O          │
│  │                                         │                       │
│  │  Usage: bash("md-tool renumber doc.md") │                       │
│  └─────────────────────────────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Design Principle: Equivalent Capabilities

The CLI tool (Condition C) must provide **exactly the same operations** as the
SDK tool (Condition B). The only difference is the integration method:

| Operation | SDK Tool | CLI Tool |
|-----------|----------|----------|
| Validate | `tool.run(command="validate", file="doc.md")` | `md-tool validate doc.md` |
| Renumber | `tool.run(command="renumber", file="doc.md")` | `md-tool renumber doc.md` |
| TOC Update | `tool.run(command="toc_update", file="doc.md", depth=3)` | `md-tool toc-update doc.md --depth 3` |
| Move | `tool.run(command="move", section="3.2", position="after", target="2.1")` | `md-tool move doc.md --section 3.2 --after 2.1` |
| ... | ... | ... |

### 2.3 Controlling for Discoverability

A potential confound is that SDK tools are automatically visible in the agent's
tool list, while CLI tools must be discovered or mentioned.

**Approach**: Include CLI tool existence in the system prompt for Condition C:

```
You have access to `md-tool`, a command-line tool for markdown operations.
Run `md-tool --help` to see available commands.
Commands include: validate, renumber, toc-update, toc-remove, move, 
insert, delete, promote, demote, rewrap, lint, fix, cleanup.
```

This ensures fair comparison — both conditions know a tool exists.

### 2.4 Model Selection

Primary experiments use a single model to isolate tool effects:
- **Primary**: Claude 3.5 Sonnet (or Claude 4)

Secondary experiments test generalization:
- GPT-4o
- Gemini 2.0 Flash
- Open-weight models (Llama 3.3 70B, DeepSeek V3)

---

## 3. Metrics and Measurement

### 3.1 Primary Metrics: Efficiency

Unlike traditional benchmarks that focus on pass rate for hard problems, we
focus on **efficiency for solvable tasks**:

| Metric | Definition | Why It Matters |
|--------|------------|----------------|
| **Tokens per success** | (input + output tokens) / successful completions | Direct cost proxy |
| **Time to completion** | Wall-clock seconds | User experience |
| **Tool/command calls** | Number of tool invocations or bash commands | Interaction efficiency |
| **First-attempt success** | % passing without conversation retry | Reliability |

### 3.2 Secondary Metrics: Quality Gates

Pass rate serves as a **quality gate**, not the headline metric:

| Metric | Expected Range | Purpose |
|--------|----------------|---------|
| Pass rate | 85-95% | Ensure baseline capability |
| Error rate | <5% | Ensure reliability |
| Content preservation | 100% | Ensure correctness |

### 3.3 Diagnostic Metrics

To understand WHY one approach outperforms another:

| Metric | What It Reveals |
|--------|-----------------|
| Tokens before first tool use | Discoverability / planning overhead |
| Error recovery attempts | Ease of error handling |
| Tool call success rate | Are structured inputs more reliable? |
| Thinking vs action ratio | Planning efficiency |

### 3.4 Statistical Approach

**Sample sizes**:
- Development: 20 problems (golden set) for rapid iteration
- Validation: 50-100 problems for pre-publication checks
- Publication: 300-500 problems for robust statistics

**Handling variance**:
- Run each problem 3x, report mean ± std
- Use paired comparisons (same problems across conditions)
- Report median alongside mean (robust to outliers)

---

## 4. The Benchmark: Markdown Document Editing

### 4.1 Why Markdown?

Markdown document editing is an ideal test case because:

1. **Solvable by current LLMs** — Not capability-limited, so efficiency matters
2. **Structural operations** — Clear right/wrong answers for validation
3. **Real-world relevance** — Agents edit docs as part of software development
4. **Tool-amenable** — Operations like renumbering benefit from tooling

### 4.2 The LXA Markdown Document Tool

The SDK-native tool provides these operations:

| Category | Operations |
|----------|------------|
| Validation | `validate` - Check structure and numbering |
| Numbering | `renumber` - Fix sequential section numbers |
| TOC | `toc_update`, `toc_remove` - Manage table of contents |
| Structure | `move`, `insert`, `delete` - Section manipulation |
| Hierarchy | `promote`, `demote` - Change heading levels |
| Formatting | `rewrap`, `lint`, `fix` - Clean up markdown |
| Combined | `cleanup` - All-in-one formatting pass |

### 4.3 Problem Categories

| Category | Description | % of Benchmark |
|----------|-------------|----------------|
| Structural | Move, insert, delete sections | 25% |
| Hierarchy | Promote, demote headings | 12% |
| Numbering | Fix broken section numbers | 12% |
| TOC | Create, update, remove TOC | 10% |
| Formatting | Rewrap, lint, fix issues | 12% |
| Multi-operation | Complex sequences (3+ ops) | 20% |
| Error recovery | Fix malformed documents | 9% |

### 4.4 Document Sizes

| Size | Word Count | Distribution |
|------|------------|--------------|
| Short | 200-500 | 40% |
| Medium | 1,000-3,000 | 35% |
| Long | 5,000-15,000 | 20% |
| Very Long | 20,000+ | 5% |

---

## 5. Hypotheses and Predictions

### 5.1 Primary Hypotheses

**H1: SDK tools > CLI tools (Efficiency)**

Prediction: SDK-native tools will show 15-30% lower token usage due to:
- No shell parsing overhead
- Structured error messages
- Direct parameter binding

**H2: SDK tools > CLI tools (Reliability)**

Prediction: SDK-native tools will show 5-10% higher first-attempt success due to:
- Input validation before execution
- Clearer error observations
- Typed parameters prevent malformed calls

**H3: Both >> Baseline**

Prediction: Both tool conditions will show 40-60% lower token usage than
baseline, validating that specialized tools help regardless of integration.

### 5.2 Secondary Hypotheses

**H4: Document size moderates tool benefit**

Prediction: Tool advantages increase with document size because:
- Longer documents are harder to edit manually
- More opportunities for numbering/TOC errors
- Context limits make manual editing harder

**H5: Multi-operation tasks show largest SDK advantage**

Prediction: Complex tasks benefit most from SDK tools because:
- CLI requires multiple bash calls with string wrangling
- SDK tool maintains state across operations
- Structured observations guide multi-step planning

**H6: CLI tools may excel at composability**

Prediction: For tasks requiring novel combinations or shell integration,
CLI tools may match or exceed SDK tools.

---

## 6. Anticipated Results

### 6.1 Optimistic Scenario (Strong SDK Advantage)

```
                      Tokens/Success    Time/Success    Pass Rate
Baseline              5,200 ± 890       42.3s ± 12.1    82%
CLI Tool              3,100 ± 650       24.8s ± 8.4     89%
SDK Tool              2,100 ± 420       16.2s ± 5.2     93%

SDK vs CLI improvement:    32%              35%          +4%
SDK vs Baseline:           60%              62%          +11%
```

**Interpretation**: SDK integration provides substantial efficiency gains
beyond just having the capability available.

### 6.2 Moderate Scenario (Tools Help, Integration Similar)

```
                      Tokens/Success    Time/Success    Pass Rate
Baseline              5,200 ± 890       42.3s ± 12.1    82%
CLI Tool              2,400 ± 520       19.5s ± 6.8     90%
SDK Tool              2,100 ± 480       17.8s ± 6.1     91%

SDK vs CLI improvement:    12%              9%           +1%
Both vs Baseline:          ~55%            ~55%          +9%
```

**Interpretation**: Tools provide major benefits; SDK integration provides
modest additional gains, primarily in consistency.

### 6.3 Surprising Scenario (CLI Competitive)

```
                      Tokens/Success    Time/Success    Pass Rate
Baseline              5,200 ± 890       42.3s ± 12.1    82%
CLI Tool              2,000 ± 450       16.4s ± 5.8     92%
SDK Tool              2,200 ± 510       17.9s ± 6.2     90%

Interpretation: CLI composability and shell flexibility offset 
SDK's structured I/O advantages.
```

---

## 7. Threats to Validity

### 7.1 Internal Validity

| Threat | Mitigation |
|--------|------------|
| CLI discoverability confound | Mention tool in system prompt |
| Problem selection bias | Use diverse, stratified sample |
| Model-specific effects | Test multiple models |
| Implementation differences | Same underlying code for both tools |

### 7.2 External Validity

| Threat | Mitigation |
|--------|------------|
| Markdown-specific findings | Acknowledge domain specificity |
| Current model capabilities | Note model versions and dates |
| Tool quality effects | Ensure both tools are well-implemented |

### 7.3 Construct Validity

| Threat | Mitigation |
|--------|------------|
| Token count ≠ cost | Report actual $ costs where possible |
| Pass rate ceiling | Include some hard problems |
| Efficiency gaming | Verify solution quality, not just speed |

---

## 8. Broader Implications

### 8.1 For Tool Developers

- **When to build SDK tools**: High-frequency, well-defined operations
- **When CLI suffices**: One-off tasks, rapid prototyping
- **Hybrid approach**: SDK tool that wraps CLI for best of both

### 8.2 For Agent Framework Design

Potential SDK improvements suggested by results:
- Tool composition/pipelining
- Better CLI tool integration
- Automatic CLI-to-SDK wrapping

### 8.3 For the Research Community

- Efficiency benchmarks complement capability benchmarks
- Tool integration is an understudied variable
- Structured evaluation of agent tooling

---

## 9. Paper Outline (Draft)

### Title Options

1. "Tool Integration Strategies for AI Coding Agents: A Comparative Study"
2. "Native vs CLI: Evaluating Tool Integration Approaches for LLM Agents"
3. "Beyond Capability: Measuring Tool Efficiency in AI Coding Assistants"

### Abstract (Draft)

> As AI coding agents adopt increasingly sophisticated tooling, questions arise
> about optimal integration strategies. We present a comparative study of three
> approaches to extending agent capabilities: (1) no specialized tools,
> (2) SDK-native tools with structured input/output, and (3) equivalent CLI
> tools invoked via shell. Using a novel benchmark of N markdown document
> editing tasks, we evaluate efficiency (tokens, time, cost) and reliability
> (pass rate, error recovery) across conditions. Our findings show that
> [RESULTS TBD], with implications for tool developers and agent framework
> designers.

### Proposed Sections

1. **Introduction**
   - AI agents and tool use
   - The tool integration question
   - Contributions

2. **Background**
   - Agent tool frameworks
   - Related benchmarks (SWE-bench, EditEval, etc.)
   - Efficiency vs capability evaluation

3. **Experimental Setup**
   - The three conditions
   - The markdown benchmark
   - Metrics and measurement

4. **Results**
   - Overall efficiency comparison
   - Analysis by problem type
   - Analysis by document size
   - Model generalization

5. **Discussion**
   - Why SDK tools help (or don't)
   - When to use each approach
   - Framework design implications

6. **Limitations and Future Work**

7. **Conclusion**

---

## 10. Timeline and Milestones

### Phase 1: Infrastructure (2-3 weeks)
- [ ] Finalize benchmark problem set (300+ problems)
- [ ] Implement CLI tool wrapper
- [ ] Set up OpenHands benchmark harness integration
- [ ] Validate automated scoring

### Phase 2: Development Runs (1-2 weeks)
- [ ] Run golden set (20 problems) across conditions
- [ ] Iterate on tool implementations
- [ ] Calibrate metrics collection

### Phase 3: Full Evaluation (2-3 weeks)
- [ ] Run full benchmark (300+ problems × 3 conditions × 3 runs)
- [ ] Analyze results
- [ ] Test model generalization (2-3 additional models)

### Phase 4: Write-up (2-3 weeks)
- [ ] Draft paper
- [ ] Create visualizations
- [ ] Internal review
- [ ] Submission

---

## 11. Open Questions

1. **Venue**: Workshop paper? Full conference? Technical report?

2. **Scope**: Focus on markdown, or include second domain for generalization?

3. **Models**: How many models to test for generalization claims?

4. **CLI integration depth**: Just mention in prompt, or add as pseudo-tool?

5. **Cost tracking**: Use actual API costs or normalize by token?

---

## Appendix A: Efficiency Benchmark Rationale

### A.1 Why Not a Traditional "Hard Problems" Benchmark?

Most AI benchmarks (SWE-bench, MATH, etc.) focus on **capability ceiling**:
- Low pass rates (10-30%)
- Room to show model improvements
- Differentiates weak vs strong models

Our benchmark inverts this for good reasons:

| Traditional Approach | Our Approach |
|---------------------|---------------|
| "Can the LLM do this?" | "How efficiently can it do this?" |
| 20% pass rate | 85-95% pass rate |
| Measures capability | Measures operational efficiency |
| Differentiates models | Differentiates tool strategies |

### A.2 Why Efficiency Matters More Here

For production use of AI agents editing documents:

1. **Tasks are solvable** - Current LLMs CAN edit markdown
2. **Cost matters** - Token usage directly impacts API costs
3. **Speed matters** - Users waiting for edits care about latency
4. **Reliability matters** - First-attempt success reduces frustration

The real question isn't "can Claude edit markdown?" but:
- "How much does it cost per edit?"
- "How long do users wait?"
- "How often do we need retries?"

### A.3 Precedents for Efficiency Benchmarks

| Benchmark/Metric | Focus |
|------------------|-------|
| SWE-bench cost leaderboards | $/solve alongside pass rate |
| Inference efficiency papers | FLOPS per correct output |
| Web performance benchmarks | Time to interactive |
| Database benchmarks (TPC-H) | Queries per second |

### A.4 Handling the "Too Easy" Concern

To maintain rigor while focusing on efficiency:

1. **Pass rate as gate, not metric** - Only count efficiency for correct solutions
2. **Include some hard problems** - 10-15% with lower expected pass rates
3. **Report pass rate** - But headline the efficiency metrics
4. **Quality verification** - Ensure solutions are actually correct, not just fast

## Appendix B: CLI Tool Advantages and Composability

### B.1 Potential CLI Advantages

The CLI condition might outperform or match SDK tools in some scenarios:

**Composability**
```bash
# Chain operations with pipes
md-tool validate doc.md | jq '.issues | length'

# Loop over multiple files
for f in *.md; do md-tool renumber "$f"; done

# Conditional execution
md-tool validate doc.md || md-tool fix doc.md
```

**Flexibility**
```bash
# Combine with other tools
md-tool toc-update doc.md && git diff doc.md

# Custom processing
md-tool parse doc.md | jq '.sections[] | select(.level == 2)'
```

**Familiarity**
- Agents trained on vast amounts of shell scripting
- Standard Unix patterns well-understood
- Error handling via exit codes is familiar

### B.2 When CLI Might Win

| Scenario | Why CLI Might Excel |
|----------|---------------------|
| Multi-file operations | Shell loops and globs |
| Novel combinations | Ad-hoc piping |
| Inspection tasks | jq/grep post-processing |
| Conditional logic | Shell if/then/else |

### B.3 When SDK Might Win

| Scenario | Why SDK Might Excel |
|----------|---------------------|
| Single complex operation | Structured parameters |
| Error recovery | Rich error observations |
| Discovery | Tool appears in available tools |
| Validation | Input validation before execution |

### B.4 What the Results Will Tell Us

**If SDK >> CLI**: SDK integration has unique value
- Invest in SDK tool development
- Structured I/O and discoverability matter

**If SDK ≈ CLI**: Tools help, integration method secondary
- Provide CLI tools for simplicity
- SDK tools for special cases

**If CLI >> SDK in some cases**: Learn from CLI advantages
- Consider adding composability to SDK
- Document when to use which approach

## Appendix C: CLI Tool Specification

See `cli/md_tool.py` for implementation.

```bash
# Command structure
md-tool <command> <file> [options]

# Available commands
md-tool validate <file>                    # Check structure
md-tool renumber <file>                    # Fix section numbers
md-tool toc-update <file> [--depth N]      # Update TOC
md-tool toc-remove <file>                  # Remove TOC
md-tool move <file> --section S --before|after T
md-tool insert <file> --heading H --level L --before|after T
md-tool delete <file> --section S
md-tool promote <file> --section S
md-tool demote <file> --section S
md-tool rewrap <file> [--width N]
md-tool lint <file>
md-tool fix <file>
md-tool cleanup <file>

# Output format: JSON to stdout
# Exit codes: 0 = success, 1 = validation failed, 2 = error
```

## Appendix D: Related Work Summary

| Paper | Relevance |
|-------|-----------|
| SWE-bench (Jimenez et al., 2024) | Benchmark methodology, harness design |
| EDIT-Bench (Chi et al., 2025) | Code editing evaluation, real-world problems |
| EditEval (Dwivedi-Yu et al., 2024) | Text editing, instruction-based tasks |
| StructEval (2025) | Structured output evaluation including markdown |
| Tool use in LLMs (various) | Tool integration patterns |
