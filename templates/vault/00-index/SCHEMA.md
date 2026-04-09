---
type: schema
version: 1.1
updated: YYYY-MM-DD
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

---

## Note Types

| Type | Used for | Folder |
|---|---|---|
| `index` | Registry and navigation files | `00-index/` |
| `schema` | Conventions and rules | `00-index/` |
| `registry` | Lists of agents, skills, projects | `00-index/` |
| `firm-context` | Constraints, domain, stakeholders | `01-firm-context/` |
| `project` | Project overview notes | `02-projects/` |
| `task` | Specific task within a project | `02-projects/<slug>/` |
| `agent` | Agent definition and config | `03-agents/` |
| `skill` | Reusable prompt/skill file | `04-skills/` |
| `conversation` | Session summary | `05-conversations/` |
| `finding` | Research result or discovery | `06-findings/` |
| `resource` | External reference material | `07-resources/` |
| `scratch` | Temporary working note | `08-scratch/` |

---

## Naming Conventions

- **Files**: `kebab-case.md` always. No spaces, no capitals.
- **Project slugs**: short, lowercase, hyphenated. Example: `my-poc`, `client-dashboard`
- **Dates**: always `YYYY-MM-DD` in frontmatter. Never ambiguous formats.
- **Tags**: lowercase, hyphenated. Prefer specific over generic.

---

## Agent Write Rules

Agents may:
- Create new notes in `05-conversations/`, `06-findings/`, `08-scratch/`
- Append to index files in `00-index/`
- Create task notes in existing project folders

Agents must not:
- Rename or delete existing files
- Modify `00-index/SCHEMA.md` without human approval
- Create new top-level folders
- Write to `99-archive/`
- **Write code files** (`.py`, `.ts`, `.json`, `.yaml`, etc.) to the vault — use `projects__write_file` instead
