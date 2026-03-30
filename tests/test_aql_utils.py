"""Unit tests for AQL identifier validation — the security boundary for AQL injection."""

import pytest

from aql_utils import validate_aql_identifier, validate_aql_identifiers


class TestValidateAqlIdentifier:
    """Tests for validate_aql_identifier."""

    # ── Valid identifiers ─────────────────────────────────────────────

    @pytest.mark.parametrize(
        "name",
        [
            "users",
            "my_collection",
            "_system",
            "Col123",
            "edge-links",
            "ns:prefix",
            "a.b.c",
            "A",
            "_",
            "_leading_underscore",
            "with-dashes-and_underscores",
            "mixed:colons.dots-dashes_underscores123",
        ],
    )
    def test_valid_identifiers_pass(self, name):
        assert validate_aql_identifier(name) == name

    def test_returns_original_string(self):
        assert validate_aql_identifier("users", "collection") == "users"

    # ── Invalid identifiers (injection vectors) ───────────────────────

    @pytest.mark.parametrize(
        "name",
        [
            "` OR 1==1 //",
            "col; DROP",
            "name with spaces",
            "has\ttab",
            "has\nnewline",
            "123startsWithDigit",
            "-startsWithDash",
            ".startsWithDot",
            ":startsWithColon",
            "col`backtick",
            'col"doublequote',
            "col'singlequote",
            "col(paren)",
            "col[bracket]",
            "col{brace}",
            "col/slash",
            "col\\backslash",
            "col@at",
            "col#hash",
            "col$dollar",
            "col%percent",
            "col^caret",
            "col&amp",
            "col*star",
            "col+plus",
            "col=equals",
            "col!bang",
            "col?question",
            "col<angle>",
            "col|pipe",
            "col~tilde",
            "col,comma",
        ],
    )
    def test_injection_vectors_rejected(self, name):
        with pytest.raises(ValueError):
            validate_aql_identifier(name)

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_aql_identifier("")

    def test_custom_label_in_error_empty(self):
        with pytest.raises(ValueError, match="collection_name cannot be empty"):
            validate_aql_identifier("", "collection_name")

    def test_custom_label_in_error_unsafe(self):
        with pytest.raises(ValueError, match="Unsafe field_name"):
            validate_aql_identifier("bad value", "field_name")


class TestValidateAqlIdentifiers:
    """Tests for validate_aql_identifiers (list variant)."""

    def test_all_valid(self):
        result = validate_aql_identifiers(["users", "orders", "_system"])
        assert result == ["users", "orders", "_system"]

    def test_empty_list(self):
        assert validate_aql_identifiers([]) == []

    def test_single_invalid_rejects_all(self):
        with pytest.raises(ValueError):
            validate_aql_identifiers(["valid", "also-valid", "bad value"])

    def test_first_invalid_fails_fast(self):
        with pytest.raises(ValueError):
            validate_aql_identifiers(["` injection", "valid"])

    def test_custom_label_propagated(self):
        with pytest.raises(ValueError, match="edge_collection"):
            validate_aql_identifiers(["bad value"], "edge_collection")
