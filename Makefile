# ============================================================================
# ESE Enterprise Task Management API — Development Makefile
# ============================================================================
# Usage:
#   make run          — kill port 8000 (if busy) then start Django dev server
#   make run PORT=9000 — use a custom port
#   make test         — run pytest with coverage
#   make migrate      — apply database migrations
#   make shell        — open Django shell
#   make kill-port    — free the dev server port without starting the server
#
# Platform: macOS / Linux (including GitHub Codespaces).
#   On Windows use WSL or Git Bash, or manually free the port with:
#     netstat -ano | findstr :8000   then   taskkill /PID <pid> /F
# ============================================================================

# Configurable port — override with: make run PORT=9000
PORT ?= 8000

# Detect virtualenv activate script
ACTIVATE := . venv/bin/activate

# ---------- Targets ----------------------------------------------------------

.PHONY: help run kill-port test migrate makemigrations shell lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

kill-port: ## Free the dev server port (kills any process on PORT)
	@lsof -ti:$(PORT) | while read -r pid; do kill -9 "$$pid"; done 2>/dev/null || true
	@echo "✓ Port $(PORT) is free"

run: kill-port ## Start Django dev server (safe — frees port first)
	$(ACTIVATE) && python manage.py runserver $(PORT)

test: ## Run pytest with coverage
	$(ACTIVATE) && pytest --cov --cov-report=term-missing

migrate: ## Apply database migrations
	$(ACTIVATE) && python manage.py migrate

makemigrations: ## Create new migrations
	$(ACTIVATE) && python manage.py makemigrations

shell: ## Open Django interactive shell
	$(ACTIVATE) && python manage.py shell

lint: ## Check code style (flake8 if installed)
	$(ACTIVATE) && flake8 apps/ config/ --max-line-length=120 || echo "flake8 not installed — skipping"
