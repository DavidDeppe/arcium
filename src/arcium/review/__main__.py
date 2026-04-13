"""
Entry point for `python -m arcium.review`.

Usage:
    poetry run python -m arcium.review \\
        --architecture path/to/architecture.md \\
        --standards path/to/standards.md

Authentication
--------------
This module calls the Anthropic API directly and requires ANTHROPIC_API_KEY.
It looks for the key in two places (in order):

1. Shell environment variable (recommended):
       export ANTHROPIC_API_KEY=sk-ant-...
       poetry run python -m arcium.review -a arch.md -s standards.md

2. .env file in the architecture-reviewer PoC project:
       ~/projects/architecture-reviewer/.env
       containing: ANTHROPIC_API_KEY=sk-ant-...

IMPORTANT: Do NOT set ANTHROPIC_API_KEY in Arcium's own .env
(~/Documents/Programming Projects/arcium/.env). Arcium's WAT pipeline
agents authenticate via the Claude Code Max plan subscription. Adding a
direct API key to Arcium's .env would route pipeline traffic to paid API
billing instead of the subscription.
"""

from .cli import main

if __name__ == "__main__":
    main()
