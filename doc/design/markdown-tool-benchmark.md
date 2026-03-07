# Markdown Document Editing Benchmark Specification

**Status**: Draft  
**Related**: [Tool Integration Experiment Design](tool-integration-experiment.md)  
**Last Updated**: 2025-03-07

---

## 1. Overview

This document specifies the technical design of a benchmark for evaluating
markdown document editing by AI agents. It covers problem format, dataset
structure, evaluation harness integration, and automated scoring.

For the broader research context and experimental design, see the companion
document: [Tool Integration Experiment Design](tool-integration-experiment.md).

### 1.1 Purpose

This benchmark measures **efficiency** (tokens, time, cost) rather than
capability ceiling. Problems are designed to be solvable by current LLMs,
with differentiation based on how efficiently solutions are achieved.

### 1.3 Related Benchmarks and Papers

The following existing benchmarks and research papers are relevant:

#### Code Editing Benchmarks

| Benchmark | Size | Focus | Paper/Source |
|-----------|------|-------|--------------|
| **SWE-bench** | 2,294 | Python GitHub issues | Jimenez et al., 2024 |
| **SWE-bench Verified** | 500 | Curated subset | OpenAI, 2024 |
| **EDIT-Bench** | 540 | IDE code editing | Chi et al., 2025 (arXiv:2511.04486) |
| **Aider Polyglot** | ~130 | Multi-language editing | Gauthier, 2025 |
| **CanItEdit** | - | Instructed code editing | Cassano et al., COLM 2024 |

#### Text Editing & Revision Benchmarks

| Benchmark | Size | Focus | Paper/Source |
|-----------|------|-------|--------------|
| **EditEval** | ~2,000 | Instruction-based text editing | Dwivedi-Yu et al., CoNLL 2024 (Meta) |
| **ITERATER** | ~8,000 | Iterative text revision | Du et al., 2022 |
| **XATU** | 1,000 | Explainable text updates | arxiv:2309.11063 |
| **RewriteLM / OpenRewriteEval** | - | Cross-sentence rewriting | AAAI 2024 |

#### Structured Output Benchmarks

| Benchmark | Size | Focus | Paper/Source |
|-----------|------|-------|--------------|
| **StructEval** | 2,035 | Structured output (JSON, YAML, Markdown, LaTeX) | arxiv:2505.20139 |
| **TeXpert** | - | LaTeX code generation | ACL 2025 SDP Workshop |
| **InstrEditBench** | 30,000+ | Structured editing (Wiki, LaTeX, code, DSL) | arxiv:2502.13358 (FineEdit) |

#### Instruction Following Benchmarks

| Benchmark | Size | Focus | Paper/Source |
|-----------|------|-------|--------------|
| **IFEval** | ~500 | Instruction following | Zhou et al., 2023 (arXiv:2311.07911) |
| **LLMBar** | 419 | Meta-evaluation for instruction following | Zeng et al., ICLR 2024 |
| **InFoBench** | 500 | Multi-constraint instructions | - |

### 1.3 Key Papers to Review

1. **"EditEval: An Instruction-Based Benchmark for Text Improvements"**
   - Meta AI (Facebook Research)
   - Tasks: Fluency, coherence, clarity, simplification, neutralization,
     paraphrasing, updating information
   - GitHub: github.com/facebookresearch/EditEval
   - *Most relevant for methodology*

2. **"EDIT-Bench: Evaluating LLM Abilities to Perform Real-World Instructed
   Code Edits"** (Chi et al., 2025)
   - 540 problems from real IDE usage
   - Includes cursor position, highlighted code context
   - Found even best models (Claude Sonnet 4) achieve only 64.8%
   - *Most relevant for experimental design*

3. **"Improving Iterative Text Revision by Learning Where to Edit"**
   (DELITERATER)
   - Focuses on WHERE to edit, not just WHAT to edit
   - Uses edit intent trajectories
   - *Relevant for multi-operation sequences*

4. **"StructEval: Benchmarking LLMs' Capabilities to Generate Structural
   Outputs"**
   - 18 formats including Markdown, LaTeX, JSON
   - Generation vs conversion tasks
   - Even o1-mini achieves only 75.58%
   - *Directly relevant for markdown generation*

5. **"FineEdit: Unlock Instruction-Based Text Editing for LLMs"**
   (InstrEditBench)
   - 30,000+ structured editing tasks
   - Includes Wikipedia articles, LaTeX, code
   - DiffEval metric for evaluating edits
   - *Relevant for scale and automation*

### 1.4 Gap Analysis

| Aspect | Existing Benchmarks | Our Need |
|--------|---------------------|----------|
| Document type | Code, prose, LaTeX | **Markdown specifically** |
| Operations | General edits | **Structural ops (TOC, sections, numbering)** |
| Document length | Mostly short | **Short to very long (20K+ words)** |
| Multi-operation | Limited | **Complex sequences** |
| Tool use | No | **With/without specialized tools** |

This confirms we need a **novel benchmark** for markdown document editing.

## 2. Statistical Requirements

### 2.1 Sample Size Analysis

For comparing success rates between conditions (e.g., with-tool vs without-tool):

| Effect Size to Detect | Power | Samples per Condition | Total (2 conditions) |
|-----------------------|-------|----------------------|---------------------|
| 20% (50% → 70%)       | 80%   | ~80                  | ~160                |
| 15% (50% → 65%)       | 80%   | ~150                 | ~300                |
| 10% (50% → 60%)       | 80%   | ~400                 | ~800                |
| 10% (50% → 60%)       | 90%   | ~530                 | ~1060               |

**Recommendation**: Target **300-500 problems** for robust statistical power to
detect 10-15% improvements with 80%+ power.

### 2.1.1 Sample Size Summary by Use Case

| Use Case | Problems | Runs/Problem | Total Runs | Detects | Time | Cost |
|----------|----------|--------------|------------|---------|------|------|
| **Dev iteration** | 20 | 1 | 20 | ±20%+ regressions | ~10 min | ~$1 |
| **PR validation** | 50 | 1 | 50 | ±15% changes | ~25 min | ~$2 |
| **Accurate measure** | 100 | 3 | 300 | ±10% effects | ~3 hrs | ~$15 |
| **Paper-ready** | 300-350 | 3 | 900-1050 | ±5-10% effects | ~10 hrs | ~$50 |
| **High confidence** | 500 | 5 | 2500 | ±5% effects | ~25 hrs | ~$150 |

**For this benchmark, we target**:
- **Minimum viable**: 300 problems × 3 runs = 900 data points per condition
- **Paper-ready**: 350 problems × 3 runs × 3 conditions = ~3,150 total runs
- **With model generalization**: Add 100 problems × 2 additional models = +600 runs

**Development approach**: Pilot first. Before committing to full-scale runs:
1. Build and run golden set (20 problems) across all conditions
2. Validate core assumptions (tool benefit exists, automated verification works)
3. Determine appropriate scale based on observed effect sizes and variance
4. Defer venue, scope, and model selection decisions until pilot results inform them

### 2.2 Handling LLM Stochasticity

LLM outputs vary even with identical inputs. To account for this:

- Run each problem **3-5 times** per model/configuration
- Report mean and confidence intervals
- Use temperature=0 where possible (reduces but doesn't eliminate variance)
- For 300 problems × 3 runs = 900 data points per condition

### 2.3 Multiple Comparisons

With 4+ conditions being compared, apply corrections:
- Bonferroni correction for pairwise comparisons
- Or use ANOVA-style analysis with post-hoc tests

## 3. Benchmark Structure

### 3.1 Document Categories

| Category   | Word Count   | Sections | Purpose                          |
|------------|--------------|----------|----------------------------------|
| Short      | 200-500      | 5-15     | Baseline, fit in context easily  |
| Medium     | 1,000-3,000  | 20-50    | Typical design doc               |
| Long       | 5,000-15,000 | 50-150   | Complex specification            |
| Very Long  | 20,000+      | 150+     | Stress test, context limits      |

**Distribution**: 40% Short, 35% Medium, 20% Long, 5% Very Long

### 3.2 Problem Types by Operation

Based on the tool's capabilities:

| Operation Category | Operations                        | Problems | Priority |
|--------------------|-----------------------------------|----------|----------|
| Structural         | move, insert, delete              | 80-100   | High     |
| Hierarchy          | promote, demote                   | 40-50    | High     |
| Numbering          | renumber (after manual changes)   | 40-50    | High     |
| TOC                | toc_update, toc_remove            | 30-40    | Medium   |
| Formatting         | rewrap, lint, fix                 | 40-50    | Medium   |
| Multi-operation    | Complex sequences (3+ ops)        | 60-80    | High     |
| Error Recovery     | Fix broken/malformed documents    | 30-40    | Medium   |

**Total**: 320-410 problems

### 3.2.1 Final Problem Mix Target (350 problems)

For paper-ready benchmark with balanced coverage:

| Category | Count | % | Rationale |
|----------|-------|---|-----------|
| Structural (move, insert, delete) | 90 | 26% | Core structural ops, high tool benefit |
| Multi-operation (3+ ops) | 70 | 20% | Complex tasks show largest differences |
| Numbering (renumber, validate) | 45 | 13% | Clear automated validation |
| Hierarchy (promote, demote) | 45 | 13% | Distinct operation type |
| Formatting (rewrap, lint, fix) | 40 | 11% | Tests formatting capabilities |
| TOC (toc_update, toc_remove) | 35 | 10% | Specific feature test |
| Error Recovery (malformed docs) | 25 | 7% | Edge cases and robustness |
| **Total** | **350** | 100% | |

**By document size**:
| Size | Count | % |
|------|-------|---|
| Short (200-500 words) | 140 | 40% |
| Medium (1-3K words) | 124 | 35% |
| Long (5-15K words) | 70 | 20% |
| Very Long (20K+ words) | 16 | 5% |

**By complexity**:
| Complexity | Count | % |
|------------|-------|---|
| Atomic (single op) | 140 | 40% |
| Compound (2-3 ops) | 122 | 35% |
| Complex (4+ ops) | 88 | 25% |

### 3.3 Complexity Levels

| Level     | Description                                      | Distribution |
|-----------|--------------------------------------------------|--------------|
| Atomic    | Single operation, clear instruction              | 40%          |
| Compound  | 2-3 operations, sequential                       | 35%          |
| Complex   | 4+ operations, interrelated, requires planning   | 25%          |

### 3.4 Problem Distribution Matrix

```
                    Short   Medium   Long    VLong   Total
Structural          36      32       18      4       90
Multi-op            28      25       14      3       70
Numbering           18      16       9       2       45
Hierarchy           18      16       9       2       45
Formatting          16      14       8       2       40
TOC                 14      12       7       2       35
Error Recovery      10      9        5       1       25
─────────────────────────────────────────────────────────
Total               140     124      70      16      350
```

*Note: Size distribution targets 40% short, 35% medium, 20% long, 5% very long.*

## 4. Problem Design

### 4.1 Problem Format

Each problem consists of:

```yaml
problem_id: "struct-move-001"
category: "structural"
operation: "move"
complexity: "atomic"
document_size: "medium"

# The input document (markdown content)
input_document: |
  # Project Design
  
  ## 1. Introduction
  ...

# Natural language instruction (what the user wants)
instruction: |
  Move section "3.2 Error Handling" to appear after section "2.1 Overview".
  After moving, ensure the section numbers are updated correctly.

# Expected output or verification criteria
expected_output: |
  # Project Design
  ...

# Automated verification rules
verification:
  - type: "section_order"
    check: "3.2 Error Handling comes after 2.1 Overview"
  - type: "numbering_valid"
    check: "all sections have sequential numbers"
  - type: "content_preserved"
    check: "no content lost or duplicated"
```

### 4.2 Instruction Variation

To test robustness, include variations:

1. **Precise instructions**: "Move section 3.2 to after section 2.1"
2. **Vague instructions**: "Put the error handling section earlier in the doc"
3. **Multi-step instructions**: "Add a new Security section, then move the
   existing Error Handling under it as a subsection"
4. **Error-recovery instructions**: "Fix the broken section numbering"

### 4.3 Example Problems

#### Example 1: Atomic Structural (Move)

```yaml
problem_id: "struct-move-001"
category: "structural"
operation: "move"
complexity: "atomic"
instruction: "Move the 'Future Work' section to appear before the 'Conclusion' section."
```

#### Example 2: Compound (Insert + Renumber)

```yaml
problem_id: "compound-insert-001"
category: "multi-operation"
operation: "insert,renumber"
complexity: "compound"
instruction: |
  Insert a new section titled 'Security Considerations' between 
  'Implementation' and 'Testing'. Make sure all section numbers 
  are updated.
```

#### Example 3: Complex Multi-Operation

```yaml
problem_id: "complex-restructure-001"
category: "multi-operation"
operation: "move,promote,delete,renumber,toc_update"
complexity: "complex"
instruction: |
  Restructure this document:
  1. The 'Advanced Features' subsection (3.2.1) should be its own 
     top-level section
  2. Remove the deprecated 'Legacy Support' section (4.3)
  3. Ensure all numbering is correct
  4. Update the table of contents
```

## 5. Metrics

### 5.1 Primary Metrics

| Metric              | Description                                    | Unit       |
|---------------------|------------------------------------------------|------------|
| Success Rate        | % of problems fully solved correctly           | %          |
| Partial Success     | % of required changes completed                | %          |
| Token Efficiency    | Total tokens (input + output) per problem      | tokens     |
| Cost                | API cost per problem                           | $ USD      |
| Latency             | Time to completion                             | seconds    |

### 5.2 Secondary Metrics

| Metric                | Description                                  |
|-----------------------|----------------------------------------------|
| Tool Call Count       | Number of tool invocations needed            |
| Retry Rate            | % of problems requiring retry/correction     |
| Error Rate            | % of problems with errors/exceptions         |
| Context Overflow Rate | % of problems exceeding context limits       |

### 5.3 Derived Metrics

| Metric              | Formula                                      |
|---------------------|----------------------------------------------|
| Cost per Success    | Total Cost / Successful Problems             |
| Tokens per Success  | Total Tokens / Successful Problems           |
| Efficiency Ratio    | Success Rate / (Tokens / 1000)               |

## 6. Verification Methods

**Verification Hierarchy**: Automated checks are the primary verification method
and should handle 95%+ of problems. LLM-as-judge is a fallback for semantic edge
cases only. Human validation is used solely for calibration.

### 6.1 Automated Verification (Primary)

Automated verification is deterministic, fast, and cheap. It is the **primary**
method for scoring benchmark results.

1. **Structural Validation**
   - Parse output document into section tree
   - Verify expected sections exist in correct order
   - Check parent-child relationships

2. **Numbering Validation**
   - Run `validate` command on output
   - Check sequential numbering

3. **Content Preservation**
   - Verify no content lost (diff-based comparison of section bodies)
   - Verify no unintended content added
   - Normalize whitespace before comparison

4. **Lint Validation**
   - Run linter on output
   - Check for introduced errors

5. **Expected Output Comparison** (when applicable)
   - Compare against `expected_file` for deterministic problems
   - Use for atomic operations with single correct answer

### 6.2 LLM-as-Judge (Fallback Only)

**Use sparingly.** LLM-as-judge adds variance, latency, and cost. Only invoke
when automated checks cannot determine correctness—for example, when multiple
valid restructurings exist or semantic equivalence matters more than exact match.

```python
def llm_judge_verify(problem, output):
    """Fallback for cases where automated checks are insufficient."""
    prompt = f"""
    You are evaluating whether an LLM correctly completed a markdown editing task.
    
    Original Document:
    {problem.input_document}
    
    Instruction:
    {problem.instruction}
    
    Output Document:
    {output}
    
    Evaluate:
    1. Did the edit follow the instruction correctly? (yes/no)
    2. Was any content unintentionally changed? (yes/no)
    3. Is the document structure valid? (yes/no)
    4. Overall score (0-100)
    
    Respond in JSON format.
    """
```

### 6.3 Human Validation (Calibration Only)

For ground truth calibration, not routine scoring:
- Randomly sample 10% of problems
- Have 2+ human annotators verify
- Use to calibrate automated check accuracy
- Run once during benchmark development, not per evaluation

## 7. Experimental Design

### 7.1 Conditions to Test

| Condition                    | Description                            |
|------------------------------|----------------------------------------|
| Baseline (no tools)          | Raw LLM with file_editor only          |
| OpenHands (standard)         | OpenHands without markdown tool        |
| OpenHands + Markdown Tool    | OpenHands with the specialized tool    |
| Claude Code                  | Anthropic's coding assistant           |
| Cursor / Other IDEs          | IDE-integrated assistants              |

### 7.2 Models to Test

| Provider   | Models                                      |
|------------|---------------------------------------------|
| Anthropic  | Claude 3.5 Sonnet, Claude 4 Opus            |
| OpenAI     | GPT-4o, o1-preview, o3-mini                 |
| Google     | Gemini 2.0 Flash, Gemini 2.0 Pro            |
| Open       | Llama 3.3 70B, DeepSeek V3                  |

### 7.3 Experimental Protocol

1. **Randomization**: Shuffle problem order for each run
2. **Independence**: Fresh conversation/context for each problem
3. **Reproducibility**: Fixed random seeds, logged prompts
4. **Blinding**: Automated evaluation where possible

### 7.4 Data Collection

For each run, record:
- Problem ID
- Condition (model + tools)
- Input tokens
- Output tokens
- Wall-clock time
- Tool calls (names, arguments, responses)
- Final output
- Verification results
- Errors/exceptions

## 8. Dataset Structure

### 8.1 Directory Layout

```
benchmarks/markdown/
├── data/
│   ├── problems/                    # Actual markdown files
│   │   ├── short/
│   │   │   ├── struct-move-001_input.md
│   │   │   ├── struct-move-001_expected.md
│   │   │   ├── struct-move-002_input.md
│   │   │   └── ...
│   │   ├── medium/
│   │   │   └── ...
│   │   ├── long/
│   │   │   └── ...
│   │   └── very_long/
│   │       └── ...
│   ├── problems.jsonl               # Problem metadata (not file contents)
│   └── golden_set.jsonl             # 20-problem dev subset
├── run_infer.py                     # Main entry point
├── eval_infer.py                    # Scoring logic
├── config.py                        # Default settings
├── prompts/
│   └── default.j2                   # Prompt template
└── README.md
```

### 8.2 JSONL Format (Metadata Only)

The JSONL file contains problem metadata with **file references**, not embedded
content. This allows markdown files to remain as readable `.md` files:

```jsonl
{"instance_id": "struct-move-001", "category": "structural", "operation": "move", "complexity": "atomic", "size": "short", "instruction": "Move section '3.2 Error Handling' to appear after section '2.1 Overview'. Update all section numbers.", "input_file": "short/struct-move-001_input.md", "expected_file": "short/struct-move-001_expected.md", "verification": {"numbering_valid": true, "content_preserved": true}}
{"instance_id": "toc-update-001", "category": "toc", "operation": "toc_update", "complexity": "atomic", "size": "medium", "instruction": "The table of contents is out of date. Update it to match current sections.", "input_file": "medium/toc-update-001_input.md", "expected_file": "medium/toc-update-001_expected.md", "verification": {"toc_valid": true}}
```

### 8.3 Problem Schema

```python
class Problem(BaseModel):
    instance_id: str                    # Unique identifier
    category: Literal["structural", "hierarchy", "numbering", 
                      "toc", "formatting", "multi-op", "error-recovery"]
    operation: str                      # Primary operation(s)
    complexity: Literal["atomic", "compound", "complex"]
    size: Literal["short", "medium", "long", "very_long"]
    instruction: str                    # Natural language instruction
    input_file: str                     # Relative path to input markdown
    expected_file: str                  # Relative path to expected output
    verification: dict                  # Automated verification criteria
```

## 9. OpenHands Harness Integration

### 9.1 Evaluation Class

Extends the OpenHands `Evaluation` abstract base class:

```python
from benchmarks.utils.evaluation import Evaluation
from benchmarks.utils.models import EvalInstance, EvalOutput

class MarkdownEvaluation(Evaluation):
    DATA_DIR = Path(__file__).parent / "data" / "problems"
    
    def prepare_instances(self) -> List[EvalInstance]:
        """Load problem metadata from JSONL."""
        df = get_dataset(
            dataset_name=str(Path(__file__).parent / "data" / "problems.jsonl"),
            split="train",
            eval_limit=self.metadata.eval_limit,
        )
        return [
            EvalInstance(id=row["instance_id"], data=row.to_dict()) 
            for _, row in df.iterrows()
        ]
    
    def prepare_workspace(
        self, 
        instance: EvalInstance, 
        resource_factor: int = 1,
        forward_env: list[str] | None = None,
    ) -> RemoteWorkspace:
        """Create workspace and copy input document."""
        workspace = DockerWorkspace(
            server_image=EVAL_AGENT_SERVER_IMAGE,
            working_dir="/workspace",
            forward_env=forward_env or [],
        )
        
        # Copy input markdown to workspace
        input_path = self.DATA_DIR / instance.data["input_file"]
        workspace.file_upload(str(input_path), "/workspace/document.md")
        
        return workspace
    
    def evaluate_instance(
        self, 
        instance: EvalInstance, 
        workspace: RemoteWorkspace
    ) -> EvalOutput:
        """Run agent and collect results."""
        # Configure tools based on condition
        tools = self._get_tools_for_condition()
        
        agent = Agent(llm=self.metadata.llm, tools=tools)
        conversation = Conversation(
            agent=agent,
            workspace=workspace,
            max_iteration_per_run=self.metadata.max_iterations,
        )
        
        # Build instruction
        instruction = self._build_instruction(instance)
        conversation.send_message(instruction)
        run_conversation_with_fake_user_response(conversation)
        
        # Get output
        result = workspace.execute_command("cat /workspace/document.md")
        output_content = result.stdout
        
        return EvalOutput(
            instance_id=instance.id,
            test_result={
                "output": output_content,
                "expected_file": instance.data["expected_file"],
            },
            instruction=instruction,
            history=list(conversation.state.events),
            metrics=conversation.conversation_stats.get_combined_metrics(),
        )
```

### 9.2 Condition Configuration

Support for the three experimental conditions:

```python
class ToolCondition(Enum):
    BASELINE = "baseline"       # file_editor, bash only
    SDK_TOOL = "sdk_tool"       # + MarkdownDocumentTool
    CLI_TOOL = "cli_tool"       # + md-tool in PATH

def get_tools_for_condition(condition: ToolCondition) -> list[Tool]:
    base_tools = get_default_tools(enable_browser=False)
    
    if condition == ToolCondition.BASELINE:
        return base_tools
    elif condition == ToolCondition.SDK_TOOL:
        return base_tools + [MarkdownDocumentTool]
    elif condition == ToolCondition.CLI_TOOL:
        # CLI tool installed in workspace, no SDK tool
        return base_tools
```

### 9.3 CLI Tool Installation (Condition C)

For the CLI condition, install `md-tool` in the workspace:

```python
def prepare_workspace_with_cli(workspace: RemoteWorkspace):
    """Install md-tool CLI for Condition C."""
    # Install the CLI tool
    workspace.execute_command("pip install lxa-md-tool")
    
    # Verify installation
    result = workspace.execute_command("md-tool --help")
    assert result.exit_code == 0
```

### 9.4 Scoring Implementation

```python
# eval_infer.py
def score_instance(output: EvalOutput, data_dir: Path) -> dict:
    """Score a single instance."""
    output_content = output.test_result["output"]
    expected_path = data_dir / output.test_result["expected_file"]
    expected_content = expected_path.read_text()
    
    # Use markdown tool for structural validation
    parser = MarkdownParser()
    output_parsed = parser.parse_content(output_content)
    
    numberer = SectionNumberer()
    numbering_result = numberer.validate(
        output_parsed.sections, 
        output_parsed.toc_section
    )
    
    toc_manager = TocManager()
    toc_result = toc_manager.validate_toc(output_content)
    
    # Content preservation check
    content_preserved = check_content_preserved(expected_content, output_content)
    
    # Overall pass
    passed = (
        numbering_result.valid and 
        toc_result.valid and 
        content_preserved
    )
    
    return {
        "passed": passed,
        "numbering_valid": numbering_result.valid,
        "toc_valid": toc_result.valid,
        "content_preserved": content_preserved,
        "numbering_issues": len(numbering_result.issues),
    }
```

## 10. Implementation Plan

### 10.1 Phase 1: Problem Generation (2-3 weeks)

- [ ] Create document templates at each size
- [ ] Implement programmatic corruption functions
- [ ] Generate atomic problems (160 problems)
- [ ] Generate compound problems (110 problems)
- [ ] Generate complex problems (80 problems)
- [ ] Create verification rules for each problem
- [ ] Build golden set (20 problems) for dev iteration
- [ ] Review and validate problem set

### 10.2 Phase 2: CLI Tool Implementation (1 week)

- [ ] Create `md-tool` CLI wrapper
- [ ] Ensure feature parity with SDK tool
- [ ] Package for pip installation
- [ ] Test in isolated environment

### 10.3 Phase 3: Evaluation Harness (1-2 weeks)

- [ ] Implement MarkdownEvaluation class
- [ ] Add condition configuration
- [ ] Implement automated scoring
- [ ] Build metrics collection
- [ ] Create reporting scripts

### 10.4 Phase 4: Development Runs (1-2 weeks)

- [ ] Run golden set across all conditions
- [ ] Validate scoring accuracy
- [ ] Tune prompts and configuration
- [ ] Identify and fix issues

### 10.5 Phase 5: Full Evaluation (2-3 weeks)

- [ ] Run full benchmark (300+ problems × 3 conditions × 3 runs)
- [ ] Statistical analysis
- [ ] Test model generalization
- [ ] Write up results

## 11. Expected Outcomes

See [Tool Integration Experiment Design](tool-integration-experiment.md) for
detailed hypotheses and predictions.

### 11.1 Summary Hypotheses

1. **H1**: The Markdown Document Tool improves success rate by 15-30% compared
   to no tools for structural operations.

2. **H2**: Token efficiency improves by 30-50% for complex multi-operation
   tasks (fewer retries, cleaner edits).

3. **H3**: Very long documents show the largest improvement (context management
   is harder without tools).

4. **H4**: Complex multi-operation tasks benefit most from specialized tools
   (atomic tasks may not differ significantly).

### 11.2 Risk Factors

- **Tool overhead**: Adding tools might confuse the model or add latency
- **Benchmark contamination**: Models may have seen similar problems in training
- **Evaluation variance**: LLM-as-judge may have biases

## 12. Open Questions

1. Should we include "adversarial" problems (e.g., malformed markdown)?
2. How to weight different problem types in aggregate scores?
3. Should we test with different system prompts?
4. Include human preference evaluation?

## 13. Resources Required

| Resource               | Estimate                               |
|------------------------|----------------------------------------|
| Problem Generation     | 2-3 person-weeks                       |
| Harness Development    | 1-2 person-weeks                       |
| API Costs (full run)   | ~$1,000-2,000 per condition            |
| Human Evaluation       | ~40 hours for calibration subset       |

## 14. Problem Construction Methodology

### 14.1 The "Reverse Engineering" Approach

Rather than manually creating before/after pairs, we start with finished
documents and work backwards:

```
Finished Document → [Corruption] → Problem State
        ↓                              ↓
   Ground Truth                   Benchmark Problem
```

**Why this works well:**
1. **Guarantees solvable problems** - We know a solution exists
2. **Automated ground truth** - The original IS the answer
3. **Scalable** - Corruption can be automated
4. **Deterministic verification** - Can diff against original

### 14.2 Programmatic Corruption Functions

```python
def corrupt_numbering(doc: str) -> tuple[str, str]:
    """Introduce numbering errors."""
    # Parse sections, scramble numbers
    corrupted = swap_section_numbers(doc, "2.1", "3.2")
    instruction = "Fix the section numbering in this document."
    return corrupted, instruction

def corrupt_toc(doc: str) -> tuple[str, str]:
    """Make TOC stale."""
    # Add a section but don't update TOC
    corrupted = add_section_without_toc_update(doc, 
        heading="## 5. New Section",
        after="## 4. Testing"
    )
    instruction = "The table of contents is out of date. Update it."
    return corrupted, instruction

def corrupt_structure(doc: str) -> tuple[str, str]:
    """Move a section to wrong location."""
    section, original_after = move_section_randomly(doc)
    instruction = f"Move '{section}' back to appear after '{original_after}'."
    return corrupted, instruction

def corrupt_hierarchy(doc: str) -> tuple[str, str]:
    """Break heading levels."""
    corrupted = change_heading_level(doc, "### 2.1.1 Details", "## 2.1.1 Details")
    instruction = "Fix the heading levels - section 2.1.1 should be a subsection."
    return corrupted, instruction
```

### 14.3 LLM-Assisted Instruction Generation

For more natural, varied instructions:

```python
def generate_natural_instruction(
    original: str, 
    corrupted: str, 
    corruption_type: str
) -> str:
    """Use LLM to generate human-like instruction."""
    prompt = f"""
    A markdown document was modified with this type of change: {corruption_type}
    
    Generate a natural instruction (1-2 sentences) that a human might give 
    to fix it. Vary your phrasing - sometimes be specific, sometimes vague.
    
    Examples of style variation:
    - Precise: "Renumber section 3.2 to be 4.1"
    - Natural: "Fix the broken section numbers"  
    - Vague: "Clean up this document's structure"
    - Contextual: "I added a section but forgot to update the TOC"
    
    Corruption type: {corruption_type}
    Document excerpt (first 500 chars): {corrupted[:500]}
    
    Generate instruction:
    """
    return llm.generate(prompt)
```

### 14.4 Problem Validation

Before adding a problem to the dataset:

```python
def validate_problem(original: str, corrupted: str, instruction: str) -> bool:
    """Ensure problem is valid and solvable."""
    # 1. Corruption actually changed something
    assert original != corrupted, "Corruption had no effect"
    
    # 2. Original validates correctly
    orig_result = validate_document(original)
    assert orig_result.valid, "Original document has issues"
    
    # 3. Corrupted has detectable issues
    corr_result = validate_document(corrupted)
    assert not corr_result.valid or has_structural_diff(original, corrupted), \
        "Corruption not detectable"
    
    # 4. Instruction is non-empty and reasonable length
    assert 10 < len(instruction) < 500, "Instruction length out of range"
    
    return True
```

## 15. Development Workflow

### 15.1 The Golden Set

A hand-picked subset of 20 problems for rapid iteration during development:

**Selection criteria:**
- At least one problem per operation type
- Include known edge cases (things that broke before)
- Mix of difficulty levels (6 easy, 10 medium, 4 hard)
- Mix of document sizes (10 short, 6 medium, 4 long)
- Deterministic outcomes (clear right/wrong)

**Golden set composition:**
```
Golden Set (20 problems):
├── Structural (6)
│   ├── move_simple          # Easy baseline
│   ├── move_with_children   # Tests recursive handling
│   ├── insert_section       # Basic insert
│   ├── delete_section       # Basic delete
│   ├── promote_section      # Hierarchy change
│   └── demote_section       # Hierarchy change
├── Numbering (4)
│   ├── renumber_simple      # Sequential fix
│   ├── renumber_after_insert # Numbers after structural change
│   ├── renumber_deep_nesting # 4+ levels deep
│   └── validate_broken      # Detection only
├── TOC (4)
│   ├── toc_create          # From scratch
│   ├── toc_update_stale    # Existing but outdated
│   ├── toc_with_depth      # Depth parameter
│   └── toc_remove          # Delete existing
├── Formatting (3)
│   ├── rewrap_long_lines   # Line length
│   ├── lint_and_fix        # Multiple small issues
│   └── cleanup_combined    # Full cleanup pass
└── Multi-op (3)
    ├── restructure_simple  # 2-3 operations
    ├── restructure_medium  # 3-4 operations
    └── restructure_complex # 5+ operations
```

### 15.2 Development Run Estimates

| Problems | Tokens (est.) | Cost (Claude) | Time | Use Case |
|----------|---------------|---------------|------|----------|
| 10 | 100-200K | $0.30-0.60 | ~5 min | Quick sanity check |
| 20 | 200-400K | $0.60-1.20 | ~10 min | Golden set |
| 50 | 500K-1M | $1.50-3.00 | ~25 min | PR validation |
| 100 | 1-2M | $3-6 | ~1 hour | Pre-release check |
| 300 | 3-6M | $10-20 | ~3 hours | Full benchmark |

*Costs assume Claude 3.5 Sonnet pricing (~$3/1M input, $15/1M output)*

### 15.3 Development Iteration Cycle

```
1. Make code change to markdown tool
              │
              ▼
2. Run golden set (20 problems, ~10 min)
   $ python run_infer.py --dataset golden_set.jsonl
              │
      ┌───────┴───────┐
      ▼               ▼
  Pass rate        Pass rate
  dropped?         improved?
      │               │
      ▼               ▼
  Debug/fix       Continue
      │               │
      └───────┬───────┘
              ▼
3. Run PR validation (50 problems, ~25 min)
   $ python run_infer.py --dataset problems.jsonl --n_limit 50
              │
              ▼
4. If significant change: Run full benchmark before merge
```

### 15.4 Interpreting Results at Small Scale

With 20 problems, statistical power is limited:

| Observed Difference | Interpretation |
|---------------------|----------------|
| 4+ problems (20%+) | **Clear signal** - likely real difference |
| 2-3 problems (10-15%) | **Possible signal** - run more problems |
| 0-1 problems (<10%) | **Noise** - cannot distinguish |

**Key principle**: Use golden set for regression detection and directional 
signals, not precise measurement. Save full runs for final validation.

## 16. LXA Markdown Tool Operations Reference

Quick reference mapping tool operations to benchmark problem categories:

| Tool Command | Description | Problem Category |
|--------------|-------------|------------------|
| `validate` | Check structure and numbering | Numbering, Error Recovery |
| `renumber` | Fix sequential section numbers | Numbering |
| `parse` | Show document structure (sections, levels) | (Diagnostic only) |
| `toc_update` | Generate or update table of contents | TOC |
| `toc_remove` | Remove existing table of contents | TOC |
| `move` | Move section to new location | Structural |
| `insert` | Insert new section | Structural |
| `delete` | Delete section | Structural |
| `promote` | Increase heading level (### → ##) | Hierarchy |
| `demote` | Decrease heading level (## → ###) | Hierarchy |
| `rewrap` | Normalize paragraph line lengths | Formatting |
| `lint` | Check for formatting issues | Formatting |
| `fix` | Auto-fix detected issues | Formatting |
| `cleanup` | All-in-one: rewrap + fix + renumber + toc update | Multi-op |

### Operation Parameters

```
# Validation / Inspection
validate file=<path>
parse file=<path>
lint file=<path>

# Numbering
renumber file=<path>

# Table of Contents
toc_update file=<path> depth=<1-6, default 3>
toc_remove file=<path>

# Section Operations  
move file=<path> section=<title or number> position=<before|after> target=<title or number>
insert file=<path> heading=<text> level=<1-6> position=<before|after> target=<title or number>
delete file=<path> section=<title or number>
promote file=<path> section=<title or number>
demote file=<path> section=<title or number>

# Formatting
rewrap file=<path> width=<chars, default 80>
fix file=<path>
cleanup file=<path>
```

## 17. Appendix: Sample Problems

### A.1 Short Document Template

```markdown
# Feature Specification

## 1. Overview

Brief description of the feature.

## 2. Requirements

### 2.1 Functional Requirements

- Requirement A
- Requirement B

### 2.2 Non-Functional Requirements

- Performance: < 100ms response time
- Availability: 99.9% uptime

## 3. Implementation

Implementation details here.

## 4. Testing

Testing strategy.
```

### A.2 Problem: Section Move

**Instruction**: "Move section '2.2 Non-Functional Requirements' to become
section 3, renaming it to 'Performance Requirements'. Update all section
numbers accordingly."

**Verification**:
- Section order changed
- Numbers updated (2.2 → 3, old 3 → 4, old 4 → 5)
- Content preserved

### A.3 Problem: TOC Generation

**Instruction**: "This document is missing a table of contents. Add one after
the title that includes all sections down to level 3 headings."

**Verification**:
- TOC section exists
- Contains all h2 and h3 headings
- Links are correct (if applicable)
