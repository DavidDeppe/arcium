"""
Skill injection system for the WAT pipeline.

Loads skill files from the vault and injects them into ReactAgent system prompts
or ClaudeCodeAgent configurations to create specialist agents with specific roles
and capabilities.
"""

import logging
from pathlib import Path
from typing import Dict, List, Union, Literal, Tuple, Optional
import yaml
from ..vault import VaultTools
from ..projects import ProjectTools
from ..agent.react import ReactAgent, VAULT_TOOLS, PROJECTS_TOOLS
from ..agent.backend import AnthropicBackend, AgentResult
from ..agent.claude_code_agent import ClaudeCodeAgent
from ..config import get_config

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """Raised when an agent file cannot be found at any known lookup path."""
    pass


class FrontmatterParseError(Exception):
    """Raised when a vault file has malformed or invalid frontmatter."""
    pass


def _parse_frontmatter(content: str) -> Tuple[dict, str]:
    """
    Parse YAML frontmatter from a markdown file.

    Returns (frontmatter_dict, body_string).

    Raises FrontmatterParseError if frontmatter delimiters are present
    but the YAML block is malformed. Files with no frontmatter return
    ({}, full_content) — not an error.
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        raise FrontmatterParseError(
            "Frontmatter opening delimiter found but no closing '---'. "
            "File is malformed — fix the frontmatter or remove the opening delimiter."
        )

    yaml_block = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as e:
        raise FrontmatterParseError(f"Malformed YAML frontmatter: {e}") from e

    if parsed is None:
        parsed = {}

    if not isinstance(parsed, dict):
        raise FrontmatterParseError(
            f"Frontmatter parsed to {type(parsed).__name__}, expected dict. "
            "Check that the YAML block is key:value pairs, not a bare scalar."
        )

    list_fields = ["reviewed_by", "approved_for_tiers", "default_skills",
                   "default_tools", "suggested_tools", "tags"]
    for field in list_fields:
        if field in parsed and not isinstance(parsed[field], list):
            raise FrontmatterParseError(
                f"Field '{field}' must be a YAML list but parsed as "
                f"{type(parsed[field]).__name__}: {parsed[field]!r}. "
                f"Use YAML list syntax: [{field}: [value1, value2]]"
            )

    return parsed, body


def _is_legacy_skill_file(frontmatter: dict) -> bool:
    """
    Returns True if this file uses the old SKILL.md format (pre-Phase 1).
    Detection: old format uses 'type' key; new format uses 'kind' key.
    When True, the runtime treats the file as a combined AGENT+SKILL and
    composes the prompt using the full file body, identical to pre-Phase 1 behavior.
    This shim is removed in Phase 3 when the registry resolver replaces skill_injector.
    """
    return "type" in frontmatter and "kind" not in frontmatter


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
- Search for related past work in 05-sessions/ and 04-findings/
- Read project-specific files in 03-cohort-work/ or 06-scratch/
- Read stakeholder information from 01-firm-context/STAKEHOLDERS.md if needed
- Read any other vault files not listed above
"""

        self.context_cache["firm_context"] = context
        return context

    def _build_agent_index(self) -> dict:
        """Walk 02-marketplace/agents/ recursively. Returns id→path dict."""
        index = {}
        agents_dir = Path(self.vault.vault_path) / "02-marketplace" / "agents"
        if agents_dir.exists():
            for path in agents_dir.rglob("*.md"):
                try:
                    fm, _ = _parse_frontmatter(path.read_text())
                    if fm.get("kind") == "agent":
                        agent_id = fm.get("id", path.stem)
                        existing = index.get(agent_id)
                        if existing is None or path.parent != agents_dir:
                            index[agent_id] = path
                except Exception:
                    continue
        return index

    def _resolve_agent_path(self, agent_id: str) -> str:
        """
        Resolve a bare agent ID to its canonical vault path.

        Searches recursively under 02-marketplace/agents/ using _build_agent_index.
        Also accepts full vault-relative paths (e.g. "02-marketplace/skills/vault-navigation.md").

        Raises AgentNotFoundError if the file does not exist.
        """
        if "/" in agent_id:
            try:
                self.vault.read_file(agent_id)
                return agent_id
            except Exception:
                raise AgentNotFoundError(
                    f"Agent file not found at path: '{agent_id}'"
                )

        index = self._build_agent_index()
        path = index.get(agent_id)
        if path is None:
            available = sorted(index.keys())
            raise AgentNotFoundError(
                f"Agent '{agent_id}' not found in marketplace. "
                f"Available: {available}"
            )
        return str(path.relative_to(Path(self.vault.vault_path)))

    def load_skill(self, skill_path: str) -> str:
        """
        Load skill/agent file from vault with caching.

        Supports both legacy SKILL.md format (type: skill) and new AGENT.md
        format (kind: agent). For new-format files, strips frontmatter so only
        the markdown body is injected into the system prompt. For legacy files,
        the full content (including frontmatter) is returned unchanged — identical
        to pre-Phase 1 behavior.

        Args:
            skill_path: Bare agent ID (e.g. "team-lead") or full vault path (e.g. "02-marketplace/skills/vault-navigation.md")

        Returns:
            Content to inject into the system prompt
        """
        if skill_path in self.skill_cache:
            return self.skill_cache[skill_path]

        resolved_path = self._resolve_agent_path(skill_path)
        raw_content = self.vault.read_file(resolved_path)

        frontmatter, body = _parse_frontmatter(raw_content)

        if _is_legacy_skill_file(frontmatter):
            # Legacy format: inject full content unchanged (pre-Phase 1 behavior)
            result = raw_content
        else:
            # New format (kind: agent or kind: skill): inject body only, drop frontmatter.
            # Phase 3 resolver will replace this branch entirely.
            logger.debug(
                "New-format agent file loaded: %s (kind=%s)",
                resolved_path,
                frontmatter.get("kind", "unknown"),
            )
            result = body

        self.skill_cache[skill_path] = result
        return result

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
