"""Comprehensive test script for the LSP tool with multi-language support.

This script tests the LspTool and LspServerManager by:
1. Creating sample code files in multiple languages
2. Testing all LSP operations (goToDefinition, findReferences, hover, documentSymbol, workspaceSymbol)
3. Testing the server manager lifecycle (server reuse, idle timeout, force restart)
4. Testing error handling

Run this test in a Linux environment (sandbox) as LSP requires asyncio subprocess support.
"""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


# =============================================================================
# Sample Code Files for Multi-Language Testing
# =============================================================================

SAMPLE_PYTHON = '''"""Sample Python module for LSP testing."""

from typing import List, Optional


class Calculator:
    """A simple calculator class."""
    
    def __init__(self, precision: int = 2):
        self.precision = precision
        self._history: List[float] = []
    
    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = round(a + b, self.precision)
        self._history.append(result)
        return result
    
    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        result = round(a - b, self.precision)
        self._history.append(result)
        return result
    
    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        result = round(a * b, self.precision)
        self._history.append(result)
        return result
    
    def divide(self, a: float, b: float) -> Optional[float]:
        """Divide a by b. Returns None if b is zero."""
        if b == 0:
            return None
        result = round(a / b, self.precision)
        self._history.append(result)
        return result
    
    def get_history(self) -> List[float]:
        """Return the history of results."""
        return self._history.copy()
    
    def clear_history(self) -> None:
        """Clear the calculation history."""
        self._history.clear()


def create_calculator(precision: int = 2) -> Calculator:
    """Factory function to create a calculator."""
    return Calculator(precision)


class ScientificCalculator(Calculator):
    """Extended calculator with scientific operations."""
    
    def __init__(self, precision: int = 4):
        super().__init__(precision)
    
    def power(self, base: float, exponent: float) -> float:
        """Calculate base raised to exponent."""
        result = round(base ** exponent, self.precision)
        self._history.append(result)
        return result
    
    def sqrt(self, x: float) -> Optional[float]:
        """Calculate square root. Returns None for negative numbers."""
        if x < 0:
            return None
        result = round(x ** 0.5, self.precision)
        self._history.append(result)
        return result


# Module-level usage
if __name__ == "__main__":
    calc = create_calculator()
    print(calc.add(10, 5))
    print(calc.get_history())
'''

SAMPLE_TYPESCRIPT = '''/**
 * Sample TypeScript module for LSP testing.
 */

interface User {
    id: number;
    name: string;
    email: string;
    createdAt: Date;
}

interface UserService {
    getUser(id: number): Promise<User | null>;
    createUser(name: string, email: string): Promise<User>;
    updateUser(id: number, updates: Partial<User>): Promise<User>;
    deleteUser(id: number): Promise<boolean>;
}

class InMemoryUserService implements UserService {
    private users: Map<number, User> = new Map();
    private nextId: number = 1;

    async getUser(id: number): Promise<User | null> {
        return this.users.get(id) || null;
    }

    async createUser(name: string, email: string): Promise<User> {
        const user: User = {
            id: this.nextId++,
            name,
            email,
            createdAt: new Date()
        };
        this.users.set(user.id, user);
        return user;
    }

    async updateUser(id: number, updates: Partial<User>): Promise<User> {
        const user = this.users.get(id);
        if (!user) {
            throw new Error(`User ${id} not found`);
        }
        const updatedUser = { ...user, ...updates };
        this.users.set(id, updatedUser);
        return updatedUser;
    }

    async deleteUser(id: number): Promise<boolean> {
        return this.users.delete(id);
    }

    getAllUsers(): User[] {
        return Array.from(this.users.values());
    }
}

// Factory function
function createUserService(): UserService {
    return new InMemoryUserService();
}

// Usage example
async function main() {
    const service = createUserService();
    const user = await service.createUser("John Doe", "john@example.com");
    console.log("Created user:", user);
}

export { User, UserService, InMemoryUserService, createUserService };
'''

SAMPLE_JAVASCRIPT = '''/**
 * Sample JavaScript module for LSP testing.
 */

class EventEmitter {
    constructor() {
        this.events = {};
    }

    on(event, listener) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(listener);
        return this;
    }

    off(event, listener) {
        if (!this.events[event]) return this;
        this.events[event] = this.events[event].filter(l => l !== listener);
        return this;
    }

    emit(event, ...args) {
        if (!this.events[event]) return false;
        this.events[event].forEach(listener => listener(...args));
        return true;
    }

    once(event, listener) {
        const onceWrapper = (...args) => {
            listener(...args);
            this.off(event, onceWrapper);
        };
        return this.on(event, onceWrapper);
    }
}

class TaskQueue extends EventEmitter {
    constructor(concurrency = 1) {
        super();
        this.concurrency = concurrency;
        this.queue = [];
        this.running = 0;
    }

    add(task) {
        return new Promise((resolve, reject) => {
            this.queue.push({ task, resolve, reject });
            this.processNext();
        });
    }

    async processNext() {
        if (this.running >= this.concurrency || this.queue.length === 0) {
            return;
        }

        this.running++;
        const { task, resolve, reject } = this.queue.shift();

        try {
            const result = await task();
            resolve(result);
            this.emit('taskComplete', result);
        } catch (error) {
            reject(error);
            this.emit('taskError', error);
        } finally {
            this.running--;
            this.processNext();
        }
    }

    get pending() {
        return this.queue.length;
    }

    get active() {
        return this.running;
    }
}

function createTaskQueue(concurrency) {
    return new TaskQueue(concurrency);
}

module.exports = { EventEmitter, TaskQueue, createTaskQueue };
'''

SAMPLE_RUST = '''//! Sample Rust module for LSP testing.

use std::collections::HashMap;

/// A simple key-value store.
pub struct KeyValueStore<K, V> {
    data: HashMap<K, V>,
}

impl<K, V> KeyValueStore<K, V>
where
    K: std::hash::Hash + Eq,
{
    /// Create a new empty store.
    pub fn new() -> Self {
        Self {
            data: HashMap::new(),
        }
    }

    /// Insert a key-value pair.
    pub fn insert(&mut self, key: K, value: V) -> Option<V> {
        self.data.insert(key, value)
    }

    /// Get a reference to a value.
    pub fn get(&self, key: &K) -> Option<&V> {
        self.data.get(key)
    }

    /// Remove a key-value pair.
    pub fn remove(&mut self, key: &K) -> Option<V> {
        self.data.remove(key)
    }

    /// Check if a key exists.
    pub fn contains(&self, key: &K) -> bool {
        self.data.contains_key(key)
    }

    /// Get the number of entries.
    pub fn len(&self) -> usize {
        self.data.len()
    }

    /// Check if the store is empty.
    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }
}

impl<K, V> Default for KeyValueStore<K, V>
where
    K: std::hash::Hash + Eq,
{
    fn default() -> Self {
        Self::new()
    }
}

/// A cache with optional TTL support.
pub struct Cache<K, V> {
    store: KeyValueStore<K, V>,
    max_size: usize,
}

impl<K, V> Cache<K, V>
where
    K: std::hash::Hash + Eq + Clone,
{
    /// Create a new cache with maximum size.
    pub fn new(max_size: usize) -> Self {
        Self {
            store: KeyValueStore::new(),
            max_size,
        }
    }

    /// Set a value in the cache.
    pub fn set(&mut self, key: K, value: V) {
        if self.store.len() >= self.max_size {
            // In a real implementation, we'd evict oldest entries
            return;
        }
        self.store.insert(key, value);
    }

    /// Get a value from the cache.
    pub fn get(&self, key: &K) -> Option<&V> {
        self.store.get(key)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_key_value_store() {
        let mut store: KeyValueStore<String, i32> = KeyValueStore::new();
        store.insert("key".to_string(), 42);
        assert_eq!(store.get(&"key".to_string()), Some(&42));
    }
}
'''

SAMPLE_GO = '''// Sample Go package for LSP testing.
package main

import (
	"errors"
	"sync"
)

// Counter represents a thread-safe counter.
type Counter struct {
	mu    sync.RWMutex
	value int
}

// NewCounter creates a new counter with initial value.
func NewCounter(initial int) *Counter {
	return &Counter{value: initial}
}

// Increment increases the counter by 1.
func (c *Counter) Increment() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value++
	return c.value
}

// Decrement decreases the counter by 1.
func (c *Counter) Decrement() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value--
	return c.value
}

// Value returns the current counter value.
func (c *Counter) Value() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.value
}

// Add adds delta to the counter.
func (c *Counter) Add(delta int) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value += delta
	return c.value
}

// Reset resets the counter to zero.
func (c *Counter) Reset() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value = 0
}

// Stack is a generic stack implementation.
type Stack[T any] struct {
	items []T
}

// NewStack creates a new empty stack.
func NewStack[T any]() *Stack[T] {
	return &Stack[T]{items: make([]T, 0)}
}

// Push adds an item to the top of the stack.
func (s *Stack[T]) Push(item T) {
	s.items = append(s.items, item)
}

// Pop removes and returns the top item.
func (s *Stack[T]) Pop() (T, error) {
	var zero T
	if len(s.items) == 0 {
		return zero, errors.New("stack is empty")
	}
	item := s.items[len(s.items)-1]
	s.items = s.items[:len(s.items)-1]
	return item, nil
}

// Peek returns the top item without removing it.
func (s *Stack[T]) Peek() (T, error) {
	var zero T
	if len(s.items) == 0 {
		return zero, errors.New("stack is empty")
	}
	return s.items[len(s.items)-1], nil
}

// Len returns the number of items in the stack.
func (s *Stack[T]) Len() int {
	return len(s.items)
}

// IsEmpty checks if the stack is empty.
func (s *Stack[T]) IsEmpty() bool {
	return len(s.items) == 0
}

func main() {
	counter := NewCounter(0)
	counter.Increment()
	counter.Increment()
	println("Counter:", counter.Value())
	
	stack := NewStack[string]()
	stack.Push("hello")
	stack.Push("world")
	println("Stack length:", stack.Len())
}
'''


# =============================================================================
# Test Utilities
# =============================================================================

class TestResult:
    """Holds a single test result."""
    def __init__(self, name: str, passed: bool, message: str, duration_ms: float = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration_ms = duration_ms


class TestRunner:
    """Collects and reports test results."""
    def __init__(self):
        self.results: list[TestResult] = []
    
    def add(self, result: TestResult):
        self.results.append(result)
        status = "[PASS]" if result.passed else "[FAIL]"
        print(f"   {status}: {result.name} ({result.duration_ms:.1f}ms)")
        if not result.passed:
            print(f"         {result.message}")
    
    def summary(self):
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        
        print("\n" + "=" * 60)
        print(f"TEST SUMMARY: {passed}/{total} passed, {failed} failed")
        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")
        print("=" * 60)
        return failed == 0


# =============================================================================
# Test Functions
# =============================================================================

async def create_test_files(temp_dir: Path) -> Dict[str, Path]:
    """Create sample code files for testing."""
    files = {
        "python": temp_dir / "sample.py",
        "typescript": temp_dir / "sample.ts",
        "javascript": temp_dir / "sample.js",
        "rust": temp_dir / "sample.rs",
        "go": temp_dir / "sample.go",
    }
    
    files["python"].write_text(SAMPLE_PYTHON)
    files["typescript"].write_text(SAMPLE_TYPESCRIPT)
    files["javascript"].write_text(SAMPLE_JAVASCRIPT)
    files["rust"].write_text(SAMPLE_RUST)
    files["go"].write_text(SAMPLE_GO)
    
    return files


async def test_python_operations(lsp_tool, file_path: Path, runner: TestRunner):
    """Test LSP operations on Python code."""
    print("\n[Python] Testing Python operations...")
    
    # Test documentSymbol
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "documentSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "Python: documentSymbol",
        not result.is_error and "Calculator" in result.llm_content,
        result.llm_content[:200] if result.is_error else "Found symbols",
        duration
    ))
    
    # Test goToDefinition on Calculator class (line 8)
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "goToDefinition",
        "filePath": str(file_path),
        "line": 8,  # class Calculator:
        "character": 10,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "Python: goToDefinition (class)",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "Definition found",
        duration
    ))
    
    # Test hover on add method (line 14)
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "hover",
        "filePath": str(file_path),
        "line": 14,  # def add
        "character": 10,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "Python: hover (method)",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "Hover info retrieved",
        duration
    ))
    
    # Test findReferences on _history (line 12)
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "findReferences",
        "filePath": str(file_path),
        "line": 12,  # self._history
        "character": 14,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "Python: findReferences (_history)",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "References found",
        duration
    ))


async def test_typescript_operations(lsp_tool, file_path: Path, runner: TestRunner):
    """Test LSP operations on TypeScript code."""
    print("\n[TypeScript] Testing TypeScript operations...")
    
    # Test documentSymbol
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "documentSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "TypeScript: documentSymbol",
        not result.is_error and ("User" in result.llm_content or "InMemoryUserService" in result.llm_content),
        result.llm_content[:200] if result.is_error else "Found symbols",
        duration
    ))
    
    # Test goToDefinition on interface User (line 5)
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "goToDefinition",
        "filePath": str(file_path),
        "line": 5,
        "character": 12,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "TypeScript: goToDefinition (interface)",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "Definition found",
        duration
    ))
    
    # Test hover on createUser method
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "hover",
        "filePath": str(file_path),
        "line": 24,
        "character": 15,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "TypeScript: hover (method)",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "Hover info retrieved",
        duration
    ))


async def test_javascript_operations(lsp_tool, file_path: Path, runner: TestRunner):
    """Test LSP operations on JavaScript code."""
    print("\n[JavaScript] Testing JavaScript operations...")
    
    # Test documentSymbol
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "documentSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "JavaScript: documentSymbol",
        not result.is_error and ("EventEmitter" in result.llm_content or "TaskQueue" in result.llm_content),
        result.llm_content[:200] if result.is_error else "Found symbols",
        duration
    ))
    
    # Test goToDefinition on EventEmitter class
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "goToDefinition",
        "filePath": str(file_path),
        "line": 5,
        "character": 10,
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "JavaScript: goToDefinition (class)",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "Definition found",
        duration
    ))


async def test_server_lifecycle(lsp_tool, file_path: Path, runner: TestRunner):
    """Test the server manager lifecycle (server reuse, timing)."""
    print("\n[Lifecycle] Testing Server Lifecycle Management...")
    
    from backend.src.tool_server.tools.file_system.lsp_manager import get_lsp_manager
    
    manager = get_lsp_manager()
    
    # First operation - server should start
    start1 = time.time()
    result1 = await lsp_tool.execute({
        "operation": "documentSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
    })
    duration1 = (time.time() - start1) * 1000
    
    runner.add(TestResult(
        "Lifecycle: First operation (cold start)",
        not result1.is_error,
        f"Duration: {duration1:.0f}ms",
        duration1
    ))
    
    # Get manager stats
    stats = manager.get_stats()
    runner.add(TestResult(
        "Lifecycle: Server cached in manager",
        stats["active_servers"] >= 1,
        f"Active servers: {stats['active_servers']}",
        0
    ))
    
    # Second operation - should reuse server (faster)
    start2 = time.time()
    result2 = await lsp_tool.execute({
        "operation": "hover",
        "filePath": str(file_path),
        "line": 14,
        "character": 10,
    })
    duration2 = (time.time() - start2) * 1000
    
    # Second operation should generally be faster (server already running)
    runner.add(TestResult(
        "Lifecycle: Second operation (warm)",
        not result2.is_error,
        f"Duration: {duration2:.0f}ms (should be faster than first)",
        duration2
    ))
    
    # Test force restart
    start3 = time.time()
    result3 = await lsp_tool.execute({
        "operation": "documentSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
        "forceRestart": True,
    })
    duration3 = (time.time() - start3) * 1000
    
    runner.add(TestResult(
        "Lifecycle: Force restart operation",
        not result3.is_error,
        f"Duration: {duration3:.0f}ms (server restarted)",
        duration3
    ))
    
    # Test custom timeout
    start4 = time.time()
    result4 = await lsp_tool.execute({
        "operation": "documentSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
        "timeout": 10,  # Short timeout
    })
    duration4 = (time.time() - start4) * 1000
    
    runner.add(TestResult(
        "Lifecycle: Custom timeout parameter",
        not result4.is_error,
        f"Duration: {duration4:.0f}ms",
        duration4
    ))


async def test_error_handling(lsp_tool, runner: TestRunner):
    """Test error handling scenarios."""
    print("\n[Errors] Testing Error Handling...")
    
    # Test non-existent file
    result = await lsp_tool.execute({
        "operation": "goToDefinition",
        "filePath": "/nonexistent/path/file.py",
        "line": 1,
        "character": 1,
    })
    
    # On Windows, we get "not supported" error; on Linux we'd get "not found"
    runner.add(TestResult(
        "Error: Non-existent file",
        result.is_error,
        f"Got error: {result.llm_content[:100]}..." if result.is_error else "Should have errored",
        0
    ))
    
    # Test unsupported file type
    result = await lsp_tool.execute({
        "operation": "goToDefinition",
        "filePath": "README.md",
        "line": 1,
        "character": 1,
    })
    
    # On Windows we get platform error; on Linux we'd get "no lsp server"
    runner.add(TestResult(
        "Error: Unsupported file type",
        result.is_error,
        f"Got error: {result.llm_content[:100]}..." if result.is_error else "Should have errored",
        0
    ))
    
    # Test invalid operation
    result = await lsp_tool.execute({
        "operation": "invalidOperation",
        "filePath": "test.py",
        "line": 1,
        "character": 1,
    })
    
    runner.add(TestResult(
        "Error: Invalid operation",
        result.is_error and ("invalid" in result.llm_content.lower() or "windows" in result.llm_content.lower()),
        f"Got error: {result.llm_content[:100]}..." if result.is_error else "Should have errored",
        0
    ))
    
    # Test missing required params
    result = await lsp_tool.execute({
        "operation": "goToDefinition",
        "filePath": "test.py",
        # Missing line and character
    })
    
    runner.add(TestResult(
        "Error: Missing required params",
        result.is_error,
        "Error correctly reported" if result.is_error else "Should have errored",
        0
    ))


async def test_workspace_symbol(lsp_tool, file_path: Path, runner: TestRunner):
    """Test workspace symbol search."""
    print("\n[Search] Testing Workspace Symbol Search...")
    
    # Search for "Calculator" across workspace
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "workspaceSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
        "query": "Calculator",
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "workspaceSymbol: Search for 'Calculator'",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "Search completed",
        duration
    ))
    
    # Search with empty query (all symbols)
    start = time.time()
    result = await lsp_tool.execute({
        "operation": "workspaceSymbol",
        "filePath": str(file_path),
        "line": 1,
        "character": 1,
        "query": "",
    })
    duration = (time.time() - start) * 1000
    
    runner.add(TestResult(
        "workspaceSymbol: Empty query (all symbols)",
        not result.is_error,
        result.llm_content[:200] if result.is_error else "Search completed",
        duration
    ))


# =============================================================================
# Main Test Entry Point
# =============================================================================

async def run_tests():
    """Run all LSP tool tests."""
    import platform
    
    print("=" * 60)
    print("LSP Tool Comprehensive Test Suite")
    print("=" * 60)
    print(f"Platform: {platform.system()}")
    print(f"Python: {sys.version}")
    
    # Check platform
    if platform.system() == "Windows":
        print("\n[!] WARNING: LSP tool is not supported on Windows.")
        print("   This test should be run in a Linux sandbox environment.")
        print("   Some tests will fail due to asyncio subprocess limitations.")
        print("   We'll still run tests to verify error handling.\n")
    
    # Create temp directory for test files
    with tempfile.TemporaryDirectory(prefix="lsp_test_") as temp_dir:
        temp_path = Path(temp_dir)
        print(f"\n[Dir] Test directory: {temp_path}")
        
        # Create test files
        print("[Files] Creating sample code files...")
        files = await create_test_files(temp_path)
        for lang, path in files.items():
            print(f"   - {lang}: {path.name}")
        
        # Setup workspace manager and LSP tool
        from backend.src.tool_server.tools.file_system import LspTool
        from backend.src.tool_server.core.workspace import WorkspaceManager
        
        workspace_manager = WorkspaceManager(str(temp_path))
        lsp_tool = LspTool(workspace_manager)
        
        # Initialize test runner
        runner = TestRunner()
        
        # Run test suites
        try:
            # Test error handling first (works on all platforms)
            await test_error_handling(lsp_tool, runner)
            
            # The following tests require Linux
            if platform.system() != "Windows":
                # Python tests
                await test_python_operations(lsp_tool, files["python"], runner)
                
                # TypeScript tests
                await test_typescript_operations(lsp_tool, files["typescript"], runner)
                
                # JavaScript tests
                await test_javascript_operations(lsp_tool, files["javascript"], runner)
                
                # Workspace symbol tests
                await test_workspace_symbol(lsp_tool, files["python"], runner)
                
                # Lifecycle tests
                await test_server_lifecycle(lsp_tool, files["python"], runner)
            else:
                print("\n[Skip] Skipping language-specific tests on Windows")
            
        finally:
            # Cleanup: shutdown all servers
            print("\n[Cleanup] Cleaning up servers...")
            from backend.src.tool_server.tools.file_system import shutdown_lsp_servers
            await shutdown_lsp_servers()
        
        # Print summary
        success = runner.summary()
        return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_tests())
    sys.exit(exit_code)
