.PHONY: help setup install format lint test clean run migrate shell

# Colors for output
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RESET  := \033[0m

help: ## Show this help message
	@echo '$(GREEN)Available commands:$(RESET)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'

# ============================================
# Setup & Installation
# ============================================

setup: ## Initial project setup (first time only)
	@echo "$(GREEN)Setting up StatusWatch...$(RESET)"
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file"; fi
	@make install
	@echo "$(GREEN)Setup complete! Run 'make migrate' next.$(RESET)"

install: ## Install all dependencies
	@echo "$(GREEN)Installing backend dependencies...$(RESET)"
	cd backend && pip install -r requirements-dev.txt
	@echo "$(GREEN)Installing frontend dependencies...$(RESET)"
	cd frontend && npm install
	@echo "$(GREEN)Dependencies installed!$(RESET)"

# ============================================
# Code Quality
# ============================================

format: ## Format code with Black and isort
	@echo "$(GREEN)Formatting Python code...$(RESET)"
	cd backend && python -m black .
	cd backend && python -m isort .
	@echo "$(GREEN)Code formatted!$(RESET)"

lint: ## Run linters (Ruff, ESLint)
	@echo "$(GREEN)Linting backend...$(RESET)"
	cd backend && python -m ruff check .
	@echo "$(GREEN)Linting frontend...$(RESET)"
	cd frontend && npm run lint
	@echo "$(GREEN)Linting complete!$(RESET)"

lint-fix: ## Run linters and auto-fix issues
	@echo "$(GREEN)Auto-fixing backend issues...$(RESET)"
	cd backend && python -m ruff check --fix .
	@echo "$(GREEN)Auto-fixing frontend issues...$(RESET)"
	cd frontend && npm run lint -- --fix
	@echo "$(GREEN)Auto-fix complete!$(RESET)"

type-check: ## Run type checking (mypy)
	@echo "$(GREEN)Type checking backend...$(RESET)"
	cd backend && python -m mypy . --config-file=../pyproject.toml
	@echo "$(GREEN)Type checking frontend...$(RESET)"
	cd frontend && npx tsc --noEmit
	@echo "$(GREEN)Type checking complete!$(RESET)"

quality: format lint type-check ## Run all code quality checks

# ============================================
# Testing
# ============================================

test: ## Run all tests
	@echo "$(GREEN)Running backend tests...$(RESET)"
	cd backend && python -m pytest
	@echo "$(GREEN)Running frontend tests...$(RESET)"
	cd frontend && npm test -- --run
	@echo "$(GREEN)All tests passed!$(RESET)"

test-backend: ## Run backend tests only
	@echo "$(GREEN)Running backend tests...$(RESET)"
	cd backend && python -m pytest -v

test-frontend: ## Run frontend tests only
	@echo "$(GREEN)Running frontend tests...$(RESET)"
	cd frontend && npm test -- --run

test-watch: ## Run backend tests in watch mode
	cd backend && python -m pytest-watch

coverage: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(RESET)"
	cd backend && python -m pytest --cov=. --cov-report=html --cov-report=term
	@echo "$(GREEN)Coverage report generated in backend/htmlcov/index.html$(RESET)"
	cd frontend && npm test -- --run --coverage
	@echo "$(GREEN)Coverage reports generated!$(RESET)"

# ============================================
# Django Management
# ============================================

migrate: ## Run Django migrations
	@echo "$(GREEN)Running migrations...$(RESET)"
	cd backend && python manage.py migrate

makemigrations: ## Create new migrations
	@echo "$(GREEN)Creating migrations...$(RESET)"
	cd backend && python manage.py makemigrations

migrate-tenant: ## Migrate tenant schemas
	@echo "$(GREEN)Migrating tenant schemas...$(RESET)"
	cd backend && python manage.py migrate_schemas

shell: ## Open Django shell
	cd backend && python manage.py shell

shell-plus: ## Open Django shell with models loaded
	cd backend && python manage.py shell_plus

dbshell: ## Open database shell
	cd backend && python manage.py dbshell

createsuperuser: ## Create Django superuser
	cd backend && python manage.py createsuperuser

collectstatic: ## Collect static files
	cd backend && python manage.py collectstatic --noinput

# ============================================
# Development Servers
# ============================================

run: ## Run both backend and frontend (requires tmux or run in separate terminals)
	@echo "$(YELLOW)This requires two terminals or tmux.$(RESET)"
	@echo "$(GREEN)Terminal 1: make backend-dev$(RESET)"
	@echo "$(GREEN)Terminal 2: make frontend-dev$(RESET)"

backend-dev: ## Run Django development server
	cd backend && python manage.py runserver

frontend-dev: ## Run Vite development server
	cd frontend && npm run dev

celery-worker: ## Run Celery worker
	cd backend && celery -A app worker -l info

celery-beat: ## Run Celery beat scheduler
	cd backend && celery -A app beat -l info

# ============================================
# Docker Commands
# ============================================

docker-up: ## Start Docker services (PostgreSQL, Redis)
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-ps: ## List running containers
	docker-compose ps

docker-shell-db: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U postgres -d dj01

docker-shell-redis: ## Open Redis CLI
	docker-compose exec redis redis-cli

# ============================================
# Database Management
# ============================================

db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(YELLOW)WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ]
	cd backend && python manage.py flush --noinput
	@make migrate
	@echo "$(GREEN)Database reset complete!$(RESET)"

db-backup: ## Backup database
	@echo "$(GREEN)Backing up database...$(RESET)"
	mkdir -p backups
	docker-compose exec -T postgres pg_dump -U postgres dj01 > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup created in backups/$(RESET)"

db-restore: ## Restore database from backup (requires BACKUP_FILE=path/to/backup.sql)
	@if [ -z "$(BACKUP_FILE)" ]; then echo "$(YELLOW)Usage: make db-restore BACKUP_FILE=backups/backup.sql$(RESET)"; exit 1; fi
	@echo "$(YELLOW)Restoring database from $(BACKUP_FILE)...$(RESET)"
	docker-compose exec -T postgres psql -U postgres -d dj01 < $(BACKUP_FILE)
	@echo "$(GREEN)Database restored!$(RESET)"

# ============================================
# Utilities
# ============================================

check: ## Run Django system checks
	cd backend && python manage.py check --deploy

check-security: ## Run security checks
	@echo "$(GREEN)Running Django security checks...$(RESET)"
	cd backend && python manage.py check --deploy --tag security
	@echo "$(GREEN)Checking for vulnerabilities in Python packages...$(RESET)"
	cd backend && pip list --outdated
	@echo "$(GREEN)Checking for vulnerabilities in npm packages...$(RESET)"
	cd frontend && npm audit

list-tenants: ## List all tenants
	cd backend && python scripts/list_tenants.py

create-tenant: ## Create a new tenant (interactive)
	cd backend && python manage.py shell -c "from api.serializers import RegistrationSerializer; print('Use /api/auth/register/ endpoint')"

logs: ## Tail application logs
	tail -f backend/logs/statuswatch.log

logs-error: ## Tail error logs
	tail -f backend/logs/error.log

logs-security: ## Tail security logs
	tail -f backend/logs/security.log

clean: ## Clean up temporary files
	@echo "$(GREEN)Cleaning up...$(RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	cd frontend && rm -rf node_modules/.vite 2>/dev/null || true
	cd frontend && rm -rf dist 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(RESET)"

clean-all: clean ## Clean everything including dependencies
	@echo "$(YELLOW)Removing node_modules and venv...$(RESET)"
	rm -rf frontend/node_modules
	@echo "$(GREEN)Full cleanup complete!$(RESET)"

# ============================================
# Production Build
# ============================================

build: ## Build frontend for production
	@echo "$(GREEN)Building frontend...$(RESET)"
	cd frontend && npm run build
	@echo "$(GREEN)Build complete! Output in frontend/dist/$(RESET)"

build-check: ## Check if production build works
	cd frontend && npm run build && npm run preview

# ============================================
# Documentation
# ============================================

docs-serve: ## Serve documentation (if using mkdocs)
	@echo "$(YELLOW)Documentation serving not yet configured.$(RESET)"
	@echo "$(GREEN)See .github/docs/ for documentation.$(RESET)"

# ============================================
# Pre-commit Hooks
# ============================================

install-hooks: ## Install pre-commit hooks
	@echo "$(GREEN)Installing pre-commit hooks...$(RESET)"
	pip install pre-commit
	pre-commit install
	@echo "$(GREEN)Pre-commit hooks installed!$(RESET)"

run-hooks: ## Run pre-commit hooks on all files
	pre-commit run --all-files

# ============================================
# Quick Commands
# ============================================

quick-check: format lint test ## Run format, lint, and tests (quick CI check)
	@echo "$(GREEN)✓ All checks passed!$(RESET)"

fresh-start: clean docker-down docker-up migrate ## Fresh start (reset everything)
	@echo "$(GREEN)Fresh start complete! Run 'make run' to start servers.$(RESET)"
