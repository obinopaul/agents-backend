"""
Build the E2B sandbox template for DEVELOPMENT.

Usage (from project root):
    python backend/build_dev.py

This rebuilds the 'agents-sandbox-dev' template using the E2B CLI,
which fully supports multi-stage Dockerfiles. Resource limits
(CPU, RAM) are read from backend/template.py.

Prerequisites:
    - E2B CLI installed:  npm i -g @e2b/cli
    - E2B_API_KEY set in .env or environment
    - Docker running (CLI invokes Docker to build the image)
"""
import sys
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# Add backend/ to path for template import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from template import SANDBOX_CPU_COUNT, SANDBOX_MEMORY_MB, SANDBOX_START_CMD

# Project root is one level above backend/
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


def build():
    print(
        f"Building DEV template 'agents-sandbox-dev' "
        f"with {SANDBOX_CPU_COUNT} vCPUs and {SANDBOX_MEMORY_MB} MB RAM...\n"
    )

    cmd = (
        f'npx -y @e2b/cli@latest template build'
        f' --dockerfile backend/e2b.Dockerfile'
        f' --name agents-sandbox-dev'
        f' --cmd "{SANDBOX_START_CMD}"'
        f' --cpu-count {SANDBOX_CPU_COUNT}'
        f' --memory-mb {SANDBOX_MEMORY_MB}'
    )

    print(f"Running: {cmd}\n")

    result = subprocess.run(
        cmd,
        cwd=str(_project_root),
        shell=True,  # required on Windows for npx/PATH resolution
    )

    if result.returncode != 0:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    print("\nDevelopment template build complete.")


if __name__ == "__main__":
    build()
