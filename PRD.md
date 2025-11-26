# Product Requirements Document: claude-code-memory

## Overview

**Product Name**: claude-code-memory
**Version**: 1.0.0
**Type**: Claude Code Plugin
**Philosophy**: Plug-and-play, zero-config, smart defaults

## Problem Statement

Claude Code users struggle with context management across sessions. CLAUDE.md files become stale as codebases evolve, leading to:
- Outdated architecture documentation
- Missing build/test commands after package changes
- Inconsistent code conventions
- Lost insights from git history and development decisions

Developers manually update CLAUDE.md files, which is time-consuming and often forgotten.

## Solution

A Claude Code plugin that automatically maintains CLAUDE.md files using a token-efficient architecture:
- Tracking file changes via lightweight PostToolUse hook (zero token cost)
- Batching changes at end of turn via Stop hook
- Processing all changes in isolated agent context (doesn't bloat main conversation)
- Analyzing code patterns and conventions
- Extracting insights from git history when relevant
- Updating relevant documentation sections
- Managing hierarchical CLAUDE.md structure across project subdirectories

## Target Users

- **Solo developers**: Want their project context to stay fresh without manual maintenance
- **Development teams**: Need consistent, up-to-date documentation across the codebase
- **Large codebases**: Require hierarchical context management across multiple modules

## Core Features

### 1. Intelligent Initialization (`/memory-init`)

**User Story**: As a developer, I want to quickly set up auto-managed CLAUDE.md files so I don't have to manually create and maintain them.

**Functionality**:
- Interactive wizard that analyzes the codebase
- Detects existing CLAUDE.md and asks how to handle it (migrate/backup/merge/cancel)
- Fetches best practices from docs.claude.com
- Shows findings: detected patterns, suggested sections, subtree candidates
- User approves/modifies before generation
- Creates CLAUDE.md with marker-based sections

**Acceptance Criteria**:
- Wizard completes in under 60 seconds for typical projects
- Existing content is never lost without user consent
- Generated CLAUDE.md includes all relevant sections for the project type

### 2. End-of-Turn Synchronization

**User Story**: As a developer, I want my CLAUDE.md to update automatically when I make changes so it always reflects the current state.

**Functionality**:
- PostToolUse hook (Edit|Write matcher) appends file paths to `.claude/.dirty-files`
- Hook has zero token cost (no Claude context injection)
- Stop hook fires at end of turn, checks for dirty files
- If dirty files exist, Stop hook asks Claude to spawn memory-updater agent
- Agent runs in isolated context (doesn't bloat main conversation)
- Agent analyzes changed files, uses git when historical context is needed
- Agent updates relevant CLAUDE.md sections, clears dirty files
- Preserves manual content outside auto-managed markers

**Acceptance Criteria**:
- File paths tracked within 10ms of edit (bash append only)
- All changes from turn processed in single agent invocation
- Main conversation context stays clean
- Manual content is never overwritten
- Updates are accurate and contextually relevant

### 3. Pattern Detection

**User Story**: As a developer, I want the plugin to learn my code patterns so new team members understand our conventions.

**Functionality**:
- AI-powered pattern detection using Claude Code Skills
- Auto-invoked when Claude analyzes code
- Detects: naming conventions, import patterns, architectural styles, common practices
- Auto-adds patterns to Code Conventions section

**Acceptance Criteria**:
- Detects patterns with 90%+ accuracy
- Filters out one-off patterns (only persistent patterns added)
- Patterns are documented clearly and concisely

### 4. Hierarchical Structure Management

**User Story**: As a developer working in a monorepo, I want subdirectory-specific CLAUDE.md files so each module has its own context.

**Functionality**:
- AI infers when to create subtree CLAUDE.md files
- Heuristics: significant file count, distinct frameworks, architectural boundaries
- Creates subtree templates automatically
- Maintains consistency between root and subtree documentation

**Acceptance Criteria**:
- Subtrees created only when genuinely needed (no noise)
- Subtree CLAUDE.md inherits relevant root context
- Clear separation between global and module-specific content

### 5. Manual Control Commands

**User Story**: As a developer, I want to manually trigger updates and check status when needed.

**Functionality**:
- `/memory-sync` - Force recalibration of all CLAUDE.md files
- `/memory-status` - View last sync time, detected patterns, processing queue

**Acceptance Criteria**:
- Commands respond instantly (< 500ms)
- Status shows actionable information
- Sync command handles large projects efficiently

## Auto-Managed Sections

All CLAUDE.md files include marker-based sections:

1. **Build/Test Commands** - Extracted from package.json, Makefile, scripts
2. **Architecture Overview** - Directory structure, modules, components
3. **Code Conventions** - Naming, imports, style patterns
4. **Git Insights** - Decisions from commits, breaking changes, refactoring notes
5. **Detected Patterns** - AI-discovered coding patterns
6. **Best Practices** - From official Claude Code documentation
7. **Project Description** - Auto-generated overview

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  PostToolUse Hook (Edit|Write matcher)                          │
│  - Appends file path to .claude/.dirty-files                    │
│  - NO output (zero token cost)                                  │
│  - Pure bash, no Claude involvement                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
              .claude/.dirty-files
              (simple text file, one path per line)
                       │
           (accumulates during Claude's turn)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stop Hook (fires when Claude's turn ends)                      │
│  - Checks if .dirty-files exists and has content                │
│  - If empty/missing: pass through (turn ends normally)          │
│  - If files exist AND stop_hook_active=false:                   │
│    → Output: {"decision":"block","reason":"Spawn                │
│       memory-updater agent for: file1.ts, file2.ts..."}         │
│  - Claude sees reason → spawns agent via Task tool              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  memory-updater Agent (spawned via Task tool)                   │
│  - Runs in ISOLATED context (doesn't bloat main convo)          │
│  - Lightweight orchestrator (~50 tokens)                        │
│  - Invokes memory-processor skill for actual processing         │
│  - Returns summary to main conversation                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  memory-processor Skill (invoked by agent)                      │
│  - PROGRESSIVE DISCLOSURE: loads only when invoked              │
│  - Reads .dirty-files, analyzes changes                         │
│  - Runs git commands if needed                                  │
│  - Updates relevant CLAUDE.md sections                          │
│  - Clears .dirty-files                                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
              Stop Hook fires again
              (stop_hook_active=true, passes through)
              Turn ends
```

**Why this architecture:**
- PostToolUse hook has zero token cost (pure bash, no Claude context)
- Stop hook provides natural batching at end of turn
- Agent runs in isolated context (doesn't pollute main conversation)
- **Progressive disclosure**: Skill instructions load only when invoked
- Single agent invocation per turn instead of N skill invocations for N edits
- `stop_hook_active` flag prevents infinite loops
- No external dependencies or cloud services required

**Reliability Note:** Per Claude Code documentation, the Stop hook's `reason` field guides Claude's behavior but "effectiveness depends on prompt quality rather than guaranteed compliance." The `/memory-sync` command provides a manual fallback if automatic updates don't trigger.

## Scope

### In Scope
- Project root CLAUDE.md
- Subtree CLAUDE.md files
- PostToolUse hook for change tracking (Edit|Write matcher, zero token cost)
- Stop hook for end-of-turn batch processing
- Dedicated agent for isolated CLAUDE.md updates
- Git history analysis within agent context
- Smart defaults (no config files)

### Out of Scope
- Global/user CLAUDE.md management (~/.claude/CLAUDE.md)
- CLAUDE.local.md (git-ignored personal notes)
- External file watcher (only Claude-made changes)
- Configuration files (plug-and-play only)
- Direct git commit hook tracking (unreliable PostToolUse for Bash)
- Cloud storage or external services
- Real-time per-edit processing (batched at turn end instead)

## Success Metrics

- **Time Saved**: 30+ minutes per week per developer on documentation maintenance
- **Adoption**: 70% of users keep plugin enabled after 1 week
- **Accuracy**: 90%+ accuracy on auto-generated content
- **Performance**: < 1 second update latency on file changes
- **Reliability**: Zero data loss incidents (manual content always preserved)

## Technical Constraints

- Must work with Claude Code plugin system
- Must use PostToolUse hooks with Edit|Write matcher (reliable, zero token cost)
- Must use Stop hook for end-of-turn batch processing
- Must use dedicated agent for processing (isolated context)
- Must use `stop_hook_active` flag to prevent infinite loops
- Must fetch from docs.claude.com (requires internet for best practices)
- Must preserve backward compatibility with existing CLAUDE.md files
- Must not rely on PostToolUse for Bash tool (known reliability issues)

## Non-Goals

- Managing user-global Claude Code settings
- Syncing across multiple machines (separate concern)
- Version control integration beyond git commit analysis
- Custom configuration DSL (keeping it simple)

## Future Considerations

- Integration with external file watchers for IDE changes
- Team collaboration features (shared pattern libraries)
- Analytics dashboard for documentation health
- Export to other documentation formats
