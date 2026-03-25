---
name: testing-workflow
description: Testing best practices with pytest. Use this skill when writing tests, setting up test infrastructure, or debugging test failures.
---

# Testing Workflow Skill

A comprehensive guide to writing and organizing tests with pytest.

## When to Use This Skill
- User asks to "write tests" or "add unit tests"
- Setting up a testing framework
- Test coverage improvements
- Debugging test failures

## Testing Setup

### Project Structure
```
project/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       └── module.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Shared fixtures
│   ├── test_module.py
│   └── integration/
│       └── test_api.py
├── pytest.ini
└── requirements-dev.txt
```

### pytest.ini Configuration
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --cov=src --cov-report=term-missing
filterwarnings = ignore::DeprecationWarning
```

## Test Patterns

### 1. Basic Unit Test
```python
# tests/test_calculator.py
import pytest
from mypackage.calculator import Calculator

class TestCalculator:
    def test_add_positive_numbers(self):
        calc = Calculator()
        assert calc.add(2, 3) == 5
    
    def test_add_negative_numbers(self):
        calc = Calculator()
        assert calc.add(-1, -1) == -2
    
    def test_divide_by_zero_raises_error(self):
        calc = Calculator()
        with pytest.raises(ZeroDivisionError):
            calc.divide(10, 0)
```

### 2. Using Fixtures
```python
# tests/conftest.py
import pytest
from mypackage.database import Database

@pytest.fixture
def db():
    """Provide a test database connection."""
    db = Database(":memory:")
    db.create_tables()
    yield db
    db.close()

@pytest.fixture
def sample_user(db):
    """Create a sample user for testing."""
    user = db.create_user("test@example.com", "password123")
    return user
```

### 3. Parametrized Tests
```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_uppercase(input, expected):
    assert input.upper() == expected
```

### 4. Mocking External Dependencies
```python
from unittest.mock import Mock, patch, MagicMock
import pytest

def test_api_call():
    with patch('mypackage.api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response
        
        result = api.fetch_data()
        
        assert result == {"data": "test"}
        mock_get.assert_called_once()
```

### 5. Async Tests
```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected_value
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_module.py

# Run specific test
pytest tests/test_module.py::test_function

# Run with coverage
pytest --cov=src --cov-report=html

# Run only fast tests
pytest -m "not slow"

# Run with verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Best Practices

1. **Test one thing per test** - Single assertion focus
2. **Use descriptive names** - `test_user_login_with_invalid_password_returns_401`
3. **Arrange-Act-Assert (AAA)** - Clear test structure
4. **Don't test implementation** - Test behavior, not internals
5. **Keep tests fast** - Mock slow dependencies
6. **Use fixtures** - Share setup code efficiently
7. **Test edge cases** - Empty inputs, None values, boundaries

## Common Issues

- **Flaky tests**: Often due to timing or order dependencies
- **Slow tests**: Mock external services and databases
- **Test pollution**: Ensure proper cleanup in fixtures
