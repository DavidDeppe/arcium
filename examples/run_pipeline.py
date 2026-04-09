"""
Example: Run the WAT Pipeline end-to-end.

This script delegates to the pipeline CLI entry point.
You can also invoke it directly:

    poetry run python -m arcium.workflow.poc_pipeline --help

    poetry run python -m arcium.workflow.poc_pipeline \\
        --idea "Build a CLI tool that counts word frequency in a text file" \\
        --slug "word-frequency"

Prerequisites:
    - poetry install
    - python scripts/setup_vault.py
    - cp config.json.example config.json  (update vault_path)
    - cp .mcp.json.example .mcp.json
    - Autonomous mode (default): Claude Code CLI installed with Max/Pro subscription
    - API mode (--mode api):     ANTHROPIC_API_KEY set with sufficient credits
"""
from arcium.workflow.poc_pipeline import _cli_main

if __name__ == "__main__":
    _cli_main()
