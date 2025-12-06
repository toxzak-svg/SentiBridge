# =============================================================================
# SentiBridge Makefile
# =============================================================================
# Common development, testing, and deployment commands
# Usage: make <target>
# =============================================================================

.PHONY: all help install build test lint clean deploy docs

# Default target
all: help

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------

help: ## Show this help message
	@echo "SentiBridge Development Commands"
	@echo "================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# Installation
# -----------------------------------------------------------------------------

install: install-contracts install-workers install-api ## Install all dependencies

install-contracts: ## Install contract dependencies
	@echo "Installing contract dependencies..."
	cd contracts && forge install

install-workers: ## Install worker dependencies
	@echo "Installing worker dependencies..."
	cd workers && pip install -e ".[dev]"

install-api: ## Install API dependencies
	@echo "Installing API dependencies..."
	cd api && pip install -e ".[dev]"

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------

build: build-contracts ## Build all components

build-contracts: ## Build smart contracts
	@echo "Building contracts..."
	cd contracts && forge build

build-optimized: ## Build contracts with optimizer
	@echo "Building optimized contracts..."
	cd contracts && FOUNDRY_PROFILE=production forge build

# -----------------------------------------------------------------------------
# Testing
# -----------------------------------------------------------------------------

test: test-contracts ## Run all tests

test-contracts: ## Run contract tests
	@echo "Running contract tests..."
	cd contracts && forge test -vvv

test-fuzz: ## Run fuzz tests
	@echo "Running fuzz tests..."
	cd contracts && forge test --match-contract Fuzz -vvvv

test-invariant: ## Run invariant tests
	@echo "Running invariant tests..."
	cd contracts && forge test --match-contract Invariant -vvvv

test-coverage: ## Run tests with coverage
	@echo "Running coverage..."
	cd contracts && forge coverage

test-gas: ## Run tests with gas reporting
	@echo "Running gas report..."
	cd contracts && forge test --gas-report

test-workers: ## Run worker tests
	@echo "Running worker tests..."
	cd workers && pytest -v

test-api: ## Run API tests
	@echo "Running API tests..."
	cd api && pytest -v

test-integration: ## Run integration tests (mock mode)
	@echo "Running integration tests..."
	cd workers && python integration_test.py --mock

# -----------------------------------------------------------------------------
# Linting & Formatting
# -----------------------------------------------------------------------------

lint: lint-contracts lint-python ## Lint all code

lint-contracts: ## Lint Solidity contracts
	@echo "Linting contracts..."
	cd contracts && forge fmt --check

lint-python: ## Lint Python code
	@echo "Linting Python code..."
	cd workers && ruff check .
	cd api && ruff check .

format: format-contracts format-python ## Format all code

format-contracts: ## Format Solidity contracts
	@echo "Formatting contracts..."
	cd contracts && forge fmt

format-python: ## Format Python code
	@echo "Formatting Python code..."
	cd workers && ruff format .
	cd api && ruff format .

# -----------------------------------------------------------------------------
# Security
# -----------------------------------------------------------------------------

security: slither audit-checklist ## Run all security checks

slither: ## Run Slither static analysis
	@echo "Running Slither..."
	cd contracts && slither . --filter-paths "test|script|lib" 2>&1 | tee slither-report.txt

audit-checklist: ## Generate audit checklist status
	@echo "Security Audit Checklist:"
	@echo "========================="
	@cat docs/SECURITY_AUDIT_CHECKLIST.md | grep -E "^\- \[" | head -20

check-sizes: ## Check contract sizes
	@echo "Checking contract sizes..."
	cd contracts && forge build --sizes

# -----------------------------------------------------------------------------
# Local Development
# -----------------------------------------------------------------------------

anvil: ## Start local Anvil node
	@echo "Starting Anvil..."
	cd contracts && anvil --chain-id 31337

deploy-local: ## Deploy to local Anvil
	@echo "Deploying to local node..."
	cd contracts && forge script script/Deploy.s.sol:DeployScript \
		--rpc-url http://localhost:8545 \
		--private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
		--broadcast

dev-api: ## Start API in development mode
	@echo "Starting API..."
	cd api && uvicorn src.main:app --reload --port 8000

dev-workers: ## Start workers in development mode
	@echo "Starting workers..."
	cd workers && python -m orchestrator.main

# -----------------------------------------------------------------------------
# Testnet Deployment
# -----------------------------------------------------------------------------

deploy-amoy: ## Deploy to Polygon Amoy testnet
	@echo "Deploying to Polygon Amoy..."
	@test -n "$(PRIVATE_KEY)" || (echo "PRIVATE_KEY not set" && exit 1)
	@test -n "$(AMOY_RPC_URL)" || (echo "AMOY_RPC_URL not set" && exit 1)
	cd contracts && forge script script/Deploy.s.sol:DeployScript \
		--rpc-url $(AMOY_RPC_URL) \
		--private-key $(PRIVATE_KEY) \
		--broadcast \
		--verify \
		-vvvv

deploy-amoy-production: ## Deploy with timelock to Amoy
	@echo "Deploying production config to Polygon Amoy..."
	@test -n "$(PRIVATE_KEY)" || (echo "PRIVATE_KEY not set" && exit 1)
	@test -n "$(AMOY_RPC_URL)" || (echo "AMOY_RPC_URL not set" && exit 1)
	cd contracts && TIMELOCK_DELAY=3600 forge script script/DeployProduction.s.sol:DeployProductionScript \
		--rpc-url $(AMOY_RPC_URL) \
		--private-key $(PRIVATE_KEY) \
		--broadcast \
		--verify \
		-vvvv

# -----------------------------------------------------------------------------
# Mainnet Deployment (USE WITH CAUTION!)
# -----------------------------------------------------------------------------

deploy-polygon: ## Deploy to Polygon mainnet (PRODUCTION)
	@echo "⚠️  WARNING: Deploying to MAINNET!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read
	@test -n "$(PRIVATE_KEY)" || (echo "PRIVATE_KEY not set" && exit 1)
	@test -n "$(POLYGON_RPC_URL)" || (echo "POLYGON_RPC_URL not set" && exit 1)
	cd contracts && forge script script/DeployProduction.s.sol:DeployProductionScript \
		--rpc-url $(POLYGON_RPC_URL) \
		--private-key $(PRIVATE_KEY) \
		--broadcast \
		--verify \
		-vvvv

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------

docker-build: ## Build all Docker images
	@echo "Building Docker images..."
	docker-compose build

docker-up: ## Start all services with Docker
	@echo "Starting Docker services..."
	docker-compose up -d

docker-down: ## Stop all Docker services
	@echo "Stopping Docker services..."
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

# -----------------------------------------------------------------------------
# Documentation
# -----------------------------------------------------------------------------

docs: ## Generate documentation
	@echo "Generating contract documentation..."
	cd contracts && forge doc

docs-serve: ## Serve documentation locally
	@echo "Serving documentation..."
	cd contracts && forge doc --serve --port 4000

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------

clean: clean-contracts clean-python ## Clean all build artifacts

clean-contracts: ## Clean contract build artifacts
	@echo "Cleaning contract artifacts..."
	cd contracts && forge clean
	rm -rf contracts/cache contracts/out

clean-python: ## Clean Python artifacts
	@echo "Cleaning Python artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# -----------------------------------------------------------------------------
# Git Hooks
# -----------------------------------------------------------------------------

setup-hooks: ## Set up git hooks
	@echo "Setting up git hooks..."
	@echo '#!/bin/sh\nmake lint' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed!"

# -----------------------------------------------------------------------------
# Release
# -----------------------------------------------------------------------------

version: ## Show current version
	@echo "Contract version:"
	@grep -r "VERSION" contracts/src/SentimentOracleV1.sol | head -1

changelog: ## Generate changelog
	@echo "Generating changelog..."
	git log --oneline --decorate --graph | head -50
