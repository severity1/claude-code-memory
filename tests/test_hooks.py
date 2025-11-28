"""Tests for hook scripts."""
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


class TestPostToolUseHook:
    """Tests for post-tool-use.py hook."""

    def test_creates_dirty_file(self, tmp_path):
        """Hook creates .claude/.dirty-files if it doesn't exist."""
        env = {
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_FILE_PATHS": "/path/to/file.py",
        }
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()

    def test_appends_paths(self, tmp_path):
        """Hook appends file paths to dirty file."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/existing/file.py\n")

        env = {
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_FILE_PATHS": "/new/file.py",
        }
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            capture_output=True,
        )
        content = dirty_file.read_text()
        assert "/existing/file.py" in content
        assert "/new/file.py" in content

    def test_no_output(self, tmp_path):
        """Hook produces no output (zero token cost)."""
        env = {
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_FILE_PATHS": "/path/to/file.py",
        }
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            capture_output=True,
            text=True,
        )
        assert result.stdout == ""
        assert result.stderr == ""

    def test_handles_missing_env_vars(self):
        """Hook exits gracefully when env vars are missing."""
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_handles_multiline_paths(self, tmp_path):
        """Hook handles multiple file paths separated by newlines."""
        env = {
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_FILE_PATHS": "/file1.py\n/file2.py\n/file3.py",
        }
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            capture_output=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        content = dirty_file.read_text()
        assert "/file1.py" in content
        assert "/file2.py" in content
        assert "/file3.py" in content


class TestStopHook:
    """Tests for stop.py hook."""

    def test_passes_when_empty(self, tmp_path):
        """Hook passes through when no dirty files exist."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_passes_when_active(self, tmp_path):
        """Hook passes through when stop_hook_active is true."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input='{"stop_hook_active": true}',
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_blocks_with_files(self, tmp_path):
        """Hook blocks and outputs JSON when dirty files exist."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["decision"] == "block"
        assert "memory-updater" in output["reason"]

    def test_json_format(self, tmp_path):
        """Hook output is valid JSON with required fields."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        assert "decision" in output
        assert "reason" in output

    def test_deduplicates_files(self, tmp_path):
        """Hook deduplicates file paths in output."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/file.py\n/file.py\n/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        # Should only mention file once
        assert output["reason"].count("/file.py") == 1

    def test_limits_file_count(self, tmp_path):
        """Hook limits file list to 20 files max."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        files = [f"/file{i}.py" for i in range(30)]
        dirty_file.write_text("\n".join(files) + "\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        # Count commas + 1 = number of files (should be <= 20)
        file_count = output["reason"].count(",") + 1
        assert file_count <= 20

    def test_handles_invalid_json_input(self, tmp_path):
        """Hook handles invalid JSON input gracefully."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="not valid json",
            capture_output=True,
            text=True,
        )
        # Should still work, treating input as empty
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["decision"] == "block"
