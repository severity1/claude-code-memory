---
description: Initialize CLAUDE.md memory structure for project with interactive wizard
---

Initialize auto-managed CLAUDE.md memory files for this project.

## Workflow

### Step 1: Configure Trigger Mode

Ask the user how auto-memory should trigger updates using AskUserQuestion:

**Question**: "How should auto-memory trigger CLAUDE.md updates?"

**Options**:
- **default** (recommended): Track file edits in real-time. Updates trigger after Edit/Write operations and file modifications (rm, mv, etc.). Best for most workflows.
- **gitmode**: Only trigger on git commits. Updates happen when you commit changes. Best for developers who commit frequently and prefer "if you didn't commit, it didn't happen" workflow.

Save the selection to `.claude/auto-memory/config.json`:
```json
{
  "triggerMode": "default"
}
```

### Step 2: Analyze Codebase

Invoke the `codebase-analyzer` skill to:
1. Analyze the codebase structure
2. Detect frameworks and build commands
3. Identify subtree candidates for monorepos
4. Detect code patterns and conventions

### Step 3: Generate CLAUDE.md

Guide the user through the setup process and confirm before writing any files.
