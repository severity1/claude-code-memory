---
name: memory-processor
description: Process file changes and update CLAUDE.md documentation sections
---

# Memory Processor

Process changed files from `.claude/.dirty-files` and update relevant CLAUDE.md sections.

## Algorithm

1. **Read dirty files**: Read `.claude/.dirty-files` and deduplicate paths
2. **Categorize changes**: For each file, determine which CLAUDE.md section(s) to update:
   - **BUILD**: `package.json`, `Makefile`, `*.config.*`, `Dockerfile`, `pyproject.toml`
   - **ARCHITECTURE**: `src/**/*.{ts,js,py,go}`, `lib/**/*`, new directories
   - **CONVENTIONS**: Any source file (for pattern detection)
3. **Gather context** (if needed):
   - `git log -1 --format="%s" -- <file>` - Recent commit message
   - `git diff HEAD~5 -- <file>` - Recent changes
4. **Update CLAUDE.md**: Modify relevant sections while preserving AUTO-MANAGED markers
5. **Clear queue**: Remove processed files from `.claude/.dirty-files`

## Marker Syntax

CLAUDE.md uses HTML comment markers for selective updates:

```markdown
<!-- AUTO-MANAGED: section-name -->
Content that will be automatically updated by this plugin
<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
Content that will never be touched by this plugin
<!-- END MANUAL -->
```

## Section Names

- `project-description` - Project overview and purpose
- `build-commands` - Build, test, lint, dev commands
- `architecture` - Directory structure, key components
- `conventions` - Naming patterns, import styles, code standards
- `patterns` - AI-detected coding patterns
- `git-insights` - Decisions from git commit history
- `best-practices` - From official Claude Code documentation

## Update Rules

1. **Only update relevant sections** - If package.json changed, update build-commands
2. **Preserve manual content** - Never modify content inside `<!-- MANUAL -->` blocks
3. **Maintain formatting** - Keep consistent markdown style
4. **Be concise** - Root CLAUDE.md should be 150-200 lines max

## Output

Return a brief summary:
- "Updated [section names] in CLAUDE.md based on changes to [file names]"
- "No updates needed - changes do not affect documented sections"
