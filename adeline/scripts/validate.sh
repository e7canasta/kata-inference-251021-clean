#!/bin/bash
# Validation Script for Adeline
# ==============================
#
# Runs type checking and tests to validate codebase.
#
# Usage:
#   ./scripts/validate.sh          # Run all checks
#   ./scripts/validate.sh --fast   # Skip slow tests

set -e  # Exit on error

echo "🔍 Adeline Validation Suite"
echo "============================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse arguments
FAST_MODE=false
if [[ "$1" == "--fast" ]]; then
    FAST_MODE=true
    echo "⚡ Fast mode: Skipping slow tests"
    echo ""
fi

# ============================================================================
# 1. Type Checking with mypy
# ============================================================================
echo "🔎 Running mypy type checker..."
if mypy . --config-file mypy.ini; then
    echo -e "${GREEN}✅ Type checking passed${NC}"
else
    echo -e "${RED}❌ Type checking failed${NC}"
    exit 1
fi
echo ""

# ============================================================================
# 2. Run pytest
# ============================================================================
if [ "$FAST_MODE" = true ]; then
    echo "🧪 Running tests (fast mode - unit tests only)..."
    if pytest -v -m unit; then
        echo -e "${GREEN}✅ Tests passed${NC}"
    else
        echo -e "${RED}❌ Tests failed${NC}"
        exit 1
    fi
else
    echo "🧪 Running all tests..."
    if pytest -v; then
        echo -e "${GREEN}✅ All tests passed${NC}"
    else
        echo -e "${RED}❌ Tests failed${NC}"
        exit 1
    fi
fi
echo ""

# ============================================================================
# 3. Config validation (if config.yaml exists)
# ============================================================================
if [ -f "config/adeline/config.yaml" ]; then
    echo "⚙️  Validating config.yaml..."
    if python -c "from config.schemas import AdelineConfig; AdelineConfig.from_yaml('config/adeline/config.yaml'); print('✅ Config valid')"; then
        echo -e "${GREEN}✅ Config validation passed${NC}"
    else
        echo -e "${RED}❌ Config validation failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  No config.yaml found, skipping config validation${NC}"
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${GREEN}✅ All validations passed!${NC}"
echo ""
echo "Next steps:"
echo "  - Run application: python -m adeline"
echo "  - Run specific tests: pytest tests/test_roi.py -v"
echo "  - Check coverage: pytest --cov=adeline --cov-report=html"
