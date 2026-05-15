"""
scripts/setup_vault.py

Generates a complete arcium-vault directory structure from the templates in templates/vault/.
Also generates AGENTS.md and tool-specific AI briefing files from a shared template.

Usage:
    python scripts/setup_vault.py
    python scripts/setup_vault.py --vault-path ~/Documents/my-custom-vault
    python scripts/setup_vault.py --vault-path /absolute/path/to/vault

The script:
    1. Creates all vault folders (new Phase 4 structure)
    2. Copies sanitized template files into the vault
    3. Writes .vault-config.yaml from .vault-config.yaml.example (if not present)
    4. Generates AGENTS.md in the project root (canonical AI briefing)
    5. Generates CLAUDE.md as a one-line redirect to AGENTS.md
    6. Generates .cursorrules for Cursor IDE
    7. Generates .github/copilot-instructions.md for GitHub Copilot
"""

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates" / "vault"

VAULT_FOLDERS = [
    "00-index/workflows",
    "01-firm-context",
    # Marketplace — nested structure (Phase 5a)
    "02-marketplace/cohorts",
    "02-marketplace/agents/leads",
    "02-marketplace/agents/architects",
    "02-marketplace/agents/developers",
    "02-marketplace/agents/reviewers",
    "02-marketplace/agents/communicators",
    "02-marketplace/agents/specialists",
    "02-marketplace/skills",
    "02-marketplace/tools/vault",
    "02-marketplace/tools/code",
    "02-marketplace/_registry",
    "03-cohort-work",
    "04-findings",
    "05-sessions",
    "06-scratch",
    "07-sync-outbox",
    "99-archive",
]

# Leaf directories that need .gitkeep so Git preserves them when empty
_GITKEEP_DIRS = [
    "02-marketplace/cohorts",
    "02-marketplace/agents/leads",
    "02-marketplace/agents/architects",
    "02-marketplace/agents/developers",
    "02-marketplace/agents/reviewers",
    "02-marketplace/agents/communicators",
    "02-marketplace/agents/specialists",
    "02-marketplace/skills",
    "02-marketplace/tools/vault",
    "02-marketplace/tools/code",
    "03-cohort-work",
    "04-findings",
    "05-sessions",
    "06-scratch",
    "07-sync-outbox",
    "99-archive",
]

# File extensions copied verbatim (after date-placeholder replacement for text files)
_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt", ""}

TODAY = date.today().isoformat()


def replace_date_placeholders(content: str) -> str:
    return content.replace("YYYY-MM-DD", TODAY)


def copy_templates(vault_path: Path) -> None:
    """Copy all template files into the vault, replacing date placeholders in text files."""
    if not TEMPLATES_DIR.exists():
        print(f"ERROR: Templates directory not found: {TEMPLATES_DIR}")
        print("Make sure you are running this script from the arcium project root.")
        sys.exit(1)

    copied = 0
    skipped = 0

    for template_file in TEMPLATES_DIR.rglob("*"):
        if not template_file.is_file():
            continue
        if template_file.name == ".gitkeep":
            continue

        rel_path = template_file.relative_to(TEMPLATES_DIR)
        dest_path = vault_path / rel_path

        if dest_path.exists():
            print(f"  SKIP (exists): {rel_path}")
            skipped += 1
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if template_file.suffix in _TEXT_SUFFIXES:
            content = template_file.read_text(encoding="utf-8")
            content = replace_date_placeholders(content)
            dest_path.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(template_file, dest_path)

        print(f"  CREATE: {rel_path}")
        copied += 1

    print(f"\nTemplate copy complete: {copied} files created, {skipped} skipped (already exist).")


def write_vault_config(vault_path: Path) -> None:
    """Write .vault-config.yaml from the example template if not already present."""
    dest = vault_path / ".vault-config.yaml"
    if dest.exists():
        print("  SKIP (exists): .vault-config.yaml")
        return

    example = TEMPLATES_DIR / ".vault-config.yaml.example"
    if not example.exists():
        print("  WARN: .vault-config.yaml.example not found in templates — skipping")
        return

    shutil.copy2(example, dest)
    print("  CREATE: .vault-config.yaml (copied from .vault-config.yaml.example)")
    print("  NOTE:   Edit .vault-config.yaml and set your vault_id before first use.")


def create_vault_structure(vault_path: Path) -> None:
    """Create all vault folders and .gitkeep files for empty leaf directories."""
    print(f"\nCreating vault at: {vault_path}")
    vault_path.mkdir(parents=True, exist_ok=True)

    for folder in VAULT_FOLDERS:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)

    for folder in _GITKEEP_DIRS:
        gitkeep = vault_path / folder / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

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

**Arcium** is an enterprise agentic coordination platform built in Python.

Define agent teams as composable CAST manifests (Cohort, Agent, Skill, Tool), coordinate them
autonomously through a manifest-driven graph executor, and manage persistent knowledge through
a federated vault architecture.

Stack: MCP file server + CohortCoordinator + CAST manifests + Obsidian vault memory
Language: Python (Poetry for dependency management)
Phase: Active development

---

## Step 1 — Read these vault files first (in order)

1. `{vault_path}/00-index/INDEX.md` — vault structure and write rules
2. `{vault_path}/00-index/CONVERSATIONS.md` — last 2-3 session entries
3. `{vault_path}/03-cohort-work/` — deliverables from completed cohort runs
4. `{vault_path}/00-index/SCHEMA.md` — note types, frontmatter rules, naming conventions

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
- Create new notes in `05-sessions/`, `04-findings/`, or `06-scratch/`
- Append to index files in `00-index/` (never overwrite)
- Follow the schema in `00-index/SCHEMA.md` — all new files need valid frontmatter
- Never delete, rename, or move existing files
- Never write to `99-archive/`
- **CRITICAL: Only write `.md` files to the vault. Never write code files (`.py`, `.ts`,
  `.json`, `.yaml`, etc.) to the vault path. Use `projects__write_file` instead.**

---

## Step 4 — At session end

Run the session-close workflow:
`{vault_path}/00-index/workflows/session-close.md`

---

## Project Structure

```
~/Documents/Programming Projects/arcium/     <- code lives here
{vault_path}/                                <- memory lives here
```

---

## Key facts

- MCP server: `arcium.mcp.server` — 12 tools across vault__* and projects__* namespaces
- CAST manifests: `{vault_path}/02-marketplace/` — agents, skills, tools, cohorts
- Marketplace registry: `{vault_path}/02-marketplace/_registry/index.json`
- Firm context: `{vault_path}/01-firm-context/`
- Cohort deliverables: `{vault_path}/03-cohort-work/<slug>/`
- Agent reasoning logs: `{vault_path}/04-findings/`
- Scratch work: `{vault_path}/06-scratch/cohort-<slug>/`
"""


def generate_briefing_files(vault_path: Path) -> None:
    """Generate AGENTS.md and tool-specific variants from the same source."""
    agents_content = build_agents_md_content(vault_path)

    # 1. AGENTS.md — canonical, recognized by Claude Code and most AI tools
    (PROJECT_ROOT / "AGENTS.md").write_text(agents_content, encoding="utf-8")
    print("  CREATE: AGENTS.md")

    # 2. CLAUDE.md — one-line redirect (Claude Code looks for this name)
    (PROJECT_ROOT / "CLAUDE.md").write_text(
        "See AGENTS.md for project briefing and vault instructions.\n",
        encoding="utf-8",
    )
    print("  CREATE: CLAUDE.md (redirect to AGENTS.md)")

    # 3. .cursorrules — Cursor IDE reads this file
    (PROJECT_ROOT / ".cursorrules").write_text(agents_content, encoding="utf-8")
    print("  CREATE: .cursorrules")

    # 4. .github/copilot-instructions.md — GitHub Copilot reads this
    copilot_dir = PROJECT_ROOT / ".github"
    copilot_dir.mkdir(exist_ok=True)
    (copilot_dir / "copilot-instructions.md").write_text(agents_content, encoding="utf-8")
    print("  CREATE: .github/copilot-instructions.md")


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

    create_vault_structure(vault_path)

    print("\nCopying template files...")
    copy_templates(vault_path)

    print("\nWriting vault identity config...")
    write_vault_config(vault_path)

    print("\nGenerating AI briefing files...")
    generate_briefing_files(vault_path)

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print(f"\nVault location: {vault_path}")
    print("\nNext steps:")
    print(f"  1. Edit {vault_path}/.vault-config.yaml — set your vault_id")
    print("  2. Edit vault/01-firm-context/CONSTRAINTS.md — add your organization's constraints")
    print("  3. Edit vault/01-firm-context/DOMAIN.md — describe your domain and tech stack")
    print("  4. Edit vault/01-firm-context/STAKEHOLDERS.md — add your stakeholders")
    print("  5. cp arcium.config.example.yaml arcium.config.yaml")
    print(f"     Update vault.path to: {vault_path}")
    print("  6. cp .mcp.json.example .mcp.json  # set poetry path")
    print("\nFor full setup instructions, see README.md.")


if __name__ == "__main__":
    main()
