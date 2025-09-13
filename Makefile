# PVCFC RAG API - Development Commands
# For Windows users: use equivalent PowerShell scripts in scripts/ folder

# Python và virtual environment
PYTHON := python
VENV_DIR := venv
PIP := $(VENV_DIR)/Scripts/pip
PYTHON_VENV := $(VENV_DIR)/Scripts/python

# Default phiên bản Python
PYTHON_VERSION := 3.11

.PHONY: help dev run test lint smoke clean
.DEFAULT_GOAL := help

help: ## Hiển thị help message
	@echo "PVCFC RAG API - Development Commands"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Tạo virtual environment và cài dependencies
	@echo "Setting up development environment..."
	$(PYTHON) -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Development environment ready!"
	@echo "Don't forget to copy env.example to .env and configure your settings"

run: ## Chạy development server
	@echo "Starting PVCFC RAG API server..."
	$(PYTHON_VENV) -m uvicorn app.main:app --reload --host 0.0.0.0 --port $${API_PORT:-8000}

test: ## Chạy unit tests
	@echo "Running tests..."
	$(PYTHON_VENV) -m pytest tests/ -v --tb=short

lint: ## Kiểm tra code quality (placeholder)
	@echo "Running code quality checks..."
	@echo "Linting tools sẽ được thêm trong phase sau"
	# $(PYTHON_VENV) -m flake8 app/ tests/
	# $(PYTHON_VENV) -m mypy app/

smoke: ## Test kết nối LLM (nếu có key)
	@echo "Running smoke tests..."
	$(PYTHON_VENV) tools/smoke_test.py || echo "Smoke test skipped - no LLM keys configured"

clean: ## Xóa cache và temp files
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

install-git-hooks: ## Cài pre-commit hooks
	$(PYTHON_VENV) -m pre_commit install

# Phase 1 commands - Production Ready
ingest-pilot: ## Ingest pilot documents (Phase 1)
	@echo "Ingesting pilot documents..."
	$(PYTHON_VENV) tools/extract_pilot.py

build-index: ## Build search indices (Phase 1)
	@echo "Building BM25 search index..."
	$(PYTHON_VENV) tools/demo_pipeline.py

qa-extraction: ## Run QA on extracted documents
	@echo "Running extraction quality analysis..."
	$(PYTHON_VENV) tools/qa_extraction.py

demo: ## Launch Streamlit demo UI (Phase 3)
	@echo "Launching demo UI..."
	@echo "Will be implemented in Phase 3"
