# tests/unit/test_files_chunking.py
"""Tests for file download chunking behavior and path truncation.

These tests verify:
1. Chunking env vars limit the number of files downloaded
2. Without chunking env vars, all files are processed
3. The orchestrator clears stale chunking env vars
4. Windows path truncation works correctly
"""

from __future__ import annotations

import os
from unittest import mock

from sfdump.files import (
    _order_and_chunk_rows,
    _truncate_path_for_windows,
    _WINDOWS_MAX_PATH,
)


class TestOrderAndChunkRows:
    """Tests for the _order_and_chunk_rows function."""

    def test_no_chunking_returns_all_rows(self) -> None:
        """Without chunking env vars, all rows are returned."""
        rows = [{"Id": f"ID{i}"} for i in range(100)]

        # Ensure no chunking env vars are set
        with mock.patch.dict(os.environ, {}, clear=True):
            result = _order_and_chunk_rows(rows, kind="test")

        assert len(result) == 100

    def test_chunking_limits_rows(self) -> None:
        """With chunking env vars, only a subset of rows is returned."""
        rows = [{"Id": f"ID{i:03d}"} for i in range(100)]

        # Set chunking to get 1 of 10 chunks (should get ~10 rows)
        env = {
            "SFDUMP_FILES_CHUNK_TOTAL": "10",
            "SFDUMP_FILES_CHUNK_INDEX": "1",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            result = _order_and_chunk_rows(rows, kind="test")

        assert len(result) == 10  # 100 rows / 10 chunks = 10 per chunk

    def test_chunking_second_chunk(self) -> None:
        """Second chunk returns different rows than first chunk."""
        rows = [{"Id": f"ID{i:03d}"} for i in range(100)]

        env1 = {"SFDUMP_FILES_CHUNK_TOTAL": "10", "SFDUMP_FILES_CHUNK_INDEX": "1"}
        env2 = {"SFDUMP_FILES_CHUNK_TOTAL": "10", "SFDUMP_FILES_CHUNK_INDEX": "2"}

        with mock.patch.dict(os.environ, env1, clear=True):
            chunk1 = _order_and_chunk_rows(rows, kind="test")

        with mock.patch.dict(os.environ, env2, clear=True):
            chunk2 = _order_and_chunk_rows(rows, kind="test")

        # Chunks should have different rows
        chunk1_ids = {r["Id"] for r in chunk1}
        chunk2_ids = {r["Id"] for r in chunk2}
        assert chunk1_ids.isdisjoint(chunk2_ids)

    def test_invalid_chunk_total_ignored(self) -> None:
        """Invalid chunk total falls back to no chunking."""
        rows = [{"Id": f"ID{i}"} for i in range(100)]

        env = {"SFDUMP_FILES_CHUNK_TOTAL": "invalid", "SFDUMP_FILES_CHUNK_INDEX": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            result = _order_and_chunk_rows(rows, kind="test")

        assert len(result) == 100

    def test_chunk_index_out_of_range_ignored(self) -> None:
        """Chunk index out of range falls back to no chunking."""
        rows = [{"Id": f"ID{i}"} for i in range(100)]

        env = {"SFDUMP_FILES_CHUNK_TOTAL": "10", "SFDUMP_FILES_CHUNK_INDEX": "20"}
        with mock.patch.dict(os.environ, env, clear=True):
            result = _order_and_chunk_rows(rows, kind="test")

        assert len(result) == 100


class TestOrchestratorClearsChunkingEnvVars:
    """Tests that the orchestrator clears stale chunking env vars."""

    def test_stale_chunking_env_vars_are_cleared(self) -> None:
        """Orchestrator clears SFDUMP_FILES_CHUNK_* env vars for non-light exports.

        This prevents incomplete exports when env vars are left over from
        previous runs or set unintentionally.
        """
        # We can't easily test the full orchestrator without mocking Salesforce,
        # but we can verify the clearing logic exists in the code
        import inspect

        from sfdump import orchestrator

        source = inspect.getsource(orchestrator.run_full_export)

        # Verify the clearing logic is present
        assert 'os.environ.pop("SFDUMP_FILES_CHUNK_TOTAL", None)' in source
        assert 'os.environ.pop("SFDUMP_FILES_CHUNK_INDEX", None)' in source
        assert "Clearing stale SFDUMP_FILES_CHUNK_TOTAL" in source


class TestWindowsPathTruncation:
    """Tests for the _truncate_path_for_windows function."""

    def test_truncates_long_filename(self) -> None:
        """Long filenames are truncated to fit within MAX_PATH."""
        files_root = "C:\\Users\\Test\\exports\\files"
        subdir = "00"
        # Create a filename that would exceed MAX_PATH
        long_name = "00P2X00001y8TAKUA2_" + "A" * 300 + ".pdf"

        result = _truncate_path_for_windows(files_root, subdir, long_name)

        # Result should be within MAX_PATH
        assert len(result) <= _WINDOWS_MAX_PATH
        # Should preserve the ID prefix
        assert "00P2X00001y8TAKUA2_" in result
        # Should preserve the extension
        assert result.endswith(".pdf")
        # Should have truncation marker
        assert "~" in result

    def test_preserves_short_filename(self) -> None:
        """Short filenames that fit are preserved."""
        files_root = "C:\\exports"
        subdir = "00"
        short_name = "00P2X00001y8TAKUA2_short_file.pdf"

        result = _truncate_path_for_windows(files_root, subdir, short_name)

        # Short name should be preserved
        assert result.endswith(short_name)

    def test_preserves_extension(self) -> None:
        """File extension is always preserved."""
        files_root = "C:\\Users\\Test\\OneDrive\\Very\\Long\\Path\\exports\\files"
        subdir = "00"
        long_name = "00P2X00001y8TAKUA2_" + "B" * 200 + ".docx"

        result = _truncate_path_for_windows(files_root, subdir, long_name)

        assert result.endswith(".docx")

    def test_preserves_id_prefix(self) -> None:
        """Salesforce ID prefix is always preserved."""
        files_root = "C:\\Users\\Test\\exports\\files"
        subdir = "00"
        long_name = "00Pw00000106dCoEAI_" + "X" * 300 + ".pdf"

        result = _truncate_path_for_windows(files_root, subdir, long_name)

        # The ID prefix should be in the result
        assert "00Pw00000106dCoEAI_" in os.path.basename(result)

    def test_handles_no_extension(self) -> None:
        """Files without extension are handled correctly."""
        files_root = "C:\\Users\\Test\\exports\\files"
        subdir = "00"
        long_name = "00P2X00001y8TAKUA2_" + "Z" * 300

        result = _truncate_path_for_windows(files_root, subdir, long_name)

        assert len(result) <= _WINDOWS_MAX_PATH
        assert "00P2X00001y8TAKUA2_" in result
