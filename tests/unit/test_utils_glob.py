"""Tests for glob-to-regex conversion used by Document Explorer."""

from __future__ import annotations

from sfdump.utils import glob_to_regex


class TestGlobToRegex:
    """Tests for glob_to_regex function."""

    def test_literal_text_unchanged(self):
        """Plain text without wildcards passes through unchanged."""
        assert glob_to_regex("PIN010063") == "PIN010063"
        assert glob_to_regex("SIN001234") == "SIN001234"
        assert glob_to_regex("AcmeCorp") == "AcmeCorp"

    def test_asterisk_converts_to_dot_star(self):
        """Asterisk (*) converts to regex .* for any characters."""
        assert glob_to_regex("PIN01006*") == "PIN01006.*"
        assert glob_to_regex("*AcmeCorp*") == ".*AcmeCorp.*"
        assert glob_to_regex("SIN*") == "SIN.*"
        assert glob_to_regex("*") == ".*"

    def test_question_mark_converts_to_dot(self):
        """Question mark (?) converts to regex . for single character."""
        assert glob_to_regex("PIN01006?") == "PIN01006."
        assert glob_to_regex("PIN0100??") == "PIN0100.."
        assert glob_to_regex("?") == "."

    def test_combined_wildcards(self):
        """Mixed wildcards work correctly."""
        assert glob_to_regex("PIN*?") == "PIN.*."
        assert glob_to_regex("?IN01006*") == ".IN01006.*"
        assert glob_to_regex("*?*") == ".*..*"

    def test_character_class_simple(self):
        """Character classes [abc] pass through."""
        assert glob_to_regex("PIN01006[123]") == "PIN01006[123]"
        assert glob_to_regex("[abc]") == "[abc]"

    def test_character_class_range(self):
        """Character ranges [1-5] pass through."""
        assert glob_to_regex("PIN01006[0-9]") == "PIN01006[0-9]"
        assert glob_to_regex("PIN01006[1-5]") == "PIN01006[1-5]"
        assert glob_to_regex("[a-z]") == "[a-z]"
        assert glob_to_regex("[A-Za-z0-9]") == "[A-Za-z0-9]"

    def test_character_class_negation_glob_style(self):
        """Glob-style negation [!abc] converts to regex [^abc]."""
        assert glob_to_regex("[!0-9]") == "[^0-9]"
        assert glob_to_regex("PIN[!abc]") == "PIN[^abc]"

    def test_character_class_negation_regex_style(self):
        """Regex-style negation [^abc] passes through."""
        assert glob_to_regex("[^0-9]") == "[^0-9]"
        assert glob_to_regex("PIN[^abc]") == "PIN[^abc]"

    def test_unclosed_bracket_escaped(self):
        """Unclosed [ is escaped as literal."""
        assert glob_to_regex("PIN[123") == "PIN\\[123"
        assert glob_to_regex("[") == "\\["

    def test_regex_special_chars_escaped(self):
        """Regex special characters are escaped for literal matching."""
        assert glob_to_regex("file.pdf") == "file\\.pdf"
        assert glob_to_regex("a+b") == "a\\+b"
        assert glob_to_regex("(test)") == "\\(test\\)"
        assert glob_to_regex("a|b") == "a\\|b"
        assert glob_to_regex("end$") == "end\\$"
        assert glob_to_regex("^start") == "\\^start"
        assert glob_to_regex("a{2}") == "a\\{2\\}"

    def test_real_world_examples(self):
        """Real-world search patterns work correctly."""
        # Invoice number searches
        assert glob_to_regex("PIN01006*") == "PIN01006.*"
        assert glob_to_regex("SIN00123?") == "SIN00123."
        assert glob_to_regex("PIN0100[6-9]*") == "PIN0100[6-9].*"

        # Filename with extension
        assert glob_to_regex("*.pdf") == ".*\\.pdf"
        assert glob_to_regex("invoice*.pdf") == "invoice.*\\.pdf"

        # Company name variations
        assert glob_to_regex("Arm*") == "Arm.*"
        assert glob_to_regex("*Limited") == ".*Limited"


class TestGlobToRegexEdgeCases:
    """Edge case tests for glob_to_regex."""

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert glob_to_regex("") == ""

    def test_bracket_as_first_char_in_class(self):
        """Literal ] as first char in character class."""
        assert glob_to_regex("[]]") == "[]]"
        assert glob_to_regex("[!]]") == "[^]]"

    def test_multiple_character_classes(self):
        """Multiple character classes in one pattern."""
        assert glob_to_regex("[a-z][0-9]") == "[a-z][0-9]"
        assert glob_to_regex("PIN[0-9][0-9][0-9]") == "PIN[0-9][0-9][0-9]"

    def test_character_class_with_wildcards(self):
        """Character classes combined with wildcards."""
        assert glob_to_regex("[A-Z]*[0-9]?") == "[A-Z].*[0-9]."
        assert glob_to_regex("*[!0-9]*") == ".*[^0-9].*"
