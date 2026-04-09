"""
Smoke test: Run the ReactAgent with a real task against the vault.

Usage:
    poetry run python examples/smoke_test_agent.py

Prerequisites:
    - poetry install
    - python scripts/setup_vault.py
    - cp config.json.example config.json  (update vault_path)
    - ANTHROPIC_API_KEY set in .env (required for ReactAgent)
"""
import sys
from pathlib import Path

# Add src to path for development use without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arcium import run_react_agent


def main():
    task = "Search the vault for all findings related to MCP servers and summarize what was built"

    print("\n" + "=" * 80)
    print("REACT AGENT SMOKE TEST")
    print("=" * 80)
    print(f"\nTask: {task}\n")
    print("Starting agent...\n")

    try:
        result = run_react_agent(task=task, max_steps=10)

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        print(f"\nCompleted: {result.completed}")
        print(f"Reason: {result.reason}")
        print(f"Total Steps: {result.total_steps}")
        print(f"Finding Path: {result.finding_path}")
        print(f"\nFinal Answer:\n{result.final_answer}")
        print("\n")

    except Exception as e:
        print(f"\nSmoke test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
