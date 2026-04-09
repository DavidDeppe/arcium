"""
Arcium - Internal reusable AI infrastructure library.

Provides MCP (Model Context Protocol) servers and AI agent utilities
for building proof-of-concept AI systems.

Modules:
    vault: MCP server for Obsidian vault operations
    agent: AI agents (ReAct, etc.)

Usage as a library:
    # In another project's pyproject.toml:
    [tool.poetry.dependencies]
    arcium = {path = "../arcium", develop = true}

    # Then import in your code:
    from arcium.vault import VaultTools, Config
    from arcium import ReactAgent, run_react_agent

    # Use vault tools
    config = Config()
    vault = VaultTools(config.vault_path)
    content = vault.read_file("path/to/file.md")

    # Use ReAct agent
    result = run_react_agent("Search vault for findings about MCP")
    print(result.final_answer)
"""

from . import vault
from . import agent
from . import workflow
from . import projects
from .agent import ReactAgent, ReActResult, Step, TokenUsage
from .workflow import PoCPipeline, run_poc_pipeline
from .projects import ProjectTools

__version__ = "0.1.0"
__all__ = [
    "vault",
    "agent",
    "workflow",
    "projects",
    "ReactAgent",
    "ReActResult",
    "Step",
    "TokenUsage",
    "PoCPipeline",
    "run_poc_pipeline",
    "ProjectTools",
]
