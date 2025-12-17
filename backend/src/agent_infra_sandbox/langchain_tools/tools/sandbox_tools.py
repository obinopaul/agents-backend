"""Sandbox utility and info tools for AIO Sandbox."""

from typing import List, Literal

import structlog
from langchain_core.tools import tool, BaseTool

from langchain_tools.client import SandboxClient

logger = structlog.get_logger(__name__)


def create_sandbox_tools(client: SandboxClient) -> List[BaseTool]:
    """Create sandbox utility/info tools bound to the given sandbox client.
    
    Args:
        client: SandboxClient instance
        
    Returns:
        List of sandbox utility tools
    """
    
    @tool
    async def sandbox_context() -> str:
        """Get sandbox environment information.
        
        Returns the home directory, system information, and runtime environment.
        
        Returns:
            Sandbox context information, or error
        """
        try:
            logger.info("Getting sandbox context")
            
            result = await client.async_client.sandbox.get_context()
            
            output = "Sandbox Environment:\n"
            output += f"  Home Directory: {result.home_dir}\n"
            
            if hasattr(result, 'system_env') and result.system_env:
                output += f"  OS: {result.system_env.os or 'unknown'}\n"
                output += f"  Arch: {result.system_env.arch or 'unknown'}\n"
            
            if hasattr(result, 'runtime_env') and result.runtime_env:
                if result.runtime_env.python_version:
                    output += f"  Python: {result.runtime_env.python_version}\n"
                if result.runtime_env.node_version:
                    output += f"  Node.js: {result.runtime_env.node_version}\n"
            
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to get sandbox context: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def sandbox_packages(
        language: Literal["python", "nodejs"] = "python",
    ) -> str:
        """List installed packages in the sandbox.
        
        Args:
            language: Which runtime's packages to list ('python' or 'nodejs')
            
        Returns:
            List of installed packages, or error
        """
        try:
            logger.info("Getting sandbox packages", language=language)
            
            if language == "python":
                result = await client.async_client.sandbox.get_python_packages()
            else:
                result = await client.async_client.sandbox.get_nodejs_packages()
            
            packages = result.data if hasattr(result, 'data') else result
            
            if not packages:
                return f"No {language} packages found"
            
            # Handle different response formats
            if isinstance(packages, list):
                output = f"Installed {language} packages ({len(packages)}):\n"
                for pkg in packages[:50]:  # Limit output
                    if isinstance(pkg, dict):
                        name = pkg.get('name', pkg.get('package', str(pkg)))
                        version = pkg.get('version', '')
                        output += f"  - {name}{' (' + version + ')' if version else ''}\n"
                    else:
                        output += f"  - {pkg}\n"
                if len(packages) > 50:
                    output += f"  ... and {len(packages) - 50} more\n"
            else:
                output = str(packages)
            
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to get packages: {e!s}"
            logger.error(error_msg, language=language, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def sandbox_health() -> str:
        """Check if the sandbox is healthy and responding.
        
        Returns:
            Health status message
        """
        try:
            logger.info("Checking sandbox health")
            
            is_healthy = await client.health_check()
            
            if is_healthy:
                return "✅ Sandbox is healthy and responding"
            else:
                return "❌ Sandbox is not responding"
                
        except Exception as e:
            error_msg = f"Health check failed: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"❌ Sandbox health check failed: {error_msg}"
    
    return [
        sandbox_context,
        sandbox_packages,
        sandbox_health,
    ]
