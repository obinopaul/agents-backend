# Tests Documentation

This directory contains all unit and integration tests for the agents-backend project.

## Directory Structure

```
backend/tests/
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_metrics_service.py     # LLM metrics & credit tracking
│   ├── test_credit_service.py      # Credit management tests
│   ├── test_ptc_tools.py           # PTC tool generation tests
│   ├── test_slides_api.py          # Slides API tests
│   └── ...
├── integration/             # Integration tests (requires DB/services)
│   └── ...
└── README.md               # This file
```

## Running Tests

### All Tests
```bash
cd backend
pytest tests/ -v
```

### Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Specific Test File
```bash
pytest tests/unit/test_metrics_service.py -v
```

### With Coverage
```bash
pytest tests/ --cov=backend --cov-report=html
```

## Test Categories

### Unit Tests (`tests/unit/`)

| Test File | Description | Tests |
|-----------|-------------|-------|
| `test_metrics_service.py` | LLM token usage tracking, credit calculation | 13 |
| `test_credit_service.py` | User credit management, session metrics | 8 |
| `test_ptc_tools.py` | PTC tool imports, factory functions | 10 |
| `test_slides_api.py` | Slides API endpoints, models | 12 |

**Total: 43+ passing tests**

### Integration Tests (`tests/integration/`)

These require external services (PostgreSQL, Redis) to be running.

## Key Test Dependencies

```bash
pip install pytest pytest-asyncio pytest-cov mongomock
```

## Test Configuration

Tests use mocked dependencies to avoid requiring real database connections.

```python
# Example: Mocking database session
@pytest.fixture
def mock_db():
    return MagicMock(spec=AsyncSession)
```

## Writing New Tests

1. **Unit tests**: Place in `tests/unit/test_<module>.py`
2. **Integration tests**: Place in `tests/integration/test_<module>.py`
3. **Use fixtures** for common setup
4. **Mock external dependencies** (DB, HTTP, etc.)

## Recent Test Additions (2024-12)

- **`test_metrics_service.py`**: Tests for LLM token tracking and credit deduction
- **`test_credit_service.py`**: Tests for user credit management
- **`test_ptc_tools.py`**: Tests for PTC sandbox tool generation
- **`test_slides_api.py`**: Tests for slide presentation API
