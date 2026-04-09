---
type: index
updated: YYYY-MM-DD
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
| `01-firm-context/` | Constraints, domain, stakeholders, POC templates | Human |
| `02-projects/` | One subfolder per active or archived project | Human + agents |
| `03-agents/` | Agent definitions, prompts, configs | Human |
| `04-skills/` | Reusable skill files injected into agent prompts | Human |
| `05-conversations/` | Summaries of key Claude sessions | Agent (auto-logged) |
| `06-findings/` | Research notes, discoveries, experiments | Agents |
| `07-resources/` | Reference material, links, docs, papers | Human |
| `08-scratch/` | Temporary working notes, drafts, experiments | Human + agents |
| `99-archive/` | Completed projects and deprecated content | Human |

---

## Navigation Rules for Agents

1. **Always read `00-index/INDEX.md` first** to orient before searching or writing.
2. **Check `00-index/PROJECTS.md`** to find the right project folder before filing anything.
3. **Read `00-index/SCHEMA.md`** before creating any new note — frontmatter must conform.
4. **Append to `00-index/CONVERSATIONS.md`** at the end of every session with a summary.
5. **Never write to `99-archive/`** — only humans archive content.
6. **Use `08-scratch/`** for intermediate work; move to permanent folders when complete.

---

## Vault Health

- Total projects: 0
- Last agent session: YYYY-MM-DD
- Last human review: YYYY-MM-DD
- Schema version: 1.1
