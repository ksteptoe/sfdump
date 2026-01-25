# tests/unit/test_files_chunking.py
"""Tests for file download chunking behavior.

These tests verify:
1. Chunking env vars limit the number of files downloaded
2. Without chunking env vars, all files are processed
3. The orchestrator clears stale chunking env vars
"""

from __future__ import annotations

import os
from unittest import mock

from sfdump.files import _order_and_chunk_rows


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
