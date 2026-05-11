---
type: schema
version: 1.2
updated: 2026-05-11
---

# Vault Schema

> All agents and humans must follow these conventions.
> Deviating from the schema breaks agent navigation and search.

---

## Frontmatter Standard

Every note in this vault must open with a YAML frontmatter block. Required fields depend on the note type.

### All notes (required)

```yaml
---
type: <note type — see types below>
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [tag1, tag2]
---
```

### Project notes (add these)

```yaml
project: <project-slug>
status: active | paused | complete | archived
owner: human | agent | both
```

### Agent-generated notes (add these)

```yaml
generated-by: <agent name>
session: <conversation summary title or date>
confidence: high | medium | low
```

### Finding / research notes (add these)

```yaml
source: <url, filename, or "agent research">
verified: true | false
```

### CAST artifact notes (agents, skills, tools, cohorts)

```yaml
id: <kebab-case-id>
version: <semver e.g. 1.0.0>
kind: agent | skill | tool | cohort
tier: firm | personal | community
```

---

## Note Types

| Type | Used for | Folder |
|---|---|---|
| `index` | Registry and navigation files | `00-index/` |
| `schema` | Conventions and rules | `00-index/` |
| `workflow` | Operator runbooks | `00-index/workflows/` |
| `firm-context` | Constraints, domain, stakeholders | `01-firm-context/` |
| `project` | Cohort run deliverables | `03-cohort-work/` |
| `conversation` | Session summary | `05-sessions/` |
| `finding` | Research result or discovery | `04-findings/` |
| `scratch` | Temporary working note | `06-scratch/` |
| `agent` | Agent persona definition | `02-marketplace/agents/` |
| `skill` | Injectable capability | `02-marketplace/skills/` |
| `tool` | MCP tool manifest | `02-marketplace/tools/` |
| `cohort` | Cohort manifest (graph + roles) | `02-marketplace/cohorts/` |

---

## Index Files in `00-index/`

| File | Purpose | Written by |
|---|---|---|
| `INDEX.md` | Vault entry point, folder map, health stats | Human + agents |
| `SCHEMA.md` | Conventions, note types, naming rules | Human |
| `CONVERSATIONS.md` | Log of Claude development sessions | Agents (session-close) |
| `COHORT-RUNS.md` | Log of WAT cohort execution runs | Vault-librarian (auto) |
| `COHORT-DECISIONS.md` | Per-run agent decision log | Vault-librarian (auto) |
| `workflows/session-close.md` | Session-end runbook | Human |

`CONVERSATIONS.md`, `COHORT-RUNS.md`, and `COHORT-DECISIONS.md` are separate concerns:
- **CONVERSATIONS.md** — Arcium development history: what was built, decided, or discovered in Claude Code sessions. Written manually at session-close.
- **COHORT-RUNS.md** — Cohort execution history: one row per `CohortCoordinator.run()` invocation with slug, outcome, cost, iterations, and timestamp. Written automatically by `_vault_librarian()` on every coordination exit.
- **COHORT-DECISIONS.md** — Decision-level detail: one structured entry per run recording agent verdicts, routing outcomes, and escalations. Written automatically by `_vault_librarian()` on every coordination exit.

---

## Naming Conventions

- **Files**: `kebab-case.md` always. No spaces, no capitals.
- **Project slugs**: short, lowercase, hyphenated. Example: `word-frequency`, `json-log-parser`
- **Dates**: always `YYYY-MM-DD` in frontmatter. Never ambiguous formats.
- **Tags**: lowercase, hyphenated. Prefer specific over generic.

---

## Folder Naming

Top-level folders use a two-digit prefix to enforce sort order.

```
03-cohort-work/
  json-log-parser/
    overview.md
    executive-summary.md
  word-frequency/
    overview.md
```

---

## Linking Rules

- Use Obsidian wiki links: `[[filename]]` or `[[filename|display text]]`
- Always link project notes back to their project overview
- Index files link forward; notes link back to their index
- Agents may create links; they must verify the target file exists before linking

---

## Agent Write Rules

Agents may:
- Create new notes in `05-sessions/`, `04-findings/`, `06-scratch/`
- Append to index files in `00-index/`
- Create project folders and notes in `03-cohort-work/`

Agents must not:
- Rename or delete existing files
- Modify `00-index/SCHEMA.md` without human approval
- Create new top-level folders
- Write to `99-archive/`
- Write code files (`.py`, `.ts`, `.json`, `.yaml`, etc.) to the vault — use `projects__write_file` instead
