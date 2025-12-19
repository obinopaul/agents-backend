"""
Tests for lgctl CLI module.
"""

import argparse
from unittest.mock import AsyncMock, patch

import pytest

from lgctl.cli import create_parser, main, run_command


class TestCreateParser:
    """Tests for create_parser function."""

    def test_parser_created(self):
        """Test parser is created successfully."""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_parser_prog_name(self):
        """Test parser has correct program name."""
        parser = create_parser()
        assert parser.prog == "lgctl"

    def test_global_options(self):
        """Test global options are present."""
        parser = create_parser()
        args = parser.parse_args(["--url", "http://test.com", "store", "ls"])
        assert args.url == "http://test.com"

    def test_format_option(self):
        """Test format option."""
        parser = create_parser()
        args = parser.parse_args(["--format", "json", "store", "ls"])
        assert args.format == "json"

    def test_format_option_choices(self):
        """Test format option only accepts valid choices."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--format", "invalid", "store", "ls"])

    def test_quiet_option(self):
        """Test quiet option."""
        parser = create_parser()
        args = parser.parse_args(["-q", "store", "ls"])
        assert args.quiet is True

    def test_api_key_option(self):
        """Test API key option."""
        parser = create_parser()
        args = parser.parse_args(["-k", "test-key", "store", "ls"])
        assert args.api_key == "test-key"


class TestStoreSubcommands:
    """Tests for store subcommands."""

    def test_store_ls(self):
        """Test store ls command."""
        parser = create_parser()
        args = parser.parse_args(["store", "ls"])
        assert args.command == "store"
        assert args.subcommand == "ls"

    def test_store_ls_with_namespace(self):
        """Test store ls with namespace."""
        parser = create_parser()
        args = parser.parse_args(["store", "ls", "user,123"])
        assert args.namespace == "user,123"

    def test_store_ls_with_depth(self):
        """Test store ls with depth."""
        parser = create_parser()
        args = parser.parse_args(["store", "ls", "-d", "5"])
        assert args.depth == 5

    def test_store_ls_with_items(self):
        """Test store ls with items flag."""
        parser = create_parser()
        args = parser.parse_args(["store", "ls", "-i", "user,123"])
        assert args.items is True

    def test_store_get(self):
        """Test store get command."""
        parser = create_parser()
        args = parser.parse_args(["store", "get", "user,123", "key"])
        assert args.subcommand == "get"
        assert args.namespace == "user,123"
        assert args.key == "key"

    def test_store_cat_alias(self):
        """Test store cat is alias for get."""
        parser = create_parser()
        args = parser.parse_args(["store", "cat", "user,123", "key"])
        assert args.subcommand == "cat"

    def test_store_put(self):
        """Test store put command."""
        parser = create_parser()
        args = parser.parse_args(["store", "put", "ns", "key", "value"])
        assert args.subcommand == "put"
        assert args.namespace == "ns"
        assert args.key == "key"
        assert args.value == ["value"]

    def test_store_put_with_json(self):
        """Test store put with JSON flag."""
        parser = create_parser()
        args = parser.parse_args(["store", "put", "ns", "key", '{"a": 1}', "-j"])
        assert args.json is True

    def test_store_rm(self):
        """Test store rm command."""
        parser = create_parser()
        args = parser.parse_args(["store", "rm", "ns", "key"])
        assert args.subcommand == "rm"

    def test_store_search(self):
        """Test store search command."""
        parser = create_parser()
        args = parser.parse_args(["store", "search", "ns", "query"])
        assert args.subcommand == "search"
        assert args.namespace == "ns"
        assert args.query == "query"

    def test_store_mv(self):
        """Test store mv command."""
        parser = create_parser()
        args = parser.parse_args(["store", "mv", "src", "key", "dst"])
        assert args.subcommand == "mv"
        assert args.src_namespace == "src"
        assert args.src_key == "key"
        assert args.dst_namespace == "dst"

    def test_store_cp(self):
        """Test store cp command."""
        parser = create_parser()
        args = parser.parse_args(["store", "cp", "src", "key", "dst"])
        assert args.subcommand == "cp"

    def test_store_count(self):
        """Test store count command."""
        parser = create_parser()
        args = parser.parse_args(["store", "count", "ns"])
        assert args.subcommand == "count"
        assert args.namespace == "ns"

    def test_store_tree(self):
        """Test store tree command."""
        parser = create_parser()
        args = parser.parse_args(["store", "tree"])
        assert args.subcommand == "tree"

    def test_store_alias(self):
        """Test store alias 's'."""
        parser = create_parser()
        args = parser.parse_args(["s", "ls"])
        assert args.command == "s"


class TestThreadSubcommands:
    """Tests for thread subcommands."""

    def test_threads_ls(self):
        """Test threads ls command."""
        parser = create_parser()
        args = parser.parse_args(["threads", "ls"])
        assert args.command == "threads"
        assert args.subcommand == "ls"

    def test_threads_ls_with_status(self):
        """Test threads ls with status filter."""
        parser = create_parser()
        args = parser.parse_args(["threads", "ls", "--status", "idle"])
        assert args.status == "idle"

    def test_threads_get(self):
        """Test threads get command."""
        parser = create_parser()
        args = parser.parse_args(["threads", "get", "thread-001"])
        assert args.subcommand == "get"
        assert args.thread_id == "thread-001"

    def test_threads_create(self):
        """Test threads create command."""
        parser = create_parser()
        args = parser.parse_args(["threads", "create"])
        assert args.subcommand == "create"

    def test_threads_create_with_id(self):
        """Test threads create with custom ID."""
        parser = create_parser()
        args = parser.parse_args(["threads", "create", "--id", "custom-id"])
        assert args.id == "custom-id"

    def test_threads_rm(self):
        """Test threads rm command."""
        parser = create_parser()
        args = parser.parse_args(["threads", "rm", "thread-001"])
        assert args.subcommand == "rm"

    def test_threads_state(self):
        """Test threads state command."""
        parser = create_parser()
        args = parser.parse_args(["threads", "state", "thread-001"])
        assert args.subcommand == "state"

    def test_threads_history(self):
        """Test threads history command."""
        parser = create_parser()
        args = parser.parse_args(["threads", "history", "thread-001"])
        assert args.subcommand == "history"

    def test_threads_alias(self):
        """Test threads alias 't'."""
        parser = create_parser()
        args = parser.parse_args(["t", "ls"])
        assert args.command == "t"


class TestRunSubcommands:
    """Tests for run subcommands."""

    def test_runs_ls(self):
        """Test runs ls command."""
        parser = create_parser()
        args = parser.parse_args(["runs", "ls", "thread-001"])
        assert args.command == "runs"
        assert args.subcommand == "ls"
        assert args.thread_id == "thread-001"

    def test_runs_get(self):
        """Test runs get command."""
        parser = create_parser()
        args = parser.parse_args(["runs", "get", "thread-001", "run-001"])
        assert args.subcommand == "get"
        assert args.run_id == "run-001"

    def test_runs_cancel(self):
        """Test runs cancel command."""
        parser = create_parser()
        args = parser.parse_args(["runs", "cancel", "thread-001", "run-001"])
        assert args.subcommand == "cancel"

    def test_runs_alias(self):
        """Test runs alias 'r'."""
        parser = create_parser()
        args = parser.parse_args(["r", "ls", "thread-001"])
        assert args.command == "r"


class TestAssistantSubcommands:
    """Tests for assistant subcommands."""

    def test_assistants_ls(self):
        """Test assistants ls command."""
        parser = create_parser()
        args = parser.parse_args(["assistants", "ls"])
        assert args.command == "assistants"
        assert args.subcommand == "ls"

    def test_assistants_get(self):
        """Test assistants get command."""
        parser = create_parser()
        args = parser.parse_args(["assistants", "get", "assistant-001"])
        assert args.subcommand == "get"
        assert args.assistant_id == "assistant-001"

    def test_assistants_schema(self):
        """Test assistants schema command."""
        parser = create_parser()
        args = parser.parse_args(["assistants", "schema", "assistant-001"])
        assert args.subcommand == "schema"

    def test_assistants_graph(self):
        """Test assistants graph command."""
        parser = create_parser()
        args = parser.parse_args(["assistants", "graph", "assistant-001"])
        assert args.subcommand == "graph"

    def test_assistants_alias(self):
        """Test assistants alias 'a'."""
        parser = create_parser()
        args = parser.parse_args(["a", "ls"])
        assert args.command == "a"


class TestCronSubcommands:
    """Tests for cron subcommands."""

    def test_crons_ls(self):
        """Test crons ls command."""
        parser = create_parser()
        args = parser.parse_args(["crons", "ls"])
        assert args.command == "crons"
        assert args.subcommand == "ls"

    def test_crons_get(self):
        """Test crons get command."""
        parser = create_parser()
        args = parser.parse_args(["crons", "get", "cron-001"])
        assert args.subcommand == "get"
        assert args.cron_id == "cron-001"

    def test_crons_rm(self):
        """Test crons rm command."""
        parser = create_parser()
        args = parser.parse_args(["crons", "rm", "cron-001"])
        assert args.subcommand == "rm"

    def test_crons_alias(self):
        """Test crons alias 'c'."""
        parser = create_parser()
        args = parser.parse_args(["c", "ls"])
        assert args.command == "c"


class TestOpsSubcommands:
    """Tests for ops subcommands."""

    def test_ops_analyze(self):
        """Test ops analyze command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "analyze"])
        assert args.command == "ops"
        assert args.subcommand == "analyze"

    def test_ops_analyze_detailed(self):
        """Test ops analyze with detailed flag."""
        parser = create_parser()
        args = parser.parse_args(["ops", "analyze", "-d"])
        assert args.detailed is True

    def test_ops_stats(self):
        """Test ops stats command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "stats"])
        assert args.subcommand == "stats"

    def test_ops_export(self):
        """Test ops export command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "export", "ns", "-o", "file.jsonl"])
        assert args.subcommand == "export"
        assert args.namespace == "ns"
        assert args.output == "file.jsonl"

    def test_ops_import(self):
        """Test ops import command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "import", "input.jsonl"])
        assert args.subcommand == "import"
        assert args.input_file == "input.jsonl"

    def test_ops_prune(self):
        """Test ops prune command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "prune", "ns", "--days", "30"])
        assert args.subcommand == "prune"
        assert args.days == 30

    def test_ops_dedupe(self):
        """Test ops dedupe command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "dedupe", "ns"])
        assert args.subcommand == "dedupe"

    def test_ops_find(self):
        """Test ops find command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "find", "ns", "-k", "pattern"])
        assert args.subcommand == "find"
        assert args.key == "pattern"

    def test_ops_grep(self):
        """Test ops grep command."""
        parser = create_parser()
        args = parser.parse_args(["ops", "grep", "pattern", "ns"])
        assert args.subcommand == "grep"
        assert args.pattern == "pattern"

    def test_ops_alias(self):
        """Test ops alias 'o'."""
        parser = create_parser()
        args = parser.parse_args(["o", "stats"])
        assert args.command == "o"


class TestReplCommand:
    """Tests for REPL command."""

    def test_repl_command(self):
        """Test repl command."""
        parser = create_parser()
        args = parser.parse_args(["repl"])
        assert args.command == "repl"


class TestRunCommand:
    """Tests for run_command function."""

    @pytest.mark.asyncio
    @patch("lgctl.cli.get_client")
    async def test_run_command_store_ls(self, mock_get_client, mock_client):
        """Test running store ls command."""
        mock_get_client.return_value = mock_client

        parser = create_parser()
        args = parser.parse_args(["--format", "json", "store", "ls"])

        result = await run_command(args)
        assert result == 0

    @pytest.mark.asyncio
    @patch("lgctl.cli.get_client")
    async def test_run_command_returns_error_on_exception(self, mock_get_client, mock_client):
        """Test run_command returns error code on exception during command execution."""
        # Mock client that raises exception during store operations
        mock_get_client.return_value = mock_client
        mock_client.store.list_namespaces = AsyncMock(side_effect=Exception("Store error"))

        parser = create_parser()
        args = parser.parse_args(["store", "ls"])

        result = await run_command(args)
        assert result == 1

    @pytest.mark.asyncio
    @patch("lgctl.cli.get_client")
    async def test_run_command_raises_on_client_error(self, mock_get_client):
        """Test run_command raises if get_client fails (not inside try block)."""
        mock_get_client.side_effect = Exception("Connection error")

        parser = create_parser()
        args = parser.parse_args(["store", "ls"])

        # get_client is called outside try block, so exception propagates
        with pytest.raises(Exception) as exc_info:
            await run_command(args)
        assert "Connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("lgctl.cli.get_client")
    async def test_run_command_no_subcommand(self, mock_get_client, mock_client):
        """Test run_command with no subcommand shows usage."""
        mock_get_client.return_value = mock_client

        parser = create_parser()
        args = parser.parse_args(["store"])
        args.subcommand = None

        result = await run_command(args)
        assert result == 1


class TestMainFunction:
    """Tests for main entry point."""

    def test_main_no_command(self, capsys):
        """Test main with no command shows help."""
        with patch("sys.argv", ["lgctl"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        # Verify help was printed
        captured = capsys.readouterr()
        assert "lgctl" in captured.out or "usage" in captured.out.lower()

    def test_main_with_command(self, mock_client):
        """Test main with command runs it."""
        with patch("lgctl.cli.get_client") as mock_get_client:
            mock_get_client.return_value = mock_client
            with patch("sys.argv", ["lgctl", "--format", "json", "store", "ls"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                # Exit code 0 means success
                assert exc_info.value.code == 0
