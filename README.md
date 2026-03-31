# Arcium

Internal reusable AI infrastructure library for building AI-powered proof-of-concept systems.

Arcium provides:
- **MCP (Model Context Protocol) servers** for connecting Claude Code to external systems
- **AI agent utilities** (coming soon) including ReAct agents and other cognitive architectures
- **Reusable components** that can be imported into other Python projects

## Modules

### `arcium.vault`
MCP server for Obsidian vault operations, exposing five core tools:
- `read_vault_file` - Read any file from the vault
- `write_vault_file` - Create or overwrite files (with safety checks)
- `append_vault_file` - Append content to existing files
- `list_vault_files` - List files with glob pattern support
- `search_vault_content` - Search file contents (grep-like)

### `arcium.agent` (Coming Soon)
ReAct agents and other AI cognitive architectures for building autonomous systems.

## Prerequisites

- Python 3.10 or higher
- Poetry (for dependency management)
- An Obsidian vault (or any markdown-based knowledge base)

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd <my_projects>/arcium
   ```

2. **Install dependencies with Poetry:**
   ```bash
   poetry install
   ```

   This will:
   - Create a virtual environment in `.venv/`
   - Install the MCP SDK and all dependencies
   - Set up the project for development

## Configuration

1. **Set the vault path:**

   Edit `config.json` and set your vault path:
   ```json
   {
     "vault_path": "<my_vault>/claude-obi-vault"
   }
   ```

## Usage

### Option 1: As an MCP Server (Standalone)

Run the vault server directly for use with Claude Code:

```bash
poetry run python -m arcium.vault.server
```

**Connect to Claude Code:**

Add to your `.mcp.json` or Claude desktop config:

```json
{
  "mcpServers": {
    "vault": {
      "command": "poetry",
      "args": ["run", "python", "-m", "arcium.vault.server"],
      "cwd": "/path/to/arcium"
    }
  }
}
```

### Option 2: As a Python Library (Reusable)

Install Arcium as a dependency in your own project:

**In your project's `pyproject.toml`:**

```toml
[tool.poetry.dependencies]
arcium = {path = "../arcium", develop = true}
```

Or with pip in editable mode:

```bash
pip install -e /path/to/arcium
```

**Import and use in your code:**

```python
from arcium.vault import VaultTools, Config

# Initialize vault tools
config = Config()  # Uses config.json in Arcium's root
vault = VaultTools(config.vault_path)

# Read files
content = vault.read_file("notes/example.md")

# Write files
vault.write_file("output/result.md", "# Results\n\nData here...")

# List files
markdown_files = vault.list_files("**/*.md")

# Search content
results = vault.search_content("TODO", file_pattern="*.md")
```

**Example PoC project structure:**

```
my-poc-project/
├── pyproject.toml          # Declares arcium as dependency
├── src/
│   └── my_poc/
│       ├── __init__.py
│       └── agent.py        # Imports from arcium
└── README.md

../arcium/                   # Arcium library (sibling directory)
```

## Project Structure

```
arcium/
├── pyproject.toml              # Poetry configuration & package metadata
├── poetry.lock                 # Locked dependencies
├── README.md                   # This file
├── config.json                 # Vault path configuration
├── .mcp.json                   # MCP server configuration
├── .venv/                      # Virtual environment
└── src/
    └── arcium/
        ├── __init__.py         # Top-level package exports
        ├── __main__.py         # Entry point (backward compat)
        ├── vault/              # Vault MCP server module
        │   ├── __init__.py     # Exports Config, VaultTools, main
        │   ├── __main__.py     # Module entry point
        │   ├── server.py       # MCP server implementation
        │   ├── tools.py        # VaultTools class
        │   └── config.py       # Configuration loader
        └── agent/              # Future: ReAct agents, etc.
            └── __init__.py
```

## Tools Reference

### read_vault_file
Reads a file from the vault.
- **Parameters:** `path` (string) - Relative path from vault root
- **Returns:** File contents as string

### write_vault_file
Creates or overwrites a file in the vault.
- **Parameters:**
  - `path` (string) - Relative path from vault root
  - `content` (string) - File content
- **Returns:** Success message

### append_vault_file
Appends content to an existing file.
- **Parameters:**
  - `path` (string) - Relative path from vault root
  - `content` (string) - Content to append
- **Returns:** Success message

### list_vault_files
Lists files in the vault with optional glob pattern.
- **Parameters:**
  - `pattern` (string, optional) - Glob pattern (e.g., "*.md", "**/*.md")
- **Returns:** List of matching file paths

### search_vault_content
Searches file contents using regex patterns.
- **Parameters:**
  - `query` (string) - Search pattern (regex supported)
  - `file_pattern` (string, optional) - Limit search to matching files
- **Returns:** List of matches with file paths and line numbers

## Development

### Working on Arcium

```bash
# Install dependencies
poetry install

# Run vault server
poetry run python -m arcium.vault.server

# Add new dependencies
poetry add package-name

# Run tests (when added)
poetry run pytest
```

### Adding New Vault Tools

1. Add method to `VaultTools` class in `src/arcium/vault/tools.py`
2. Register as MCP tool in `src/arcium/vault/server.py` using `@mcp.tool()`
3. Update exports in `src/arcium/vault/__init__.py` if needed
4. Restart the MCP server

### Creating New Modules

Future modules (like `arcium.agent.react`) should follow this structure:

```
src/arcium/agent/
├── __init__.py          # Export public API
└── react/
    ├── __init__.py      # Export ReActAgent, etc.
    ├── agent.py         # Implementation
    └── prompts.py       # Prompt templates
```

## Using Arcium in Your PoC Projects

Here's a complete example of creating a new project that uses Arcium:

### Step 1: Create Your Project

```bash
cd ~/<my_projects>
mkdir my-agent-poc
cd my-agent-poc
poetry init -n
```

### Step 2: Add Arcium as Dependency

Edit `pyproject.toml` to add Arcium:

```toml
[tool.poetry.dependencies]
python = "^3.10"
arcium = {path = "../arcium", develop = true}
```

Then install:

```bash
poetry install
```

### Step 3: Use Arcium in Your Code

Create `src/my_agent/main.py`:

```python
from arcium.vault import VaultTools, Config

def main():
    # Access vault through Arcium's config
    config = Config()  # Uses arcium/config.json
    vault = VaultTools(config.vault_path)

    # Read your agent's instructions from vault
    instructions = vault.read_file("agents/my-agent-instructions.md")

    # Process and write results back
    result = process_with_agent(instructions)
    vault.write_file("agents/output.md", result)

    print("Agent completed!")

if __name__ == "__main__":
    main()
```

### Step 4: Run Your Agent

```bash
poetry run python src/my_agent/main.py
```

This approach allows you to:
- Keep Arcium as a shared library across multiple PoCs
- Import vault tools, future agent utilities, etc.
- Maintain one source of truth for common infrastructure

## Troubleshooting

**Server won't start:**
- Ensure Poetry installed dependencies: `poetry install`
- Check Python version: `poetry run python --version`
- Verify config.json exists and vault_path is valid

**Claude Code can't connect:**
- Check `.mcp.json` or Claude desktop config
- Verify module path is `arcium.vault.server` (not `arcium.server`)
- Verify `cwd` points to Arcium project directory
- Restart Claude Code after config changes

**Import errors in PoC project:**
- Ensure path dependency is correct in `pyproject.toml`
- Run `poetry install` in your PoC project
- Check that Arcium is installed: `poetry show arcium`

**File operation errors:**
- Verify vault path in config.json
- Check file permissions on vault directory
- Ensure paths are relative to vault root

## License

MIT
