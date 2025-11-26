# Technical Specification: claude-code-memory

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Claude Code Environment                       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │               claude-code-memory Plugin                      │ │
│  │                                                              │ │
│  │  ┌─────────────┐  ┌───────────────┐  ┌───────────────────┐  │ │
│  │  │  Commands   │  │    Agents     │  │      Hooks        │  │ │
│  │  │             │  │               │  │                   │  │ │
│  │  │ memory-init │  │ memory-       │  │ post-tool-use     │  │ │
│  │  │ memory-sync │  │ updater       │  │ (Edit|Write)      │  │ │
│  │  │ memory-     │  │ (orchestrator)│  │       │           │  │ │
│  │  │ status      │  │       │       │  │       ▼           │  │ │
│  │  │             │  │       ▼       │  │ .dirty-files      │  │ │
│  │  └─────────────┘  │ ┌───────────┐ │  │       │           │  │ │
│  │                   │ │  Skills   │ │  │       ▼           │  │ │
│  │                   │ │           │ │  │ stop hook         │  │ │
│  │                   │ │ memory-   │ │  │ (end of turn)     │  │ │
│  │                   │ │ processor │ │  └───────┬───────────┘  │ │
│  │                   │ │(on-demand)│ │          │              │ │
│  │                   │ └─────┬─────┘ │          │              │ │
│  │                   └───────┼───────┘──────────┘              │ │
│  │                           │                                 │ │
│  │                           │  Progressive Disclosure:        │ │
│  │                           │  Skill loads only when invoked  │ │
│  │                           │                                 │ │
│  │                           ▼                                 │ │
│  │                   ┌───────────────────┐                     │ │
│  │                   │   CLAUDE.md Files │                     │ │
│  │                   │                   │                     │ │
│  │                   │   ./CLAUDE.md     │                     │ │
│  │                   │   ./src/CLAUDE.md │                     │ │
│  │                   │   ./lib/CLAUDE.md │                     │ │
│  │                   └───────────────────┘                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. PostToolUse hook (Edit|Write) fires after Claude edits files
2. Hook appends file path to `.claude/.dirty-files` (zero token cost)
3. Stop hook fires when Claude's turn ends
4. If dirty files exist, Stop hook outputs `{"decision":"block","reason":"Spawn memory-updater agent..."}`
5. Claude spawns memory-updater agent via Task tool (isolated context)
6. Agent invokes memory-processor skill (progressive disclosure - loads only now)
7. Skill analyzes files, runs git commands, updates CLAUDE.md
8. Skill clears `.dirty-files`
9. Agent returns summary to main conversation
10. Stop hook fires again with `stop_hook_active=true`, passes through

**Progressive Disclosure Token Savings:**
- Agent startup: ~150 tokens (agent prompt + skill metadata)
- Skill invocation: ~500+ tokens (detailed processing instructions)
- If no processing needed: skill instructions never load

## Plugin Structure

```
claude-code-memory/
├── package.json                 # Plugin metadata and dependencies
├── README.md                    # User-facing documentation
├── PRD.md                       # Product requirements
├── SPEC.md                      # This file
│
├── .claude-plugin/              # Claude Code plugin configuration
│   ├── settings.json            # Hook configurations
│   │
│   ├── agents/                  # Spawnable agents (isolated context)
│   │   └── memory-updater.md   # Lightweight orchestrator agent
│   │
│   ├── skills/                  # Skills with progressive disclosure
│   │   ├── memory-processor/   # Processing skill (used by agent + /memory-sync)
│   │   │   └── SKILL.md        # Detailed processing instructions
│   │   │
│   │   └── codebase-analyzer/  # Analysis skill (used by /memory-init)
│   │       └── SKILL.md        # Wizard logic, pattern detection
│   │
│   ├── commands/                # Slash commands (lightweight, invoke skills)
│   │   ├── memory-init.md      # Invokes codebase-analyzer skill
│   │   ├── memory-sync.md      # Invokes memory-processor skill
│   │   └── memory-status.md    # Simple status (no skill needed)
│   │
│   └── hooks/                   # Event-driven scripts
│       ├── post-tool-use.sh    # Fires after Write/Edit, appends to .dirty-files
│       └── stop.sh             # Fires at end of turn, triggers agent spawn
│
├── templates/                   # CLAUDE.md templates
│   ├── CLAUDE.root.md.template # Root project template
│   └── CLAUDE.subtree.md.template # Subdirectory template
│
└── .claude/                     # Runtime data (created per-project)
    └── .dirty-files            # Simple text file, one path per line
```

## Component Specifications

### 1. Hook: PostToolUse (Zero Token Cost)

**File**: `.claude-plugin/hooks/post-tool-use.sh`

**Trigger**: After Write or Edit tool execution (Edit|Write matcher in settings.json)

**Environment Variables**:
- `$CLAUDE_FILE_PATHS` - Newline-separated list of affected file paths
- `$CLAUDE_PROJECT_DIR` - Absolute path to project root

**Responsibilities**:
1. Append file paths to `.claude/.dirty-files`
2. NO output (zero token cost - no Claude context injection)
3. Execute quickly (< 10ms) - just file append

**Implementation**:
```bash
#!/bin/bash
DIRTY_FILE="$CLAUDE_PROJECT_DIR/.claude/.dirty-files"

# Ensure .claude directory exists
mkdir -p "$CLAUDE_PROJECT_DIR/.claude"

# Append file paths to dirty file (one per line)
echo "$CLAUDE_FILE_PATHS" >> "$DIRTY_FILE"

# NO output - zero token cost
```

**Note**: We use `Edit|Write` matcher (not `*` or `Bash`) because PostToolUse hooks are reliable for these tools but have known issues with Bash tool tracking.

### 2. Hook: Stop (End of Turn Trigger)

**File**: `.claude-plugin/hooks/stop.sh`

**Trigger**: When Claude's turn ends (before response is finalized)

**Input** (via stdin): JSON object with conversation state including `stop_hook_active` flag

**Responsibilities**:
1. Check if `.dirty-files` exists and has content
2. If dirty files exist AND `stop_hook_active=false`: block and request agent spawn
3. If `stop_hook_active=true` or no dirty files: pass through (turn ends normally)

**Implementation**:
```bash
#!/bin/bash
DIRTY_FILE="$CLAUDE_PROJECT_DIR/.claude/.dirty-files"

# Read ALL stdin first, then parse (stdin can only be read once)
INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

# If already processing, pass through to avoid infinite loop
if [ "$STOP_ACTIVE" = "true" ]; then
  exit 0
fi

# Check for dirty files
if [ ! -f "$DIRTY_FILE" ] || [ ! -s "$DIRTY_FILE" ]; then
  exit 0
fi

# Get unique file list (max 20 to avoid huge messages)
FILES=$(sort -u "$DIRTY_FILE" | head -20 | tr '\n' ', ' | sed 's/,$//')

# Output block decision with explicit instructions
cat << EOF
{
  "decision": "block",
  "reason": "Files were modified this turn. Use the Task tool to spawn 'memory-updater' agent with prompt: 'Update CLAUDE.md for changed files: $FILES'"
}
EOF
```

**settings.json configuration** (combined hooks):
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude-plugin/hooks/post-tool-use.sh"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude-plugin/hooks/stop.sh"
      }]
    }]
  }
}
```

**Loop Prevention**: The `stop_hook_active` flag is set to `true` when Claude spawns the agent. When the stop hook fires again after agent completion, it reads this flag and passes through.

**Reliability Note**: Per Claude Code documentation, the `reason` field guides Claude's behavior but "effectiveness depends on prompt quality rather than guaranteed compliance." The explicit instruction format ("Use the Task tool to spawn...") maximizes compliance, but users should be aware that `/memory-sync` provides a manual fallback.

### 3. Agent: memory-updater (Lightweight Orchestrator)

**File**: `.claude-plugin/agents/memory-updater.md`

**Invocation**: Spawned via Task tool when Stop hook blocks with dirty files

**Context**: Runs in ISOLATED context - does not bloat main conversation

**Design Philosophy**: Lightweight orchestrator that delegates to skill for detailed processing. This enables progressive disclosure - detailed instructions load only when skill is invoked.

**Agent Definition** (~50 tokens):
```markdown
---
name: memory-updater
description: Orchestrates CLAUDE.md updates for changed files
---

Read .claude/.dirty-files. Invoke memory-processor skill. Return summary.
```

**Token Efficiency**: Agent prompt is minimal. Detailed processing logic lives in the memory-processor skill which loads on-demand via progressive disclosure.

**Output**: Brief summary returned to main conversation

### 4. Skill: memory-processor (Progressive Disclosure)

**File**: `.claude-plugin/skills/memory-processor/SKILL.md`

**Invocation**: Invoked by memory-updater agent when processing is needed

**Progressive Disclosure**: Only the skill's name and description (~100 tokens) load at agent startup. The full skill instructions (~500+ tokens) load only when the skill is invoked.

**SKILL.md Definition**:
```markdown
---
name: memory-processor
description: Process file changes and update CLAUDE.md documentation
---

# Memory Processor

Process changed files from .claude/.dirty-files and update CLAUDE.md.

## Algorithm
1. Read .dirty-files, dedupe paths
2. For each file, categorize:
   - BUILD: package.json, Makefile, *.config.*
   - ARCHITECTURE: src/**/*.{ts,js,py,go}
   - CONVENTIONS: any source file
3. If needed, run git log/diff for context
4. Update relevant CLAUDE.md section (preserve AUTO-MANAGED markers)
5. Clear .dirty-files

Return brief summary of updates.
```

**Git Integration** (used within skill):
```bash
git log -1 --format="%s" -- <file>     # Recent commit message
git diff HEAD~5 -- <file>               # Recent changes
git log --oneline -5 -- <file>          # Recent history
```

**Categorization Rules**:
```
BUILD:        package.json, Makefile, *.config.*, Dockerfile
ARCHITECTURE: src/**/*.{ts,js,py,go}, lib/**/*
CONVENTIONS:  Any source file (for pattern detection)
```

**Output**: CLAUDE.md files updated, .dirty-files cleared

### 5. Skill: codebase-analyzer (Progressive Disclosure)

**File**: `.claude-plugin/skills/codebase-analyzer/SKILL.md`

**Invocation**: Invoked by /memory-init command for wizard logic

**Progressive Disclosure**: Only skill metadata loads when command starts. Full wizard instructions load only when skill is invoked.

**SKILL.md Definition**:
```markdown
---
name: codebase-analyzer
description: Analyze codebase structure and generate CLAUDE.md templates
---

# Codebase Analyzer

Analyze project structure and generate CLAUDE.md files.

## Algorithm
1. Check for existing CLAUDE.md - ask user how to handle (migrate/backup/merge/cancel)
2. Scan directory structure, detect frameworks (package.json, Makefile, etc.)
3. Extract build commands from config files
4. Identify subtree candidates (src/, lib/, api/)
5. Detect code patterns and conventions
6. Fetch best practices from docs.claude.com
7. Present findings to user for approval
8. Generate CLAUDE.md files using templates
```

**User Interactions** (handled within skill):
- Existing CLAUDE.md handling
- Subtree location confirmation
- Final approval before generation

**Output**: Generated CLAUDE.md files, user-approved structure

### 6. Command: /memory-init (Lightweight)

**File**: `.claude-plugin/commands/memory-init.md`

**Purpose**: Initialize CLAUDE.md structure for project

**Design**: Lightweight command that delegates to codebase-analyzer skill for wizard logic.

**Command Definition** (~30 tokens):
```markdown
---
name: memory-init
description: Initialize CLAUDE.md structure for project
---

Invoke codebase-analyzer skill. Ask user to confirm before writing files.
```

**Progressive Disclosure**: Detailed wizard logic loads only when codebase-analyzer skill is invoked.

### 7. Command: /memory-sync (Lightweight)

**File**: `.claude-plugin/commands/memory-sync.md`

**Purpose**: Force recalibration of all CLAUDE.md files

**Design**: Reuses memory-processor skill (same as agent uses).

**Command Definition** (~30 tokens):
```markdown
---
name: memory-sync
description: Force recalibration of CLAUDE.md files
---

Invoke memory-processor skill for all tracked files. Report summary.
```

### 8. Command: /memory-status (No Skill)

**File**: `.claude-plugin/commands/memory-status.md`

**Purpose**: Show CLAUDE.md sync status

**Design**: Simple status display - no skill needed (not enough complexity to warrant progressive disclosure).

**Command Definition** (~50 tokens):
```markdown
---
name: memory-status
description: Show CLAUDE.md sync status
---

Read .claude/.dirty-files and last update times. Display:
- Pending changes count
- Last sync timestamp
- CLAUDE.md file locations
```

### 9. Dirty Files Format

**File**: `.claude/.dirty-files`

**Purpose**: Simple list of files changed during Claude's turn, pending processing

**Format**: Plain text, one file path per line
```
/path/to/file.ts
/path/to/package.json
/path/to/src/component.tsx
```

**Processing**:
- PostToolUse hook appends paths (may contain duplicates)
- Stop hook reads and deduplicates with `sort -u`
- memory-updater agent processes all files
- Agent clears file after processing (truncate or delete)

**Benefits over JSONL queue**:
- Simpler format (no JSON parsing in hooks)
- Smaller file size
- Easier to debug
- Deduplication happens at read time

### 10. Script: template-generator.js

**Purpose**: Generates CLAUDE.md files from templates

**Templates**:

**Root Template** (`CLAUDE.root.md.template`):
```markdown
# Project: {{PROJECT_NAME}}

<!-- AUTO-MANAGED: project-description -->
{{DESCRIPTION}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->
## Build Commands
{{BUILD_COMMANDS}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Architecture Overview
{{ARCHITECTURE}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Code Conventions
{{CONVENTIONS}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Detected Patterns
{{PATTERNS}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->
## Best Practices
{{BEST_PRACTICES}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->
## Git Insights
{{GIT_INSIGHTS}}
<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Custom Notes
Add your custom notes here. This section will never be auto-modified.
<!-- END MANUAL -->
```

**Subtree Template** (`CLAUDE.subtree.md.template`):
```markdown
# Module: {{MODULE_NAME}}

<!-- AUTO-MANAGED: module-description -->
{{DESCRIPTION}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Module Architecture
{{ARCHITECTURE}}
<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Module Conventions
{{CONVENTIONS}}
<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Module Notes
<!-- END MANUAL -->
```

### 11. Script: pattern-analyzer.js

**Purpose**: Analyzes code to detect patterns

**Detection Methods**:
- **Naming Conventions**: Analyze file/variable names for patterns
- **Import Styles**: Parse import statements for consistency
- **Architectural Patterns**: Detect MVC, layered architecture, etc.
- **Code Style**: Indentation, quotes, semicolons

**Example Output**:
```json
{
  "naming": {
    "components": "PascalCase",
    "utilities": "camelCase",
    "constants": "UPPER_SNAKE_CASE"
  },
  "imports": {
    "style": "ES6 modules",
    "ordering": "stdlib → external → internal"
  },
  "architecture": {
    "pattern": "Feature-based structure",
    "layers": ["components", "hooks", "utils", "api"]
  }
}
```

### 12. Script: docs-fetcher.js

**Purpose**: Fetches best practices from docs.claude.com

**Endpoint**: `https://docs.claude.com/en/docs/claude-code/best-practices`

**Process**:
1. Fetch HTML content
2. Parse relevant sections
3. Convert to markdown
4. Filter for project-relevant practices

**Cached**: Store in memory for session (avoid repeated fetches)

## Data Structures

### Dirty Files
```
# Simple text file format
# One file path per line, may contain duplicates
/absolute/path/to/file1.ts
/absolute/path/to/file2.ts
/absolute/path/to/file1.ts  # duplicate, deduped at read time
```

### Pattern
```typescript
interface Pattern {
  type: 'naming' | 'import' | 'architecture' | 'style';
  description: string;
  confidence: number; // 0-1
  examples: string[];
}
```

### Section Update
```typescript
interface SectionUpdate {
  category: 'BUILD' | 'ARCHITECTURE' | 'CONVENTIONS' | 'GIT_INSIGHTS' | 'PATTERNS' | 'BEST_PRACTICES';
  content: string;
  targetFile: string;
}
```

## Marker Syntax

All auto-managed sections use HTML comment markers:

```markdown
<!-- AUTO-MANAGED: section-name -->
Content that will be automatically updated
<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
Content that will never be touched by the plugin
<!-- END MANUAL -->
```

**Supported section names**:
- `project-description`
- `build-commands`
- `architecture`
- `conventions`
- `patterns`
- `best-practices`
- `git-insights`
- `module-description` (subtrees only)

## Performance Considerations

- **PostToolUse hook**: < 10ms (bash append only, zero token cost)
- **Stop hook**: < 50ms (file check + JSON output)
- **Agent processing**: < 5s for typical batch (isolated context)
- **Template generation**: < 3s for typical project
- **Docs fetching**: Cached per session

### Token Efficiency

The architecture prioritizes token efficiency:
- PostToolUse hook has **zero token cost** (no output to Claude context)
- Stop hook outputs minimal JSON only when dirty files exist
- Agent runs in **isolated context** (doesn't bloat main conversation)
- Single agent invocation per turn (batched processing)

## Error Handling

1. **Network failures** (docs-fetcher.js): Graceful fallback, skip best practices section
2. **Parse errors**: Log warning, preserve existing content
3. **File conflicts**: Backup before write, atomic operations
4. **Invalid markers**: Warn user, skip update

## Security

- Never execute arbitrary code from CLAUDE.md
- Sanitize all user input in templates
- Validate file paths (prevent directory traversal)
- No sensitive data in auto-managed sections

## Testing Strategy

1. **Unit tests**: template-generator.js, pattern-analyzer.js, docs-fetcher.js
2. **Integration tests**: Full /memory-init flow
3. **Hook tests**: Simulate PostToolUse and Stop hook events
4. **Agent tests**: Verify memory-updater processes dirty files correctly
5. **Template tests**: Validate generation with various inputs
6. **Edge cases**: Existing CLAUDE.md, corrupted markers, large files, empty dirty-files

## Dependencies

**System Requirements**:
- `jq` - JSON parsing in stop hook (commonly pre-installed)
- `bash` - Hook scripts

**Node.js Dependencies** (for /memory-init command):
```json
{
  "dependencies": {
    "node-fetch": "^3.3.0",
    "cheerio": "^1.0.0"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}
```

## Deployment

1. Package as npm module
2. Publish to Claude Code plugin marketplace
3. Installation: `/plugin install claude-code-memory`

## Version Strategy

- **v1.0.0**: Core features (init, sync, status, hooks)
- **v1.1.0**: Enhanced pattern detection
- **v1.2.0**: Git insights from commit history
- **v2.0.0**: Team collaboration features (future)
