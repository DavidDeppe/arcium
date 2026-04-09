"""
Unified Arcium MCP Server

Provides two namespaced tool groups with independent security boundaries:

1. Vault Tools (vault__*): Operations on Obsidian vault (scoped to vault_path)
2. Projects Tools (projects__*): Python project code generation (scoped to ~/projects/<slug>/)

Security:
- Each tool group validates its own path boundaries using Path.is_relative_to()
- Project slugs validated against ^[a-z0-9-]+$ before any filesystem operation
- projects__run_tests() uses subprocess with timeout, never shell=True
"""

import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

# Security: Slug validation pattern
SLUG_PATTERN = re.compile(r'^[a-z0-9-]+$')

def validate_slug(slug: str) -> bool:
    """
    Validate project slug is safe for filesystem operations.

    Rules:
    - Only lowercase letters, numbers, and hyphens
    - 1-100 characters
    - Cannot start or end with hyphen
    """
    if not slug or len(slug) > 100:
        return False
    if not SLUG_PATTERN.match(slug):
        return False
    if slug.startswith('-') or slug.endswith('-'):
        return False
    return True

def validate_vault_path(vault_root: Path, target_path: str) -> Path:
    """
    Ensure path is within vault boundary using Path.is_relative_to().

    Args:
        vault_root: Absolute path to vault root
        target_path: Relative path from user (e.g., "06-findings/foo.md")

    Returns:
        Resolved absolute path if valid

    Raises:
        ValueError: If path escapes vault boundary
    """
    vault_root = vault_root.resolve()
    target = (vault_root / target_path).resolve()

    if not target.is_relative_to(vault_root):
        raise ValueError(f"Path escape attempt blocked: {target_path}")

    return target

def validate_project_path(slug: str, relative_path: str) -> Path:
    """
    Ensure path is within project boundary using Path.is_relative_to().

    Args:
        slug: Project slug (validated separately)
        relative_path: Relative path within project (e.g., "src/foo/main.py")

    Returns:
        Resolved absolute path if valid

    Raises:
        ValueError: If slug invalid or path escapes project boundary
    """
    if not validate_slug(slug):
        raise ValueError(f"Invalid project slug: {slug}")

    project_root = (Path.home() / "projects" / slug).resolve()
    target = (project_root / relative_path).resolve()

    if not target.is_relative_to(project_root):
        raise ValueError(f"Path escape attempt blocked: {relative_path}")

    return target

def slug_to_package_name(slug: str) -> str:
    """Convert slug to Python package name (hyphens to underscores)."""
    return slug.replace('-', '_')

def slug_to_title(slug: str) -> str:
    """Convert slug to title case (e.g., 'meeting-summarizer' -> 'Meeting Summarizer')."""
    return ' '.join(word.capitalize() for word in slug.split('-'))


# ============================================================================
# MCP SERVER SETUP
# ============================================================================

# Initialize MCP server
mcp = FastMCP("arcium")

# Load vault configuration
from ..vault.config import Config
config = Config()
VAULT_PATH = Path(config.vault_path).resolve()


# ============================================================================
# VAULT TOOLS (5 tools - migrated from arcium.vault.server)
# ============================================================================

@mcp.tool()
def vault__read_file(path: str) -> str:
    """
    Read a file from the vault.

    Args:
        path: Relative path from vault root (e.g., "06-findings/foo.md")

    Returns:
        File contents as string

    Security:
        Path must be within vault boundary
    """
    target = validate_vault_path(VAULT_PATH, path)

    if not target.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not target.is_file():
        raise ValueError(f"Not a file: {path}")

    return target.read_text(encoding='utf-8')


@mcp.tool()
def vault__write_file(path: str, content: str) -> str:
    """
    Create or overwrite a file in the vault.

    IMPORTANT: This tool is for markdown documentation only.
    Code files (.py, .toml, .yml, etc.) must use projects__write_file.

    Args:
        path: Relative path from vault root
        content: File content to write

    Returns:
        Success message

    Security:
        Path must be within vault boundary
        Rejects code file extensions - vault accepts markdown only
    """
    # Vault write guard: reject code files
    CODE_EXTENSIONS = {'.py', '.toml', '.cfg', '.yml', '.yaml', '.gitignore', '.env', '.json', '.txt', '.sh'}
    path_lower = path.lower()

    for ext in CODE_EXTENSIONS:
        if path_lower.endswith(ext):
            raise ValueError(
                f"Code files must use projects__write_file, not vault__write_file. "
                f"The vault accepts markdown only. "
                f"Rejected file: {path}"
            )

    target = validate_vault_path(VAULT_PATH, path)

    # Create parent directories if needed
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(content, encoding='utf-8')

    return f"Successfully wrote to {path}"


@mcp.tool()
def vault__append_file(path: str, content: str) -> str:
    """
    Append content to an existing file in the vault.

    Args:
        path: Relative path from vault root
        content: Content to append

    Returns:
        Success message

    Security:
        Path must be within vault boundary
    """
    target = validate_vault_path(VAULT_PATH, path)

    if not target.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with target.open('a', encoding='utf-8') as f:
        f.write(content)

    return f"Successfully appended to {path}"


@mcp.tool()
def vault__list_files(pattern: Optional[str] = None) -> List[str]:
    """
    List files in the vault with optional glob pattern.

    Args:
        pattern: Optional glob pattern (e.g., "**/*.md", "06-findings/*")
                If None, lists all files recursively

    Returns:
        List of relative file paths sorted alphabetically

    Security:
        Only lists files within vault boundary
    """
    if pattern:
        files = VAULT_PATH.glob(pattern)
    else:
        files = VAULT_PATH.rglob('*')

    # Filter to files only, return relative paths
    result = []
    for f in files:
        if f.is_file():
            try:
                rel_path = f.relative_to(VAULT_PATH)
                result.append(str(rel_path))
            except ValueError:
                # Skip files outside vault (shouldn't happen with glob)
                continue

    return sorted(result)


@mcp.tool()
def vault__search_content(query: str, file_pattern: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search file contents using regex patterns.

    Args:
        query: Search pattern (regex supported, case-insensitive)
        file_pattern: Optional glob pattern to limit search scope

    Returns:
        List of matches with file path, line number, line content, and matched text

    Security:
        Only searches within vault boundary
    """
    import re

    pattern = re.compile(query, re.IGNORECASE)
    results = []

    # Get files to search
    if file_pattern:
        files = VAULT_PATH.glob(file_pattern)
    else:
        files = VAULT_PATH.rglob('*')

    for file_path in files:
        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = file_path.relative_to(VAULT_PATH)

            for line_num, line in enumerate(content.splitlines(), 1):
                match = pattern.search(line)
                if match:
                    results.append({
                        "file": str(rel_path),
                        "line": line_num,
                        "content": line.strip(),
                        "match": match.group(0)
                    })
        except (UnicodeDecodeError, ValueError):
            # Skip binary files or files outside vault
            continue

    return results


# ============================================================================
# PROJECTS TOOLS (7 tools - new filesystem access for code generation)
# ============================================================================

@mcp.tool()
def projects__create_structure(slug: str) -> Dict[str, Any]:
    """
    Scaffold a complete GitHub-ready Python project with Poetry/pytest.

    Creates:
    - pyproject.toml with Poetry config (includes anthropic, python-dotenv)
    - src/<package>/ with __init__.py and main.py
    - tests/ with __init__.py, conftest.py, and test_main.py
    - .gitignore covering Python/Poetry standards
    - .env.example template
    - README.md with setup and usage instructions

    Args:
        slug: Project slug (e.g., "meeting-summarizer")
              Must match ^[a-z0-9-]+$

    Returns:
        Dict with created file paths and project info

    Security:
        Slug validated before any filesystem operation
        Creates in ~/projects/<slug>/ only
    """
    if not validate_slug(slug):
        raise ValueError(f"Invalid project slug: {slug}")

    project_root = Path.home() / "projects" / slug
    package_name = slug_to_package_name(slug)
    title = slug_to_title(slug)

    # Create project structure
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "src" / package_name).mkdir(parents=True, exist_ok=True)
    (project_root / "tests").mkdir(parents=True, exist_ok=True)

    created_files = []

    # pyproject.toml
    pyproject_content = f"""[tool.poetry]
name = "{slug}"
version = "0.1.0"
description = "AI-powered proof-of-concept project"
authors = ["Your Name <you@example.com>"]
readme = "README.md"
packages = [{{include = "{package_name}", from = "src"}}]

[tool.poetry.dependencies]
python = "^3.10"
anthropic = "^0.40.0"
python-dotenv = "^1.0.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-cov = "^4.1.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
"""
    (project_root / "pyproject.toml").write_text(pyproject_content)
    created_files.append("pyproject.toml")

    # .gitignore
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv

# Environment variables
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# OS
.DS_Store
Thumbs.db
"""
    (project_root / ".gitignore").write_text(gitignore_content)
    created_files.append(".gitignore")

    # .env.example
    env_example = """# Environment configuration template
# Copy to .env and fill in your values

# API Keys
# ANTHROPIC_API_KEY=your-key-here

# Application settings
# DEBUG=false
"""
    (project_root / ".env.example").write_text(env_example)
    created_files.append(".env.example")

    # README.md
    readme_content = f"""# {title}

AI-powered proof-of-concept project built with the Arcium WAT pipeline.

## Prerequisites

- Python 3.10 or higher
- Poetry (for dependency management)

## Installation

1. Install dependencies:
   ```bash
   cd ~/projects/{slug}
   poetry install
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Usage

```bash
poetry run python -m {package_name}
```

## Testing

```bash
poetry run pytest
```

## Project Structure

```
{slug}/
├── src/{package_name}/    # Main application code
├── tests/                 # Test suite
├── pyproject.toml         # Poetry configuration
└── README.md              # This file
```

## License

MIT
"""
    (project_root / "README.md").write_text(readme_content)
    created_files.append("README.md")

    # src/<package>/__init__.py
    init_content = f'''"""
{title} - AI-powered PoC

Built with the Arcium WAT pipeline.
"""

__version__ = "0.1.0"
'''
    (project_root / "src" / package_name / "__init__.py").write_text(init_content)
    created_files.append(f"src/{package_name}/__init__.py")

    # src/<package>/main.py
    main_content = f'''"""
Main entry point for {slug}.
"""

def main():
    """Main application entry point."""
    print("Hello from {slug}!")

if __name__ == "__main__":
    main()
'''
    (project_root / "src" / package_name / "main.py").write_text(main_content)
    created_files.append(f"src/{package_name}/main.py")

    # tests/__init__.py
    (project_root / "tests" / "__init__.py").write_text("")
    created_files.append("tests/__init__.py")

    # tests/conftest.py
    conftest_content = '''"""
Pytest configuration and fixtures.
"""
import pytest

@pytest.fixture
def sample_data():
    """Provide sample test data."""
    return {"test": "data"}
'''
    (project_root / "tests" / "conftest.py").write_text(conftest_content)
    created_files.append("tests/conftest.py")

    # tests/test_main.py
    test_main_content = f'''"""
Tests for main module.
"""
import pytest
from {package_name}.main import main

def test_main():
    """Test main function."""
    # Add your tests here
    assert True
'''
    (project_root / "tests" / "test_main.py").write_text(test_main_content)
    created_files.append("tests/test_main.py")

    return {
        "status": "success",
        "project_root": str(project_root),
        "package_name": package_name,
        "created_files": created_files,
        "message": f"Successfully created project structure for {slug}"
    }


@mcp.tool()
def projects__write_file(slug: str, path: str, content: str) -> str:
    """
    Write any file type into the project directory.

    Supports: .py, .txt, .yml, .md, .json, .toml, etc.

    Args:
        slug: Project slug
        path: Relative path within project (e.g., "src/foo/bar.py", "README.md")
        content: File content to write

    Returns:
        Success message

    Security:
        Slug validated, path must be within ~/projects/<slug>/

    Examples:
        projects__write_file("my-poc", "src/my_poc/utils.py", "def helper(): pass")
        projects__write_file("my-poc", "tests/test_utils.py", "def test_helper(): assert True")
    """
    target = validate_project_path(slug, path)

    # Create parent directories if needed
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(content, encoding='utf-8')

    return f"Successfully wrote to {slug}/{path}"


@mcp.tool()
def projects__read_file(slug: str, path: str) -> str:
    """
    Read a file from the project directory.

    Args:
        slug: Project slug
        path: Relative path within project

    Returns:
        File contents as string

    Security:
        Slug validated, path must be within ~/projects/<slug>/
    """
    target = validate_project_path(slug, path)

    if not target.exists():
        raise FileNotFoundError(f"File not found: {slug}/{path}")

    if not target.is_file():
        raise ValueError(f"Not a file: {slug}/{path}")

    return target.read_text(encoding='utf-8')


@mcp.tool()
def projects__list_files(slug: str, pattern: Optional[str] = None) -> List[str]:
    """
    List files in the project directory with optional glob pattern.

    Args:
        slug: Project slug
        pattern: Optional glob pattern (e.g., "**/*.py", "src/*")
                If None, lists all files recursively

    Returns:
        List of relative file paths sorted alphabetically

    Security:
        Slug validated, only lists within ~/projects/<slug>/
    """
    if not validate_slug(slug):
        raise ValueError(f"Invalid project slug: {slug}")

    project_root = (Path.home() / "projects" / slug).resolve()

    if not project_root.exists():
        raise FileNotFoundError(f"Project not found: {slug}")

    if pattern:
        files = project_root.glob(pattern)
    else:
        files = project_root.rglob('*')

    # Filter to files only, return relative paths
    result = []
    for f in files:
        if f.is_file():
            try:
                rel_path = f.relative_to(project_root)
                result.append(str(rel_path))
            except ValueError:
                # Skip files outside project (shouldn't happen with glob)
                continue

    return sorted(result)


@mcp.tool()
def projects__check_syntax(slug: str, path: str) -> Dict[str, Any]:
    """
    Compile Python file and return syntax errors or OK.

    Uses Python's compile() to validate syntax without executing code.

    Args:
        slug: Project slug
        path: Relative path to Python file (e.g., "src/foo/main.py")

    Returns:
        {"status": "ok"} or {"status": "error", "errors": [...]}

    Security:
        Slug validated, path must be within ~/projects/<slug>/
        Only compiles, does not execute code
    """
    target = validate_project_path(slug, path)

    if not target.exists():
        raise FileNotFoundError(f"File not found: {slug}/{path}")

    if not target.suffix == '.py':
        raise ValueError(f"Not a Python file: {path}")

    try:
        source = target.read_text(encoding='utf-8')
        compile(source, str(target), 'exec')
        return {"status": "ok"}
    except SyntaxError as e:
        return {
            "status": "error",
            "errors": [{
                "line": e.lineno,
                "offset": e.offset,
                "message": e.msg,
                "text": e.text.strip() if e.text else None
            }]
        }
    except Exception as e:
        return {
            "status": "error",
            "errors": [{"message": str(e)}]
        }


@mcp.tool()
def projects__check_dependencies(slug: str) -> Dict[str, Any]:
    """
    Run poetry check to verify dependency tree resolves correctly.

    Validates:
    - pyproject.toml is valid
    - All dependencies are compatible
    - Dependency tree has no conflicts

    Args:
        slug: Project slug

    Returns:
        {"status": "ok"} or {"status": "error", "stdout": str, "stderr": str}

    Security:
        Slug validated
        Runs in project directory only
        60-second timeout
    """
    if not validate_slug(slug):
        raise ValueError(f"Invalid project slug: {slug}")

    project_root = Path.home() / "projects" / slug

    if not project_root.exists():
        raise FileNotFoundError(f"Project not found: {slug}")

    if not (project_root / "pyproject.toml").exists():
        raise FileNotFoundError(f"pyproject.toml not found in {slug}")

    try:
        result = subprocess.run(
            ["poetry", "check"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            return {
                "status": "ok",
                "message": "All dependencies valid"
            }
        else:
            return {
                "status": "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "poetry check timed out after 60 seconds"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to run poetry check: {str(e)}"
        }


@mcp.tool()
def projects__run_tests(slug: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Execute poetry run pytest in project directory.

    Automatically runs poetry install --quiet if .venv doesn't exist.
    This ensures dependencies are available without requiring bash access.

    Args:
        slug: Project slug
        timeout: Maximum execution time in seconds (default 60)

    Returns:
        {
            "status": "passed|failed|error",
            "stdout": str,
            "stderr": str,
            "exit_code": int
        }

    Security:
        Slug validated
        Runs in project directory only
        Uses subprocess with timeout, never shell=True
    """
    if not validate_slug(slug):
        raise ValueError(f"Invalid project slug: {slug}")

    project_root = Path.home() / "projects" / slug

    if not project_root.exists():
        raise FileNotFoundError(f"Project not found: {slug}")

    venv_path = project_root / ".venv"

    # Auto-install dependencies if venv doesn't exist
    if not venv_path.exists():
        try:
            install_result = subprocess.run(
                ["poetry", "install", "--quiet"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes for install
            )

            if install_result.returncode != 0:
                return {
                    "status": "error",
                    "stdout": install_result.stdout,
                    "stderr": f"Failed to install dependencies:\n{install_result.stderr}",
                    "exit_code": install_result.returncode
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "stdout": "",
                "stderr": "Dependency installation timed out after 5 minutes",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Failed to run poetry install: {str(e)}",
                "exit_code": -1
            }

    try:
        result = subprocess.run(
            ["poetry", "run", "pytest"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Determine status from exit code
        if result.returncode == 0:
            status = "passed"
        elif result.returncode == 1:
            status = "failed"
        else:
            status = "error"

        return {
            "status": status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"Test execution timed out after {timeout} seconds",
            "exit_code": -1
        }
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"Failed to run tests: {str(e)}",
            "exit_code": -1
        }


# ============================================================================
# SERVER ENTRYPOINT
# ============================================================================

def main():
    """Run the unified Arcium MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
