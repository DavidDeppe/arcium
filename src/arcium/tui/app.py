"""
Arcium TUI — main launcher and home screen.

Entry point for 'arcium' and 'arcium init' commands.
"""
import os
import questionary
from pathlib import Path


def launch_tui(start_at: str | None = None) -> None:
    """
    Launch the Arcium TUI.

    Args:
        start_at: Optional screen to jump to directly.
                  Options: 'create', 'run', 'validate', 'marketplace'
                  If None, shows the home screen.
    """
    from arcium.tui.styles import console, print_header, print_section, info
    from arcium.tui.prompts import ask_select, ask_confirm

    vault_path = Path(
        os.getenv(
            "ARCIUM_VAULT_PATH",
            str(Path.home() / "Documents" / "arcium-vault"),
        )
    )

    print_header()

    if start_at == "create":
        _flow_create(vault_path)
        return
    elif start_at == "marketplace":
        _flow_browse(vault_path)
        return

    # Home screen loop
    while True:
        print_section("What would you like to do?")
        action = ask_select("", choices=[
            questionary.Choice("✦  Create a CAST artifact",  value="create"),
            questionary.Choice("▶  Run a cohort",            value="run"),
            questionary.Choice("✓  Validate a cohort",       value="validate"),
            questionary.Choice("◈  Browse marketplace",      value="marketplace"),
            questionary.Choice("◻  Exit",                    value="exit"),
        ])

        if action == "exit" or action is None:
            info("Goodbye.")
            break
        elif action == "create":
            _flow_create(vault_path)
        elif action == "run":
            _flow_run(vault_path)
        elif action == "validate":
            _flow_validate(vault_path)
        elif action == "marketplace":
            _flow_browse(vault_path)

        console.print()


def _flow_create(vault_path: Path) -> None:
    from arcium.tui.create import CreateFlow
    flow = CreateFlow(vault_path)
    flow.run()


def _flow_run(vault_path: Path) -> None:
    from arcium.tui.styles import console, print_section, success, error
    from arcium.tui.prompts import ask_required, ask_kebab, ask_select
    from arcium.workflow.cohort_resolver import CohortManifestResolver

    print_section("Run a cohort", "arcium.teal")

    resolver = CohortManifestResolver(str(vault_path))
    cohort_choices = sorted(resolver._cohort_index.keys())

    if not cohort_choices:
        error("No cohorts found in marketplace. Create one first.")
        return

    cohort_id = ask_select("Select cohort:", cohort_choices)
    if not cohort_id:
        return

    idea = ask_required("Describe the task or idea (one sentence):")
    if not idea:
        return
    slug = ask_kebab("Project slug (kebab-case):")
    if not slug:
        return

    console.print()
    success(f"Starting {cohort_id} cohort...")
    console.print()

    from arcium.workflow.cohort_coordinator import CohortCoordinator
    coordinator = CohortCoordinator(cohort_id=cohort_id)
    coordinator.run(poc_idea=idea, poc_slug=slug)


def _flow_validate(vault_path: Path) -> None:
    from arcium.tui.styles import print_section, success, error
    from arcium.tui.prompts import ask_select, ask_confirm
    from arcium.tui.create import _print_validation_result
    from arcium.workflow.cohort_resolver import CohortManifestResolver
    from arcium.marketplace.validator import MarketplaceValidator

    print_section("Validate a cohort", "arcium.subtitle")

    resolver = CohortManifestResolver(str(vault_path))
    cohort_choices = sorted(resolver._cohort_index.keys())

    if not cohort_choices:
        error("No cohorts found.")
        return

    cohort_id = ask_select("Select cohort to validate:", cohort_choices)
    if not cohort_id:
        return

    validator = MarketplaceValidator(str(vault_path))
    result = validator.validate(cohort_id)

    _print_validation_result(result)

    if result.status == "passed":
        write = ask_confirm("Write validation report to marketplace?", default=True)
        if write:
            cohort_path = resolver._cohort_index[cohort_id]
            report_path = validator.write_report(result, cohort_path.parent)
            success(f"Report written: {report_path.name}")


def _flow_browse(vault_path: Path) -> None:
    from arcium.tui.browse import BrowseFlow
    flow = BrowseFlow(vault_path)
    flow.run()
