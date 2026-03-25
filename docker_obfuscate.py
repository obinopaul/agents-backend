#!/usr/bin/env python3
"""
Tool Server Obfuscation Script for E2B Sandbox

This script uses PyArmor to obfuscate the tool_server source code
before packaging it into the E2B sandbox template.

Based on the ii-tool obfuscation pattern that correctly handles
non-Python files like .js resources.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def obfuscate_tool_server():
    src_dir = Path("/obfuscate/tool_server")
    output_dir = Path("/obfuscate/output")
    final_dir = Path("/obfuscate/final")

    # Identify large Python files and non-Python files
    MAX_FILE_SIZE = 32768
    large_files = []
    non_python_files = []

    for item in src_dir.rglob("*"):
        if item.is_file():
            relative_path = item.relative_to(src_dir)
            # Skip __pycache__ and venv
            if "__pycache__" in str(relative_path) or ".venv" in str(relative_path):
                continue
            if item.suffix == ".py":
                if item.stat().st_size > MAX_FILE_SIZE:
                    large_files.append(item)
                    print(f"Large Python file will be copied as-is: {relative_path}")
            else:
                non_python_files.append(item)
                print(f"Non-Python file will be preserved: {relative_path}")

    # Remove large files and non-Python files temporarily
    temp_storage = Path("/obfuscate/temp_storage")
    temp_storage.mkdir(exist_ok=True)

    for large_file in large_files:
        relative_path = large_file.relative_to(src_dir)
        dest = temp_storage / "large" / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(large_file), str(dest))

    for non_py_file in non_python_files:
        relative_path = non_py_file.relative_to(src_dir)
        dest = temp_storage / "non_python" / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(non_py_file), str(dest))

    # Obfuscate the rest
    cmd = [
        "pyarmor", "gen",
        "--recursive",
        "--platform", "linux.x86_64",
        "--output", str(output_dir),
        str(src_dir)
    ]

    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Obfuscation successful!")
        print(result.stdout)

        # Create final structure with runtime at src level
        final_dir.mkdir(exist_ok=True)

        # Move obfuscated tool_server
        obfuscated_tool_server = output_dir / "tool_server"
        if obfuscated_tool_server.exists():
            shutil.move(str(obfuscated_tool_server), str(final_dir / "tool_server"))
            print("Moved obfuscated tool_server to final/tool_server")

        # Move PyArmor runtime to src level (same level as tool_server)
        for runtime_dir in output_dir.glob("pyarmor_runtime_*"):
            dest_runtime = final_dir / runtime_dir.name
            shutil.move(str(runtime_dir), str(dest_runtime))
            print(f"Moved PyArmor runtime to final/{runtime_dir.name}")

        # Restore large Python files
        large_storage = temp_storage / "large"
        if large_storage.exists():
            for large_file in large_storage.rglob("*.py"):
                relative_path = large_file.relative_to(large_storage)
                dest = final_dir / "tool_server" / relative_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(large_file), str(dest))
                print(f"Restored large Python file: {relative_path}")

        # Restore non-Python files (like .js, .json, fonts, etc.)
        non_py_storage = temp_storage / "non_python"
        if non_py_storage.exists():
            for non_py_file in non_py_storage.rglob("*"):
                if non_py_file.is_file():
                    relative_path = non_py_file.relative_to(non_py_storage)
                    dest = final_dir / "tool_server" / relative_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(non_py_file), str(dest))
                    print(f"Restored non-Python file: {relative_path}")

        print(f"\nFinal structure in {final_dir}:")
        for item in sorted(final_dir.iterdir()):
            print(f"  - {item.name}/")
            if item.name == "tool_server":
                # Show first few items in tool_server
                for subitem in sorted(item.iterdir())[:10]:
                    print(f"      - {subitem.name}")

    except subprocess.CalledProcessError as e:
        print(f"Obfuscation failed: {e.stderr}")
        # Fallback: copy files without obfuscation
        print("\nFalling back to plain copy...")
        copy_plain(src_dir, final_dir)


def copy_plain(src_dir: Path, final_dir: Path):
    """Fallback: Copy all files without obfuscation."""
    final_dir.mkdir(exist_ok=True)
    dest = final_dir / "tool_server"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src_dir, 
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "venv")
    )
    
    # Create empty runtime directory for compatibility
    runtime_dir = final_dir / "pyarmor_runtime_000000"
    runtime_dir.mkdir(exist_ok=True)
    (runtime_dir / "__init__.py").touch()
    print("Copied all files without obfuscation (fallback)")


if __name__ == "__main__":
    obfuscate_tool_server()
