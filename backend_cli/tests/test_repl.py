"""
Tests for lgctl REPL module.
"""

import pytest

from lgctl.repl import REPL


class TestREPLInit:
    """Tests for REPL initialization."""

    def test_init(self, mock_client, table_formatter):
        """Test REPL initialization."""
        repl = REPL(mock_client, table_formatter)
        assert repl.client is mock_client
        assert repl.formatter is table_formatter
        assert repl.current_namespace is None

    def test_init_command_handlers(self, mock_client, table_formatter):
        """Test REPL initializes all command handlers."""
        repl = REPL(mock_client, table_formatter)
        assert repl.store is not None
        assert repl.threads_cmd is not None
        assert repl.runs_cmd is not None
        assert repl.assistants_cmd is not None
        assert repl.crons_cmd is not None
        assert repl.ops is not None


class TestREPLPrompt:
    """Tests for REPL prompt generation."""

    def test_prompt_default(self, mock_client, table_formatter):
        """Test default prompt."""
        repl = REPL(mock_client, table_formatter)
        assert repl._prompt() == "lgctl> "

    def test_prompt_with_namespace(self, mock_client, table_formatter):
        """Test prompt with namespace set."""
        repl = REPL(mock_client, table_formatter)
        repl.current_namespace = "user,123"
        assert repl._prompt() == "[user,123]> "


class TestREPLNamespaceResolution:
    """Tests for REPL namespace resolution."""

    def test_resolve_namespace_none(self, mock_client, table_formatter):
        """Test resolving None uses current namespace."""
        repl = REPL(mock_client, table_formatter)
        repl.current_namespace = "user,123"
        assert repl._resolve_namespace() == "user,123"

    def test_resolve_namespace_empty_current(self, mock_client, table_formatter):
        """Test resolving with no current namespace."""
        repl = REPL(mock_client, table_formatter)
        assert repl._resolve_namespace() == ""

    def test_resolve_namespace_explicit(self, mock_client, table_formatter):
        """Test resolving explicit namespace."""
        repl = REPL(mock_client, table_formatter)
        repl.current_namespace = "user,123"
        assert repl._resolve_namespace("other,ns") == "other,ns"

    def test_resolve_namespace_parent(self, mock_client, table_formatter):
        """Test resolving parent namespace (..)."""
        repl = REPL(mock_client, table_formatter)
        repl.current_namespace = "user,123,preferences"
        assert repl._resolve_namespace("..") == "user,123"

    def test_resolve_namespace_parent_at_top(self, mock_client, table_formatter):
        """Test resolving parent at top level."""
        repl = REPL(mock_client, table_formatter)
        repl.current_namespace = "user"
        assert repl._resolve_namespace("..") == ""

    def test_resolve_namespace_parent_no_current(self, mock_client, table_formatter):
        """Test resolving parent with no current namespace."""
        repl = REPL(mock_client, table_formatter)
        assert repl._resolve_namespace("..") == ""


class TestREPLCommandHandling:
    """Tests for REPL command handling."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_handle_empty_command(self, repl):
        """Test handling empty command."""
        result = await repl._handle_command("")
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_whitespace_command(self, repl):
        """Test handling whitespace command."""
        result = await repl._handle_command("   ")
        assert result is True

    @pytest.mark.asyncio
    async def test_exit_command(self, repl):
        """Test exit command returns False."""
        result = await repl._handle_command("exit")
        assert result is False

    @pytest.mark.asyncio
    async def test_quit_command(self, repl):
        """Test quit command returns False."""
        result = await repl._handle_command("quit")
        assert result is False

    @pytest.mark.asyncio
    async def test_q_command(self, repl):
        """Test q shortcut returns False."""
        result = await repl._handle_command("q")
        assert result is False

    @pytest.mark.asyncio
    async def test_help_command(self, repl, capsys):
        """Test help command."""
        result = await repl._handle_command("help")
        assert result is True
        captured = capsys.readouterr()
        assert "lgctl REPL" in captured.out

    @pytest.mark.asyncio
    async def test_help_aliases(self, repl):
        """Test help command aliases."""
        assert await repl._handle_command("h") is True
        assert await repl._handle_command("?") is True

    @pytest.mark.asyncio
    async def test_clear_command(self, repl):
        """Test clear command."""
        result = await repl._handle_command("clear")
        assert result is True

    @pytest.mark.asyncio
    async def test_pwd_command(self, repl, capsys):
        """Test pwd command."""
        repl.current_namespace = "user,123"
        result = await repl._handle_command("pwd")
        assert result is True
        captured = capsys.readouterr()
        assert "user,123" in captured.out

    @pytest.mark.asyncio
    async def test_pwd_no_namespace(self, repl, capsys):
        """Test pwd with no namespace."""
        result = await repl._handle_command("pwd")
        assert result is True
        captured = capsys.readouterr()
        assert "(root)" in captured.out


class TestREPLNavigationCommands:
    """Tests for REPL navigation commands."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_use_command(self, repl, capsys):
        """Test use command sets namespace."""
        result = await repl._handle_command("use user,123")
        assert result is True
        assert repl.current_namespace == "user,123"
        captured = capsys.readouterr()
        assert "user,123" in captured.out

    @pytest.mark.asyncio
    async def test_cd_command(self, repl):
        """Test cd command (alias for use)."""
        await repl._handle_command("cd user,123")
        assert repl.current_namespace == "user,123"

    @pytest.mark.asyncio
    async def test_use_clear(self, repl, capsys):
        """Test use without argument clears namespace."""
        repl.current_namespace = "user,123"
        await repl._handle_command("use")
        assert repl.current_namespace is None
        captured = capsys.readouterr()
        assert "cleared" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_use_root(self, repl):
        """Test use / goes to root."""
        repl.current_namespace = "user,123"
        await repl._handle_command("use /")
        assert repl.current_namespace is None

    @pytest.mark.asyncio
    async def test_dotdot_command(self, repl, capsys):
        """Test .. command goes up one level."""
        repl.current_namespace = "user,123,preferences"
        await repl._handle_command("..")
        assert repl.current_namespace == "user,123"

    @pytest.mark.asyncio
    async def test_use_dotdot(self, repl):
        """Test use .. goes up one level."""
        repl.current_namespace = "user,123"
        await repl._handle_command("use ..")
        # Goes up from user,123 to user
        assert repl.current_namespace == "user"

    @pytest.mark.asyncio
    async def test_use_dotdot_to_root(self, repl):
        """Test use .. at single level goes to root."""
        repl.current_namespace = "user"
        await repl._handle_command("use ..")
        assert repl.current_namespace is None


class TestREPLStoreCommands:
    """Tests for REPL store commands."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_command(self, repl):
        """Test ls command."""
        result = await repl._handle_command("ls")
        assert result is True

    @pytest.mark.asyncio
    async def test_l_shortcut(self, repl):
        """Test l shortcut for ls."""
        result = await repl._handle_command("l")
        assert result is True

    @pytest.mark.asyncio
    async def test_ls_with_namespace(self, repl):
        """Test ls with namespace."""
        result = await repl._handle_command("ls user,123")
        assert result is True

    @pytest.mark.asyncio
    async def test_ls_items_flag(self, repl):
        """Test ls -i flag."""
        result = await repl._handle_command("ls -i user,123")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_command(self, repl):
        """Test get command."""
        result = await repl._handle_command("get user,123 preferences")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_with_current_namespace(self, repl):
        """Test get using current namespace."""
        repl.current_namespace = "user,123"
        result = await repl._handle_command("get preferences")
        assert result is True

    @pytest.mark.asyncio
    async def test_g_shortcut(self, repl):
        """Test g shortcut for get."""
        repl.current_namespace = "user,123"
        result = await repl._handle_command("g preferences")
        assert result is True

    @pytest.mark.asyncio
    async def test_cat_command(self, repl):
        """Test cat command (alias for get)."""
        result = await repl._handle_command("cat user,123 preferences")
        assert result is True

    @pytest.mark.asyncio
    async def test_put_command(self, repl, capsys):
        """Test put command."""
        result = await repl._handle_command("put user,999 test_key test_value")
        assert result is True
        captured = capsys.readouterr()
        assert "stored" in captured.out.lower() or "ok" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_put_with_current_namespace(self, repl, capsys):
        """Test put using current namespace."""
        repl.current_namespace = "user,999"
        result = await repl._handle_command("put test_key test_value")
        assert result is True

    @pytest.mark.asyncio
    async def test_put_json_value(self, repl, capsys):
        """Test put with JSON value."""
        result = await repl._handle_command('put user,999 json_key {"data": 123}')
        assert result is True

    @pytest.mark.asyncio
    async def test_rm_command(self, repl, capsys):
        """Test rm command."""
        result = await repl._handle_command("rm user,123 preferences")
        assert result is True
        captured = capsys.readouterr()
        assert "deleted" in captured.out.lower() or "ok" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_search_command(self, repl):
        """Test search command."""
        result = await repl._handle_command("search user,123 theme")
        assert result is True

    @pytest.mark.asyncio
    async def test_s_shortcut(self, repl):
        """Test s shortcut for search."""
        repl.current_namespace = "user,123"
        result = await repl._handle_command("s theme")
        assert result is True

    @pytest.mark.asyncio
    async def test_count_command(self, repl, capsys):
        """Test count command."""
        result = await repl._handle_command("count user,123")
        assert result is True
        captured = capsys.readouterr()
        assert "items" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_tree_command(self, repl):
        """Test tree command."""
        result = await repl._handle_command("tree")
        assert result is True


class TestREPLThreadCommands:
    """Tests for REPL thread commands."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_threads_command(self, repl):
        """Test threads command."""
        result = await repl._handle_command("threads")
        assert result is True

    @pytest.mark.asyncio
    async def test_threads_with_limit(self, repl):
        """Test threads command with limit."""
        result = await repl._handle_command("threads 5")
        assert result is True

    @pytest.mark.asyncio
    async def test_thread_command(self, repl):
        """Test thread command."""
        result = await repl._handle_command("thread thread-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_state_command(self, repl):
        """Test state command."""
        result = await repl._handle_command("state thread-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_history_command(self, repl):
        """Test history command."""
        result = await repl._handle_command("history thread-001")
        assert result is True


class TestREPLAssistantCommands:
    """Tests for REPL assistant commands."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_assistants_command(self, repl):
        """Test assistants command."""
        result = await repl._handle_command("assistants")
        assert result is True

    @pytest.mark.asyncio
    async def test_assistant_command(self, repl):
        """Test assistant command."""
        result = await repl._handle_command("assistant assistant-001")
        assert result is True


class TestREPLRunCommands:
    """Tests for REPL run commands."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_runs_command(self, repl):
        """Test runs command."""
        result = await repl._handle_command("runs thread-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_run_command(self, repl):
        """Test run command."""
        result = await repl._handle_command("run thread-001 run-001")
        assert result is True


class TestREPLOpsCommands:
    """Tests for REPL ops commands."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_analyze_command(self, repl, capsys):
        """Test analyze command."""
        result = await repl._handle_command("analyze")
        assert result is True
        captured = capsys.readouterr()
        assert "Memory Analysis" in captured.out or "namespaces" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_stats_command(self, repl):
        """Test stats command."""
        result = await repl._handle_command("stats")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_command(self, repl):
        """Test find command."""
        result = await repl._handle_command("find user,123 -k pref")
        assert result is True

    @pytest.mark.asyncio
    async def test_grep_command(self, repl):
        """Test grep command."""
        result = await repl._handle_command("grep theme user,123")
        assert result is True

    @pytest.mark.asyncio
    async def test_export_command(self, repl):
        """Test export command."""
        result = await repl._handle_command("export user,123")
        assert result is True


class TestREPLErrorHandling:
    """Tests for REPL error handling."""

    @pytest.fixture
    def repl(self, mock_client, table_formatter):
        """Provide REPL instance."""
        return REPL(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_unknown_command(self, repl, capsys):
        """Test unknown command handling."""
        result = await repl._handle_command("unknowncommand")
        assert result is True
        captured = capsys.readouterr()
        assert "Unknown command" in captured.out

    @pytest.mark.asyncio
    async def test_missing_arguments(self, repl, capsys):
        """Test missing arguments shows usage."""
        result = await repl._handle_command("thread")
        assert result is True
        captured = capsys.readouterr()
        assert "Usage" in captured.out

    @pytest.mark.asyncio
    async def test_command_error_handling(self, repl, capsys, mock_client):
        """Test error handling in commands."""

        # Make store raise an exception
        async def raise_error(*args, **kwargs):
            raise Exception("Test error")

        repl.store.ls = raise_error

        result = await repl._handle_command("ls")
        assert result is True  # Should continue despite error
        captured = capsys.readouterr()
        assert "Error" in captured.out


class TestREPLHelp:
    """Tests for REPL help content."""

    def test_help_contains_navigation(self, mock_client, table_formatter):
        """Test help contains navigation section."""
        repl = REPL(mock_client, table_formatter)
        assert "Navigation" in repl.HELP

    def test_help_contains_store_commands(self, mock_client, table_formatter):
        """Test help contains store commands."""
        repl = REPL(mock_client, table_formatter)
        assert "Store Commands" in repl.HELP
        assert "ls" in repl.HELP
        assert "get" in repl.HELP
        assert "put" in repl.HELP

    def test_help_contains_thread_commands(self, mock_client, table_formatter):
        """Test help contains thread commands."""
        repl = REPL(mock_client, table_formatter)
        assert "Thread Commands" in repl.HELP
        assert "threads" in repl.HELP

    def test_help_contains_shortcuts(self, mock_client, table_formatter):
        """Test help contains shortcuts."""
        repl = REPL(mock_client, table_formatter)
        assert "Shortcuts" in repl.HELP
