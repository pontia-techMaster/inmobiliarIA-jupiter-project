# InmobiliarIA - Property Scraper & FastAPI Application

Aplicación para extraer datos de viviendas en Madrid desde archivos HTML y proporcionar una API FastAPI.

## 📋 Tabla de Contenidos

- [Instalación](#instalación)
- [Uso](#uso)
- [Desarrollo](#desarrollo)
- [Testing](#testing)
- [Linting & Code Quality](#linting--code-quality)
- [Verificación](#verificación)
- [Estructura del Proyecto](#estructura-del-proyecto)

## 🚀 Instalación

### Requisitos
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer

### Instalar uv
```bash
# En Windows (PowerShell)
powershell -ExecutionPolicy BypassUser -c "irm https://astral.sh/uv/install.ps1 | iex"

# En macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# O con pip
pip install uv
```

### Setup del proyecto
```bash
# Clonar el repositorio
git clone <repo>
cd inmobiliarIA-jupiter-project

# Instalar dependencias (incluye dev por defecto)
uv sync

# Solo dependencias de producción
uv sync --no-dev
```

## 📖 Uso

### Ejecutar el scraper
```bash
cd viviendas_data/scrapper

# Procesar un archivo HTML individual
uv run python main.py source_html/arganzuela/1.html --json

# Procesar todos los archivos en batch
uv run python main.py --batch --source-dir ./source_html --output ./parsed_properties.json

# Con modo silencioso
uv run python main.py --batch --source-dir ./source_html --output ./parsed_properties.json --quiet
```

### Ejecutar la API FastAPI
```bash
uv run uvicorn app:app --reload
```

## 🧪 Testing

```bash
# Ejecutar todos los tests
uv run pytest tests/ -v

# Con cobertura
uv run pytest tests/ -v --cov=. --cov-report=html

# Tests específicos
uv run pytest tests/test_main.py::TestPropertyExtractor -v
```

## 🔍 Linting & Code Quality

### Flake8 (Code Style)
```bash
uv run flake8 . --max-line-length=127 --max-complexity=10
```

### Pylint (Code Analysis)
```bash
uv run pylint **/*.py
```

### Black (Code Formatting)
```bash
# Check
uv run black --check .

# Format
uv run black .
```

### isort (Import Sorting)
```bash
# Check
uv run isort --check-only .

# Sort
uv run isort .
```

## ✅ Verificación

### Type Checking (mypy)
```bash
uv run mypy . --ignore-missing-imports
```

### Security Scan (bandit)
```bash
uv run bandit -r . --skip B101,B601,B105
```

### Verify Python Syntax
```bash
uv run python -m py_compile $(find . -name "*.py" -type f)
```

## 🔄 Ejecución Completa de Verificaciones

```bash
# Tests
uv run pytest . -v --cov

# Linting completo
uv run flake8 . && uv run pylint **/*.py && uv run black --check . && uv run isort --check-only .

# Verificación
uv run mypy . --ignore-missing-imports && uv run bandit -r .
```

## 📁 Estructura del Proyecto

```
inmobiliarIA-jupiter-project/
├── .github/
│   └── workflows/
│       ├── tests.yml          # Pipeline de tests con uv
│       ├── lint.yml           # Pipeline de linting con uv
│       └── verify.yml         # Pipeline de verificación con uv
├── viviendas_data/
│   └── scrapper/
│       ├── main.py            # Extractor principal
│       ├── source_html/       # Archivos HTML a procesar
│       ├── tests/             # Tests unitarios
│       └── parsed_properties.json  # Salida
├── pyproject.toml            # Configuración principal (uv)
├── uv.lock                   # Lock file de dependencias
├── .flake8                   # Configuración Flake8
├── .pylintrc                 # Configuración Pylint
├── .bandit                   # Configuración Bandit
├── mypy.ini                  # Configuración mypy
└── README.md                 # Este archivo
```

## 🔄 CI/CD Workflows (Powered by uv)

### Tests (tests.yml)
```yaml
- Usa: uv sync --dev
- Ejecuta: uv run pytest . -v --cov
- Dispara en: push y pull request
```

### Lint (lint.yml)
```yaml
- Usa: uv sync --dev
- Ejecuta: uv run flake8, pylint, black, isort
- Dispara en: push y pull request
```

### Verify (verify.yml)
```yaml
- Usa: uv sync --dev
- Ejecuta: uv run mypy, bandit
- Dispara en: push y pull request
```

## 📦 Dependencias Principales

### Core
- **fastapi**: Framework web moderno
- **uvicorn**: ASGI server para FastAPI
- **pydantic**: Validación de datos

### Scraping
- **beautifulsoup4**: Parsing HTML
- **lxml**: Parser rápido para BeautifulSoup

### Development (con `uv sync`)
- **pytest**: Testing framework
- **black**: Code formatter
- **pylint**: Code linter
- **flake8**: Style checker
- **mypy**: Type checker
- **bandit**: Security scanner
- **isort**: Import sorter

## 🛠️ Configuración

- **Línea máxima**: 127 caracteres
- **Python**: 3.10+
- **Package manager**: uv
- **Type hints**: Recomendado
- **Docstrings**: Recomendado

## 💡 Ventajas de uv

- ⚡ **10-100x más rápido** que pip
- 🔒 Determinístico: `uv.lock` garantiza reproducibilidad
- 📦 Compatible con PyPI
- 🚀 Desarrollo rápido con `uv run`
- 📋 Gestión de grupos de dependencias

## 📝 Próximos Pasos

- [ ] Desarrollar API FastAPI para servir datos
- [ ] Agregar endpoints de búsqueda y filtros
- [ ] Implementar persistencia en base de datos
- [ ] Agregar autenticación
- [ ] Containerizar con Docker
- [ ] Deploy en producción

## 📞 Contacto

Para más información, contactar al equipo de desarrollo.
