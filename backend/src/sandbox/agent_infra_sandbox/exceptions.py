"""Common exceptions for Agent-Infra Sandbox operations."""


class SandboxError(Exception):
    """Base exception for sandbox operations."""
    pass


class SandboxConnectionError(SandboxError):
    """Raised when unable to connect to the sandbox."""
    
    def __init__(self, message: str = "Unable to connect to sandbox", url: str = None):
        self.url = url
        super().__init__(f"{message}: {url}" if url else message)


class SandboxTimeoutError(SandboxError):
    """Raised when a sandbox operation times out."""
    
    def __init__(self, message: str = "Sandbox operation timed out", timeout: float = None):
        self.timeout = timeout
        super().__init__(f"{message} after {timeout}s" if timeout else message)


class SandboxExecutionError(SandboxError):
    """Raised when command execution fails in the sandbox."""
    
    def __init__(self, message: str, exit_code: int = None, output: str = None):
        self.exit_code = exit_code
        self.output = output
        super().__init__(message)


class SandboxNotRunningError(SandboxConnectionError):
    """Raised when the sandbox container is not running."""
    
    def __init__(self, url: str = "http://localhost:8080"):
        super().__init__(
            "Sandbox is not running. Start with: docker-compose up -d",
            url=url
        )
