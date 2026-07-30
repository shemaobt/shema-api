# Local quality gates (see obt/.claude/quality-gates-plan.md).
# `make quality` = all fast gates (static + coverage).
REPORTS := reports/quality
TEST_ENV := JWT_SECRET_KEY=test-secret-for-pytest-only DATABASE_URL=sqlite+aiosqlite:///./test.db

.PHONY: quality static deps size coverage mutation reports-dir

reports-dir:
	@mkdir -p $(REPORTS)

## quality: local entrypoint — fast gates (static + coverage)
quality: static coverage

## static: lint+complexity (ruff), formatting, types (mypy), file size, architecture (import-linter)
static: reports-dir
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy app/
	uv run python scripts/check_module_size.py
	uv run lint-imports

## deps: architecture/dependency gate only (cycles + layers + forbidden imports)
deps:
	uv run lint-imports

## size: module/file-length gate (non-prompt files)
size:
	uv run python scripts/check_module_size.py

## coverage: test suite with coverage gate (fail_under in pyproject.toml)
coverage: reports-dir
	$(TEST_ENV) uv run pytest tests/ \
	  --cov=app --cov-report=term-missing \
	  --cov-report=json:$(REPORTS)/coverage.json \
	  --cov-report=lcov:$(REPORTS)/coverage.lcov

## mutation: mutation testing (slow; nightly, never blocks PR)
mutation: reports-dir
	$(TEST_ENV) uv run cosmic-ray init cosmic-ray.toml $(REPORTS)/mutation.sqlite
	$(TEST_ENV) uv run cosmic-ray exec cosmic-ray.toml $(REPORTS)/mutation.sqlite
	uv run cr-report $(REPORTS)/mutation.sqlite
