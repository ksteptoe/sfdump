"""Tests for sfdump.viewer_app.services.paths module."""

from pathlib import Path

from sfdump.viewer_app.services.paths import infer_export_root, resolve_export_path


class TestInferExportRoot:
    """Tests for infer_export_root function."""

    def test_standard_layout_sfdata_db_in_meta(self, tmp_path):
        """EXPORT_ROOT/meta/sfdata.db -> returns EXPORT_ROOT."""
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        db_path = meta_dir / "sfdata.db"
        db_path.touch()

        result = infer_export_root(db_path)

        assert result == tmp_path

    def test_sfdata_db_with_sibling_meta_folder(self, tmp_path):
        """If sfdata.db is in a folder with sibling 'meta', return parent."""
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        db_path = tmp_path / "sfdata.db"
        db_path.touch()

        result = infer_export_root(db_path)

        assert result == tmp_path

    def test_sfdata_db_without_meta_folder(self, tmp_path):
        """If sfdata.db has no meta context, return None."""
        db_path = tmp_path / "sfdata.db"
        db_path.touch()

        result = infer_export_root(db_path)

        assert result is None

    def test_non_sfdata_db_file(self, tmp_path):
        """Non-sfdata.db file returns None."""
        db_path = tmp_path / "other.db"
        db_path.touch()

        result = infer_export_root(db_path)

        assert result is None

    def test_case_insensitive_sfdata_db(self, tmp_path):
        """Case variations of sfdata.db are recognized."""
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        db_path = meta_dir / "SFDATA.DB"
        db_path.touch()

        result = infer_export_root(db_path)

        assert result == tmp_path


class TestResolveExportPath:
    """Tests for resolve_export_path function."""

    def test_empty_path_returns_export_root(self, tmp_path):
        """Empty or whitespace path returns export_root."""
        result = resolve_export_path(tmp_path, "")
        assert result == tmp_path

        result2 = resolve_export_path(tmp_path, "   ")
        assert result2 == tmp_path

    def test_absolute_path_returned_as_is(self, tmp_path):
        """Absolute paths are returned unchanged."""
        if Path("/absolute/path").is_absolute():
            result = resolve_export_path(tmp_path, "/absolute/path")
            assert result == Path("/absolute/path")

    def test_relative_path_joined_to_export_root(self, tmp_path):
        """Relative paths are joined to export_root."""
        result = resolve_export_path(tmp_path, "files/doc.pdf")

        assert result == tmp_path / "files" / "doc.pdf"

    def test_backslash_paths_normalized(self, tmp_path):
        """Windows-style backslashes are normalized to forward slashes."""
        result = resolve_export_path(tmp_path, "files\\subdir\\doc.pdf")

        assert result == tmp_path / "files" / "subdir" / "doc.pdf"

    def test_leading_slash_stripped_from_relative(self, tmp_path):
        """Leading slashes/backslashes are stripped from relative paths."""
        result = resolve_export_path(tmp_path, "/files/doc.pdf")

        # On Unix this is absolute; on Windows it's relative
        # The function handles this by checking is_absolute()
        if not Path("/files/doc.pdf").is_absolute():
            assert result == tmp_path / "files" / "doc.pdf"

    def test_none_path_treated_as_empty(self, tmp_path):
        """None path is handled gracefully."""
        result = resolve_export_path(tmp_path, None)
        assert result == tmp_path
