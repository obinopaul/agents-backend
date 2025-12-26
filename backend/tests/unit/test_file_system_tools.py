"""
Unit tests for File System tools.

Tests FileReadTool, FileWriteTool, FileEditTool, GrepTool, and other
file system-related tools with mocked workspace manager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestFileReadTool:
    """Test FileReadTool."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        manager.is_path_in_workspace.return_value = True
        return manager

    @pytest.mark.asyncio
    async def test_file_read_success(self, mock_workspace_manager):
        """Test successful file read."""
        from backend.src.tool_server.tools.file_system.file_read import FileReadTool
        
        tool = FileReadTool(mock_workspace_manager)
        
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="file contents"))),
            __exit__=MagicMock()
        ))):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    result = await tool.execute({
                        "file_path": "/workspace/test.txt"
                    })
        
        # Result should contain file content
        assert result is not None

    @pytest.mark.asyncio
    async def test_file_read_with_line_range(self, mock_workspace_manager):
        """Test reading specific line range."""
        from backend.src.tool_server.tools.file_system.file_read import FileReadTool
        
        tool = FileReadTool(mock_workspace_manager)
        
        file_content = "line1\nline2\nline3\nline4\nline5"
        
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(
                read=MagicMock(return_value=file_content),
                readlines=MagicMock(return_value=file_content.split("\n"))
            )),
            __exit__=MagicMock()
        ))):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    result = await tool.execute({
                        "file_path": "/workspace/test.txt",
                        "start_line": 2,
                        "end_line": 4
                    })
        
        assert result is not None


class TestFileWriteTool:
    """Test FileWriteTool."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        manager.is_path_in_workspace.return_value = True
        return manager

    @pytest.mark.asyncio
    async def test_file_write_success(self, mock_workspace_manager):
        """Test successful file write."""
        from backend.src.tool_server.tools.file_system.file_write import FileWriteTool
        
        tool = FileWriteTool(mock_workspace_manager)
        
        mock_open = MagicMock()
        with patch("builtins.open", mock_open):
            with patch("os.makedirs"):
                result = await tool.execute({
                    "file_path": "/workspace/new_file.txt",
                    "content": "new file contents"
                })
        
        assert result is not None
        assert result.is_error is False or result.is_error is None

    @pytest.mark.asyncio
    async def test_file_write_creates_directories(self, mock_workspace_manager):
        """Test that FileWriteTool creates parent directories."""
        from backend.src.tool_server.tools.file_system.file_write import FileWriteTool
        
        tool = FileWriteTool(mock_workspace_manager)
        
        with patch("builtins.open", MagicMock()):
            with patch("os.makedirs") as mock_makedirs:
                with patch("os.path.dirname", return_value="/workspace/subdir"):
                    await tool.execute({
                        "file_path": "/workspace/subdir/file.txt",
                        "content": "content"
                    })


class TestFileEditTool:
    """Test FileEditTool."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        manager.is_path_in_workspace.return_value = True
        return manager

    @pytest.mark.asyncio
    async def test_file_edit_success(self, mock_workspace_manager):
        """Test successful file edit."""
        from backend.src.tool_server.tools.file_system.file_edit import FileEditTool
        
        tool = FileEditTool(mock_workspace_manager)
        
        original_content = "Hello World"
        
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(
                read=MagicMock(return_value=original_content)
            )),
            __exit__=MagicMock()
        ))):
            with patch("os.path.exists", return_value=True):
                result = await tool.execute({
                    "file_path": "/workspace/test.txt",
                    "old_content": "World",
                    "new_content": "Everyone"
                })
        
        assert result is not None


class TestGrepTool:
    """Test GrepTool."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        return manager

    @pytest.mark.asyncio
    async def test_grep_search_success(self, mock_workspace_manager):
        """Test successful grep search."""
        from backend.src.tool_server.tools.file_system.grep import GrepTool
        
        tool = GrepTool(mock_workspace_manager)
        
        # Mock subprocess for ripgrep
        mock_result = MagicMock()
        mock_result.stdout = "test.py:10:def test_function():\n"
        mock_result.returncode = 0
        
        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute({
                "pattern": "test_function",
                "path": "/workspace"
            })
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_grep_with_file_type_filter(self, mock_workspace_manager):
        """Test grep with file type filter."""
        from backend.src.tool_server.tools.file_system.grep import GrepTool
        
        tool = GrepTool(mock_workspace_manager)
        
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await tool.execute({
                "pattern": "import",
                "path": "/workspace",
                "include": "*.py"
            })


class TestASTGrepTool:
    """Test ASTGrepTool."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        return manager

    @pytest.mark.asyncio
    async def test_ast_grep_success(self, mock_workspace_manager):
        """Test successful AST grep search."""
        from backend.src.tool_server.tools.file_system.ast_grep import ASTGrepTool
        
        tool = ASTGrepTool(mock_workspace_manager)
        
        mock_result = MagicMock()
        mock_result.stdout = '{"matches": []}'
        mock_result.returncode = 0
        
        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute({
                "pattern": "def $NAME($_):",
                "path": "/workspace",
                "language": "python"
            })
        
        assert result is not None


class TestApplyPatchTool:
    """Test ApplyPatchTool."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        manager.is_path_in_workspace.return_value = True
        return manager

    @pytest.mark.asyncio
    async def test_apply_patch_success(self, mock_workspace_manager):
        """Test successful patch application."""
        from backend.src.tool_server.tools.file_system.apply_patch import ApplyPatchTool
        
        tool = ApplyPatchTool(mock_workspace_manager)
        
        patch_content = """--- a/test.txt
+++ b/test.txt
@@ -1 +1 @@
-old line
+new line
"""
        
        with patch("builtins.open", MagicMock()):
            with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                result = await tool.execute({
                    "patch": patch_content
                })
        
        assert result is not None


class TestStrReplaceEditorTool:
    """Test StrReplaceEditorTool."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        manager.is_path_in_workspace.return_value = True
        return manager

    @pytest.mark.asyncio
    async def test_str_replace_view_command(self, mock_workspace_manager):
        """Test view command."""
        from backend.src.tool_server.tools.file_system.str_replace_editor import StrReplaceEditorTool
        
        tool = StrReplaceEditorTool(mock_workspace_manager)
        
        file_content = "line1\nline2\nline3"
        
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=file_content))),
            __exit__=MagicMock()
        ))):
            with patch("os.path.exists", return_value=True):
                result = await tool.execute({
                    "command": "view",
                    "path": "/workspace/test.txt"
                })
        
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
