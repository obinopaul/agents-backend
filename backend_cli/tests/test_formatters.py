"""
Tests for lgctl formatters module.
"""

import json

import pytest

from lgctl.formatters import (
    Formatter,
    JsonFormatter,
    RawFormatter,
    TableFormatter,
    get_formatter,
)


class TestTableFormatter:
    """Tests for TableFormatter."""

    def test_init_defaults(self):
        """Test default initialization."""
        fmt = TableFormatter()
        assert fmt.max_width == 80
        assert fmt.truncate == 50

    def test_init_custom(self):
        """Test custom initialization."""
        fmt = TableFormatter(max_width=120, truncate=30)
        assert fmt.max_width == 120
        assert fmt.truncate == 30

    def test_truncate_value_short(self, table_formatter):
        """Test truncation of short values."""
        result = table_formatter._truncate_value("short")
        assert result == "short"

    def test_truncate_value_long(self, table_formatter):
        """Test truncation of long values."""
        long_value = "x" * 100
        result = table_formatter._truncate_value(long_value)
        assert len(result) == 50
        assert result.endswith("...")

    def test_truncate_value_exact(self, table_formatter):
        """Test truncation at exact boundary."""
        exact_value = "x" * 50
        result = table_formatter._truncate_value(exact_value)
        assert result == exact_value
        assert len(result) == 50

    def test_format_timestamp_none(self, table_formatter):
        """Test formatting None timestamp."""
        result = table_formatter._format_timestamp(None)
        assert result == "N/A"

    def test_format_timestamp_iso(self, table_formatter):
        """Test formatting ISO timestamp."""
        result = table_formatter._format_timestamp("2024-01-15T12:30:45Z")
        assert "2024-01-15" in result
        assert "12:30" in result

    def test_format_timestamp_iso_offset(self, table_formatter):
        """Test formatting ISO timestamp with offset."""
        result = table_formatter._format_timestamp("2024-01-15T12:30:45+00:00")
        assert "2024-01-15" in result

    def test_format_timestamp_string(self, table_formatter):
        """Test formatting non-ISO timestamp string."""
        result = table_formatter._format_timestamp("not a timestamp")
        assert result == "not a timestamp"

    def test_format_timestamp_long_string(self, table_formatter):
        """Test formatting long non-ISO timestamp string."""
        long_ts = "a" * 30
        result = table_formatter._format_timestamp(long_ts)
        assert len(result) == 16

    def test_format_item_basic(self, table_formatter):
        """Test formatting a basic item."""
        item = {"key": "value", "number": 42}
        result = table_formatter.format_item(item)
        assert "=" * 60 in result
        assert "key: value" in result
        assert "number: 42" in result

    def test_format_item_with_fields(self, table_formatter):
        """Test formatting item with specific fields."""
        item = {"key": "value", "other": "hidden", "number": 42}
        result = table_formatter.format_item(item, fields=["key", "number"])
        assert "key: value" in result
        assert "number: 42" in result
        assert "other" not in result

    def test_format_item_with_timestamps(self, table_formatter):
        """Test formatting item with timestamps."""
        item = {
            "key": "value",
            "created_at": "2024-01-15T12:30:45Z",
            "updated_at": "2024-01-16T08:00:00Z",
        }
        result = table_formatter.format_item(item)
        assert "2024-01-15" in result
        assert "2024-01-16" in result

    def test_format_item_with_nested(self, table_formatter):
        """Test formatting item with nested dict/list."""
        item = {"data": {"nested": "value"}, "list": [1, 2, 3]}
        result = table_formatter.format_item(item)
        assert "data:" in result
        assert "list:" in result

    def test_format_list_empty(self, table_formatter):
        """Test formatting empty list."""
        result = table_formatter.format_list([])
        assert result == "No items found."

    def test_format_list_basic(self, table_formatter):
        """Test formatting basic list."""
        items = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        result = table_formatter.format_list(items)
        assert "id" in result
        assert "name" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "(2 items)" in result

    def test_format_list_with_fields(self, table_formatter):
        """Test formatting list with specific fields."""
        items = [
            {"id": 1, "name": "Alice", "secret": "hidden"},
            {"id": 2, "name": "Bob", "secret": "also hidden"},
        ]
        result = table_formatter.format_list(items, fields=["name"])
        assert "name" in result
        assert "Alice" in result
        assert "secret" not in result

    def test_format_error(self, table_formatter):
        """Test formatting error message."""
        result = table_formatter.format_error("Something went wrong")
        assert result == "error: Something went wrong"

    def test_format_success(self, table_formatter):
        """Test formatting success message."""
        result = table_formatter.format_success("Operation completed")
        assert result == "ok: Operation completed"

    def test_print_item(self, table_formatter, capsys):
        """Test print_item method."""
        item = {"key": "value"}
        table_formatter.print_item(item)
        captured = capsys.readouterr()
        assert "key: value" in captured.out

    def test_print_list(self, table_formatter, capsys):
        """Test print_list method."""
        items = [{"key": "value"}]
        table_formatter.print_list(items)
        captured = capsys.readouterr()
        assert "key" in captured.out

    def test_print_error(self, table_formatter, capsys):
        """Test print_error method."""
        table_formatter.print_error("Error message")
        captured = capsys.readouterr()
        assert "error: Error message" in captured.err

    def test_print_success(self, table_formatter, capsys):
        """Test print_success method."""
        table_formatter.print_success("Success message")
        captured = capsys.readouterr()
        assert "ok: Success message" in captured.out


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_init_defaults(self):
        """Test default initialization."""
        fmt = JsonFormatter()
        assert fmt.indent == 2

    def test_init_custom(self):
        """Test custom initialization."""
        fmt = JsonFormatter(indent=4)
        assert fmt.indent == 4

    def test_init_no_indent(self):
        """Test initialization without indentation."""
        fmt = JsonFormatter(indent=None)
        assert fmt.indent is None

    def test_format_item_basic(self, json_formatter):
        """Test formatting a basic item."""
        item = {"key": "value", "number": 42}
        result = json_formatter.format_item(item)
        parsed = json.loads(result)
        assert parsed == item

    def test_format_item_with_fields(self, json_formatter):
        """Test formatting item with specific fields."""
        item = {"key": "value", "other": "hidden", "number": 42}
        result = json_formatter.format_item(item, fields=["key", "number"])
        parsed = json.loads(result)
        assert parsed == {"key": "value", "number": 42}
        assert "other" not in parsed

    def test_format_item_nested(self, json_formatter):
        """Test formatting item with nested structures."""
        item = {"data": {"nested": "value"}, "list": [1, 2, 3]}
        result = json_formatter.format_item(item)
        parsed = json.loads(result)
        assert parsed == item

    def test_format_list_empty(self, json_formatter):
        """Test formatting empty list."""
        result = json_formatter.format_list([])
        parsed = json.loads(result)
        assert parsed == []

    def test_format_list_basic(self, json_formatter):
        """Test formatting basic list."""
        items = [{"id": 1}, {"id": 2}]
        result = json_formatter.format_list(items)
        parsed = json.loads(result)
        assert parsed == items

    def test_format_list_with_fields(self, json_formatter):
        """Test formatting list with specific fields."""
        items = [
            {"id": 1, "name": "Alice", "secret": "hidden"},
            {"id": 2, "name": "Bob", "secret": "also hidden"},
        ]
        result = json_formatter.format_list(items, fields=["id", "name"])
        parsed = json.loads(result)
        assert parsed == [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

    def test_format_error(self, json_formatter):
        """Test formatting error message."""
        result = json_formatter.format_error("Something went wrong")
        parsed = json.loads(result)
        assert parsed == {"error": "Something went wrong"}

    def test_format_success(self, json_formatter):
        """Test formatting success message."""
        result = json_formatter.format_success("Operation completed")
        parsed = json.loads(result)
        assert parsed == {"status": "ok", "message": "Operation completed"}

    def test_format_with_datetime(self, json_formatter):
        """Test formatting with datetime (uses default=str)."""
        from datetime import datetime

        item = {"timestamp": datetime(2024, 1, 15, 12, 30, 45)}
        result = json_formatter.format_item(item)
        parsed = json.loads(result)
        assert "2024" in parsed["timestamp"]


class TestRawFormatter:
    """Tests for RawFormatter."""

    def test_init_defaults(self):
        """Test default initialization."""
        fmt = RawFormatter()
        assert fmt.separator == "\t"

    def test_init_custom(self):
        """Test custom initialization."""
        fmt = RawFormatter(separator=",")
        assert fmt.separator == ","

    def test_format_item_basic(self, raw_formatter):
        """Test formatting a basic item."""
        item = {"key": "value", "number": 42}
        result = raw_formatter.format_item(item)
        assert "value" in result
        assert "42" in result
        assert "\t" in result

    def test_format_item_with_fields(self, raw_formatter):
        """Test formatting item with specific fields."""
        item = {"key": "value", "other": "hidden", "number": 42}
        result = raw_formatter.format_item(item, fields=["key", "number"])
        parts = result.split("\t")
        assert parts == ["value", "42"]

    def test_format_item_missing_field(self, raw_formatter):
        """Test formatting item with missing field."""
        item = {"key": "value"}
        result = raw_formatter.format_item(item, fields=["key", "missing"])
        parts = result.split("\t")
        assert parts == ["value", ""]

    def test_format_list_empty(self, raw_formatter):
        """Test formatting empty list."""
        result = raw_formatter.format_list([])
        assert result == ""

    def test_format_list_basic(self, raw_formatter):
        """Test formatting basic list."""
        items = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = raw_formatter.format_list(items)
        lines = result.split("\n")
        assert len(lines) == 2

    def test_format_list_with_fields(self, raw_formatter):
        """Test formatting list with specific fields."""
        items = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        result = raw_formatter.format_list(items, fields=["name"])
        lines = result.split("\n")
        assert lines == ["Alice", "Bob"]

    def test_format_error(self, raw_formatter):
        """Test formatting error message."""
        result = raw_formatter.format_error("Something went wrong")
        assert result == "ERROR: Something went wrong"

    def test_format_success(self, raw_formatter):
        """Test formatting success message."""
        result = raw_formatter.format_success("Operation completed")
        assert result == "Operation completed"

    def test_custom_separator(self):
        """Test with custom separator."""
        fmt = RawFormatter(separator="|")
        item = {"a": 1, "b": 2}
        result = fmt.format_item(item)
        assert "|" in result


class TestGetFormatter:
    """Tests for get_formatter function."""

    def test_get_table_formatter(self):
        """Test getting table formatter."""
        fmt = get_formatter("table")
        assert isinstance(fmt, TableFormatter)

    def test_get_json_formatter(self):
        """Test getting JSON formatter."""
        fmt = get_formatter("json")
        assert isinstance(fmt, JsonFormatter)

    def test_get_raw_formatter(self):
        """Test getting raw formatter."""
        fmt = get_formatter("raw")
        assert isinstance(fmt, RawFormatter)

    def test_get_formatter_default(self):
        """Test default formatter is table."""
        fmt = get_formatter()
        assert isinstance(fmt, TableFormatter)

    def test_get_formatter_invalid(self):
        """Test getting invalid formatter raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_formatter("invalid")
        assert "Unknown format: invalid" in str(exc_info.value)

    def test_get_formatter_with_kwargs(self):
        """Test passing kwargs to formatter."""
        fmt = get_formatter("table", max_width=100, truncate=30)
        assert isinstance(fmt, TableFormatter)
        assert fmt.max_width == 100
        assert fmt.truncate == 30

    def test_get_json_formatter_with_indent(self):
        """Test JSON formatter with custom indent."""
        fmt = get_formatter("json", indent=4)
        assert isinstance(fmt, JsonFormatter)
        assert fmt.indent == 4

    def test_get_raw_formatter_with_separator(self):
        """Test raw formatter with custom separator."""
        fmt = get_formatter("raw", separator=",")
        assert isinstance(fmt, RawFormatter)
        assert fmt.separator == ","


class TestFormatterABC:
    """Tests for Formatter abstract base class."""

    def test_formatter_is_abstract(self):
        """Test that Formatter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Formatter()

    def test_formatter_abstract_methods(self):
        """Test that all abstract methods must be implemented."""

        class IncompleteFormatter(Formatter):
            pass

        with pytest.raises(TypeError):
            IncompleteFormatter()

    def test_formatter_complete_implementation(self):
        """Test that complete implementation works."""

        class CompleteFormatter(Formatter):
            def format_item(self, item, fields=None):
                return str(item)

            def format_list(self, items, fields=None):
                return str(items)

            def format_error(self, error):
                return f"Error: {error}"

            def format_success(self, message):
                return f"Success: {message}"

        fmt = CompleteFormatter()
        assert fmt.format_item({"a": 1}) == "{'a': 1}"
