"""
Arcium - Internal reusable AI infrastructure library.

Provides MCP (Model Context Protocol) servers and AI agent utilities
for building proof-of-concept AI systems.

Modules:
    vault: MCP server for Obsidian vault operations
    agent: AI agents (ReAct, etc.) - coming soon

Usage as a library:
    # In another project's pyproject.toml:
    [tool.poetry.dependencies]
    arcium = {path = "../arcium", develop = true}

    # Then import in your code:
    from arcium.vault import VaultTools, Config

    config = Config()
    vault = VaultTools(config.vault_path)
    content = vault.read_file("path/to/file.md")
"""

from . import vault
from . import agent

__version__ = "0.1.0"
__all__ = ["vault", "agent"]
