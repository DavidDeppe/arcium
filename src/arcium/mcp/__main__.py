"""
Entry point for unified Arcium MCP server.

Run with: poetry run python -m arcium.mcp.server
"""

from .server import main

if __name__ == "__main__":
    main()
