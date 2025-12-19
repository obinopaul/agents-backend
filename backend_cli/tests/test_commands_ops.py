"""
Tests for lgctl commands/ops module.
"""

import json
import os
import tempfile

import pytest

from lgctl.commands.ops import MemoryOps


class TestMemoryOps:
    """Tests for MemoryOps class."""

    @pytest.fixture
    def memory_ops(self, mock_client, table_formatter):
        """Provide MemoryOps instance."""
        return MemoryOps(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_analyze_all(self, memory_ops):
        """Test analyzing all memory."""
        result = await memory_ops.analyze()
        assert "total_namespaces" in result
        assert "total_items" in result
        assert "namespaces" in result
        assert "analyzed_at" in result

    @pytest.mark.asyncio
    async def test_analyze_with_namespace(self, memory_ops):
        """Test analyzing specific namespace."""
        result = await memory_ops.analyze(namespace="user")
        assert "namespace" in result
        assert isinstance(result["namespaces"], list)

    @pytest.mark.asyncio
    async def test_analyze_detailed(self, memory_ops):
        """Test detailed analysis."""
        result = await memory_ops.analyze(detailed=True)
        assert "total_items" in result
        # Detailed should include more info per namespace
        for ns in result.get("namespaces", []):
            if ns.get("item_count", 0) > 0:
                assert "item_count" in ns

    @pytest.mark.asyncio
    async def test_analyze_largest_namespace(self, memory_ops):
        """Test that largest namespace is identified."""
        result = await memory_ops.analyze()
        if result.get("namespaces"):
            assert "largest_namespace" in result

    @pytest.mark.asyncio
    async def test_stats(self, memory_ops):
        """Test getting memory statistics."""
        result = await memory_ops.stats()
        assert "total_namespaces" in result
        assert "total_items" in result
        assert "approx_size_bytes" in result
        assert "approx_size_mb" in result
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_prune_dry_run(self, memory_ops):
        """Test pruning with dry run."""
        result = await memory_ops.prune(namespace="user,123", days_old=30, dry_run=True)
        assert result["dry_run"] is True
        assert "total_items" in result
        assert "to_delete" in result
        assert "deleted" not in result  # Dry run shouldn't delete

    @pytest.mark.asyncio
    async def test_prune_with_before_timestamp(self, memory_ops):
        """Test pruning with before timestamp."""
        result = await memory_ops.prune(
            namespace="user,123", before="2024-01-01T00:00:00Z", dry_run=True
        )
        assert result["dry_run"] is True

    @pytest.mark.asyncio
    async def test_prune_actual_deletion(self, memory_ops):
        """Test actual pruning (dry_run=False)."""
        result = await memory_ops.prune(
            namespace="user,123",
            days_old=1,  # Items older than 1 day
            dry_run=False,
        )
        assert result["dry_run"] is False
        assert "deleted" in result

    @pytest.mark.asyncio
    async def test_prune_with_filter_fn(self, memory_ops):
        """Test pruning with custom filter function."""

        def should_delete(item):
            return item.get("key", "").startswith("temp_")

        result = await memory_ops.prune(namespace="user,123", filter_fn=should_delete, dry_run=True)
        assert "to_delete" in result

    @pytest.mark.asyncio
    async def test_export_to_stdout_jsonl(self, memory_ops):
        """Test exporting to stdout as JSONL."""
        result = await memory_ops.export(namespace="user,123", format="jsonl")
        assert "exported" in result
        assert "data" in result
        # JSONL format should have newline-separated JSON
        if result.get("data"):
            lines = result["data"].split("\n")
            for line in lines:
                if line.strip():
                    # Each line should be valid JSON
                    json.loads(line)

    @pytest.mark.asyncio
    async def test_export_to_stdout_json(self, memory_ops):
        """Test exporting to stdout as JSON."""
        result = await memory_ops.export(namespace="user,123", format="json")
        assert "exported" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_export_to_file_jsonl(self, memory_ops):
        """Test exporting to file as JSONL."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name

        try:
            result = await memory_ops.export(
                namespace="user,123", output_file=temp_path, format="jsonl"
            )
            assert result["file"] == temp_path
            assert result["format"] == "jsonl"

            # Verify file content
            with open(temp_path, "r") as f:
                content = f.read()
                if content.strip():
                    for line in content.strip().split("\n"):
                        json.loads(line)
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_export_to_file_json(self, memory_ops):
        """Test exporting to file as JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            result = await memory_ops.export(
                namespace="user,123", output_file=temp_path, format="json"
            )
            assert result["file"] == temp_path

            # Verify file content is valid JSON
            with open(temp_path, "r") as f:
                data = json.load(f)
                assert isinstance(data, list)
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_export_with_key_pattern(self, memory_ops):
        """Test exporting with key pattern filter."""
        result = await memory_ops.export(namespace="user,123", key_pattern="pref")
        assert "exported" in result

    @pytest.mark.asyncio
    async def test_export_with_value_contains(self, memory_ops):
        """Test exporting with value contains filter."""
        result = await memory_ops.export(namespace="user,123", value_contains="theme")
        assert "exported" in result

    @pytest.mark.asyncio
    async def test_import_from_jsonl(self, memory_ops):
        """Test importing from JSONL file."""
        # Create a temp JSONL file
        test_data = [
            {"namespace": ["test", "import"], "key": "key1", "value": {"data": 1}},
            {"namespace": ["test", "import"], "key": "key2", "value": {"data": 2}},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            temp_path = f.name

        try:
            result = await memory_ops.import_(input_file=temp_path, dry_run=True)
            assert result["total_items"] == 2
            assert result["dry_run"] is True
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_import_from_json(self, memory_ops):
        """Test importing from JSON file."""
        test_data = [
            {"namespace": ["test", "import"], "key": "key1", "value": {"data": 1}},
            {"namespace": ["test", "import"], "key": "key2", "value": {"data": 2}},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name

        try:
            result = await memory_ops.import_(input_file=temp_path, dry_run=True)
            assert result["total_items"] == 2
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_import_with_prefix(self, memory_ops):
        """Test importing with namespace prefix."""
        test_data = [
            {"namespace": ["original"], "key": "key1", "value": {"data": 1}},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            temp_path = f.name

        try:
            result = await memory_ops.import_(
                input_file=temp_path, namespace_prefix="imported", dry_run=True
            )
            assert result["total_items"] == 1
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_import_actual(self, memory_ops):
        """Test actual import (dry_run=False)."""
        test_data = [
            {"namespace": ["test", "actual"], "key": "key1", "value": {"data": 1}},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            temp_path = f.name

        try:
            result = await memory_ops.import_(input_file=temp_path, dry_run=False, overwrite=True)
            assert "imported" in result
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_dedupe_dry_run(self, memory_ops):
        """Test deduplication with dry run."""
        result = await memory_ops.dedupe(namespace="user,123", dry_run=True)
        assert result["dry_run"] is True
        assert "total_items" in result
        assert "unique_items" in result
        assert "duplicates" in result
        assert "duplicate_keys" in result

    @pytest.mark.asyncio
    async def test_dedupe_actual(self, memory_ops):
        """Test actual deduplication."""
        result = await memory_ops.dedupe(namespace="user,123", dry_run=False)
        assert result["dry_run"] is False
        assert "deleted" in result

    @pytest.mark.asyncio
    async def test_dedupe_with_key_fn(self, memory_ops):
        """Test deduplication with custom key function."""

        def custom_key(value):
            return value.get("id", str(value))

        result = await memory_ops.dedupe(namespace="user,123", key_fn=custom_key, dry_run=True)
        assert "duplicates" in result

    @pytest.mark.asyncio
    async def test_search_all(self, memory_ops):
        """Test searching across all namespaces."""
        result = await memory_ops.search_all(query="theme")
        assert isinstance(result, list)
        # Results should have score if matched by query
        for item in result:
            assert "namespace" in item
            assert "key" in item

    @pytest.mark.asyncio
    async def test_search_all_with_limit(self, memory_ops):
        """Test search_all with limit."""
        result = await memory_ops.search_all(query="", limit=5)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_find_by_key_pattern(self, memory_ops):
        """Test finding by key pattern."""
        result = await memory_ops.find(namespace="user,123", key_pattern="pref")
        assert isinstance(result, list)
        for item in result:
            assert "pref" in item["key"]

    @pytest.mark.asyncio
    async def test_find_by_value_contains(self, memory_ops):
        """Test finding by value contains."""
        result = await memory_ops.find(namespace="user,123", value_contains="dark")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_find_with_limit(self, memory_ops):
        """Test finding with limit."""
        result = await memory_ops.find(namespace="user,123", limit=5)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_find_all_namespaces(self, memory_ops):
        """Test finding across all namespaces."""
        result = await memory_ops.find(key_pattern="item")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_grep_basic(self, memory_ops):
        """Test basic grep search."""
        result = await memory_ops.grep(pattern="theme", namespace="user,123")
        assert isinstance(result, list)
        for match in result:
            assert "namespace" in match
            assert "key" in match
            # Should have context or match
            assert "context" in match or "match" in match

    @pytest.mark.asyncio
    async def test_grep_regex_pattern(self, memory_ops):
        """Test grep with regex pattern."""
        result = await memory_ops.grep(
            pattern=r"\d+",  # Match numbers
            namespace="user,123",
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_grep_all_namespaces(self, memory_ops):
        """Test grep across all namespaces."""
        result = await memory_ops.grep(pattern="theme", namespace="")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_grep_with_limit(self, memory_ops):
        """Test grep with limit."""
        result = await memory_ops.grep(pattern=".*", namespace="user,123", limit=5)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_grep_invalid_regex_fallback(self, memory_ops):
        """Test grep falls back to string match for invalid regex."""
        result = await memory_ops.grep(
            pattern="[invalid(regex",  # Invalid regex
            namespace="user,123",
        )
        # Should still work (falls back to string match)
        assert isinstance(result, list)


class TestMemoryOpsEdgeCases:
    """Edge case tests for MemoryOps."""

    @pytest.fixture
    def memory_ops(self, mock_client, table_formatter):
        """Provide MemoryOps instance."""
        return MemoryOps(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_analyze_empty_namespace(self, memory_ops, mock_client):
        """Test analyzing when no namespaces exist."""

        # Mock empty response
        async def empty_namespaces(*args, **kwargs):
            return {"namespaces": []}

        mock_client.store.list_namespaces = empty_namespaces

        result = await memory_ops.analyze()
        assert result["total_namespaces"] == 0
        assert result["total_items"] == 0

    @pytest.mark.asyncio
    async def test_export_empty_namespace(self, memory_ops, mock_client):
        """Test exporting empty namespace."""

        async def empty_items(*args, **kwargs):
            return {"items": []}

        mock_client.store.search_items = empty_items

        result = await memory_ops.export(namespace="empty")
        assert result["exported"] == 0

    @pytest.mark.asyncio
    async def test_dedupe_no_duplicates(self, memory_ops, mock_client):
        """Test deduplication when no duplicates exist."""

        async def unique_items(*args, **kwargs):
            return {
                "items": [
                    {"namespace": ("test",), "key": "k1", "value": {"unique": 1}},
                    {"namespace": ("test",), "key": "k2", "value": {"unique": 2}},
                ]
            }

        mock_client.store.search_items = unique_items

        result = await memory_ops.dedupe(namespace="test", dry_run=True)
        assert result["duplicates"] == 0

    @pytest.mark.asyncio
    async def test_find_no_matches(self, memory_ops, mock_client):
        """Test finding when no matches exist."""

        async def no_items(*args, **kwargs):
            return {"items": []}

        mock_client.store.search_items = no_items

        result = await memory_ops.find(namespace="test", key_pattern="nonexistent")
        assert result == []

    @pytest.mark.asyncio
    async def test_grep_no_matches(self, memory_ops, mock_client):
        """Test grep when no matches exist."""

        async def no_items(*args, **kwargs):
            return {"items": []}

        mock_client.store.search_items = no_items

        result = await memory_ops.grep(pattern="nonexistent", namespace="test")
        assert result == []
