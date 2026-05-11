# AI Agent Briefing — Arcium Project

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

1. `/private/tmp/test-vault-scaffold/00-index/INDEX.md` — vault structure and write rules
2. `/private/tmp/test-vault-scaffold/00-index/CONVERSATIONS.md` — last 2-3 session entries
3. `/private/tmp/test-vault-scaffold/03-cohort-work/` — deliverables from completed cohort runs
4. `/private/tmp/test-vault-scaffold/00-index/SCHEMA.md` — note types, frontmatter rules, naming conventions

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
`/private/tmp/test-vault-scaffold/00-index/workflows/session-close.md`

---

## Project Structure

```
~/Documents/Programming Projects/arcium/     <- code lives here
/private/tmp/test-vault-scaffold/                                <- memory lives here
```

---

## Key facts

- MCP server: `arcium.mcp.server` — 12 tools across vault__* and projects__* namespaces
- CAST manifests: `/private/tmp/test-vault-scaffold/02-marketplace/` — agents, skills, tools, cohorts
- Marketplace registry: `/private/tmp/test-vault-scaffold/02-marketplace/_registry/index.json`
- Firm context: `/private/tmp/test-vault-scaffold/01-firm-context/`
- Cohort deliverables: `/private/tmp/test-vault-scaffold/03-cohort-work/<slug>/`
- Agent reasoning logs: `/private/tmp/test-vault-scaffold/04-findings/`
- Scratch work: `/private/tmp/test-vault-scaffold/06-scratch/cohort-<slug>/`
