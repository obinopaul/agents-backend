
from pathlib import Path

def restore_and_migrate():
    req_path = Path('requirements.txt')
    toml_path = Path('pyproject.toml')
    
    # Static parts of pyproject.toml
    header = """[project]
name = "agents-backend"
description = \"\"\"
The Agents Backend is a unified, production-ready platform that combines a high-performance 
FastAPI backend with advanced Agentic AI capabilities. It is designed to be the foundational 
"One Platform" for deploying complex AI workflows, from streaming chat agents to autonomous 
code execution sandboxes.
\"\"\"
authors = [
    { name = "Paul", email = "acobapaul@gmail.com" },
]
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
dynamic = ['version']
"""

    footer = """
[dependency-groups]
dev = [
    "pytest>=9.0.0",
    "pytest-sugar>=1.1.1",
]
lint = [
    "prek>=0.2.19",
]
server = [
    "aio-pika>=9.5.8",
    "wait-for-it>=2.3.0",
]

[tool.uv]
python-downloads = "manual"
default-groups = ["dev", "lint"]

[[tool.uv.index]]
name = "aliyun"
url = "https://mirrors.aliyun.com/pypi/simple"

[tool.hatch.build.targets.wheel]
packages = ["backend"]

[tool.hatch.version]
path = "backend/__init__.py"

[project.scripts]
fba = "backend.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

    # Parse requirements
    dependencies = []
    if req_path.exists():
        with open(req_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-e'):
                    continue
                pkg_spec = line.split('#')[0].strip()
                if pkg_spec:
                    dependencies.append(f'    "{pkg_spec}",')
    
    # Construct full content
    new_deps_block = "dependencies = [\n" + "\n".join(dependencies) + "\n]"
    full_content = header + new_deps_block + footer
    
    with open(toml_path, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"Restored pyproject.toml with {len(dependencies)} dependencies.")

if __name__ == "__main__":
    restore_and_migrate()
