"""
Arcium TUI — CAST artifact creation flow.

Handles creation of all four CAST types with inline dependency resolution:
  - Cohort: assembles agents + graph + metadata
  - Agent: persona + family + tools + skills
  - Skill: domain + body content
  - Tool: MCP server + endpoint allowlist
"""
import datetime
import questionary
from dataclasses import dataclass, field
from pathlib import Path

from arcium.tui.utils import _build_markdown


@dataclass
class CreationContext:
    """Tracks artifacts created during a session for inline dependency resolution."""
    vault_path: Path
    created_agents: list[dict] = field(default_factory=list)
    created_skills: list[dict] = field(default_factory=list)
    created_tools: list[dict] = field(default_factory=list)
    created_cohorts: list[dict] = field(default_factory=list)


class CreateFlow:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.ctx = CreationContext(vault_path=vault_path)
        self._resolver = None

    def _get_resolver(self):
        from arcium.workflow.cohort_resolver import CohortManifestResolver
        self._resolver = CohortManifestResolver(str(self.vault_path))
        return self._resolver

    def run(self) -> None:
        from arcium.tui.styles import print_section, success
        from arcium.tui.prompts import ask_select

        print_section("Create a CAST artifact", "arcium.title")

        kind = ask_select("What would you like to create?", choices=[
            questionary.Choice(
                "Cohort  — assemble agents into a coordinated team", value="cohort"),
            questionary.Choice(
                "Agent   — define a specialist role and persona", value="agent"),
            questionary.Choice(
                "Skill   — create an injectable capability", value="skill"),
            questionary.Choice(
                "Tool    — define MCP endpoint access", value="tool"),
        ])

        if kind == "cohort":
            self._create_cohort()
        elif kind == "agent":
            result = self._create_agent()
            if result:
                success(f"Agent '{result['id']}' created.")
        elif kind == "skill":
            result = self._create_skill()
            if result:
                success(f"Skill '{result['id']}' created.")
        elif kind == "tool":
            result = self._create_tool()
            if result:
                success(f"Tool '{result['id']}' created.")

    # ------------------------------------------------------------------
    # Agent creation
    # ------------------------------------------------------------------

    def _create_agent(self, inline: bool = False) -> dict | None:
        from arcium.tui.styles import console, print_section, success, warning, info
        from arcium.tui.prompts import (
            ask_kebab, ask_required, ask_select,
            ask_checkbox, ask_multiline, ask_confirm,
        )

        if not inline:
            print_section("Create an Agent", "arcium.teal")

        agent_id = ask_kebab("Agent id (kebab-case, e.g. python-developer):")
        if not agent_id:
            return None

        resolver = self._get_resolver()
        if agent_id in resolver._agent_index:
            warning(f"Agent '{agent_id}' already exists.")
            if not ask_confirm("Create anyway (will overwrite)?", default=False):
                return None

        family = ask_select("Agent family:", choices=[
            "leads", "architects", "developers",
            "reviewers", "communicators", "specialists",
        ])
        if not family:
            return None

        description = ask_required("One-sentence description (what this agent does):")
        if not description:
            return None

        available_skills = sorted(resolver._skill_index.keys())
        default_skills: list[str] = []
        if available_skills:
            info("")
            info("Select default skills for this agent (space to select):")
            default_skills = ask_checkbox("Default skills:", available_skills) or []

        default_tools = ask_select("Default tool access:", choices=["vault_only", "all"])
        if not default_tools:
            default_tools = "vault_only"

        info("")
        info("Write the agent persona body.")
        info("This is the markdown content injected into the agent's system prompt.")
        info("Cover: role, responsibilities, how they work, escalation rules.")
        persona_body = ask_multiline("Agent persona (blank line to finish):")

        today = datetime.date.today().isoformat()
        frontmatter = {
            "id": agent_id,
            "version": "1.0.0",
            "kind": "agent",
            "tier": "firm",
            "maintainer": "platform-team",
            "description": description,
            "default_skills": default_skills,
            "default_tools": [f"vault-readwrite@^1.0"],
            "blast_radius": "write-project",
            "sla": {"max_runtime_seconds": 3600, "max_cost_usd": 5.00},
            "provenance": {
                "reviewed_by": ["platform-team"],
                "reviewed_on": today,
            },
        }

        agent_dir = self.vault_path / "02-marketplace" / "agents" / family
        agent_dir.mkdir(parents=True, exist_ok=True)
        agent_path = agent_dir / f"{agent_id}.md"

        body = persona_body or f"# {agent_id}\n\n## Identity\n\n## Mandate\n\n## Escalation\n"
        agent_path.write_text(_build_markdown(frontmatter, body), encoding="utf-8")

        success(f"Agent saved: agents/{family}/{agent_id}.md")

        result = {"id": agent_id, "path": agent_path, "family": family}
        self.ctx.created_agents.append(result)
        return result

    # ------------------------------------------------------------------
    # Skill creation
    # ------------------------------------------------------------------

    def _create_skill(self, inline: bool = False) -> dict | None:
        from arcium.tui.styles import print_section, success, info
        from arcium.tui.prompts import ask_kebab, ask_required, ask_select, ask_multiline

        if not inline:
            print_section("Create a Skill", "arcium.blue")

        skill_id = ask_kebab("Skill id (kebab-case, e.g. time-series-analysis):")
        if not skill_id:
            return None

        domain = ask_select("Skill domain:", choices=[
            "observability", "architecture", "testing", "security",
            "data", "communication", "vault", "cloud", "platform", "other",
        ])
        if not domain:
            return None

        description = ask_required(
            "One-sentence description (what this skill teaches agents):")
        if not description:
            return None

        info("")
        info("Write the skill body — the content injected into agent system prompts.")
        info("Cover: standards, patterns, anti-patterns, examples.")
        skill_body = ask_multiline("Skill body (blank line to finish):")

        readme_description = ask_required(
            "README description (when should this skill be used?):")
        if not readme_description:
            return None

        today = datetime.date.today().isoformat()
        frontmatter = {
            "id": skill_id,
            "version": "1.0.0",
            "kind": "skill",
            "tier": "firm",
            "description": description,
            "applies_to": {"agent_kinds": ["engineer", "architect"]},
            "suggested_tools": [],
            "provenance": {
                "reviewed_by": ["platform-team"],
                "reviewed_on": today,
            },
        }

        skill_dir = self.vault_path / "02-marketplace" / "skills" / domain / skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)

        body = skill_body or f"# {skill_id}\n\n## Standards\n\n## Patterns\n\n## Anti-patterns\n"
        (skill_dir / "SKILL.md").write_text(_build_markdown(frontmatter, body), encoding="utf-8")
        (skill_dir / "README.md").write_text(
            f"# {skill_id}\n\n{description}\n\n"
            f"## When to use\n\n{readme_description}\n\n"
            f"## Domain\n\n{domain}\n\n"
            f"**Injectable:** Yes — use SKILL.md as system prompt injection\n",
            encoding="utf-8",
        )

        success(f"Skill saved: skills/{domain}/{skill_id}/")

        result = {"id": skill_id, "path": skill_dir, "domain": domain}
        self.ctx.created_skills.append(result)
        return result

    # ------------------------------------------------------------------
    # Tool creation
    # ------------------------------------------------------------------

    def _create_tool(self, inline: bool = False) -> dict | None:
        from arcium.tui.styles import print_section, success, info
        from arcium.tui.prompts import ask_kebab, ask_required, ask_select, ask_multiline

        if not inline:
            print_section("Create a Tool", "arcium.amber")

        tool_id = ask_kebab("Tool id (kebab-case, e.g. jira-create-ticket):")
        if not tool_id:
            return None

        category = ask_select("Tool category:", choices=[
            "vault", "code", "communication", "project-management",
            "cloud", "data", "security", "other",
        ])
        if not category:
            return None

        description = ask_required(
            "One-sentence description (what this tool allows agents to do):")
        if not description:
            return None

        mcp_server = ask_required(
            "MCP server name (must match .mcp.json key, e.g. arcium, jira, slack):")
        if not mcp_server:
            return None

        info("")
        info("List the MCP endpoints this tool ALLOWS (one per line, blank to finish).")
        info("Example: projects__write_file")
        endpoints_text = ask_multiline("Allowed endpoints:")
        endpoints_allowed = [e.strip() for e in endpoints_text.splitlines() if e.strip()]

        blast_radius = ask_select("Blast radius:", choices=[
            "read-vault", "write-vault",
            "read-project", "write-project", "execute-project",
            "read-external", "write-external",
        ])
        if not blast_radius:
            blast_radius = "write-project"

        today = datetime.date.today().isoformat()
        frontmatter = {
            "id": tool_id,
            "version": "1.0.0",
            "kind": "tool",
            "tier": "firm",
            "description": description,
            "mcp": {
                "server": mcp_server,
                "endpoints_allowed": endpoints_allowed,
                "endpoints_denied": [],
            },
            "blast_radius": blast_radius,
            "audit": {"log_to": "arcium-audit", "retention_days": 2555},
            "provenance": {
                "reviewed_by": ["platform-team"],
                "reviewed_on": today,
                "approved_for_tiers": ["personal", "team", "lob", "department", "firm"],
            },
        }

        tool_dir = self.vault_path / "02-marketplace" / "tools" / category
        tool_dir.mkdir(parents=True, exist_ok=True)
        tool_path = tool_dir / f"{tool_id}.md"
        tool_path.write_text(_build_markdown(frontmatter, ""), encoding="utf-8")

        success(f"Tool saved: tools/{category}/{tool_id}.md")

        result = {"id": tool_id, "path": tool_path, "category": category}
        self.ctx.created_tools.append(result)
        return result

    # ------------------------------------------------------------------
    # Cohort creation
    # ------------------------------------------------------------------

    def _create_cohort(self) -> dict | None:
        from arcium.tui.styles import console, print_section, success, warning, error, info
        from arcium.tui.prompts import (
            ask_kebab, ask_required, ask_select, ask_checkbox,
            ask_confirm, ask,
        )
        from arcium.tui.graph import build_graph_interactive

        print_section("Create a Cohort", "arcium.subtitle")

        cohort_id = ask_kebab("Cohort id (kebab-case, e.g. bmad-cohort):")
        if not cohort_id:
            return None

        description = ask_required(
            "One-sentence description (what this cohort delivers):")
        if not description:
            return None

        max_cost_str = ask("Max total cost USD (default 10.00):", default="10.00")
        try:
            max_cost_val = float(max_cost_str or "10.00")
        except ValueError:
            max_cost_val = 10.00

        # --- Agent assembly loop ---
        console.print()
        print_section("Assemble agents", "arcium.teal")
        info("Add agents to this cohort. Each agent needs a role name.")
        info("You can select existing agents or create new ones inline.")
        console.print()

        roles: list[dict] = []

        while True:
            resolver = self._get_resolver()
            existing_agents = sorted(resolver._agent_index.keys())

            choices = (
                [questionary.Choice(f"  {a}", value=a) for a in existing_agents]
                + [
                    questionary.Separator(),
                    questionary.Choice("+ Create a new agent inline", value="__new__"),
                    questionary.Choice("✓ Done adding agents",        value="__done__"),
                ]
            )

            agent_choice = ask_select(
                f"Select agent (role {len(roles) + 1}):",
                choices=choices,
            )

            if agent_choice == "__done__" or agent_choice is None:
                if len(roles) < 2:
                    warning("A cohort needs at least 2 agents.")
                    continue
                break

            if agent_choice == "__new__":
                info("")
                new_agent = self._create_agent(inline=True)
                if not new_agent:
                    continue
                agent_choice = new_agent["id"]
                resolver = self._get_resolver()

            role_name = ask_kebab(
                f"Role name for '{agent_choice}' in this cohort:",
                default=agent_choice,
            )
            if not role_name:
                continue

            tools = ask_select(
                f"Tool access for '{role_name}':",
                choices=["vault_only", "all"],
            )
            if not tools:
                tools = "vault_only"

            available_skills = sorted(resolver._skill_index.keys())
            skills_add: list[str] = []
            if available_skills:
                add_skills = ask_confirm(f"Add skills to '{role_name}'?", default=False)
                if add_skills:
                    skills_add = ask_checkbox("Select skills to inject:", available_skills) or []

            roles.append({
                "role": role_name,
                "agent": f"{agent_choice}@1.0.0",
                "tools": tools,
                "skills_add": skills_add,
            })
            success(f"Added: {role_name} ({agent_choice})")
            console.print()

        # --- Graph editor ---
        console.print()
        print_section("Define coordination graph", "arcium.subtitle")

        role_names = [r["role"] for r in roles]
        graph_nodes = build_graph_interactive(role_names)

        # --- Review and save ---
        console.print()
        print_section("Review", "arcium.muted")
        info(f"Cohort:      {cohort_id}")
        info(f"Description: {description}")
        info(f"Agents:      {len(roles)}")
        for r in roles:
            info(f"  • {r['role']} ({r['agent']}) — {r['tools']}")
        info(f"Max cost:    ${max_cost_val:.2f}")
        console.print()

        if not ask_confirm("Save this cohort?", default=True):
            info("Cancelled.")
            return None

        today = datetime.date.today().isoformat()
        manifest = {
            "id": cohort_id,
            "version": "1.0.0",
            "kind": "cohort",
            "tier": "firm",
            "description": description,
            "agents": roles,
            "coordination": {
                "protocol": "graph",
                "runtime_routing": "enabled",
                "max_iterations": 5,
                "escalation": "human",
                "graph": {"nodes": graph_nodes},
            },
            "sla": {
                "max_total_runtime_seconds": 7200,
                "max_total_cost_usd": max_cost_val,
            },
            "quality_gates": [
                {"test_pass_rate": ">= 0.95"},
                {"critic_severity_max": "medium"},
            ],
            "provenance": {
                "reviewed_by": ["platform-team"],
                "reviewed_on": today,
                "marketplace_listed": False,
                "signed_by": ["platform-team"],
            },
        }

        cohort_dir = self.vault_path / "02-marketplace" / "cohorts" / cohort_id
        cohort_dir.mkdir(parents=True, exist_ok=True)
        cohort_path = cohort_dir / f"{cohort_id}.md"
        cohort_path.write_text(
            _build_markdown(manifest, f"# {cohort_id}\n\n## Purpose\n\n{description}\n"),
            encoding="utf-8",
        )

        success(f"Cohort saved: cohorts/{cohort_id}/{cohort_id}.md")

        # Run validator
        console.print()
        info("Running marketplace validation...")
        from arcium.marketplace.validator import MarketplaceValidator
        validator = MarketplaceValidator(str(self.vault_path))
        # Refresh resolver so newly created agents are indexed
        validator._resolver.refresh_index()
        result = validator.validate(cohort_id)

        _print_validation_result(result)

        if result.status in ("passed", "warning"):
            write_report = ask_confirm("Write validation report?", default=True)
            if write_report:
                report_path = validator.write_report(result, cohort_dir)
                success(f"Report: {report_path.name}")

        return {"id": cohort_id, "path": cohort_dir}


# ---------------------------------------------------------------------------
# Shared helper used by both create.py and app.py
# ---------------------------------------------------------------------------

def _print_validation_result(result) -> None:
    from arcium.tui.styles import console, success, warning, error

    console.print()

    def gate(ok: bool) -> str:
        return "[arcium.success]✅[/]" if ok else "[arcium.error]❌[/]"

    console.print(f"  Schema        {gate(result.schema_valid)}")
    console.print(f"  References    {gate(result.references_valid)}")
    console.print(f"  Graph         {gate(result.graph_valid)}")
    console.print(f"  Test run      {gate(result.test_run_verified)}")
    console.print()

    if result.status == "passed":
        success(f"{result.cohort_id} v{result.cohort_version} — ready to publish")
    elif result.status == "warning":
        warning(f"{result.cohort_id} — passed with warnings")
    else:
        error(f"{result.cohort_id} — validation failed")

    if result.findings:
        console.print()
        for f in result.findings:
            console.print(f"  [arcium.muted]• {f}[/]")
