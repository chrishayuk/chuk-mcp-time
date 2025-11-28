.PHONY: help clean clean-pyc clean-build clean-test clean-all install dev-install test test-cov coverage-report lint format typecheck security check docker-build docker-run build version bump-patch bump-minor bump-major publish publish-test publish-manual release

# Detect if 'uv' is available for faster operations
UV := $(shell command -v uv 2> /dev/null)

help:
	@echo "chuk-mcp-time - High-accuracy time oracle MCP server"
	@echo ""
	@echo "Available targets:"
	@echo "  help              Show this help message"
	@echo ""
	@echo "Clean targets:"
	@echo "  clean             Clean basic artifacts (pyc, build)"
	@echo "  clean-pyc         Remove Python bytecode and cache"
	@echo "  clean-build       Remove build and dist directories"
	@echo "  clean-test        Remove pytest cache and coverage"
	@echo "  clean-all         Deep clean everything"
	@echo ""
	@echo "Development targets:"
	@echo "  install           Install package"
	@echo "  dev-install       Install in editable mode with dev dependencies"
	@echo "  test              Run pytest"
	@echo "  test-cov          Run pytest with coverage reports"
	@echo "  coverage-report   Display coverage metrics"
	@echo "  lint              Run ruff checks and formatting"
	@echo "  format            Auto-format code with ruff"
	@echo "  typecheck         Run mypy type checking"
	@echo "  security          Run bandit security checks"
	@echo "  check             Run all checks (lint, typecheck, security, test)"
	@echo ""
	@echo "Docker targets:"
	@echo "  docker-build      Build Docker image"
	@echo "  docker-run        Run Docker container"
	@echo ""
	@echo "Build & Release targets:"
	@echo "  build             Build the project (creates dist/ artifacts)"
	@echo "  version           Display current version"
	@echo "  bump-patch        Increment patch version (0.0.X)"
	@echo "  bump-minor        Increment minor version (0.X.0)"
	@echo "  bump-major        Increment major version (X.0.0)"
	@echo "  publish           Create tag and trigger GitHub Actions release"
	@echo "  publish-test      Upload to TestPyPI"
	@echo "  publish-manual    Manual PyPI upload with PYPI_TOKEN"
	@echo "  release           Alias for publish"

# Clean targets
clean: clean-pyc clean-build clean-test

clean-pyc:
	@echo "Cleaning Python bytecode and cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete

clean-build:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .eggs/

clean-test:
	@echo "Cleaning test artifacts..."
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/

clean-all: clean
	@echo "Deep cleaning..."
	rm -rf venv/
	rm -rf .venv/
	rm -rf node_modules/

# Development targets
install:
ifdef UV
	@echo "Installing with uv..."
	uv pip install .
else
	@echo "Installing with pip..."
	pip install .
endif

dev-install:
ifdef UV
	@echo "Installing in editable mode with dev dependencies (using uv)..."
	uv pip install -e ".[dev]"
else
	@echo "Installing in editable mode with dev dependencies (using pip)..."
	pip install -e ".[dev]"
endif

test:
ifdef UV
	@echo "Running tests with uv..."
	uv run pytest
else
	@echo "Running tests..."
	pytest
endif

test-cov:
ifdef UV
	@echo "Running tests with coverage (using uv)..."
	uv run pytest --cov=chuk_mcp_time --cov-report=html --cov-report=term-missing
else
	@echo "Running tests with coverage..."
	pytest --cov=chuk_mcp_time --cov-report=html --cov-report=term-missing
endif

coverage-report:
	@echo "Coverage report:"
ifdef UV
	uv run coverage report
else
	coverage report
endif

lint:
	@echo "Running ruff checks..."
	ruff check src/ tests/
	@echo "Checking formatting..."
	ruff format --check src/ tests/

format:
	@echo "Formatting code with ruff..."
	ruff format src/ tests/
	@echo "Fixing linting issues..."
	ruff check --fix src/ tests/

typecheck:
	@echo "Running mypy type checking..."
ifdef UV
	uv run mypy src/
else
	mypy src/
endif

security:
	@echo "Running bandit security checks..."
ifdef UV
	uv run bandit -r src/ -ll
else
	bandit -r src/ -ll
endif

check: lint typecheck security test
	@echo "All checks passed!"

# Docker targets
docker-build:
	@echo "Building Docker image..."
	docker build -t chuk-mcp-time:latest .

docker-run:
	@echo "Running Docker container..."
	docker run -p 8000:8000 chuk-mcp-time:latest

# Build target
build: clean-build
	@echo "Building project..."
ifdef UV
	uv build
else
	python3 -m build
endif
	@echo "Build complete. Distributions are in the 'dist' folder."

# Version & Release targets
version:
	@echo "Current version:"
	@grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'

bump-patch:
	@echo "Bumping patch version..."
	@current=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	IFS='.' read -r major minor patch <<< "$$current"; \
	new_patch=$$((patch + 1)); \
	new_version="$$major.$$minor.$$new_patch"; \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new_version\"/" pyproject.toml; \
	sed -i.bak "s/__version__ = \"$$current\"/__version__ = \"$$new_version\"/" src/chuk_mcp_time/__init__.py; \
	sed -i.bak "s/version=\"$$current\"/version=\"$$new_version\"/" src/chuk_mcp_time/server.py; \
	rm -f pyproject.toml.bak src/chuk_mcp_time/__init__.py.bak src/chuk_mcp_time/server.py.bak; \
	echo "Version bumped to $$new_version"

bump-minor:
	@echo "Bumping minor version..."
	@current=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	IFS='.' read -r major minor patch <<< "$$current"; \
	new_minor=$$((minor + 1)); \
	new_version="$$major.$$new_minor.0"; \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new_version\"/" pyproject.toml; \
	sed -i.bak "s/__version__ = \"$$current\"/__version__ = \"$$new_version\"/" src/chuk_mcp_time/__init__.py; \
	sed -i.bak "s/version=\"$$current\"/version=\"$$new_version\"/" src/chuk_mcp_time/server.py; \
	rm -f pyproject.toml.bak src/chuk_mcp_time/__init__.py.bak src/chuk_mcp_time/server.py.bak; \
	echo "Version bumped to $$new_version"

bump-major:
	@echo "Bumping major version..."
	@current=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	IFS='.' read -r major minor patch <<< "$$current"; \
	new_major=$$((major + 1)); \
	new_version="$$new_major.0.0"; \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new_version\"/" pyproject.toml; \
	sed -i.bak "s/__version__ = \"$$current\"/__version__ = \"$$new_version\"/" src/chuk_mcp_time/__init__.py; \
	sed -i.bak "s/version=\"$$current\"/version=\"$$new_version\"/" src/chuk_mcp_time/server.py; \
	rm -f pyproject.toml.bak src/chuk_mcp_time/__init__.py.bak src/chuk_mcp_time/server.py.bak; \
	echo "Version bumped to $$new_version"

publish:
	@echo "Creating release..."
	@version=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Creating tag v$$version"; \
	git tag -a "v$$version" -m "Release v$$version"; \
	git push origin "v$$version"; \
	echo "Tag created and pushed. GitHub Actions will handle the release."

publish-test: build
	@echo "Publishing to TestPyPI..."
	@echo ""
	@version=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Version: $$version"; \
	echo "";
ifdef UV
	uv run twine upload --repository testpypi dist/*
else
	python3 -m twine upload --repository testpypi dist/*
endif
	@version=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo ""; \
	echo "✓ Uploaded to TestPyPI!"; \
	echo ""; \
	echo "Install with:"; \
	echo "  pip install --index-url https://test.pypi.org/simple/ chuk-mcp-time==$$version"

publish-manual: build
	@echo "Manual PyPI Publishing"
	@echo "======================"
	@echo ""
	@version=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	tag="v$$version"; \
	echo "Version: $$version"; \
	echo "Tag: $$tag"; \
	echo ""; \
	\
	echo "Pre-flight checks:"; \
	echo "=================="; \
	\
	if git diff --quiet && git diff --cached --quiet; then \
		echo "✓ Working directory is clean"; \
	else \
		echo "✗ Working directory has uncommitted changes"; \
		echo ""; \
		git status --short; \
		echo ""; \
		echo "Please commit or stash your changes before publishing."; \
		exit 1; \
	fi; \
	\
	if git tag -l | grep -q "^$$tag$$"; then \
		echo "✓ Tag $$tag exists"; \
	else \
		echo "⚠ Tag $$tag does not exist yet"; \
		echo ""; \
		read -p "Create tag now? (y/N) " -n 1 -r; \
		echo ""; \
		if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
			git tag -a "$$tag" -m "Release $$tag"; \
			echo "✓ Tag created locally"; \
		else \
			echo "Continuing without creating tag..."; \
		fi; \
	fi; \
	\
	echo ""; \
	echo "This will upload version $$version to PyPI"; \
	echo ""; \
	read -p "Continue? (y/N) " -n 1 -r; \
	echo ""; \
	if [[ ! $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Aborted."; \
		exit 1; \
	fi; \
	\
	echo ""; \
	echo "Uploading to PyPI..."; \
	if [ -n "$$PYPI_TOKEN" ]; then \
		if command -v uv >/dev/null 2>&1; then \
			uv run twine upload --username __token__ --password "$$PYPI_TOKEN" dist/*; \
		else \
			python3 -m twine upload --username __token__ --password "$$PYPI_TOKEN" dist/*; \
		fi; \
	else \
		if command -v uv >/dev/null 2>&1; then \
			uv run twine upload dist/*; \
		else \
			python3 -m twine upload dist/*; \
		fi; \
	fi; \
	echo ""; \
	echo "✓ Published to PyPI!"; \
	echo ""; \
	if git tag -l | grep -q "^$$tag$$"; then \
		echo "Push tag with: git push origin $$tag"; \
	fi; \
	echo "Install with: pip install chuk-mcp-time==$$version"

release: publish
