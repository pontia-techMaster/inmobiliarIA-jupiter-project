# Quick setup script for uv project (Windows)

Write-Host "🚀 Setting up inmobiliarIA with uv..." -ForegroundColor Cyan

# Check if uv is installed
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "❌ uv is not installed. Installing..." -ForegroundColor Yellow
    powershell -ExecutionPolicy BypassUser -c "irm https://astral.sh/uv/install.ps1 | iex"
}

# Sync dependencies
Write-Host "📦 Syncing dependencies..." -ForegroundColor Cyan
uv sync

# Run tests
Write-Host "🧪 Running tests..." -ForegroundColor Cyan
uv run pytest tests/ -v

# Run linting
Write-Host "🔍 Running linting..." -ForegroundColor Cyan
uv run black --check .
uv run isort --check-only .
uv run flake8 .

Write-Host "✅ Setup complete! Ready to develop." -ForegroundColor Green
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Cyan
Write-Host "  uv run pytest tests/               # Run tests"
Write-Host "  uv run black .                     # Format code"
Write-Host "  uv run python main.py              # Run scripts"
