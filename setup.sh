#!/usr/bin/env bash
# FE-Analyst Setup Script
# Run: chmod +x setup.sh && ./setup.sh

set -e

echo "=========================================="
echo "  FE-Analyst Environment Setup"
echo "=========================================="

# Check Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python 3 is required but not found."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "Found Python: $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
$PYTHON_CMD -m venv venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy env file if not exists
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo "IMPORTANT: Edit .env and add your API keys!"
fi

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate the environment: source venv/bin/activate"
echo "  2. Edit .env with your API keys (see .env.example)"
echo "  3. Run: python main.py analyze AAPL"
echo "  4. Or explore: jupyter notebook notebooks/"
echo ""
echo "Free API key registration links:"
echo "  - Finnhub:    https://finnhub.io/"
echo "  - FRED:       https://fred.stlouisfed.org/docs/api/api_key.html"
echo "  - SimFin:     https://simfin.com/"
echo "  - FMP:        https://financialmodelingprep.com/"
echo "  - Reddit:     https://www.reddit.com/prefs/apps"
echo ""
