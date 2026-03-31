"""Arcium MCP server for vault file operations."""

from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

from .config import Config
from .tools import VaultTools


# Initialize configuration and tools
config = Config()
vault_tools = VaultTools(config.vault_path)

# Create MCP server
mcp = FastMCP("vault-server")


@mcp.tool()
def read_vault_file(path: str) -> str:
    """Read a file from the vault.

    Args:
        path: Relative path from vault root (e.g., "00-index/INDEX.md")

    Returns:
        File contents as string
    """
    return vault_tools.read_file(path)


@mcp.tool()
def write_vault_file(path: str, content: str) -> str:
    """Create or overwrite a file in the vault.

    Args:
        path: Relative path from vault root
        content: Content to write to the file

    Returns:
        Success message
    """
    return vault_tools.write_file(path, content)


@mcp.tool()
def append_vault_file(path: str, content: str) -> str:
    """Append content to an existing file in the vault.

    Args:
        path: Relative path from vault root
        content: Content to append

    Returns:
        Success message
    """
    return vault_tools.append_file(path, content)


@mcp.tool()
def list_vault_files(pattern: Optional[str] = None) -> List[str]:
    """List files in the vault with optional glob pattern.

    Args:
        pattern: Optional glob pattern (e.g., "*.md", "**/*.md", "00-index/*")
                If not provided, lists all files recursively

    Returns:
        List of relative file paths sorted alphabetically
    """
    return vault_tools.list_files(pattern)


@mcp.tool()
def search_vault_content(
    query: str,
    file_pattern: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search file contents using regex patterns.

    Args:
        query: Search pattern (regex supported, case-insensitive)
        file_pattern: Optional glob pattern to limit search scope

    Returns:
        List of matches with file path, line number, line content, and matched text
    """
    return vault_tools.search_content(query, file_pattern)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
