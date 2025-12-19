"""
Output formatters for lgctl commands.

Provides consistent output formatting across all commands with
support for table, JSON, and raw output modes.
"""

import json
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class Formatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format_item(self, item: Dict[str, Any], fields: Optional[List[str]] = None) -> str:
        """Format a single item."""
        pass

    @abstractmethod
    def format_list(self, items: List[Dict[str, Any]], fields: Optional[List[str]] = None) -> str:
        """Format a list of items."""
        pass

    @abstractmethod
    def format_error(self, error: str) -> str:
        """Format an error message."""
        pass

    @abstractmethod
    def format_success(self, message: str) -> str:
        """Format a success message."""
        pass

    def print_item(self, item: Dict[str, Any], fields: Optional[List[str]] = None):
        """Print a formatted item."""
        print(self.format_item(item, fields))

    def print_list(self, items: List[Dict[str, Any]], fields: Optional[List[str]] = None):
        """Print a formatted list."""
        print(self.format_list(items, fields))

    def print_error(self, error: str):
        """Print an error message."""
        print(self.format_error(error), file=sys.stderr)

    def print_success(self, message: str):
        """Print a success message."""
        print(self.format_success(message))


class TableFormatter(Formatter):
    """Human-readable table output."""

    def __init__(self, max_width: int = 80, truncate: int = 50):
        self.max_width = max_width
        self.truncate = truncate

    def _truncate_value(self, value: Any) -> str:
        """Truncate long values for display."""
        s = str(value)
        if len(s) > self.truncate:
            return s[: self.truncate - 3] + "..."
        return s

    def _format_timestamp(self, ts: Any) -> str:
        """Format a timestamp for display."""
        if ts is None:
            return "N/A"
        if isinstance(ts, str):
            # Try to parse ISO format
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, AttributeError):
                return ts[:16] if len(ts) > 16 else ts
        return str(ts)

    def format_item(self, item: Dict[str, Any], fields: Optional[List[str]] = None) -> str:
        """Format a single item as a key-value block."""
        lines = ["=" * 60]

        display_fields = fields or list(item.keys())
        for key in display_fields:
            if key in item:
                value = item[key]
                if key in ("created_at", "updated_at"):
                    value = self._format_timestamp(value)
                elif isinstance(value, (dict, list)):
                    value = self._truncate_value(json.dumps(value))
                else:
                    value = self._truncate_value(value)
                lines.append(f"  {key}: {value}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def format_list(self, items: List[Dict[str, Any]], fields: Optional[List[str]] = None) -> str:
        """Format a list as a table."""
        if not items:
            return "No items found."

        # Determine columns
        if fields:
            cols = fields
        else:
            # Use common fields or first item's keys
            cols = list(items[0].keys())[:5]  # Limit columns for readability

        # Calculate column widths
        widths = {col: len(col) for col in cols}
        for item in items:
            for col in cols:
                val = str(item.get(col, ""))[: self.truncate]
                widths[col] = max(widths[col], len(val))

        # Build table
        lines = []

        # Header
        header = "  ".join(col.ljust(widths[col]) for col in cols)
        lines.append(header)
        lines.append("-" * len(header))

        # Rows
        for item in items:
            row = []
            for col in cols:
                val = item.get(col, "")
                if col in ("created_at", "updated_at"):
                    val = self._format_timestamp(val)
                elif isinstance(val, (dict, list)):
                    val = self._truncate_value(json.dumps(val))
                else:
                    val = self._truncate_value(val)
                row.append(str(val).ljust(widths[col]))
            lines.append("  ".join(row))

        lines.append(f"\n({len(items)} items)")
        return "\n".join(lines)

    def format_error(self, error: str) -> str:
        return f"error: {error}"

    def format_success(self, message: str) -> str:
        return f"ok: {message}"


class JsonFormatter(Formatter):
    """JSON output for piping to other tools."""

    def __init__(self, indent: Optional[int] = 2):
        self.indent = indent

    def format_item(self, item: Dict[str, Any], fields: Optional[List[str]] = None) -> str:
        if fields:
            item = {k: v for k, v in item.items() if k in fields}
        return json.dumps(item, indent=self.indent, default=str)

    def format_list(self, items: List[Dict[str, Any]], fields: Optional[List[str]] = None) -> str:
        if fields:
            items = [{k: v for k, v in item.items() if k in fields} for item in items]
        return json.dumps(items, indent=self.indent, default=str)

    def format_error(self, error: str) -> str:
        return json.dumps({"error": error}, indent=self.indent)

    def format_success(self, message: str) -> str:
        return json.dumps({"status": "ok", "message": message}, indent=self.indent)


class RawFormatter(Formatter):
    """Minimal output for scripting."""

    def __init__(self, separator: str = "\t"):
        self.separator = separator

    def format_item(self, item: Dict[str, Any], fields: Optional[List[str]] = None) -> str:
        if fields:
            values = [str(item.get(f, "")) for f in fields]
        else:
            values = [str(v) for v in item.values()]
        return self.separator.join(values)

    def format_list(self, items: List[Dict[str, Any]], fields: Optional[List[str]] = None) -> str:
        lines = [self.format_item(item, fields) for item in items]
        return "\n".join(lines)

    def format_error(self, error: str) -> str:
        return f"ERROR: {error}"

    def format_success(self, message: str) -> str:
        return message


def get_formatter(format_type: str = "table", **kwargs) -> Formatter:
    """
    Get a formatter instance by type.

    Args:
        format_type: One of "table", "json", "raw"
        **kwargs: Additional arguments for the formatter

    Returns:
        Formatter instance
    """
    formatters = {
        "table": TableFormatter,
        "json": JsonFormatter,
        "raw": RawFormatter,
    }

    if format_type not in formatters:
        raise ValueError(f"Unknown format: {format_type}. Use: {list(formatters.keys())}")

    return formatters[format_type](**kwargs)
