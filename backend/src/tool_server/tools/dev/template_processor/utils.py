import importlib
import os
from pathlib import Path


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    In E2B sandbox: /app/agents_backend
    In local development: The directory containing pyproject.toml
    """
    # Check for E2B sandbox environment first
    # The templates are copied to /app/agents_backend/.templates/ in the Dockerfile
    sandbox_path = Path("/app/agents_backend")
    if sandbox_path.exists() and (sandbox_path / ".templates").exists():
        return sandbox_path
    
    # Alternative sandbox path (in case of different structure)
    alt_sandbox_path = Path("/app")
    if alt_sandbox_path.exists() and (alt_sandbox_path / ".templates").exists():
        return alt_sandbox_path
    
    # Fallback: Try to find project root via importlib (local development)
    try:
        dist = importlib.import_module("agents_backend")
        if dist.__file__:
            package_location = Path(str(dist.__file__)).resolve()
            while package_location.parent != package_location:
                if (package_location / "pyproject.toml").exists():
                    return package_location
                package_location = package_location.parent
            return package_location
    except Exception:
        pass
    
    # Last resort: Check PYTHONPATH or current working directory
    pythonpath = os.getenv("PYTHONPATH", "")
    for path in pythonpath.split(":"):
        p = Path(path)
        if p.exists() and (p / ".templates").exists():
            return p
        # Check parent directories
        parent = p.parent
        if parent.exists() and (parent / ".templates").exists():
            return parent
    
    raise Exception(
        "Failed to get project root: Could not find .templates directory. "
        "Expected at /app/agents_backend/.templates/ in sandbox or in project root locally."
    )