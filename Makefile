.PHONY: help install test coverage lint lint-fix format format-check typecheck security check clean \
       pull-splunk live-test live-test-search live-test-quick live-test-no-slow verify-v2 splunk-versions

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SPLUNK_VERSION   ?= 9.0.9
SPLUNK_IMAGE     ?= splunk/splunk:$(SPLUNK_VERSION)
TEST_ARGS        ?=

# Env vars consumed by tests/live/splunk_container.py
export SPLUNK_TEST_IMAGE     := $(SPLUNK_IMAGE)
export SPLUNK_TEST_PASSWORD  ?= REPLACE_ME_testpassword123
export SPLUNK_TEST_STARTUP_TIMEOUT ?= 300
export SPLUNK_TEST_MEM_LIMIT ?= 4g

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------
help: ## Show this help
	@echo "splunk-as Makefile  (default Splunk $(SPLUNK_VERSION))"
	@echo ""
	@echo "Dev targets (no Docker):"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; !/^(pull|live|verify|splunk-)/ {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Live test targets (Docker required):"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; /^(pull|live|verify|splunk-)/ {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Override Splunk version:  make live-test SPLUNK_VERSION=9.1.2"
	@echo "Extra pytest flags:      make live-test TEST_ARGS=\"-k test_oneshot -x\""

# ---------------------------------------------------------------------------
# Dev targets
# ---------------------------------------------------------------------------
install: ## Install package in editable mode with dev deps
	pip install -e ".[dev]"

test: ## Run unit tests (no Docker)
	pytest tests/ -m "not live" $(TEST_ARGS)

coverage: ## Unit tests with coverage report (70% threshold)
	pytest tests/ -m "not live" --cov --cov-report=term-missing $(TEST_ARGS)

lint: ## Run ruff linter
	ruff check src/ tests/

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix src/ tests/

format: ## Format code with black + isort
	black src/ tests/
	isort src/ tests/

format-check: ## Check formatting without modifying
	black --check src/ tests/
	isort --check-only src/ tests/

typecheck: ## Run mypy type checker
	mypy src/

security: ## Run bandit security scanner
	bandit -r src/

check: lint format-check typecheck test ## Run all quality gates

clean: ## Remove caches, coverage, build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/

# ---------------------------------------------------------------------------
# Live test targets (Docker required)
# ---------------------------------------------------------------------------
pull-splunk: ## Pre-pull Splunk image (~2.5 GB)
	docker pull $(SPLUNK_IMAGE)

live-test: ## All live tests against configured Splunk version
	pytest tests/live/ --live $(TEST_ARGS)

live-test-search: ## Search + export tests only (v2 API)
	pytest tests/live/test_search.py tests/live/test_export.py --live $(TEST_ARGS)

live-test-quick: ## Smoke test: server info, oneshot, generating cmd, csv export
	pytest tests/live/ --live -k "test_get_server_info or test_oneshot_simple_search or test_generating_command_search or test_export_endpoint_csv" $(TEST_ARGS)

live-test-no-slow: ## All live tests minus slow_integration
	pytest tests/live/ --live --skip-slow $(TEST_ARGS)

verify-v2: ## Full v2 API coverage: search + export + job tests
	pytest tests/live/test_search.py tests/live/test_export.py tests/live/test_job.py --live $(TEST_ARGS)

splunk-versions: ## Print known-good versions and usage
	@echo "Known-good Splunk versions:"
	@echo "  9.0.9   - T-Mobile production version"
	@echo "  9.1.2   - Recent maintenance release"
	@echo "  9.4.1   - Latest release"
	@echo "  latest  - Docker Hub latest tag"
	@echo ""
	@echo "Usage:"
	@echo "  make live-test SPLUNK_VERSION=9.0.9"
	@echo "  make live-test SPLUNK_VERSION=9.1.2"
	@echo "  make verify-v2 SPLUNK_VERSION=9.4.1"
	@echo "  make pull-splunk SPLUNK_VERSION=latest"
