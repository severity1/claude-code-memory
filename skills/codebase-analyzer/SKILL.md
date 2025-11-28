---
name: codebase-analyzer
description: Analyze codebase structure and generate CLAUDE.md templates with user approval
---

# Codebase Analyzer

Analyze project structure and generate CLAUDE.md files interactively.

## Algorithm

### 1. Check Existing CLAUDE.md

If CLAUDE.md already exists, ask the user how to handle it:
- **Migrate**: Convert to auto-managed format (add markers)
- **Backup**: Create CLAUDE.md.backup and generate fresh
- **Merge**: Keep manual sections, add auto-managed sections
- **Cancel**: Abort initialization

### 2. Scan Directory Structure

Detect frameworks and build systems:
- `package.json` - Node.js/JavaScript
- `pyproject.toml`, `setup.py` - Python
- `Cargo.toml` - Rust
- `go.mod` - Go
- `Makefile` - Make-based builds
- `Dockerfile` - Container builds

Extract build/test/lint commands from config files.

### 3. Identify Subtree Candidates

Look for framework boundaries that warrant separate CLAUDE.md files:
- `src/` with 10+ source files
- `lib/` directory
- `packages/*` (monorepo packages)
- `apps/*` (monorepo applications)

### 4. Detect Code Patterns

Analyze source files for conventions:
- **Naming**: PascalCase, camelCase, snake_case usage
- **Imports**: ES6 modules, CommonJS, ordering patterns
- **Architecture**: Feature-based, layered, MVC patterns
- **Style**: Indentation, quotes, semicolons

### 5. Fetch Best Practices (Optional)

If network available, fetch from `https://docs.claude.com/en/docs/claude-code/best-practices`:
- Use WebFetch tool
- Extract relevant sections
- Cache for session

### 6. Present Findings

Use AskUserQuestion to confirm:
- Detected framework and commands
- Suggested subtree locations
- Detected patterns

### 7. Generate CLAUDE.md

Apply templates with detected values:
- Root: 150-200 lines max
- Subtrees: 50-75 lines max

## Templates

Reference the template files:

### Root Template
@templates/CLAUDE.root.md.template

### Subtree Template
@templates/CLAUDE.subtree.md.template

## User Interactions

Use AskUserQuestion for:
1. Existing CLAUDE.md handling (migrate/backup/merge/cancel)
2. Subtree location confirmation
3. Final approval before writing files

## Output

After generating files, report:
- Files created/modified
- Sections populated
- Any warnings or suggestions
