#!/usr/bin/env python3
"""
Comprehensive Tool Server Test Suite

Tests all major tool categories:
- Shell tools (6+)
- File system tools (7+)
- Python execution
- Web tools (when configured)

Run: python test_all_tools.py
"""

import asyncio
import httpx
import uuid
import sys
from datetime import datetime
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class ToolTester:
    """Comprehensive tool tester using sandbox REST API."""
    
    def __init__(self):
        self.client = None
        self.sandbox_id = None
        self.token = None
        self.results: Dict[str, bool] = {}
    
    async def setup(self):
        self.client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                'User-Agent': 'ToolTester/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
    
    async def teardown(self):
        if self.client:
            await self.client.aclose()
    
    def log(self, msg: str, success: bool = None):
        icon = "✅" if success == True else "❌" if success == False else "ℹ️"
        print(f"   {icon} {msg}")
    
    async def login(self) -> bool:
        r = await self.client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if r.status_code == 200:
            self.token = r.json().get('access_token')
            self.client.headers['Authorization'] = f'Bearer {self.token}'
            return True
        return False
    
    async def create_sandbox(self) -> bool:
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': 'tool-tester'}
        )
        if r.status_code == 200:
            self.sandbox_id = r.json().get('data', {}).get('sandbox_id')
            return True
        return False
    
    async def delete_sandbox(self):
        if self.sandbox_id:
            await self.client.delete(
                f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
            )
    
    async def run_cmd(self, command: str) -> tuple[bool, str]:
        """Run command and return (success, output)."""
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
            json={'sandbox_id': self.sandbox_id, 'command': command}
        )
        if r.status_code == 200:
            return True, r.json().get('data', {}).get('output', '')
        return False, f"Error: {r.status_code}"
    
    async def write_file(self, path: str, content: str) -> bool:
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
            json={'sandbox_id': self.sandbox_id, 'file_path': path, 'content': content}
        )
        return r.status_code == 200
    
    async def read_file(self, path: str) -> tuple[bool, str]:
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
            json={'sandbox_id': self.sandbox_id, 'file_path': path}
        )
        if r.status_code == 200:
            return True, r.json().get('data', {}).get('content', '')
        return False, ""
    
    # ==================== SHELL TOOLS ====================
    
    async def test_shell_run_command(self) -> bool:
        """Test: shell_run_command - Execute commands."""
        success, output = await self.run_cmd("echo 'Hello Shell!'")
        return success and 'Hello Shell!' in output
    
    async def test_shell_with_pipe(self) -> bool:
        """Test: shell with pipes."""
        success, output = await self.run_cmd("echo 'line1\nline2\nline3' | wc -l")
        return success and '3' in output
    
    async def test_shell_env_vars(self) -> bool:
        """Test: shell environment variables."""
        success, output = await self.run_cmd("echo $HOME")
        return success and '/' in output
    
    async def test_shell_pwd(self) -> bool:
        """Test: shell working directory."""
        success, output = await self.run_cmd("pwd")
        return success and '/' in output
    
    async def test_shell_ls(self) -> bool:
        """Test: shell list directory."""
        success, output = await self.run_cmd("ls -la /tmp")
        return success and len(output) > 0
    
    async def test_shell_cat(self) -> bool:
        """Test: shell cat command."""
        await self.write_file('/tmp/test_cat.txt', 'CAT_TEST_CONTENT')
        success, output = await self.run_cmd("cat /tmp/test_cat.txt")
        return success and 'CAT_TEST_CONTENT' in output
    
    async def test_shell_grep(self) -> bool:
        """Test: shell grep search."""
        await self.write_file('/tmp/grep_test.txt', 'line1\nfind_me\nline3')
        success, output = await self.run_cmd("grep 'find_me' /tmp/grep_test.txt")
        return success and 'find_me' in output
    
    async def test_shell_head_tail(self) -> bool:
        """Test: shell head/tail commands."""
        content = '\n'.join([f'line{i}' for i in range(1, 11)])
        await self.write_file('/tmp/lines.txt', content)
        success1, output1 = await self.run_cmd("head -3 /tmp/lines.txt")
        success2, output2 = await self.run_cmd("tail -3 /tmp/lines.txt")
        return success1 and 'line1' in output1 and success2 and 'line10' in output2
    
    # ==================== FILE SYSTEM TOOLS ====================
    
    async def test_file_write(self) -> bool:
        """Test: file_write - Create file."""
        return await self.write_file('/tmp/test_write.txt', 'WRITE_TEST')
    
    async def test_file_read(self) -> bool:
        """Test: file_read - Read file."""
        await self.write_file('/tmp/test_read.txt', 'READ_CONTENT_123')
        success, content = await self.read_file('/tmp/test_read.txt')
        return success and 'READ_CONTENT_123' in content
    
    async def test_file_append(self) -> bool:
        """Test: file modification - Append."""
        await self.write_file('/tmp/append_test.txt', 'FIRST')
        success, _ = await self.run_cmd("echo 'SECOND' >> /tmp/append_test.txt")
        _, content = await self.read_file('/tmp/append_test.txt')
        return success and 'FIRST' in content and 'SECOND' in content
    
    async def test_file_mkdir(self) -> bool:
        """Test: mkdir - Create directory."""
        success, _ = await self.run_cmd("mkdir -p /tmp/test_dir/subdir")
        success2, output = await self.run_cmd("ls -la /tmp/test_dir/")
        return success and success2 and 'subdir' in output
    
    async def test_file_cp(self) -> bool:
        """Test: cp - Copy file."""
        await self.write_file('/tmp/original.txt', 'COPY_TEST')
        success, _ = await self.run_cmd("cp /tmp/original.txt /tmp/copy.txt")
        _, content = await self.read_file('/tmp/copy.txt')
        return success and 'COPY_TEST' in content
    
    async def test_file_mv(self) -> bool:
        """Test: mv - Move/rename file."""
        await self.write_file('/tmp/before_mv.txt', 'MOVE_TEST')
        success, _ = await self.run_cmd("mv /tmp/before_mv.txt /tmp/after_mv.txt")
        _, content = await self.read_file('/tmp/after_mv.txt')
        return success and 'MOVE_TEST' in content
    
    async def test_file_rm(self) -> bool:
        """Test: rm - Delete file."""
        await self.write_file('/tmp/to_delete.txt', 'DELETE_ME')
        success, _ = await self.run_cmd("rm /tmp/to_delete.txt")
        success2, _ = await self.run_cmd("test -f /tmp/to_delete.txt && echo 'exists' || echo 'deleted'")
        return success
    
    async def test_file_find(self) -> bool:
        """Test: find - Search for files."""
        await self.write_file('/tmp/findme.xyz', 'content')
        success, output = await self.run_cmd("find /tmp -name '*.xyz' 2>/dev/null")
        return success and 'findme.xyz' in output
    
    # ==================== PYTHON EXECUTION ====================
    
    async def test_python_basic(self) -> bool:
        """Test: Python basic execution."""
        success, output = await self.run_cmd("python3 -c \"print('Python Works!')\"")
        return success and 'Python Works!' in output
    
    async def test_python_script(self) -> bool:
        """Test: Python script execution."""
        code = '''
import sys
import os
print(f"Python {sys.version_info.major}.{sys.version_info.minor}")
print(f"CWD: {os.getcwd()}")
result = sum(range(1, 101))
print(f"Sum: {result}")
'''
        await self.write_file('/tmp/test_script.py', code)
        success, output = await self.run_cmd("python3 /tmp/test_script.py")
        return success and 'Sum: 5050' in output
    
    async def test_python_import(self) -> bool:
        """Test: Python imports."""
        code = '''
import json
import datetime
import os
data = {"test": True, "time": str(datetime.datetime.now())}
print(json.dumps(data))
'''
        await self.write_file('/tmp/test_imports.py', code)
        success, output = await self.run_cmd("python3 /tmp/test_imports.py")
        return success and '"test": true' in output.lower()
    
    async def test_python_file_io(self) -> bool:
        """Test: Python file I/O operations."""
        code = '''
with open('/tmp/py_write_test.txt', 'w') as f:
    f.write('Written by Python')
with open('/tmp/py_write_test.txt', 'r') as f:
    print(f.read())
'''
        await self.write_file('/tmp/test_file_io.py', code)
        success, output = await self.run_cmd("python3 /tmp/test_file_io.py")
        return success and 'Written by Python' in output
    
    async def test_python_error_handling(self) -> bool:
        """Test: Python error handling."""
        code = '''
try:
    x = 1 / 0
except ZeroDivisionError:
    print("ERROR_CAUGHT")
'''
        await self.write_file('/tmp/test_error.py', code)
        success, output = await self.run_cmd("python3 /tmp/test_error.py")
        return success and 'ERROR_CAUGHT' in output
    
    # ==================== ADDITIONAL TESTS ====================
    
    async def test_git_available(self) -> bool:
        """Test: git is available."""
        success, output = await self.run_cmd("git --version")
        return success and 'git version' in output
    
    async def test_node_available(self) -> bool:
        """Test: Node.js is available."""
        success, output = await self.run_cmd("node --version")
        return success and 'v' in output
    
    async def test_curl_available(self) -> bool:
        """Test: curl is available."""
        success, output = await self.run_cmd("curl --version")
        return success and 'curl' in output
    
    async def test_wget_available(self) -> bool:
        """Test: wget is available."""
        success, output = await self.run_cmd("wget --version 2>&1 | head -1")
        return success
    
    async def run_all_tests(self):
        """Run all tool tests."""
        print("=" * 70)
        print("🔧 COMPREHENSIVE TOOL SERVER TEST SUITE")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        await self.setup()
        
        # Authentication
        print("\n📋 Setup")
        if not await self.login():
            print("   ❌ Login failed")
            return False
        self.log("Login successful", True)
        
        if not await self.create_sandbox():
            print("   ❌ Sandbox creation failed")
            return False
        self.log(f"Sandbox created: {self.sandbox_id}", True)
        
        await asyncio.sleep(5)  # Wait for services
        
        # Define test groups
        test_groups = {
            "🖥️ SHELL TOOLS": [
                ("shell_run_command", self.test_shell_run_command),
                ("shell_with_pipe", self.test_shell_with_pipe),
                ("shell_env_vars", self.test_shell_env_vars),
                ("shell_pwd", self.test_shell_pwd),
                ("shell_ls", self.test_shell_ls),
                ("shell_cat", self.test_shell_cat),
                ("shell_grep", self.test_shell_grep),
                ("shell_head_tail", self.test_shell_head_tail),
            ],
            "📁 FILE SYSTEM TOOLS": [
                ("file_write", self.test_file_write),
                ("file_read", self.test_file_read),
                ("file_append", self.test_file_append),
                ("file_mkdir", self.test_file_mkdir),
                ("file_cp", self.test_file_cp),
                ("file_mv", self.test_file_mv),
                ("file_rm", self.test_file_rm),
                ("file_find", self.test_file_find),
            ],
            "🐍 PYTHON EXECUTION": [
                ("python_basic", self.test_python_basic),
                ("python_script", self.test_python_script),
                ("python_import", self.test_python_import),
                ("python_file_io", self.test_python_file_io),
                ("python_error_handling", self.test_python_error_handling),
            ],
            "🔧 ENVIRONMENT TOOLS": [
                ("git_available", self.test_git_available),
                ("node_available", self.test_node_available),
                ("curl_available", self.test_curl_available),
                ("wget_available", self.test_wget_available),
            ],
        }
        
        # Run tests
        for group_name, tests in test_groups.items():
            print(f"\n{group_name}")
            print("-" * 40)
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    self.results[test_name] = result
                    self.log(test_name, result)
                except Exception as e:
                    self.results[test_name] = False
                    self.log(f"{test_name}: {str(e)[:50]}", False)
        
        # Cleanup
        print("\n📋 Cleanup")
        await self.delete_sandbox()
        self.log("Sandbox deleted", True)
        await self.teardown()
        
        # Summary
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        print(f"   PASSED: {passed}/{total}")
        
        if passed < total:
            print("\n   Failed tests:")
            for name, result in self.results.items():
                if not result:
                    print(f"   ❌ {name}")
        
        print("=" * 70)
        return passed == total


if __name__ == '__main__':
    tester = ToolTester()
    success = asyncio.run(tester.run_all_tests())
    sys.exit(0 if success else 1)
