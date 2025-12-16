from typing import Optional, Type, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from backend.src.services.sandbox_service import sandbox_service

class SandboxRunSchema(BaseModel):
    code: str = Field(description="The python code to execute in the sandbox.")
    sandbox_id: Optional[str] = Field(default=None, description="ID of the sandbox to use. If not provided, a new one may be created.")

class PythonSandboxTool(BaseTool):
    name: str = "python_sandbox"
    description: str = (
        "A tool for executing Python code in a secure sandboxed environment. "
        "Use this for any code execution tasks, data analysis, or file manipulation. "
        "The environment is persistent during the session."
    )
    args_schema: Type[BaseModel] = SandboxRunSchema
    user_id: str

    def _run(self, code: str, sandbox_id: Optional[str] = None) -> str:
        """Synchronous execution is not supported."""
        raise NotImplementedError("Use ainvoke or run with async executor")

    async def _arun(self, code: str, sandbox_id: Optional[str] = None, **kwargs: Any) -> str:
        try:
            # Ensure service is initialized (should be done at app startup, but safe check)
            # if not sandbox_service._controller:
            #     await sandbox_service.initialize()
            
            # Obtain sandbox
            # If sandbox_id is provided, use it. Otherwise create new (or get session default)
            # For simplicity, we create a new one if not provided, but ideally we should track session -> sandbox_id
            if not sandbox_id:
                sandbox = await sandbox_service.get_or_create_sandbox(self.user_id)
                sandbox_id = sandbox.sandbox_id
            
            # Write code to file
            file_path = "script.py"
            await sandbox_service.controller.write_file(sandbox_id, file_path, code)
            
            # Execute
            cmd = f"python {file_path}"
            output = await sandbox_service.controller.run_cmd(sandbox_id, cmd)
            
            return output
            
        except Exception as e:
            return f"Error executing code in sandbox: {str(e)}"

