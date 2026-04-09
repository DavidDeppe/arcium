"""
Example: Run the WAT Pipeline end-to-end with a word-frequency PoC.

Usage:
    poetry run python examples/run_pipeline.py

Prerequisites:
    - poetry install
    - python scripts/setup_vault.py
    - cp config.json.example config.json  (update vault_path)
    - cp .mcp.json.example .mcp.json
"""
from arcium import run_poc_pipeline


def main():
    poc_idea = (
        "Build a CLI tool that takes a plain text file path as input, counts word frequency, "
        "and outputs the top 10 most common words with their counts. Single file implementation, "
        "no external API calls."
    )
    poc_slug = "word-frequency"

    print("=" * 80)
    print("WAT PIPELINE EXAMPLE RUN")
    print("=" * 80)
    print(f"PoC Idea: {poc_idea}")
    print(f"PoC Slug: {poc_slug}")
    print(f"Mode: Production (ClaudeCodeAgent autonomous, $10 limit)")
    print("=" * 80)
    print()

    try:
        result = run_poc_pipeline(
            poc_idea=poc_idea,
            poc_slug=poc_slug
        )

        print()
        print("=" * 80)
        print("PIPELINE COMPLETED")
        print("=" * 80)
        print(f"Status: {result['status']}")
        print(f"Total Cost: ${result['total_cost']:.4f}")
        print(f"Project Directory: {result['project_dir']}")
        print(f"Scratch Directory: {result['scratch_dir']}")

        if 'agent_costs' in result:
            print()
            print("Per-Agent Costs:")
            for agent, cost in result['agent_costs'].items():
                print(f"  {agent}: ${cost:.4f}")

        print("=" * 80)

    except Exception as e:
        print()
        print("=" * 80)
        print(f"ERROR: {type(e).__name__}")
        print("=" * 80)
        print(f"{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
