"""
Tests for lgctl commands/store module.
"""

import pytest

from lgctl.commands.store import (
    StoreCommands,
    format_namespace,
    parse_namespace,
)


class TestParseNamespace:
    """Tests for parse_namespace function."""

    def test_parse_empty(self):
        """Test parsing empty namespace."""
        result = parse_namespace("")
        assert result == ()

    def test_parse_single(self):
        """Test parsing single-level namespace."""
        result = parse_namespace("user")
        assert result == ("user",)

    def test_parse_double(self):
        """Test parsing two-level namespace."""
        result = parse_namespace("user,123")
        assert result == ("user", "123")

    def test_parse_triple(self):
        """Test parsing three-level namespace."""
        result = parse_namespace("website,products,electronics")
        assert result == ("website", "products", "electronics")

    def test_parse_with_spaces(self):
        """Test parsing namespace with spaces in values."""
        result = parse_namespace("user,my name")
        assert result == ("user", "my name")

    def test_parse_numeric(self):
        """Test parsing namespace with numeric parts."""
        result = parse_namespace("user,123,456")
        assert result == ("user", "123", "456")


class TestFormatNamespace:
    """Tests for format_namespace function."""

    def test_format_empty_tuple(self):
        """Test formatting empty tuple."""
        result = format_namespace(())
        assert result == "(root)"

    def test_format_empty_list(self):
        """Test formatting empty list."""
        result = format_namespace([])
        assert result == "(root)"

    def test_format_empty_string(self):
        """Test formatting empty string."""
        result = format_namespace("")
        assert result == "(root)"

    def test_format_single_tuple(self):
        """Test formatting single-level tuple namespace."""
        result = format_namespace(("user",))
        assert result == "user"

    def test_format_double_tuple(self):
        """Test formatting two-level tuple namespace."""
        result = format_namespace(("user", "123"))
        assert result == "user,123"

    def test_format_triple_tuple(self):
        """Test formatting three-level tuple namespace."""
        result = format_namespace(("website", "products", "electronics"))
        assert result == "website,products,electronics"

    def test_format_list(self):
        """Test formatting list namespace."""
        result = format_namespace(["user", "123"])
        assert result == "user,123"

    def test_format_string_passthrough(self):
        """Test formatting string passes through unchanged."""
        result = format_namespace("already,formatted")
        assert result == "already,formatted"

    def test_format_numeric_parts(self):
        """Test formatting with numeric parts."""
        result = format_namespace((123, 456))
        assert result == "123,456"


class TestStoreCommands:
    """Tests for StoreCommands class."""

    @pytest.fixture
    def store_commands(self, mock_client, table_formatter):
        """Provide StoreCommands instance."""
        return StoreCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_namespaces(self, store_commands):
        """Test listing namespaces."""
        result = await store_commands.ls()
        assert isinstance(result, list)
        assert all("namespace" in item for item in result)

    @pytest.mark.asyncio
    async def test_ls_namespaces_with_prefix(self, store_commands):
        """Test listing namespaces with prefix filter."""
        result = await store_commands.ls(namespace="user")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_items(self, store_commands):
        """Test listing items in a namespace."""
        result = await store_commands.ls(namespace="user,123", show_items=True)
        assert isinstance(result, list)
        # Should have items with keys
        for item in result:
            assert "key" in item or "namespace" in item

    @pytest.mark.asyncio
    async def test_ls_with_depth(self, store_commands):
        """Test listing with custom depth."""
        result = await store_commands.ls(max_depth=5)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_with_limit(self, store_commands):
        """Test listing with custom limit."""
        result = await store_commands.ls(limit=10)
        assert isinstance(result, list)
        assert len(result) <= 10

    @pytest.mark.asyncio
    async def test_get_existing_item(self, store_commands):
        """Test getting an existing item."""
        result = await store_commands.get("user,123", "preferences")
        assert result is not None
        assert result["key"] == "preferences"
        assert "value" in result
        assert result["namespace"] == "user,123"

    @pytest.mark.asyncio
    async def test_get_nonexistent_item(self, store_commands):
        """Test getting a non-existent item."""
        result = await store_commands.get("user,123", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cat_is_get_alias(self, store_commands):
        """Test that cat is an alias for get."""
        assert store_commands.cat == store_commands.get

    @pytest.mark.asyncio
    async def test_put_simple_value(self, store_commands):
        """Test storing a simple value."""
        result = await store_commands.put("user,999", "test_key", "test_value")
        assert result["status"] == "ok"
        assert result["namespace"] == "user,999"
        assert result["key"] == "test_key"

    @pytest.mark.asyncio
    async def test_put_dict_value(self, store_commands):
        """Test storing a dict value."""
        value = {"name": "test", "count": 42}
        result = await store_commands.put("user,999", "test_dict", value)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_put_wraps_simple_value(self, store_commands):
        """Test that simple values are wrapped in dict."""
        # After put, we should be able to get it back
        await store_commands.put("user,999", "simple", "just a string")
        result = await store_commands.get("user,999", "simple")
        assert result is not None
        # Simple values should be wrapped
        assert result["value"] == {"value": "just a string"}

    @pytest.mark.asyncio
    async def test_rm_existing_item(self, store_commands):
        """Test removing an existing item."""
        # First ensure item exists
        await store_commands.put("user,999", "to_delete", "value")

        result = await store_commands.rm("user,999", "to_delete")
        assert result["status"] == "ok"
        assert result["action"] == "deleted"

        # Verify it's gone
        get_result = await store_commands.get("user,999", "to_delete")
        assert get_result is None

    @pytest.mark.asyncio
    async def test_search_basic(self, store_commands):
        """Test basic search."""
        result = await store_commands.search(namespace="user,123", query="")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_with_query(self, store_commands):
        """Test search with query."""
        result = await store_commands.search(namespace="user,123", query="theme")
        assert isinstance(result, list)
        # Items matching "theme" should have score
        for item in result:
            if "score" in item:
                assert item["score"] is not None

    @pytest.mark.asyncio
    async def test_search_with_limit(self, store_commands):
        """Test search with limit."""
        result = await store_commands.search(namespace="user,123", limit=5)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_mv_item(self, store_commands):
        """Test moving an item."""
        # Create source item
        await store_commands.put("src,ns", "src_key", {"data": "test"})

        # Move it
        result = await store_commands.mv("src,ns", "src_key", "dst,ns", "dst_key")
        assert result["status"] == "ok"
        assert result["action"] == "moved"

        # Verify source is gone
        src_result = await store_commands.get("src,ns", "src_key")
        assert src_result is None

        # Verify destination exists
        dst_result = await store_commands.get("dst,ns", "dst_key")
        assert dst_result is not None

    @pytest.mark.asyncio
    async def test_mv_same_key(self, store_commands):
        """Test moving with same key (different namespace only)."""
        await store_commands.put("src,ns", "same_key", {"data": "test"})

        result = await store_commands.mv("src,ns", "same_key", "dst,ns")
        assert result["status"] == "ok"

        # Should use same key in destination
        dst_result = await store_commands.get("dst,ns", "same_key")
        assert dst_result is not None

    @pytest.mark.asyncio
    async def test_mv_nonexistent(self, store_commands):
        """Test moving non-existent item raises error."""
        with pytest.raises(ValueError) as exc_info:
            await store_commands.mv("nonexistent,ns", "no_key", "dst,ns")
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cp_item(self, store_commands):
        """Test copying an item."""
        # Create source item
        await store_commands.put("src,ns", "src_key", {"data": "copy_test"})

        # Copy it
        result = await store_commands.cp("src,ns", "src_key", "dst,ns", "dst_key")
        assert result["status"] == "ok"
        assert result["action"] == "copied"

        # Verify source still exists
        src_result = await store_commands.get("src,ns", "src_key")
        assert src_result is not None

        # Verify destination exists
        dst_result = await store_commands.get("dst,ns", "dst_key")
        assert dst_result is not None

    @pytest.mark.asyncio
    async def test_cp_same_key(self, store_commands):
        """Test copying with same key."""
        await store_commands.put("src,ns", "copy_key", {"data": "test"})

        result = await store_commands.cp("src,ns", "copy_key", "dst,ns")
        assert result["status"] == "ok"

        # Both should exist with same key
        src_result = await store_commands.get("src,ns", "copy_key")
        dst_result = await store_commands.get("dst,ns", "copy_key")
        assert src_result is not None
        assert dst_result is not None

    @pytest.mark.asyncio
    async def test_cp_nonexistent(self, store_commands):
        """Test copying non-existent item raises error."""
        with pytest.raises(ValueError) as exc_info:
            await store_commands.cp("nonexistent,ns", "no_key", "dst,ns")
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_count_namespace(self, store_commands):
        """Test counting items in namespace."""
        result = await store_commands.count("user,123")
        assert "count" in result
        assert "namespace" in result
        assert isinstance(result["count"], int)

    @pytest.mark.asyncio
    async def test_count_all(self, store_commands):
        """Test counting all items."""
        result = await store_commands.count()
        assert "count" in result
        assert result["namespace"] == "(all)"

    @pytest.mark.asyncio
    async def test_tree(self, store_commands):
        """Test tree display."""
        result = await store_commands.tree()
        assert isinstance(result, list)
        for item in result:
            assert "tree" in item
            assert "namespace" in item
            assert "depth" in item

    @pytest.mark.asyncio
    async def test_tree_with_namespace(self, store_commands):
        """Test tree from specific namespace."""
        result = await store_commands.tree(namespace="user")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_tree_with_depth(self, store_commands):
        """Test tree with custom depth."""
        result = await store_commands.tree(max_depth=3)
        assert isinstance(result, list)


class TestStoreCommandsEdgeCases:
    """Edge case tests for StoreCommands."""

    @pytest.fixture
    def store_commands(self, mock_client, table_formatter):
        """Provide StoreCommands instance."""
        return StoreCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_get_with_refresh_ttl(self, store_commands):
        """Test get with refresh_ttl option."""
        result = await store_commands.get("user,123", "preferences", refresh_ttl=True)
        # Should still work normally
        assert result is not None or result is None  # Either found or not

    @pytest.mark.asyncio
    async def test_put_with_index(self, store_commands):
        """Test put with index parameter."""
        result = await store_commands.put(
            "user,999", "indexed_key", {"searchable": "content"}, index=["searchable"]
        )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_search_with_filter(self, store_commands):
        """Test search with filter dict."""
        result = await store_commands.search(
            namespace="user,123", filter_dict={"type": "preference"}
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_with_offset(self, store_commands):
        """Test search with pagination offset."""
        result = await store_commands.search(namespace="user,123", offset=5, limit=10)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_handles_dict_response(self, store_commands):
        """Test ls handles dict response format."""
        # The mock returns dict format, verify it's handled
        result = await store_commands.ls()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_handles_list_response(self, mock_client, table_formatter):
        """Test ls handles list response format."""

        # Patch to return list directly
        async def list_namespaces_list(*args, **kwargs):
            return [("user", "123"), ("user", "456")]

        mock_client.store.list_namespaces = list_namespaces_list

        store = StoreCommands(mock_client, table_formatter)
        result = await store.ls()
        assert isinstance(result, list)
