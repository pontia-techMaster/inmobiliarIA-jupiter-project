#!/usr/bin/env bash
# Quick setup script for uv project

echo "🚀 Setting up inmobiliarIA with uv..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Sync dependencies
echo "📦 Syncing dependencies..."
uv sync

# Run tests
echo "🧪 Running tests..."
uv run pytest tests/ -v

# Run linting
echo "🔍 Running linting..."
uv run black --check .
uv run isort --check-only .
uv run flake8 .

echo "✅ Setup complete! Ready to develop."
echo ""
echo "Quick commands:"
echo "  uv run pytest tests/               # Run tests"
echo "  uv run black .                     # Format code"
echo "  uv run python main.py              # Run scripts"
