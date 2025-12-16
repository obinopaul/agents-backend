# Development Scripts

The `scripts/` directory contains shell scripts for development tasks.

---

## Available Scripts

```
scripts/
├── export.sh                # Export utilities
├── format.sh                # Code formatting (black, isort)
└── lint.sh                  # Linting (ruff, mypy)
```

---

## Usage

### Code Formatting

```bash
# Format all Python files
./scripts/format.sh

# Runs:
# - black (code formatter)
# - isort (import sorter)
```

### Linting

```bash
# Lint all Python files
./scripts/lint.sh

# Runs:
# - ruff (fast linter)
# - mypy (type checker)
```

### Export

```bash
# Export utilities (depends on implementation)
./scripts/export.sh
```

---

## Pre-commit Integration

These scripts can be integrated with pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: format
        name: Format code
        entry: ./scripts/format.sh
        language: script
        types: [python]
      - id: lint
        name: Lint code
        entry: ./scripts/lint.sh
        language: script
        types: [python]
```

---

*Last Updated: December 2024*
