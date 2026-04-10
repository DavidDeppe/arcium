"""
scripts/setup_vault.py

Generates a complete arcium-vault directory structure from the templates in templates/vault/.
Also generates AGENTS.md and tool-specific AI briefing files from a shared template.

Usage:
    python scripts/setup_vault.py
    python scripts/setup_vault.py --vault-path ~/Documents/my-custom-vault
    python scripts/setup_vault.py --vault-path /absolute/path/to/vault

The script:
    1. Creates all 9 numbered vault folders
    2. Copies sanitized template files into the vault
    3. Generates AGENTS.md in the project root (canonical AI briefing)
    4. Generates CLAUDE.md as a one-line redirect to AGENTS.md
    5. Generates .cursorrules for Cursor IDE
    6. Generates .github/copilot-instructions.md for GitHub Copilot
"""

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates" / "vault"

VAULT_FOLDERS = [
    "00-index",
    "01-firm-context",
    "02-projects",
    "03-agents/workflows",
    "04-skills",
    "05-conversations",
    "06-findings",
    "07-resources",
    "08-scratch",
    "99-archive",
]

TODAY = date.today().isoformat()


def replace_date_placeholders(content: str) -> str:
    """Replace YYYY-MM-DD placeholders with today's date."""
    return content.replace("YYYY-MM-DD", TODAY)


def copy_templates(vault_path: Path) -> None:
    """Copy all template files into the vault, replacing date placeholders."""
    if not TEMPLATES_DIR.exists():
        print(f"ERROR: Templates directory not found: {TEMPLATES_DIR}")
        print("Make sure you are running this script from the arcium project root.")
        sys.exit(1)

    copied = 0
    skipped = 0

    for template_file in TEMPLATES_DIR.rglob("*"):
        if template_file.name == ".gitkeep":
            continue
        if not template_file.suffix == ".md":
            continue
        # Compute relative path within templates/vault/
        rel_path = template_file.relative_to(TEMPLATES_DIR)
        dest_path = vault_path / rel_path

        if dest_path.exists():
            print(f"  SKIP (exists): {rel_path}")
            skipped += 1
            continue

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Read, replace placeholders, write
        content = template_file.read_text(encoding="utf-8")
        content = replace_date_placeholders(content)
        dest_path.write_text(content, encoding="utf-8")

        print(f"  CREATE: {rel_path}")
        copied += 1

    print(f"\nVault setup complete: {copied} files created, {skipped} skipped (already exist).")


def create_vault_structure(vault_path: Path) -> None:
    """Create all vault folders."""
    print(f"\nCreating vault at: {vault_path}")
    vault_path.mkdir(parents=True, exist_ok=True)

    for folder in VAULT_FOLDERS:
        folder_path = vault_path / folder
        folder_path.mkdir(parents=True, exist_ok=True)

    print("Vault folder structure created.")


def build_agents_md_content(vault_path: Path) -> str:
    """Build the content for AGENTS.md — the canonical AI briefing file."""
    return f"""# AI Agent Briefing — Arcium Project

This file is the canonical briefing for any AI coding assistant working in this repository.
It is recognized by multiple tools:
- **Claude Code**: reads `CLAUDE.md` (which redirects here) and `AGENTS.md`
- **Cursor**: reads `.cursorrules`
- **GitHub Copilot**: reads `.github/copilot-instructions.md`

---

## Project Overview

**Arcium** is a reusable agentic AI infrastructure library built in Python.

Stack: MCP file server + ReAct agents + skills system + Obsidian vault memory
Language: Python (Poetry for dependency management)
Phase: Active development

---

## Step 1 — Read these vault files first (in order)

1. `{vault_path}/00-index/INDEX.md` — vault structure and write rules
2. `{vault_path}/00-index/PROJECTS.md` — active project and folder
3. `{vault_path}/00-index/CONVERSATIONS.md` — last 2-3 session entries
4. `{vault_path}/02-projects/` — current project state and open tasks
5. `{vault_path}/00-index/GLOSSARY.md` — domain terms

---

## Step 2 — Confirm your orientation

After reading, briefly confirm:
- What project you're working on
- What was covered in the last session
- What the open threads are
- What you'll focus on this session

---

## Step 3 — Follow vault write rules

You may read any file in the vault freely. When writing:
- Create new notes in `05-conversations/`, `06-findings/`, or `08-scratch/`
- Append to index files in `00-index/` (never overwrite)
- Follow the schema in `00-index/SCHEMA.md` — all new files need valid frontmatter
- Never delete, rename, or move existing files
- Never write to `99-archive/`
- **CRITICAL: Only write `.md` files to the vault. Never write code files (`.py`, `.ts`,
  `.json`, `.yaml`, etc.) to the vault path. Use `projects__write_file` instead.**

---

## Step 4 — At session end

Run the session-close workflow:
`{vault_path}/03-agents/workflows/session-close.md`

---

## Project Structure

```
~/Documents/Programming Projects/arcium/     <- code lives here
{vault_path}/                                <- memory lives here
```

---

## Key facts

- MCP server: `arcium.mcp.server` — 12 tools across vault__* and projects__* namespaces
- WAT Pipeline: 5 specialist agents (Team Lead, Architect, Engineer, Critic, Comms)
- Skill files: `{vault_path}/04-skills/`
- Firm context: `{vault_path}/01-firm-context/`
"""


def generate_briefing_files(vault_path: Path) -> None:
    """Generate AGENTS.md and tool-specific variants from the same source."""
    agents_content = build_agents_md_content(vault_path)

    # 1. AGENTS.md — canonical, recognized by Claude Code and most AI tools
    agents_md_path = PROJECT_ROOT / "AGENTS.md"
    agents_md_path.write_text(agents_content, encoding="utf-8")
    print(f"  CREATE: AGENTS.md")

    # 2. CLAUDE.md — one-line redirect (Claude Code looks for this name)
    claude_md_path = PROJECT_ROOT / "CLAUDE.md"
    claude_md_path.write_text(
        "See AGENTS.md for project briefing and vault instructions.\n",
        encoding="utf-8"
    )
    print(f"  CREATE: CLAUDE.md (redirect to AGENTS.md)")

    # 3. .cursorrules — Cursor IDE reads this file
    cursorrules_path = PROJECT_ROOT / ".cursorrules"
    cursorrules_path.write_text(agents_content, encoding="utf-8")
    print(f"  CREATE: .cursorrules")

    # 4. .github/copilot-instructions.md — GitHub Copilot reads this
    copilot_dir = PROJECT_ROOT / ".github"
    copilot_dir.mkdir(exist_ok=True)
    copilot_path = copilot_dir / "copilot-instructions.md"
    copilot_path.write_text(agents_content, encoding="utf-8")
    print(f"  CREATE: .github/copilot-instructions.md")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set up the arcium-vault directory structure from templates."
    )
    parser.add_argument(
        "--vault-path",
        default=str(Path.home() / "Documents" / "arcium-vault"),
        help="Path where the vault should be created (default: ~/Documents/arcium-vault)",
    )
    args = parser.parse_args()

    vault_path = Path(args.vault_path).expanduser().resolve()

    print("=" * 60)
    print("Arcium Vault Setup")
    print("=" * 60)

    # Create vault structure
    create_vault_structure(vault_path)

    # Copy template files
    print("\nCopying template files...")
    copy_templates(vault_path)

    # Generate AI briefing files
    print("\nGenerating AI briefing files...")
    generate_briefing_files(vault_path)

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print(f"\nVault location: {vault_path}")
    print("\nNext steps:")
    print("  1. Edit vault/01-firm-context/CONSTRAINTS.md — add your organization's constraints")
    print("  2. Edit vault/01-firm-context/DOMAIN.md — describe your domain and tech stack")
    print("  3. Edit vault/01-firm-context/STAKEHOLDERS.md — add your stakeholders")
    print("  4. cp config.json.example config.json")
    print(f"     Update vault_path to: {vault_path}")
    print("  5. cp .mcp.json.example .mcp.json")
    print("  6. In Claude Code: claude mcp add arcium --command poetry -- run python -m arcium.mcp.server")
    print("\nFor full setup instructions, see README.md.")


if __name__ == "__main__":
    main()
