# Makefile for KataInference Multi-Module Project
# ================================================
# Modular structure supporting multiple inference modules (adeline, cupertino, ...)
#
# Module-specific targets use namespacing: <module>.<command>
# Default commands (no prefix) operate on 'adeline' module

.PHONY: help install run stop clean test lint format check-deps services-up services-down

# Colores para output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Python environment
PYTHON := .venv/bin/python
UV := uv

# Default target
.DEFAULT_GOAL := help

# ============================================================================
# HELP
# ============================================================================
help: ## Show this help message
	@echo "$(BLUE)KataInference Multi-Module Project - Available Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Module Structure:$(NC) adeline, cupertino (future)"
	@echo "$(YELLOW)Syntax:$(NC) make [module.]command  (e.g., 'make adeline.run' or 'make run')"
	@echo ""
	@echo "$(GREEN)Setup & Installation:$(NC)"
	@grep -E '^[a-zA-Z._-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /install|setup|clean/ {printf "  $(YELLOW)%-25s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Running Pipeline (Adeline):$(NC)"
	@grep -E '^[a-zA-Z._-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /run|start|stop|pause|resume|status/ {printf "  $(YELLOW)%-25s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Infrastructure:$(NC)"
	@grep -E '^[a-zA-Z._-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /services/ {printf "  $(YELLOW)%-25s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Monitoring:$(NC)"
	@grep -E '^[a-zA-Z._-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /monitor|metrics/ {printf "  $(YELLOW)%-25s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@grep -E '^[a-zA-Z._-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /test|lint|format|check/ {printf "  $(YELLOW)%-25s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# SETUP & INSTALLATION
# ============================================================================
install: ## Install dependencies with uv
	@echo "$(BLUE)Installing dependencies...$(NC)"
	$(UV) sync
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

install-dev: install ## Install with development dependencies
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	$(UV) sync --all-extras
	@echo "$(GREEN)✅ Development environment ready$(NC)"

upgrade-inference: ## Upgrade inference package to latest
	@echo "$(BLUE)Upgrading inference package...$(NC)"
	$(UV) sync --upgrade-package inference
	@echo "$(GREEN)✅ Inference upgraded$(NC)"

check-deps: ## Check for outdated dependencies
	@echo "$(BLUE)Checking dependencies...$(NC)"
	$(UV) pip list --outdated

# ============================================================================
# RUNNING PIPELINE
# ============================================================================
run: ## Run main inference pipeline (auto-start)
	@echo "$(BLUE)Starting Adeline Inference Pipeline...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	$(UV) run python -m adeline

start: run ## Alias for 'run'

# ============================================================================
# CONTROL COMMANDS (requires pipeline running)
# ============================================================================
stop: ## Stop running pipeline via MQTT
	@echo "$(BLUE)Sending STOP command...$(NC)"
	$(UV) run python -m adeline.control.cli stop

pause: ## Pause pipeline processing
	@echo "$(BLUE)Sending PAUSE command...$(NC)"
	$(UV) run python -m adeline.control.cli pause

resume: ## Resume pipeline processing
	@echo "$(BLUE)Sending RESUME command...$(NC)"
	$(UV) run python -m adeline.control.cli resume

status: ## Query pipeline status
	@echo "$(BLUE)Querying pipeline status...$(NC)"
	$(UV) run python -m adeline.control.cli status

metrics: ## Request pipeline metrics
	@echo "$(BLUE)Requesting pipeline metrics...$(NC)"
	$(UV) run python -m adeline.control.cli metrics

toggle-crop: ## Toggle adaptive ROI crop
	@echo "$(BLUE)Toggling adaptive ROI crop...$(NC)"
	$(UV) run python -m adeline.control.cli toggle_crop

stabilization-stats: ## Get detection stabilization statistics
	@echo "$(BLUE)Requesting stabilization stats...$(NC)"
	$(UV) run python -m adeline.control.cli stabilization_stats

# ============================================================================
# MONITORING
# ============================================================================
monitor-data: ## Monitor detection data stream
	@echo "$(BLUE)Starting data monitor...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	$(UV) run python -m adeline.data.monitors data --verbose

monitor-status: ## Monitor pipeline status updates
	@echo "$(BLUE)Starting status monitor...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	$(UV) run python -m adeline.data.monitors status

monitor: monitor-data ## Alias for monitor-data

# ============================================================================
# INFRASTRUCTURE SERVICES (Module: Adeline)
# ============================================================================
adeline.services-up: ## [Adeline] Start MQTT broker (docker-compose)
	@echo "$(BLUE)Starting Adeline infrastructure services...$(NC)"
	docker-compose -f docker/adeline/docker-compose.mqtt.yml up -d
	@echo "$(GREEN)✅ Services started (mosquitto)$(NC)"
	@echo "MQTT Broker: localhost:1883"

adeline.services-down: ## [Adeline] Stop infrastructure services
	@echo "$(BLUE)Stopping Adeline infrastructure services...$(NC)"
	docker-compose -f docker/adeline/docker-compose.mqtt.yml down
	@echo "$(GREEN)✅ Services stopped$(NC)"

adeline.services-logs: ## [Adeline] Show services logs
	docker-compose -f docker/adeline/docker-compose.mqtt.yml logs -f

adeline.services-status: ## [Adeline] Check services status
	@docker-compose -f docker/adeline/docker-compose.mqtt.yml ps

# Aliases (default module: adeline)
services-up: adeline.services-up ## Alias for adeline.services-up
services-down: adeline.services-down ## Alias for adeline.services-down
services-logs: adeline.services-logs ## Alias for adeline.services-logs
services-status: adeline.services-status ## Alias for adeline.services-status

# ============================================================================
# TESTING & QUALITY
# ============================================================================
test: ## Run tests (manual pair-programming approach)
	@echo "$(BLUE)Testing approach: Manual pair-programming$(NC)"
	@echo "1. Start pipeline: make run"
	@echo "2. Test control: make pause && make resume && make stop"
	@echo "3. Monitor data: make monitor-data"
	@echo "4. Check metrics: make metrics"

test-imports: ## Test that all imports work
	@echo "$(BLUE)Testing imports...$(NC)"
	$(PYTHON) -c "from adeline import PipelineConfig; print('✅ Core imports OK')"
	$(PYTHON) -c "from adeline.control import MQTTControlPlane; print('✅ Control plane OK')"
	$(PYTHON) -c "from adeline.data import MQTTDataPlane; print('✅ Data plane OK')"
	$(PYTHON) -c "from adeline.inference.roi import ROIBox; print('✅ ROI OK')"
	$(PYTHON) -c "from adeline.inference.stabilization import TemporalHysteresisStabilizer; print('✅ Stabilization OK')"
	@echo "$(GREEN)✅ All imports successful$(NC)"

lint: ## Run linting (placeholder - add your linter)
	@echo "$(YELLOW)⚠️ Linting not configured yet$(NC)"
	@echo "Consider adding: ruff, flake8, or pylint"

format: ## Format code (placeholder - add your formatter)
	@echo "$(YELLOW)⚠️ Formatter not configured yet$(NC)"
	@echo "Consider adding: black or ruff format"

# ============================================================================
# CLEANUP
# ============================================================================
clean: ## Clean temporary files and caches
	@echo "$(BLUE)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✅ Cleaned$(NC)"

clean-venv: clean ## Remove virtual environment (requires reinstall)
	@echo "$(RED)⚠️ Removing virtual environment...$(NC)"
	rm -rf .venv
	@echo "$(GREEN)✅ Virtual environment removed. Run 'make install' to reinstall.$(NC)"

# ============================================================================
# DOCUMENTATION
# ============================================================================
adeline.docs: ## [Adeline] Show documentation links
	@echo "$(BLUE)Adeline Documentation:$(NC)"
	@echo "  - Architecture: docs/adeline/DESIGN.md"
	@echo "  - Migration: docs/adeline/MIGRATION_GUIDE.md"
	@echo "  - README: docs/adeline/README.md"
	@echo "  - MQTT: docs/adeline/README_MQTT.md"
	@echo "  - Examples: docs/adeline/EXAMPLES.md"
	@echo "  - Config: docs/adeline/CONFIG_README.md"
	@echo "  - Pipeline: docs/adeline/inference_pipeline.md"

docs: adeline.docs ## Alias for adeline.docs

tree: ## Show project structure (all modules)
	@echo "$(BLUE)Project Structure:$(NC)"
	@tree -L 3 -I "__pycache__|*.pyc|.venv|node_modules|.git" . || \
		find . -maxdepth 3 -type d -not -path "*/.*" -not -path "*/__pycache__*" -not -path "*/node_modules*" | head -50

adeline.tree: ## [Adeline] Show adeline package structure
	@tree -L 3 -I "__pycache__|*.pyc" adeline/ || \
		find adeline -type d -not -path "*/.*" -not -path "*/__pycache__*" | head -30

# ============================================================================
# QUICK COMMANDS (workflows)
# ============================================================================
dev: services-up install ## Setup development environment (services + install)
	@echo "$(GREEN)✅ Development environment ready!$(NC)"
	@echo "Run: make run"

full-start: services-up run ## Start services and pipeline together

demo: ## Run a quick demo (services + pipeline + monitor in background)
	@echo "$(BLUE)Starting demo...$(NC)"
	@make services-up
	@sleep 2
	@echo "$(BLUE)Starting pipeline in background...$(NC)"
	@$(UV) run python -m adeline > /tmp/adeline.log 2>&1 &
	@sleep 3
	@echo "$(GREEN)✅ Demo running!$(NC)"
	@echo "Pipeline: tail -f /tmp/adeline.log"
	@echo "Monitor: make monitor-data"
	@echo "Stop: make stop && make services-down"
