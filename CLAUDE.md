# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run tests with coverage
pytest --cov=splunk_assistant_skills_lib --cov-report=xml -v

# Run a single test file
pytest tests/test_validators.py

# Run a specific test
pytest tests/test_validators.py::test_validate_sid

# Format code
black src tests
isort src tests

# Type checking
mypy src --ignore-missing-imports
```

## Architecture

This is a Python library for interacting with the Splunk REST API. The package is located at `src/splunk_assistant_skills_lib/` and exports all public APIs from `__init__.py`.

### Core Modules

- **splunk_client.py**: HTTP client (`SplunkClient`) with retry logic, dual auth (JWT Bearer or Basic), streaming support, and lookup file uploads
- **config_manager.py**: Multi-source configuration with profile support. Priority: env vars > `.claude/settings.local.json` > `.claude/settings.json` > defaults
- **error_handler.py**: Exception hierarchy (`SplunkError` base class with subclasses for 401/403/404/429/5xx) and `@handle_errors` decorator for CLI scripts

### Utility Modules

- **validators.py**: Input validation for Splunk formats (SID, SPL, time modifiers, index names)
- **spl_helper.py**: SPL query building, parsing, and complexity estimation
- **job_poller.py**: Search job state polling with `JobState` enum and `JobProgress` dataclass
- **time_utils.py**: Splunk time modifier parsing and formatting

### Key Patterns

- Configuration uses profiles for multi-environment support (production/development)
- `get_splunk_client()` is the main entry point - reads config automatically
- All HTTP errors are converted to typed exceptions via `handle_splunk_error()`
- Tests use mock fixtures from `tests/conftest.py` (`mock_splunk_client`, `mock_config`)

### Test Markers

- `@pytest.mark.live` - requires live Splunk connection
- `@pytest.mark.destructive` - modifies data
- `@pytest.mark.slow` - slow running tests
