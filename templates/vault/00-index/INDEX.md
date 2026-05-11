---
type: index
updated: 2026-05-08
maintainer: human + agents
---

# Vault Index

> This file is the entry point for all agents and humans navigating this vault.
> Read this first. Update the `updated` field and relevant section whenever structure changes.

---

## Purpose

This vault is a shared knowledge system between a human operator and a set of AI agents running in Claude Code. It stores findings, project context, agent definitions, conversation summaries, and reusable skills — persisted across sessions so nothing is lost between conversations.

---

## Folder Map

| Folder | Purpose | Owner |
|---|---|---|
| `00-index/` | Vault schema, registries, master indexes | Human + agents |
| `01-firm-context/` | Constraints, domain, stakeholders, PoC templates | Human |
| `02-marketplace/` | CAST artifacts: agents, skills, tools, cohorts, registry | Human + agents |
| `03-cohort-work/` | One subfolder per active or completed cohort run | Human + agents |
| `04-findings/` | Research notes, discoveries, experiments, reasoning logs | Agents |
| `05-sessions/` | Summaries of key Claude sessions | Agent (auto-logged) |
| `06-scratch/` | Temporary working notes, cohort scratch work | Human + agents |
| `07-sync-outbox/` | Staged artifacts pending push to parent vault | Human + agents |
| `99-archive/` | Completed projects and deprecated content | Human |

---

## Navigation Rules for Agents

1. **Always read `00-index/INDEX.md` first** to orient before searching or writing.
2. **Check `00-index/PROJECTS.md`** to find the right project folder before filing anything.
3. **Read `00-index/SCHEMA.md`** before creating any new note — frontmatter must conform.
4. **Append to `00-index/CONVERSATIONS.md`** at the end of every session with a summary.
5. **Never write to `99-archive/`** — only humans archive content.
6. **Use `06-scratch/`** for intermediate work; move to permanent folders when complete.

---

## Vault Health

- Total projects: 1 (arcium)
- Last agent session: 2026-05-11 (Phase 4 complete — vault restructure, 02-marketplace migration, registry builder, VaultSyncAgent, all runtime paths updated; 00-firm/ deleted)
- Last human review: 2026-03-31
- Schema version: 1.1
