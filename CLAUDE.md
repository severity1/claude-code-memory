# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- AUTO-MANAGED: project-description -->
## Overview

**auto-memory** - automatically maintains CLAUDE.md files as codebases evolve. Tagline: "Your CLAUDE.md, always in sync. Minimal tokens. Zero config. Just works."

Watches what Claude Code edits, deletes, and moves - then quietly updates project memory in the background. Uses PostToolUse hooks to track Edit/Write/Bash operations (including rm, mv, git rm, git mv, unlink), stores changes in .claude/auto-memory/dirty-files, then triggers isolated memory-updater agent to process and update memory sections with detected patterns, conventions, and architecture insights. Processing runs in separate context window, consuming no main session tokens.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->
## Build & Development Commands

- `uv sync` - Install dependencies (uses uv package manager)
- `uv run pytest` - Run full test suite
- `uv run pytest tests/test_hooks.py -v` - Run specific test file with verbose output
- `uv run ruff check .` - Lint code (E, F, I, N, W, UP rules, 100 char line length)
- `uv run ruff format .` - Format code to style standards
- `uv run mypy .` - Type checking in strict mode

**Package**: Published as `claude-code-auto-memory` on PyPI with minimal dependencies (dev dependencies: pytest, pyyaml, ruff, mypy)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Architecture

```
claude-code-auto-memory/
├── scripts/           # Python hook scripts
│   ├── post-tool-use.py  # Tracks edited files; detects git commits for context enrichment
│   └── stop.py           # Blocks stop if dirty files exist, triggers memory-updater
├── skills/            # Skill definitions (SKILL.md files)
│   ├── codebase-analyzer/  # Analyzes codebase, generates CLAUDE.md templates
│   ├── memory-processor/   # Processes file changes, updates CLAUDE.md sections
│   └── shared/references/  # Shared reference files for skills
│       └── guidelines.md   # Claude Code memory guidelines (imported by skills)
├── commands/          # Slash commands (markdown files)
│   ├── init.md               # /auto-memory:init - Initialize auto-memory plugin
│   ├── calibrate.md          # /auto-memory:calibrate - Full codebase recalibration
│   ├── sync.md               # /auto-memory:sync - Sync manual file changes detected by git
│   └── status.md             # /auto-memory:status - Show memory status
├── agents/            # Agent definitions
│   └── memory-updater.md  # Orchestrates CLAUDE.md updates with 6-phase workflow
├── hooks/             # Hook configuration
│   └── hooks.json        # PostToolUse and Stop hook definitions
└── tests/             # pytest test suite
```

**Data Flow**: Edit/Write/Bash (rm, mv, git rm, git mv, unlink) -> post-tool-use.py -> .claude/auto-memory/dirty-files -> stop.py -> memory-updater agent -> memory-processor skill -> CLAUDE.md updates

**State Files** (in `.claude/auto-memory/`):
- `dirty-files` - Pending file list with optional inline commit context format: `/path [hash: message]`
- `config.json` - Trigger mode configuration (default or gitmode)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Code Conventions

- **Python**: Target Python 3.9+, use type hints, strict mypy mode
- **Line length**: 100 characters max (ruff configuration)
- **Linting**: Use ruff (E, F, I, N, W, UP rules)
- **Imports**: Sorted alphabetically (ruff I rules)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Docstrings**: Triple-quoted, describe purpose at module/function level
- **Testing**: pytest with test_ prefix and `test_*` function names, fixtures in conftest or test class methods
- **Type checking**: Enabled with mypy in strict mode
- **Command YAML**: Frontmatter requires `description` field; `name` field is optional (derived from filename)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Detected Patterns

- **Hook Scripts**: Produce no stdout output (minimal token cost design)
- **File Filtering**: Exclude `.claude/` directory and CLAUDE.md files to prevent tracking and infinite loops
- **Bash Operation Tracking**: Detects rm, mv, git rm, git mv, unlink commands to track file deletions/moves; use `shlex.split()` for robust command tokenization
- **Command Skip List**: Filter read-only commands (ls, git diff, npm, etc.) before processing to reduce noise
- **Path Resolution**: Convert relative paths to absolute using project_dir context, then resolve symlinks
- **CLAUDE.md Markers**: Use `<!-- AUTO-MANAGED: section-name -->` and `<!-- END AUTO-MANAGED -->` for auto-updated sections
- **Manual Sections**: Use `<!-- MANUAL -->` markers for user-editable content
- **Skill Templates**: Use `{{PLACEHOLDER}}` syntax for variable substitution
- **File Tracking**: Dirty files stored in `.claude/auto-memory/dirty-files`, one path per line with optional inline commit context: `/path/to/file [hash: message]`
- **Deduplication Logic**: Read dirty-files into dict (path -> full line), update existing entries with commit context instead of appending duplicates; commit context always overwrites plain path entries; format string extracted to separate variable for code clarity
- **Trigger Modes**: Config-driven behavior - `default` mode tracks all Edit/Write/Bash operations; `gitmode` only triggers on git commits; default mode used if config missing
- **Git Commit Enrichment**: When git commit detected, enriches each file path with inline commit context for semantic context during updates
- **Stop Hook UX**: Blocks at turn end if dirty files exist; instructs Claude to spawn memory-updater agent using Task tool with formatted file list; suggests reading root CLAUDE.md after agent completes to refresh context
- **Memory-Updater Agent**: Orchestrates CLAUDE.md updates through 6-phase workflow using sonnet model - load dirty files (parsing inline commit context format `/path [hash: message]`), gather file context with imports, extract git insights, discover CLAUDE.md targets, invoke memory-processor skill, cleanup dirty-files; processes max 7 files per run with truncated git diffs; designed for minimal token consumption in isolated context
- **Memory Processor Updates**: Skill analyzes changed files and updates relevant AUTO-MANAGED sections with detected patterns, architecture changes, and new commands; uses shared reference file (skills/shared/references/guidelines.md) for Claude Code memory guidelines; follows content rules (specific, concise, structured); preserves manual sections and maintains < 500 line target; excludes moving targets (version numbers, test counts, dates, metrics) that become stale
- **Content Removal Verification**: Before removing documented content (patterns, conventions, architecture, build commands, dependencies), verifies absence using Grep across codebase; reads current CLAUDE.md section, searches for each missing item in relevant directories excluding node_modules/vendor/.git; keeps documentation if item exists elsewhere, removes only if not found anywhere; distinguishes conventions (explicit human-decided rules) from patterns (AI-detected recurring structures)
- **Stale Command Detection**: Memory processor compares documented commands against commands that actually executed successfully; updates documented commands to match what worked (e.g., `python pytest` -> `python -m pytest`, `pytest tests/` -> `uv run pytest`); sources from successful Bash tool executions in session context or git commit history
- **Skill Organization**: Both codebase-analyzer and memory-processor skills use import syntax (@../shared/references/guidelines.md) to load shared guidelines, keeping skill files lean via progressive disclosure pattern
- **Test Coverage**: Use subprocess to invoke hooks, verify zero output behavior, test file filtering logic; TestGitCommitContext class verifies git commit handling, file extraction, and commit context enrichment; initialize test git repos with initial commit for diff-tree parent reference

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->
## Git Insights

- Main branch workflow
- Feature branches for new functionality
- Commit messages describe the change purpose

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->
## Best Practices

- Run `uv run pytest` before committing changes
- Keep hook scripts silent (no output) to minimize token usage
- Use AUTO-MANAGED markers for sections that should be auto-updated
- Keep CLAUDE.md under 500 lines; use imports for detailed specs
- Test hook scripts with subprocess to verify zero output behavior

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Custom Notes

Add project-specific notes here. This section is never auto-modified.

<!-- END MANUAL -->
