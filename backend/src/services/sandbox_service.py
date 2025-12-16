from typing import Optional
from backend.src.sandbox_server.config import SandboxConfig
from backend.src.sandbox_server.lifecycle.sandbox_controller import SandboxController
from backend.src.sandbox_server.sandboxes.base import BaseSandbox
from backend.common.log import log

class SandboxService:
    _instance: Optional["SandboxService"] = None
    _controller: Optional[SandboxController] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SandboxService, cls).__new__(cls)
        return cls._instance
    
    @property
    def controller(self) -> SandboxController:
        if self._controller is None:
            raise RuntimeError("SandboxService not initialized. Call initialize() first.")
        return self._controller
        
    async def initialize(self):
        """Initialize the sandbox controller."""
        if self._controller is None:
            try:
                config = SandboxConfig()
                self._controller = SandboxController(config)
                await self._controller.start()
                log.info("SandboxService initialized successfully")
            except Exception as e:
                log.error(f"Failed to initialize SandboxService: {e}")
                raise

    async def shutdown(self):
        """Shutdown the service."""
        if self._controller:
            await self._controller.shutdown()
            log.info("SandboxService shutdown successfully")

    async def get_or_create_sandbox(self, user_id: str, template_id: Optional[str] = None) -> BaseSandbox:
        """Get an existing sandbox or create a new one for the user."""
        # Simple implementation: always create new for now, or implement lookup logic
        # Ideally, look up active sandbox for user in DB
        # For now, let's create a new one
        return await self.controller.create_sandbox(user_id=user_id, sandbox_template_id=template_id)

    async def run_cmd(self, sandbox_id: str, command: str, background: bool = False) -> str:
        """Run a command in a sandbox."""
        return await self.controller.run_cmd(sandbox_id, command, background)

    async def terminate_sandbox(self, sandbox_id: str):
        """Terminate a sandbox."""
        await self.controller.delete_sandbox(sandbox_id)


sandbox_service = SandboxService()
