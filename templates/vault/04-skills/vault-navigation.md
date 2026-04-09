---
type: skill
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [skill, vault, navigation, agents]
---

# Skill: Vault Navigation

Inject this into any agent that needs to read from or write to the Obsidian vault.

---

## Your job when starting a session

1. Read `00-index/INDEX.md` — understand the folder map and rules
2. Read `00-index/PROJECTS.md` — find the right project folder for this task
3. Read `00-index/GLOSSARY.md` if domain terms are unclear
4. Check `05-conversations/` for the most recent session summary

## Your job when ending a session

1. Append a summary entry to `00-index/CONVERSATIONS.md`
2. Create a full summary note in `05-conversations/YYYY-MM-DD-title.md`
3. Update the `last-activity` field in `00-index/PROJECTS.md` for any touched project
4. File any findings to `06-findings/`

## File creation rules

- Always include valid frontmatter (see `00-index/SCHEMA.md`)
- Use `kebab-case.md` filenames
- Never delete or rename existing files
- Write to `08-scratch/` if unsure where something belongs
- **Only write `.md` files to the vault** — never write code files (`.py`, `.json`, `.yaml`, etc.)
