"""
Arcium TUI — marketplace browser.

Browse all CAST artifacts in the marketplace by type and family.
"""
import questionary
from pathlib import Path


class BrowseFlow:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path

    def run(self) -> None:
        from arcium.tui.styles import print_section, info
        from arcium.tui.prompts import ask_select
        from arcium.workflow.cohort_resolver import CohortManifestResolver

        print_section("Browse marketplace", "arcium.subtitle")

        resolver = CohortManifestResolver(str(self.vault_path))

        while True:
            kind = ask_select("Browse:", choices=[
                questionary.Choice(
                    f"Cohorts    ({len(resolver._cohort_index)} available)",
                    value="cohort",
                ),
                questionary.Choice(
                    f"Agents     ({len(resolver._agent_index)} available)",
                    value="agent",
                ),
                questionary.Choice(
                    f"Skills     ({len(resolver._skill_index)} available)",
                    value="skill",
                ),
                questionary.Choice(
                    f"Tools      ({len(resolver._tool_index)} available)",
                    value="tool",
                ),
                questionary.Choice("← Back", value="back"),
            ])

            if kind == "back" or kind is None:
                break
            elif kind == "cohort":
                self._browse_cohorts(resolver)
            elif kind == "agent":
                self._browse_agents(resolver)
            elif kind == "skill":
                self._browse_skills(resolver)
            elif kind == "tool":
                self._browse_tools(resolver)

    def _browse_cohorts(self, resolver) -> None:
        from arcium.tui.styles import info
        from arcium.tui.prompts import ask_select
        from arcium.workflow.skill_injector import _parse_frontmatter

        choices = sorted(resolver._cohort_index.keys())
        if not choices:
            info("No cohorts in marketplace.")
            return

        choice = ask_select("Select cohort to view:", choices + ["← Back"])
        if not choice or choice == "← Back":
            return

        path = resolver._cohort_index[choice]
        fm, _ = _parse_frontmatter(path.read_text())
        self._print_artifact(fm, path)

    def _browse_agents(self, resolver) -> None:
        from arcium.tui.styles import info
        from arcium.tui.prompts import ask_select
        from arcium.workflow.skill_injector import _parse_frontmatter

        # Group by family
        families: dict[str, list[str]] = {}
        for agent_id, path in resolver._agent_index.items():
            family = path.parent.name
            families.setdefault(family, []).append(agent_id)

        family_choices = sorted(families.keys()) + ["← Back"]
        family = ask_select("Select family:", family_choices)
        if not family or family == "← Back":
            return

        agent = ask_select(
            "Select agent:",
            sorted(families[family]) + ["← Back"],
        )
        if not agent or agent == "← Back":
            return

        path = resolver._agent_index[agent]
        fm, _ = _parse_frontmatter(path.read_text())
        self._print_artifact(fm, path)

    def _browse_skills(self, resolver) -> None:
        from arcium.tui.styles import info
        from arcium.tui.prompts import ask_select
        from arcium.workflow.skill_injector import _parse_frontmatter

        choices = sorted(resolver._skill_index.keys())
        if not choices:
            info("No skills in marketplace.")
            return

        choice = ask_select("Select skill:", choices + ["← Back"])
        if not choice or choice == "← Back":
            return

        path = resolver._skill_index[choice]
        fm, _ = _parse_frontmatter(path.read_text())
        self._print_artifact(fm, path)

    def _browse_tools(self, resolver) -> None:
        from arcium.tui.styles import info
        from arcium.tui.prompts import ask_select
        from arcium.workflow.skill_injector import _parse_frontmatter

        choices = sorted(resolver._tool_index.keys())
        if not choices:
            info("No tools in marketplace.")
            return

        choice = ask_select("Select tool:", choices + ["← Back"])
        if not choice or choice == "← Back":
            return

        path = resolver._tool_index[choice]
        fm, _ = _parse_frontmatter(path.read_text())
        self._print_artifact(fm, path)

    def _print_artifact(self, fm: dict, path: Path) -> None:
        from arcium.tui.styles import console
        from rich.table import Table

        # Walk up to vault root: path is inside vault/02-marketplace/...
        # vault root is 3 levels up from the marketplace dir
        try:
            vault_root = path.parents[3]  # vault/02-marketplace/<family>/<file>
            rel = path.relative_to(vault_root)
        except ValueError:
            rel = path

        table = Table(
            show_header=False,
            border_style="arcium.muted",
            padding=(0, 2),
        )
        table.add_column("Field", style="arcium.muted",    min_width=16)
        table.add_column("Value", style="arcium.subtitle", min_width=40)

        for key in ["id", "version", "kind", "description", "tier", "blast_radius"]:
            if key in fm:
                table.add_row(key, str(fm[key]))

        table.add_row("path", str(rel))

        console.print()
        console.print(table)
        console.print()
