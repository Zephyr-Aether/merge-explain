---
name: "merge-explain"
description: "Analyze and resolve git merge conflicts with AI. Use when the user asks to analyze branch differences, understand conflicting changes between branches, auto-resolve merge conflicts, or get a structured merge report."
---

## Prerequisites

1. Python 3.9+ must be installed. Check `python3 --version`. If missing, ask the user to install Python.
2. API key must be configured. Check `.env` file exists with `OPENAI_API_KEY`. If missing, ask user to copy `.env.example` to `.env` and fill in the key.
3. The current directory must be a git repository. Check with `git rev-parse --git-dir`.

## Installation

If the tool is not yet installed:

```bash
cd /path/to/merge-explain
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Workflow

### 1. Analyze conflicts between two branches

Use the MCP tool `analyze_conflicts` or the CLI command:

```bash
./run.sh analyze <branch-a> <branch-b>
```

The output is a structured report containing:

- **branch_a_summary / branch_b_summary**: What each branch changed, organized by file and function
- **conflicts**: List of conflict points, each with:
  - `file_path`: Where the conflict occurs
  - `risk`: Risk level (see below)
  - `branch_a_action / branch_b_action`: What each branch did
  - `suggestion`: AI's recommended handling
  - `code_snippet`: The actual conflicting code lines
- **overall_advice**: One of `auto_merge` / `manual_review` / `blocked`
- **reasoning**: Why this advice was given

### 2. Auto-resolve conflicts

After reviewing the analysis, use the MCP tool `resolve_conflicts` or:

```bash
# Preview only (default)
./run.sh resolve <branch-a> <branch-b>

# Apply changes
./run.sh resolve <branch-a> <branch-b> --apply

# Reuse analysis suggestions
./run.sh resolve <branch-a> <branch-b> --from-report report.json
```

The tool will:
1. Trigger `git merge` to detect conflicts
2. Parse `<<<<<<<` / `=======` / `>>>>>>>` markers
3. Extract BASE / branch_a / branch_b versions with context
4. Call LLM to generate merged code for each conflict block
5. Apply changes with syntax checking

### 3. List branches

Use the MCP tool `list_branches` to see available branches.

### 4. Quick test

Run the sample analysis to verify the tool works (no API key needed):

```bash
./run.sh sample
```

## Risk Level Interpretation

| Level | Meaning | Action |
|-------|---------|--------|
| 🟢 green | Different files/functions, no logical overlap | Safe to auto-merge |
| 🟡 yellow | Same file/function, different aspects | Review recommended |
| 🔴 red | Same line or mutually exclusive logic | Must resolve manually |

## Output Formats

The `analyze` command supports:

- `terminal` (default): Rich colored table output
- `html`: Self-contained HTML report (use `-o report.html`)
- `markdown`: Markdown report (use `-o report.md`)

## Advanced Options

```bash
./run.sh analyze <branch-a> <branch-b> -v          # Show raw diff alongside report
./run.sh analyze <branch-a> <branch-b> --no-cache   # Force re-analysis
./run.sh resolve <branch-a> <branch-b> --risk-threshold green  # Only auto-solve green conflicts
```

## Safety

- `analyze` never modifies files
- `resolve` defaults to dry-run (preview only); use `--apply` to write
- Auto-backup before writing; syntax check rolls back on failure
- RED risk conflicts are always skipped in auto-resolve
