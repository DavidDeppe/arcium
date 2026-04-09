"""
Skill injection system for the WAT pipeline.

Loads skill files from the vault and injects them into ReactAgent system prompts
or ClaudeCodeAgent configurations to create specialist agents with specific roles
and capabilities.
"""

from typing import Dict, List, Union, Literal
from ..vault import VaultTools
from ..projects import ProjectTools
from ..agent.react import ReactAgent, VAULT_TOOLS, PROJECTS_TOOLS
from ..agent.backend import AnthropicBackend, AgentResult
from ..agent.claude_code_agent import ClaudeCodeAgent
from ..config import get_config


class SkillInjector:
    """
    Loads skill files from vault and injects them into agent configurations.

    Supports two execution modes:
    - 'react': ReactAgent with AnthropicBackend (multi-turn API loop)
    - 'autonomous': ClaudeCodeAgent (single subprocess call to claude CLI)

    Also pre-loads firm context files to avoid agents spending steps reading them.
    """

    def __init__(self, vault: VaultTools, projects: ProjectTools):
        self.vault = vault
        self.projects = projects
        self.skill_cache: Dict[str, str] = {}
        self.context_cache: Dict[str, str] = {}
        self.config = get_config()

    def _load_firm_context(self) -> str:
        """
        Pre-load firm context files (CONSTRAINTS.md, DOMAIN.md) to inject into system prompt.

        This optimization prevents agents from spending 2-3 steps reading these files
        during their reasoning loop. Instead, context is available from step 1.

        Returns:
            Formatted firm context string
        """
        if "firm_context" in self.context_cache:
            return self.context_cache["firm_context"]

        # Load context files
        constraints = self.vault.read_file("01-firm-context/CONSTRAINTS.md")
        domain = self.vault.read_file("01-firm-context/DOMAIN.md")

        # Format as pre-loaded context
        context = f"""# Pre-Loaded Firm Context

The following firm context has been pre-loaded for you. You do NOT need to read these files
with vault tools - the information is already available below.

## Firm Constraints

{constraints}

## Domain Context

{domain}

---

You may still use vault tools to:
- Search for related past work in 05-conversations/ and 06-findings/
- Read project-specific files in 02-projects/ or 08-scratch/
- Read stakeholder information from 01-firm-context/STAKEHOLDERS.md if needed
- Read any other vault files not listed above
"""

        self.context_cache["firm_context"] = context
        return context

    def load_skill(self, skill_path: str) -> str:
        """
        Load skill file from vault with caching.

        Args:
            skill_path: Path to skill file in vault (e.g., "04-skills/team-lead.md")

        Returns:
            Skill file content
        """
        if skill_path not in self.skill_cache:
            self.skill_cache[skill_path] = self.vault.read_file(skill_path)

        return self.skill_cache[skill_path]

    def create_specialist_agent(
        self,
        role: str,
        skill_file: str,
        tools_filter: str = 'vault_only',
        execution_mode: Literal['react', 'autonomous'] = 'react',
        **kwargs
    ) -> Union[AnthropicBackend, ClaudeCodeAgent]:
        """
        Create a specialist agent with skill and pre-loaded context.

        Args:
            role: Agent role name (for logging)
            skill_file: Path to skill file in vault
            tools_filter: 'vault_only' (5 tools) or 'all' (12 tools)
            execution_mode: 'react' for ReactAgent/AnthropicBackend, 'autonomous' for ClaudeCodeAgent
            **kwargs: Additional arguments (api_key, verbose, etc.)

        Returns:
            AnthropicBackend (wrapping ReactAgent) if execution_mode='react'
            ClaudeCodeAgent if execution_mode='autonomous'
        """
        # Load the skill file
        skill_content = self.load_skill(skill_file)

        # Pre-load firm context
        firm_context = self._load_firm_context()

        # Build system prompt (used by both backends)
        system_prompt = self._build_system_prompt(firm_context, skill_content, tools_filter)

        if execution_mode == 'react':
            # Create ReactAgent and wrap in AnthropicBackend
            return self._create_react_backend(
                role=role,
                firm_context=firm_context,
                skill_content=skill_content,
                tools_filter=tools_filter,
                **kwargs
            )
        else:  # autonomous
            # Create ClaudeCodeAgent
            return self._create_claude_code_agent(
                role=role,
                system_prompt=system_prompt,
                **kwargs
            )

    def _build_system_prompt(
        self,
        firm_context: str,
        skill_content: str,
        tools_filter: str
    ) -> str:
        """
        Build system prompt for agent (used by both ReactAgent and ClaudeCodeAgent).

        Args:
            firm_context: Pre-loaded firm context
            skill_content: Skill file content
            tools_filter: 'vault_only' or 'all'

        Returns:
            Formatted system prompt
        """
        if tools_filter == 'vault_only':
            tool_description = "5 vault tools for reading/writing markdown documentation"
        else:
            tool_description = "12 tools (5 vault__* for documentation + 7 projects__* for code)"

        return f"""You are a specialized AI agent with access to vault and project tools.

{firm_context}

{skill_content}

You have access to {tool_description}.

Use vault tools for documentation. Use projects tools for code.

Work step by step, using tools as needed to complete your task."""

    def _create_react_backend(
        self,
        role: str,
        firm_context: str,
        skill_content: str,
        tools_filter: str,
        **react_kwargs
    ) -> AnthropicBackend:
        """
        Create ReactAgent wrapped in AnthropicBackend.

        Args:
            role: Agent role
            firm_context: Pre-loaded firm context
            skill_content: Skill file content
            tools_filter: 'vault_only' or 'all'
            **react_kwargs: Arguments for ReactAgent (api_key, verbose, etc.)

        Returns:
            AnthropicBackend wrapping ReactAgent
        """
        # Determine which tools to provide
        if tools_filter == 'vault_only':
            tools = VAULT_TOOLS
        else:  # 'all'
            tools = VAULT_TOOLS + PROJECTS_TOOLS

        # Create ReactAgent with skill injection
        agent = ReactAgent(
            vault=self.vault,
            projects=self.projects,
            preloaded_firm_context=firm_context,
            skill_content=skill_content,
            **react_kwargs
        )

        # Override the tools list to filter based on tools_filter
        agent.tools = tools

        # Wrap in AnthropicBackend
        return AnthropicBackend(react_agent=agent)

    def _create_claude_code_agent(
        self,
        role: str,
        system_prompt: str,
        **kwargs
    ) -> ClaudeCodeAgent:
        """
        Create ClaudeCodeAgent for autonomous execution.

        Args:
            role: Agent role
            system_prompt: Complete system prompt
            **kwargs: Additional arguments (unused, for API compatibility)

        Returns:
            ClaudeCodeAgent instance
        """
        return ClaudeCodeAgent(
            mcp_config_path=self.config.mcp_config_path,
            vault_path=self.config.vault_path,
            projects_path=self.config.projects_path,
            reasoning_log_dir=self.config.reasoning_log_dir
        )
