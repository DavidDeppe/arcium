# AI Agent Briefing — Arcium Project

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
Vault: ~/Documents/arcium-vault (or ARCIUM_VAULT_PATH env var)

---

## First Actions Every Session

1. Read `AGENTS.md` (this file)
2. Read `~/Documents/arcium-vault/00-index/INDEX.md`
3. Read the two most recent entries in `~/Documents/arcium-vault/00-index/CONVERSATIONS.md`

---

## Step 1 — Read these vault files first (in order)

1. `/Users/daviddeppe/Documents/arcium-vault/00-index/INDEX.md` — vault structure and write rules
2. `/Users/daviddeppe/Documents/arcium-vault/00-index/PROJECTS.md` — active project and folder
3. `/Users/daviddeppe/Documents/arcium-vault/00-index/CONVERSATIONS.md` — last 2-3 session entries
4. `/Users/daviddeppe/Documents/arcium-vault/02-projects/` — current project state and open tasks
5. `/Users/daviddeppe/Documents/arcium-vault/00-index/GLOSSARY.md` — domain terms

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
`/Users/daviddeppe/Documents/arcium-vault/03-agents/workflows/session-close.md`

---

## Project Structure

```
~/Documents/Programming Projects/arcium/     <- code lives here
/Users/daviddeppe/Documents/arcium-vault/                                <- memory lives here
```

---

## Key facts

- MCP server: `arcium.mcp.server` — 12 tools across vault__* and projects__* namespaces
- WAT Pipeline: 5 specialist agents (Team Lead, Architect, Engineer, Critic, Comms)
- Skill files: `/Users/daviddeppe/Documents/arcium-vault/04-skills/`
- Firm context: `/Users/daviddeppe/Documents/arcium-vault/01-firm-context/`

## WAT Pipeline Behaviors

**Polish loop** — When the Critic returns `PASS_WITH_CONDITIONS` with only medium/low issues,
the pipeline runs one targeted polish pass (outside the main iteration counter) before
Communications. The Engineer receives a scoped work order listing only the flagged items;
the Critic then spot-checks only those items. STATUS.md shows
`Critic passed with conditions — Engineer polishing before handoff` during this phase.

**Feedback iteration** — Resume an existing PoC without re-running Discovery and Architecture:
```bash
poetry run python -m arcium.workflow.poc_pipeline \
    --slug "word-frequency" \
    --feedback "Add CSV export and support stdin in addition to file path"
```
This reads the existing Architect spec from vault, writes a feedback brief to
`08-scratch/poc-pipeline-<slug>/05-feedback-brief.md`, and routes directly to the Engineer.
Requires that the full pipeline has completed through the Architecture phase for that slug.
