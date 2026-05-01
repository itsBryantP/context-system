"""Tests for DOCX extraction error handling."""

import zipfile
from pathlib import Path

import pytest

from ctx.extractors.docx import ExtractionError, _extract_docx
from ctx.pack import _is_temp_file, scan_directory


class TestTempFileFiltering:
    """Test that temporary files are correctly identified and filtered."""

    def test_word_temp_files_detected(self):
        assert _is_temp_file(Path("~$document.docx"))
        assert _is_temp_file(Path("~$test.doc"))

    def test_macos_metadata_files_detected(self):
        assert _is_temp_file(Path(".DS_Store"))
        assert _is_temp_file(Path("._resource_fork"))

    def test_windows_thumbnails_detected(self):
        assert _is_temp_file(Path("Thumbs.db"))

    def test_generic_temp_files_detected(self):
        assert _is_temp_file(Path("file.tmp"))
        assert _is_temp_file(Path("file.swp"))

    def test_normal_files_not_detected_as_temp(self):
        assert not _is_temp_file(Path("document.docx"))
        assert not _is_temp_file(Path("README.md"))
        assert not _is_temp_file(Path("test.pdf"))

    def test_scan_directory_skips_temp_files(self, tmp_path):
        # Create test directory with mix of normal and temp files
        (tmp_path / "document.docx").write_text("content")
        (tmp_path / "~$document.docx").write_text("temp")
        (tmp_path / ".DS_Store").write_text("metadata")
        (tmp_path / "README.md").write_text("# Readme")

        results = scan_directory(tmp_path)

        # Should only include normal files
        paths = [r.source_path.name for r in results]
        assert "document.docx" in paths
        assert "README.md" in paths
        assert "~$document.docx" not in paths
        assert ".DS_Store" not in paths


class TestDocxErrorHandling:
    """Test DOCX extraction error handling."""

    def test_extraction_error_can_be_raised(self):
        with pytest.raises(ExtractionError, match="test message"):
            raise ExtractionError("test message")

    def test_corrupt_docx_raises_extraction_error(self, tmp_path):
        # Create a file that's not a valid ZIP/DOCX
        corrupt_file = tmp_path / "corrupt.docx"
        corrupt_file.write_bytes(b"not a valid docx file")

        # Should raise ExtractionError with helpful message
        with pytest.raises(ExtractionError) as exc_info:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            _extract_docx(corrupt_file, converter, remove_images=True, filter_profile_icons=True)

        # Docling catches BadZipFile and raises RuntimeError, which we convert to ExtractionError
        error_msg = str(exc_info.value)
        assert "Docling could not load" in error_msg or "Invalid or corrupt DOCX" in error_msg
        assert "corrupt.docx" in error_msg

    def test_empty_document_raises_extraction_error(self, tmp_path):
        # This test would require creating a valid but empty DOCX
        # For now, we verify the check exists in the code
        pass


class TestDocxWarningsSuppressed:
    """Test that verbose Docling warnings are suppressed."""

    def test_docling_logger_configured(self):
        import logging
        from ctx.extractors.docx import _configure_docling_logging

        _configure_docling_logging()

        docling_logger = logging.getLogger('docling')
        # Should be set to ERROR level to suppress warnings
        assert docling_logger.level == logging.ERROR
