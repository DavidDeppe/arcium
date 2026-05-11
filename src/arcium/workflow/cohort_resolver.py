"""
CohortManifestResolver — resolves a COHORT.md manifest into composed system
prompts for each agent role.

Phase 3a responsibility: composition only.
- Reads the COHORT.md manifest
- For each role, loads the AGENT.md persona
- Applies skills_add from the manifest on top of agent defaults
- Resolves tool bundle via ToolManifestResolver
- Composes system prompt in canonical order:
    1. Persona block (AGENT.md body)
    2. Skills block (each SKILL.md body, alphabetical by id)
    3. Cohort context block (role in this cohort, coordination rules)

Phase 3b: adds graph node parsing when coordination.runtime_routing == 'enabled'.
The composition contract established in 3a remains stable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import yaml

from .skill_injector import _parse_frontmatter, FrontmatterParseError
from .tool_resolver import ToolManifestResolver

logger = logging.getLogger(__name__)

_COHORTS_DIR = "02-marketplace/cohorts"
_AGENTS_DIR = "02-marketplace/agents"
_SKILLS_DIR = "02-marketplace/skills"


class CohortNotFoundError(Exception):
    """Raised when a COHORT.md file cannot be found."""
    pass


class CohortManifestError(Exception):
    """Raised when a COHORT.md has malformed or missing required fields."""
    pass


class RoleNotFoundError(Exception):
    """Raised when a requested role does not exist in the manifest."""
    pass


@dataclass
class AgentRoleSpec:
    role: str
    agent_id: str        # e.g. "team-lead" (version stripped for Phase 3a)
    tools: str           # bundle name — passed through to ToolManifestResolver
    skills_add: list = field(default_factory=list)


@dataclass
class GraphNode:
    id: str
    role: str
    default_next: str | None
    valid_routes: list
    terminal: bool = False
    on_max_iterations: str = "escalate"


@dataclass
class CohortManifest:
    id: str
    version: str
    description: str
    agents: list
    coordination: dict
    sla: dict
    quality_gates: list
    source_path: Path
    graph_nodes: dict = field(default_factory=dict)  # node_id → GraphNode, populated when runtime_routing: enabled


class CohortManifestResolver:
    """
    Resolves COHORT.md manifests into composed agent system prompts.

    Given a cohort ID, loads the manifest, then for any role within it
    composes a fully-formed system prompt by combining:
      1. The agent persona (AGENT.md body)
      2. Any additional skills (SKILL.md bodies, alphabetical)
      3. A cohort context block (role, coordination protocol, runtime context)

    Returns (system_prompt, tools_filter) so callers can pass both to
    ClaudeCodeAgent.execute_safe().
    """

    def __init__(self, vault_path: Union[str, Path]):
        self.vault_path = Path(vault_path)
        self.tool_resolver = ToolManifestResolver(vault_path=str(self.vault_path))
        self._manifest_cache: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_manifest(self, cohort_id: str) -> CohortManifest:
        """
        Load and parse a COHORT.md manifest by cohort ID.

        Args:
            cohort_id: The cohort's id field value (e.g. 'poc-generator')

        Returns:
            CohortManifest dataclass

        Raises:
            CohortNotFoundError: If the manifest file does not exist
            CohortManifestError: If frontmatter is malformed or required fields absent
        """
        if cohort_id in self._manifest_cache:
            return self._manifest_cache[cohort_id]

        manifest_path = self.vault_path / _COHORTS_DIR / f"{cohort_id}.md"
        if not manifest_path.exists():
            raise CohortNotFoundError(
                f"Cohort manifest not found: {manifest_path} (cohort id: '{cohort_id}')"
            )

        raw = manifest_path.read_text()
        try:
            frontmatter, _ = _parse_frontmatter(raw)
        except FrontmatterParseError as e:
            raise CohortManifestError(
                f"Malformed frontmatter in {manifest_path}: {e}"
            ) from e

        manifest = self._build_manifest(frontmatter, manifest_path)
        self._manifest_cache[cohort_id] = manifest
        return manifest

    def compose_system_prompt(
        self,
        manifest: CohortManifest,
        role: str,
        cohort_context: dict,
    ) -> tuple:
        """
        Compose a fully-formed system prompt for a role within a cohort.

        Args:
            manifest: A loaded CohortManifest
            role: The role name to compose for (e.g. 'team-lead')
            cohort_context: Runtime context dict injected into the cohort context block
                            (e.g. {'slug': 'my-poc', 'iteration': 1})

        Returns:
            (system_prompt: str, tools_filter: str)
            tools_filter is the bundle name for this role (e.g. 'vault_only', 'all')

        Raises:
            RoleNotFoundError: If the role is not defined in the manifest
        """
        role_spec = self._find_role(manifest, role)

        # 1. Load agent persona (body only, frontmatter stripped)
        persona = self._load_agent_body(role_spec.agent_id)

        # 2. Load additional skills (alphabetical by skill id)
        skill_bodies = []
        for skill_id in sorted(role_spec.skills_add):
            skill_bodies.append(self._load_skill_body(skill_id))

        # 3. Build cohort context block
        context_block = self._build_cohort_context_block(manifest, role_spec, cohort_context)

        # Compose in canonical order
        parts = [persona]

        if skill_bodies:
            parts.append("\n\n---\n\n## Additional Context\n\n")
            parts.append("\n\n---\n\n".join(skill_bodies))

        parts.append("\n\n" + context_block)

        system_prompt = "".join(parts)

        logger.debug(
            "Composed system prompt for role '%s' in cohort '%s': %d chars, tools=%s",
            role, manifest.id, len(system_prompt), role_spec.tools,
        )

        return system_prompt, role_spec.tools

    def resolve_tools(self, manifest: CohortManifest, role: str) -> str:
        """
        Return the tools bundle name for a given role.

        Args:
            manifest: A loaded CohortManifest
            role: Role name

        Returns:
            Bundle name string (e.g. 'vault_only', 'all')

        Raises:
            RoleNotFoundError: If the role is not defined in the manifest
        """
        return self._find_role(manifest, role).tools

    def get_graph_node(self, manifest: CohortManifest, node_id: str) -> GraphNode:
        """
        Return the GraphNode for node_id.

        Raises:
            RoleNotFoundError: If node_id is not in the manifest graph
        """
        if node_id not in manifest.graph_nodes:
            raise RoleNotFoundError(
                f"Node '{node_id}' not in cohort graph for '{manifest.id}'. "
                f"Available nodes: {list(manifest.graph_nodes.keys())}"
            )
        return manifest.graph_nodes[node_id]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_manifest(self, frontmatter: dict, source_path: Path) -> CohortManifest:
        """Parse frontmatter dict into a CohortManifest, validating required fields."""
        required = ["id", "version", "kind", "agents", "coordination"]
        missing = [f for f in required if f not in frontmatter]
        if missing:
            raise CohortManifestError(
                f"COHORT.md at {source_path} is missing required fields: {missing}"
            )

        if frontmatter.get("kind") != "cohort":
            raise CohortManifestError(
                f"File at {source_path} has kind='{frontmatter.get('kind')}', expected 'cohort'"
            )

        agents = []
        for entry in frontmatter["agents"]:
            agent_ref = entry.get("agent", "")
            # Strip semver suffix for Phase 3a: "team-lead@1.0.0" → "team-lead"
            agent_id = agent_ref.split("@")[0] if "@" in agent_ref else agent_ref
            agents.append(AgentRoleSpec(
                role=entry["role"],
                agent_id=agent_id,
                tools=entry.get("tools", "vault_only"),
                skills_add=entry.get("skills_add", []),
            ))

        # description may be a multi-line YAML scalar
        description = frontmatter.get("description", "")
        if isinstance(description, str):
            description = description.strip()

        coordination = frontmatter.get("coordination", {})

        # Parse graph nodes when runtime_routing is enabled
        graph_nodes: dict = {}
        if coordination.get("runtime_routing") == "enabled":
            for node_dict in coordination.get("graph", {}).get("nodes", []):
                node = GraphNode(
                    id=node_dict["id"],
                    role=node_dict["role"],
                    default_next=node_dict.get("default_next"),
                    valid_routes=node_dict.get("valid_routes", []),
                    terminal=node_dict.get("terminal", False),
                    on_max_iterations=node_dict.get("on_max_iterations", "escalate"),
                )
                graph_nodes[node.id] = node

        return CohortManifest(
            id=frontmatter["id"],
            version=str(frontmatter["version"]),
            description=description,
            agents=agents,
            coordination=coordination,
            sla=frontmatter.get("sla", {}),
            quality_gates=frontmatter.get("quality_gates", []),
            source_path=source_path,
            graph_nodes=graph_nodes,
        )

    def _find_role(self, manifest: CohortManifest, role: str) -> AgentRoleSpec:
        """Find AgentRoleSpec by role name. Raises RoleNotFoundError if missing."""
        for spec in manifest.agents:
            if spec.role == role:
                return spec
        available = [s.role for s in manifest.agents]
        raise RoleNotFoundError(
            f"Role '{role}' not found in cohort '{manifest.id}'. "
            f"Available roles: {available}"
        )

    def _load_agent_body(self, agent_id: str) -> str:
        """Load AGENT.md body (frontmatter stripped)."""
        agent_path = self.vault_path / _AGENTS_DIR / f"{agent_id}.md"
        if not agent_path.exists():
            raise CohortManifestError(
                f"Agent file not found: {agent_path} (agent_id: '{agent_id}')"
            )
        raw = agent_path.read_text()
        _, body = _parse_frontmatter(raw)
        return body.strip()

    def _load_skill_body(self, skill_id: str) -> str:
        """Load SKILL.md body (frontmatter stripped)."""
        skill_path = self.vault_path / _SKILLS_DIR / f"{skill_id}.md"
        if not skill_path.exists():
            raise CohortManifestError(
                f"Skill file not found: {skill_path} (skill_id: '{skill_id}')"
            )
        raw = skill_path.read_text()
        _, body = _parse_frontmatter(raw)
        return body.strip()

    def _build_cohort_context_block(
        self,
        manifest: CohortManifest,
        role_spec: AgentRoleSpec,
        cohort_context: dict,
    ) -> str:
        """
        Build the cohort context block appended to every agent's system prompt.

        Tells the agent which cohort they are participating in, their role,
        the coordination protocol, and any runtime context (slug, iteration, etc.).
        """
        lines = [
            "---",
            "## Cohort Context",
            f"Cohort: {manifest.id} v{manifest.version}",
            f"Your role: {role_spec.role}",
            f"Coordination: {manifest.coordination.get('protocol', 'sequential')}",
        ]
        for key, value in cohort_context.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Inline unit tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys

    vault_path = os.getenv(
        "ARCIUM_VAULT_PATH",
        str(Path.home() / "Documents" / "arcium-vault")
    )

    resolver = CohortManifestResolver(vault_path=vault_path)
    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        global passed, failed
        status = "PASS" if condition else "FAIL"
        suffix = f": {detail}" if detail else ""
        print(f"  [{status}] {label}{suffix}")
        if condition:
            passed += 1
        else:
            failed += 1

    print("CohortManifestResolver — unit tests")
    print("=" * 60)

    # Test 1: load_manifest returns CohortManifest with 5 agent roles
    try:
        manifest = resolver.load_manifest("poc-generator")
        check(
            "load_manifest('poc-generator') returns 5 agent roles",
            len(manifest.agents) == 5,
            f"got {len(manifest.agents)}: {[a.role for a in manifest.agents]}"
        )
    except Exception as e:
        check("load_manifest('poc-generator') returns 5 agent roles", False, str(e))
        manifest = None

    # Test 2: team-lead prompt contains content from team-lead.md body
    if manifest:
        try:
            prompt, _ = resolver.compose_system_prompt(manifest, "team-lead", {})
            # team-lead.md body starts with "# Skill: Team Lead"
            check(
                "team-lead prompt contains content from team-lead.md body",
                len(prompt) > 100 and ("Team Lead" in prompt or "team" in prompt.lower()),
                f"{len(prompt)} chars"
            )
        except Exception as e:
            check("team-lead prompt contains content from team-lead.md body", False, str(e))

    # Test 3: senior-engineer prompt and tools_filter == 'all'
    if manifest:
        try:
            prompt2, tools2 = resolver.compose_system_prompt(manifest, "senior-engineer", {})
            check(
                "senior-engineer tools_filter == 'all'",
                tools2 == "all",
                f"got '{tools2}'"
            )
        except Exception as e:
            check("senior-engineer tools_filter == 'all'", False, str(e))

    # Test 4: team-lead tools_filter == 'vault_only'
    if manifest:
        try:
            _, tools1 = resolver.compose_system_prompt(manifest, "team-lead", {})
            check(
                "team-lead tools_filter == 'vault_only'",
                tools1 == "vault_only",
                f"got '{tools1}'"
            )
        except Exception as e:
            check("team-lead tools_filter == 'vault_only'", False, str(e))

    # Test 5: nonexistent role raises RoleNotFoundError
    if manifest:
        try:
            resolver.compose_system_prompt(manifest, "nonexistent-role", {})
            check("nonexistent role raises RoleNotFoundError", False, "no exception raised")
        except RoleNotFoundError:
            check("nonexistent role raises RoleNotFoundError", True)
        except Exception as e:
            check("nonexistent role raises RoleNotFoundError", False,
                  f"wrong exception: {type(e).__name__}: {e}")

    # Test 6: nonexistent cohort raises CohortNotFoundError
    try:
        resolver.load_manifest("nonexistent-cohort")
        check("nonexistent cohort raises CohortNotFoundError", False, "no exception raised")
    except CohortNotFoundError:
        check("nonexistent cohort raises CohortNotFoundError", True)
    except Exception as e:
        check("nonexistent cohort raises CohortNotFoundError", False,
              f"wrong exception: {type(e).__name__}: {e}")

    # Test 7: cohort context block appears in every composed prompt
    if manifest:
        all_have_context = True
        missing_context = []
        for role_spec in manifest.agents:
            try:
                p, _ = resolver.compose_system_prompt(manifest, role_spec.role, {"slug": "test"})
                if "Cohort Context" not in p:
                    all_have_context = False
                    missing_context.append(role_spec.role)
            except Exception as e:
                all_have_context = False
                missing_context.append(f"{role_spec.role} (error: {e})")
        check(
            "Cohort context block appears in every composed prompt",
            all_have_context,
            f"missing in: {missing_context}" if missing_context else ""
        )

    # Test 8: skills block absent when skills_add is empty (all current roles)
    if manifest:
        # All current poc-generator roles have empty skills_add
        all_no_skills_block = True
        unexpected_skills = []
        for role_spec in manifest.agents:
            if role_spec.skills_add:
                # This role has skills — block should be present; skip this check
                continue
            try:
                p, _ = resolver.compose_system_prompt(manifest, role_spec.role, {})
                if "## Additional Context" in p:
                    all_no_skills_block = False
                    unexpected_skills.append(role_spec.role)
            except Exception as e:
                all_no_skills_block = False
                unexpected_skills.append(f"{role_spec.role} (error: {e})")
        check(
            "Skills block absent when skills_add is empty",
            all_no_skills_block,
            f"unexpected skills block in: {unexpected_skills}" if unexpected_skills else ""
        )

    # Test 9: load_manifest returns manifest with 5 graph nodes
    if manifest:
        check(
            "load_manifest('poc-generator') returns 5 graph nodes",
            len(manifest.graph_nodes) == 5,
            f"got {len(manifest.graph_nodes)}: {list(manifest.graph_nodes.keys())}"
        )

    # Test 10: solutions-critic valid_routes contains senior-architect and senior-engineer
    if manifest:
        try:
            critic_node = resolver.get_graph_node(manifest, "solutions-critic")
            has_both = (
                "senior-architect" in critic_node.valid_routes and
                "senior-engineer" in critic_node.valid_routes
            )
            check(
                "solutions-critic valid_routes contains senior-architect and senior-engineer",
                has_both,
                f"valid_routes: {critic_node.valid_routes}"
            )
        except Exception as e:
            check("solutions-critic valid_routes contains senior-architect and senior-engineer",
                  False, str(e))

    # Test 11: communications-specialist terminal is True
    if manifest:
        try:
            comms_node = resolver.get_graph_node(manifest, "communications-specialist")
            check(
                "get_graph_node(manifest, 'communications-specialist').terminal is True",
                comms_node.terminal is True,
                f"terminal={comms_node.terminal}"
            )
        except Exception as e:
            check("get_graph_node(manifest, 'communications-specialist').terminal is True",
                  False, str(e))

    # Test 12: get_graph_node('nonexistent') raises RoleNotFoundError
    if manifest:
        try:
            resolver.get_graph_node(manifest, "nonexistent")
            check("get_graph_node('nonexistent') raises RoleNotFoundError", False, "no exception raised")
        except RoleNotFoundError:
            check("get_graph_node('nonexistent') raises RoleNotFoundError", True)
        except Exception as e:
            check("get_graph_node('nonexistent') raises RoleNotFoundError", False,
                  f"wrong exception: {type(e).__name__}: {e}")

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
