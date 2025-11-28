#!/usr/bin/env python3
"""PostToolUse hook - appends edited files to dirty queue.

This hook fires after Edit or Write tool execution and tracks
changed file paths for later CLAUDE.md updates. It produces
no output to maintain zero token cost.
"""
import os
from pathlib import Path


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    file_paths = os.environ.get("CLAUDE_FILE_PATHS", "")

    if not project_dir or not file_paths:
        return

    dirty_file = Path(project_dir) / ".claude" / ".dirty-files"
    dirty_file.parent.mkdir(parents=True, exist_ok=True)

    with open(dirty_file, "a") as f:
        f.write(file_paths + "\n")

    # NO output - zero token cost


if __name__ == "__main__":
    main()
