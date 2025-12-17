"""Browser automation tools for AIO Sandbox."""

import base64
from typing import List, Optional, Literal

import structlog
from langchain_core.tools import tool, BaseTool

from backend.src.sandbox.agent_infra_sandbox.langchain_tools.client import SandboxClient

logger = structlog.get_logger(__name__)


def create_browser_tools(client: SandboxClient) -> List[BaseTool]:
    """Create all browser automation tools bound to the given sandbox client.
    
    Args:
        client: SandboxClient instance
        
    Returns:
        List of browser automation tools
    """
    
    @tool
    async def browser_info() -> str:
        """Get information about the browser in the sandbox.
        
        Returns CDP URL for Playwright/Puppeteer integration, viewport size, etc.
        
        Returns:
            Browser info including CDP URL, or error message
        """
        try:
            logger.info("Getting browser info")
            
            result = await client.async_client.browser.get_info()
            data = result.data
            
            output = "Browser Information:\n"
            output += f"  CDP URL: {data.cdp_url}\n"
            output += f"  Viewport: {data.viewport.width}x{data.viewport.height}\n"
            
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to get browser info: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def browser_screenshot() -> str:
        """Take a screenshot of the current browser display.
        
        Returns:
            Base64-encoded PNG image data, or error message
        """
        try:
            logger.info("Taking browser screenshot")
            
            # Collect all bytes from the streaming response
            image_bytes = b""
            async for chunk in client.async_client.browser.screenshot():
                image_bytes += chunk
            
            b64_image = base64.b64encode(image_bytes).decode('ascii')
            
            return f"[SCREENSHOT]\ndata:image/png;base64,{b64_image}"
            
        except Exception as e:
            error_msg = f"Failed to take screenshot: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def browser_action(
        action_type: Literal[
            "click", "double_click", "right_click",
            "move_to", "move_rel",
            "drag_to", "drag_rel",
            "scroll", "typing", "press", "hotkey",
            "key_down", "key_up",
            "wait"
        ],
        x: Optional[float] = None,
        y: Optional[float] = None,
        text: Optional[str] = None,
        key: Optional[str] = None,
        keys: Optional[List[str]] = None,
        delta_x: Optional[float] = None,
        delta_y: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> str:
        """Execute a browser action (mouse/keyboard).
        
        Args:
            action_type: Type of action to perform
            x, y: Coordinates for mouse actions (click, move_to, drag_to)
            text: Text for 'typing' action
            key: Key name for 'press', 'key_down', 'key_up' actions
            keys: List of keys for 'hotkey' action (e.g., ['ctrl', 'c'])
            delta_x, delta_y: Relative movement for move_rel, drag_rel, scroll
            duration: Duration for 'wait' action in seconds
            
        Returns:
            Success confirmation, or error message
        """
        try:
            logger.info("Executing browser action", action_type=action_type)
            
            # Build the action request based on type
            # Import action types from the SDK
            from agent_sandbox.browser import (
                Action_Click, Action_DoubleClick, Action_RightClick,
                Action_MoveTo, Action_MoveRel,
                Action_DragTo, Action_DragRel,
                Action_Scroll, Action_Typing, Action_Press, Action_Hotkey,
                Action_KeyDown, Action_KeyUp, Action_Wait,
            )
            
            action_map = {
                "click": lambda: Action_Click(x=x, y=y),
                "double_click": lambda: Action_DoubleClick(x=x, y=y),
                "right_click": lambda: Action_RightClick(x=x, y=y),
                "move_to": lambda: Action_MoveTo(x=x, y=y),
                "move_rel": lambda: Action_MoveRel(delta_x=delta_x, delta_y=delta_y),
                "drag_to": lambda: Action_DragTo(x=x, y=y),
                "drag_rel": lambda: Action_DragRel(delta_x=delta_x, delta_y=delta_y),
                "scroll": lambda: Action_Scroll(delta_x=delta_x or 0, delta_y=delta_y or 0),
                "typing": lambda: Action_Typing(text=text),
                "press": lambda: Action_Press(key=key),
                "hotkey": lambda: Action_Hotkey(keys=keys),
                "key_down": lambda: Action_KeyDown(key=key),
                "key_up": lambda: Action_KeyUp(key=key),
                "wait": lambda: Action_Wait(duration=duration or 1.0),
            }
            
            if action_type not in action_map:
                return f"ERROR: Unknown action type '{action_type}'"
            
            action = action_map[action_type]()
            await client.async_client.browser.execute_action(request=action)
            
            return f"Action '{action_type}' executed successfully"
            
        except Exception as e:
            error_msg = f"Failed to execute action: {e!s}"
            logger.error(error_msg, action_type=action_type, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def browser_config(
        resolution: Literal[
            "1920x1080", "1280x720", "1360x768", "1024x768",
            "800x600", "640x480", "1280x800", "1920x1200",
            "1280x960", "1400x1050", "1680x1050", "1280x1024", "1600x1200"
        ] = "1280x720",
    ) -> str:
        """Set the browser display resolution.
        
        Args:
            resolution: Screen resolution to set
            
        Returns:
            Success confirmation, or error message
        """
        try:
            logger.info("Setting browser config", resolution=resolution)
            
            await client.async_client.browser.set_config(resolution=resolution)
            
            return f"Browser resolution set to {resolution}"
            
        except Exception as e:
            error_msg = f"Failed to set config: {e!s}"
            logger.error(error_msg, resolution=resolution, error=str(e))
            return f"ERROR: {error_msg}"
    
    return [
        browser_info,
        browser_screenshot,
        browser_action,
        browser_config,
    ]
