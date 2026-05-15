"""Shared utilities for the Arcium TUI."""
import yaml
from pathlib import Path


def _build_markdown(frontmatter: dict, body: str) -> str:
    """
    Build a vault markdown file from frontmatter dict and body string.
    Produces clean YAML frontmatter with markdown body.
    """
    fm_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{fm_str}---\n\n{body}"
