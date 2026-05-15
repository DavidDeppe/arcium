"""
Arcium CLI entry point.

Usage:
  arcium              Launch the interactive TUI (CohortCreator)
  arcium init         Same as arcium with no args
  arcium create       Jump directly to artifact creation flow
  arcium run          Run a cohort by id
  arcium validate     Validate a cohort for marketplace publishing
  arcium vault        Launch the Arcium vault MCP server
  arcium marketplace  Browse the marketplace

All subcommands are available for scripting. The TUI is the default
experience for interactive use.
"""

import sys


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else None

    if cmd is None or cmd == "init":
        from arcium.tui.app import launch_tui
        launch_tui()

    elif cmd == "create":
        from arcium.tui.app import launch_tui
        launch_tui(start_at="create")

    elif cmd == "run":
        from arcium.tui.run import run_cohort_cli
        run_cohort_cli(args[1:])

    elif cmd == "validate":
        import runpy
        sys.argv = ["arcium-validate"] + args[1:]
        runpy.run_module("arcium.marketplace.validator", run_name="__main__")

    elif cmd == "vault":
        from arcium.vault.server import main as vault_main
        vault_main()

    elif cmd == "marketplace":
        from arcium.tui.app import launch_tui
        launch_tui(start_at="marketplace")

    elif cmd in ("--help", "-h"):
        print(__doc__)

    else:
        print(f"Unknown command: {cmd}")
        print("Run 'arcium --help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
