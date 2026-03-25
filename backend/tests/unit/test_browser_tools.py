"""
Unit tests for Browser tools.

Tests BrowserClickTool, BrowserViewTool, BrowserNavigationTool, and other
browser automation tools with mocked Browser instance.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class MockBrowser:
    """Mock Browser instance for testing."""
    
    def __init__(self):
        self.current_url = "https://example.com"
        self.page_content = "<html><body>Test</body></html>"
        self.screenshot_data = "base64_screenshot_data"
        
    async def click(self, element_id):
        return {"success": True}
    
    async def view(self):
        return {
            "url": self.current_url,
            "screenshot": self.screenshot_data,
            "elements": [
                {"id": 1, "text": "Button 1", "type": "button"},
                {"id": 2, "text": "Link", "type": "anchor"}
            ]
        }
    
    async def scroll_down(self):
        return {"success": True}
    
    async def scroll_up(self):
        return {"success": True}
    
    async def navigate(self, url):
        self.current_url = url
        return {"success": True, "url": url}
    
    async def enter_text(self, element_id, text):
        return {"success": True}
    
    async def press_key(self, key):
        return {"success": True}


class TestBrowserClickTool:
    """Test BrowserClickTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.click = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_click_success(self, mock_browser):
        """Test successful browser click."""
        from backend.src.tool_server.tools.browser.click import BrowserClickTool
        
        tool = BrowserClickTool(mock_browser)
        
        result = await tool.execute({
            "element_id": 1
        })
        
        mock_browser.click.assert_called_once()
        assert result is not None
        assert result.is_error is False or result.is_error is None

    @pytest.mark.asyncio
    async def test_browser_click_invalid_element(self, mock_browser):
        """Test browser click with invalid element."""
        mock_browser.click = AsyncMock(side_effect=Exception("Element not found"))
        
        from backend.src.tool_server.tools.browser.click import BrowserClickTool
        
        tool = BrowserClickTool(mock_browser)
        
        result = await tool.execute({
            "element_id": 999
        })
        
        # Should handle error gracefully
        assert result is not None


class TestBrowserViewTool:
    """Test BrowserViewTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.view = AsyncMock(return_value={
            "url": "https://example.com",
            "screenshot": "base64data",
            "elements": [{"id": 1, "text": "Button"}]
        })
        return browser

    @pytest.mark.asyncio
    async def test_browser_view_success(self, mock_browser):
        """Test successful browser view."""
        from backend.src.tool_server.tools.browser.view import BrowserViewTool
        
        tool = BrowserViewTool(mock_browser)
        
        result = await tool.execute({})
        
        mock_browser.view.assert_called_once()
        assert result is not None

    def test_browser_view_is_read_only(self, mock_browser):
        """Test that BrowserViewTool is read-only."""
        from backend.src.tool_server.tools.browser.view import BrowserViewTool
        
        tool = BrowserViewTool(mock_browser)
        
        assert tool.read_only is True


class TestBrowserScrollDownTool:
    """Test BrowserScrollDownTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.scroll_down = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_scroll_down_success(self, mock_browser):
        """Test successful browser scroll down."""
        from backend.src.tool_server.tools.browser.scroll_down import BrowserScrollDownTool
        
        tool = BrowserScrollDownTool(mock_browser)
        
        result = await tool.execute({})
        
        mock_browser.scroll_down.assert_called_once()
        assert result is not None


class TestBrowserScrollUpTool:
    """Test BrowserScrollUpTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.scroll_up = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_scroll_up_success(self, mock_browser):
        """Test successful browser scroll up."""
        from backend.src.tool_server.tools.browser.scroll_up import BrowserScrollUpTool
        
        tool = BrowserScrollUpTool(mock_browser)
        
        result = await tool.execute({})
        
        mock_browser.scroll_up.assert_called_once()
        assert result is not None


class TestBrowserNavigationTool:
    """Test BrowserNavigationTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.navigate = AsyncMock(return_value={"success": True, "url": "https://google.com"})
        return browser

    @pytest.mark.asyncio
    async def test_browser_navigation_success(self, mock_browser):
        """Test successful browser navigation."""
        from backend.src.tool_server.tools.browser.navigation import BrowserNavigationTool
        
        tool = BrowserNavigationTool(mock_browser)
        
        result = await tool.execute({
            "url": "https://google.com"
        })
        
        mock_browser.navigate.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_browser_navigation_with_action(self, mock_browser):
        """Test browser navigation with back/forward action."""
        mock_browser.go_back = AsyncMock(return_value={"success": True})
        
        from backend.src.tool_server.tools.browser.navigation import BrowserNavigationTool
        
        tool = BrowserNavigationTool(mock_browser)
        
        result = await tool.execute({
            "action": "back"
        })
        
        assert result is not None


class TestBrowserEnterTextTool:
    """Test BrowserEnterTextTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.enter_text = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_enter_text_success(self, mock_browser):
        """Test successful text entry."""
        from backend.src.tool_server.tools.browser.enter_text import BrowserEnterTextTool
        
        tool = BrowserEnterTextTool(mock_browser)
        
        result = await tool.execute({
            "element_id": 1,
            "text": "Hello World"
        })
        
        mock_browser.enter_text.assert_called_once()
        assert result is not None


class TestBrowserPressKeyTool:
    """Test BrowserPressKeyTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.press_key = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_press_key_success(self, mock_browser):
        """Test successful key press."""
        from backend.src.tool_server.tools.browser.press_key import BrowserPressKeyTool
        
        tool = BrowserPressKeyTool(mock_browser)
        
        result = await tool.execute({
            "key": "Enter"
        })
        
        mock_browser.press_key.assert_called_once()
        assert result is not None


class TestBrowserWaitTool:
    """Test BrowserWaitTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.wait = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_wait_success(self, mock_browser):
        """Test successful browser wait."""
        from backend.src.tool_server.tools.browser.wait import BrowserWaitTool
        
        tool = BrowserWaitTool(mock_browser)
        
        result = await tool.execute({
            "seconds": 2
        })
        
        assert result is not None


class TestBrowserSwitchTabTool:
    """Test BrowserSwitchTabTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.switch_tab = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_switch_tab_success(self, mock_browser):
        """Test successful tab switch."""
        from backend.src.tool_server.tools.browser.switch_tab import BrowserSwitchTabTool
        
        tool = BrowserSwitchTabTool(mock_browser)
        
        result = await tool.execute({
            "tab_index": 1
        })
        
        mock_browser.switch_tab.assert_called_once()
        assert result is not None


class TestBrowserOpenNewTabTool:
    """Test BrowserOpenNewTabTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.open_new_tab = AsyncMock(return_value={"success": True, "tab_index": 1})
        return browser

    @pytest.mark.asyncio
    async def test_browser_open_new_tab_success(self, mock_browser):
        """Test successful new tab opening."""
        from backend.src.tool_server.tools.browser.open_new_tab import BrowserOpenNewTabTool
        
        tool = BrowserOpenNewTabTool(mock_browser)
        
        result = await tool.execute({
            "url": "https://example.com"
        })
        
        mock_browser.open_new_tab.assert_called_once()
        assert result is not None


class TestBrowserRestartTool:
    """Test BrowserRestartTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.restart = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_restart_success(self, mock_browser):
        """Test successful browser restart."""
        from backend.src.tool_server.tools.browser.restart import BrowserRestartTool
        
        tool = BrowserRestartTool(mock_browser)
        
        result = await tool.execute({})
        
        mock_browser.restart.assert_called_once()
        assert result is not None


class TestBrowserDragTool:
    """Test BrowserDragTool."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser instance."""
        browser = MagicMock()
        browser.drag = AsyncMock(return_value={"success": True})
        return browser

    @pytest.mark.asyncio
    async def test_browser_drag_success(self, mock_browser):
        """Test successful drag operation."""
        from backend.src.tool_server.tools.browser.drag import BrowserDragTool
        
        tool = BrowserDragTool(mock_browser)
        
        result = await tool.execute({
            "from_element_id": 1,
            "to_element_id": 2
        })
        
        mock_browser.drag.assert_called_once()
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
