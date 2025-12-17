"""Code execution tools for AIO Sandbox (Jupyter, Node.js, unified)."""

from typing import List, Optional, Literal, Dict, Any

import structlog
from langchain_core.tools import tool, BaseTool

from langchain_tools.client import SandboxClient

logger = structlog.get_logger(__name__)


def create_code_tools(client: SandboxClient) -> List[BaseTool]:
    """Create all code execution tools bound to the given sandbox client.
    
    Args:
        client: SandboxClient instance
        
    Returns:
        List of code execution tools
    """
    
    @tool
    async def jupyter_execute(
        code: str,
        timeout: Optional[int] = 30,
        kernel_name: str = "python3",
        session_id: Optional[str] = None,
    ) -> str:
        """Execute Python code in a Jupyter kernel.
        
        Variables persist across calls when using the same session_id.
        Sessions expire after 30 minutes of inactivity.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds (default: 30)
            kernel_name: Kernel to use ('python3', 'python3.11', 'python3.12')
            session_id: Session ID for persistent state across calls
            
        Returns:
            Execution output (stdout, stderr, display data), or error
        """
        try:
            logger.info("Executing Jupyter code", kernel=kernel_name, session_id=session_id)
            
            result = await client.async_client.jupyter.execute_code(
                code=code,
                timeout=timeout,
                kernel_name=kernel_name,
                session_id=session_id,
            )
            
            data = result.data
            outputs = []
            
            for output in data.outputs or []:
                if hasattr(output, 'text') and output.text:
                    outputs.append(output.text)
                elif hasattr(output, 'data') and output.data:
                    # Handle rich output (images, etc.)
                    if 'text/plain' in output.data:
                        outputs.append(output.data['text/plain'])
                    elif 'text/html' in output.data:
                        outputs.append(f"[HTML Output] {output.data['text/html'][:200]}...")
            
            if data.error:
                return f"ERROR: {data.error.get('ename', 'Error')}: {data.error.get('evalue', 'Unknown error')}"
            
            if not outputs:
                return "(no output)"
                
            return "\n".join(outputs)
            
        except Exception as e:
            error_msg = f"Failed to execute code: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def nodejs_execute(
        code: str,
        timeout: Optional[int] = 30,
        stdin: Optional[str] = None,
        files: Optional[Dict[str, str]] = None,
    ) -> str:
        """Execute JavaScript code using Node.js.
        
        Each execution creates a fresh environment that's cleaned up automatically.
        
        Args:
            code: JavaScript code to execute
            timeout: Execution timeout in seconds (default: 30)
            stdin: Standard input for the process
            files: Additional files to create in execution directory {filename: content}
            
        Returns:
            Execution output (stdout, stderr), or error
        """
        try:
            logger.info("Executing Node.js code")
            
            result = await client.async_client.nodejs.execute_code(
                code=code,
                timeout=timeout,
                stdin=stdin,
                files=files,
            )
            
            data = result.data
            outputs = []
            
            for output in data.outputs or []:
                if hasattr(output, 'text') and output.text:
                    outputs.append(output.text)
            
            if data.error:
                return f"ERROR: {data.error}"
                
            if not outputs:
                return "(no output)"
                
            return "\n".join(outputs)
            
        except Exception as e:
            error_msg = f"Failed to execute code: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def code_execute(
        language: Literal["python", "javascript", "nodejs"],
        code: str,
        timeout: Optional[int] = 30,
    ) -> str:
        """Execute code using the unified runtime.
        
        Dispatches to Python (Jupyter) or JavaScript (Node.js) based on language.
        
        Args:
            language: Target language ('python', 'javascript', or 'nodejs')
            code: Source code to execute
            timeout: Execution timeout in seconds (default: 30)
            
        Returns:
            Execution output, or error
        """
        try:
            logger.info("Executing code", language=language)
            
            result = await client.async_client.code.execute_code(
                language=language,
                code=code,
                timeout=timeout,
            )
            
            data = result.data
            outputs = []
            
            for output in data.outputs or []:
                if hasattr(output, 'text') and output.text:
                    outputs.append(output.text)
            
            if data.error:
                return f"ERROR: {data.error}"
                
            if not outputs:
                return "(no output)"
                
            return "\n".join(outputs)
            
        except Exception as e:
            error_msg = f"Failed to execute code: {e!s}"
            logger.error(error_msg, language=language, error=str(e))
            return f"ERROR: {error_msg}"
    
    return [
        jupyter_execute,
        nodejs_execute,
        code_execute,
    ]
