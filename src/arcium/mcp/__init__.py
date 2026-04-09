"""
Unified Arcium MCP server.

Provides two namespaced tool groups:
- vault__* tools for Obsidian vault operations (scoped to vault path)
- projects__* tools for Python project code generation (scoped to ~/projects/<slug>/)
"""

from .server import main

__all__ = ["main"]
