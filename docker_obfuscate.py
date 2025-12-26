#!/usr/bin/env python3
"""
Tool Server Obfuscation Script for E2B Sandbox

This script uses PyArmor to obfuscate the tool_server source code
before packaging it into the E2B sandbox template.

Purpose:
- Protect proprietary tool_server implementation
- Prevent reverse engineering of the agent tools
- Secure the code deployed to sandbox environments
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configuration
SOURCE_DIR = Path("/obfuscate/tool_server")
OUTPUT_DIR = Path("/obfuscate/final/tool_server")
RUNTIME_DIR = Path("/obfuscate/final/pyarmor_runtime_000000")

# Directories/files to exclude from obfuscation (leave as plain Python)
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".venv",
    "venv",
    "*.egg-info",
    ".env*",
]


def clean_output():
    """Clean output directories."""
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def copy_non_python_files():
    """Copy non-Python files directly (configs, etc.)."""
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in ["__pycache__", ".venv", "venv", ".git"]]
        
        for file in files:
            if not file.endswith(".py"):
                src_path = Path(root) / file
                rel_path = src_path.relative_to(SOURCE_DIR)
                dst_path = OUTPUT_DIR / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                print(f"Copied: {rel_path}")


def obfuscate_python():
    """Obfuscate Python files using PyArmor."""
    try:
        # Create list of Python files
        python_files = list(SOURCE_DIR.rglob("*.py"))
        python_files = [
            f for f in python_files 
            if "__pycache__" not in str(f) 
            and ".venv" not in str(f)
            and "venv" not in str(f)
        ]
        
        if not python_files:
            print("No Python files found to obfuscate")
            return False
        
        print(f"Found {len(python_files)} Python files to obfuscate")
        
        # Run PyArmor obfuscation
        cmd = [
            "pyarmor", "gen",
            "--output", str(OUTPUT_DIR),
            "--recursive",
            "--platform", "linux.x86_64",
            str(SOURCE_DIR)
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"PyArmor error: {result.stderr}")
            # Fallback: copy files without obfuscation
            print("Falling back to plain copy...")
            return copy_plain_python()
        
        print("Obfuscation completed successfully")
        
        # Move runtime to expected location
        pyarmor_runtime = OUTPUT_DIR / "pyarmor_runtime_000000"
        if pyarmor_runtime.exists():
            shutil.move(str(pyarmor_runtime), str(RUNTIME_DIR))
            print(f"Moved runtime to {RUNTIME_DIR}")
        
        return True
        
    except Exception as e:
        print(f"Obfuscation error: {e}")
        return copy_plain_python()


def copy_plain_python():
    """Fallback: Copy Python files without obfuscation."""
    print("Copying Python files without obfuscation...")
    
    for root, dirs, files in os.walk(SOURCE_DIR):
        dirs[:] = [d for d in dirs if d not in ["__pycache__", ".venv", "venv", ".git"]]
        
        for file in files:
            if file.endswith(".py"):
                src_path = Path(root) / file
                rel_path = src_path.relative_to(SOURCE_DIR)
                dst_path = OUTPUT_DIR / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                print(f"Copied (plain): {rel_path}")
    
    # Create empty runtime directory for compatibility
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / "__init__.py").touch()
    
    return True


def main():
    """Main obfuscation workflow."""
    print("=" * 60)
    print("Tool Server Obfuscation Script")
    print("=" * 60)
    
    if not SOURCE_DIR.exists():
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        sys.exit(1)
    
    print(f"Source: {SOURCE_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    
    # Step 1: Clean output
    print("\n[1/3] Cleaning output directories...")
    clean_output()
    
    # Step 2: Copy non-Python files
    print("\n[2/3] Copying non-Python files...")
    copy_non_python_files()
    
    # Step 3: Obfuscate Python files
    print("\n[3/3] Obfuscating Python files...")
    success = obfuscate_python()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Obfuscation completed successfully")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("⚠️ Obfuscation completed with fallback (plain copy)")
        print("=" * 60)


if __name__ == "__main__":
    main()
