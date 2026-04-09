---
type: agent
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [workflow, session-close, vault-maintenance]
---

# Workflow: Session Close

Run this workflow at the end of every Claude Code session to persist session state to the vault.

---

## Steps

### 1. Write session summary to `05-conversations/`

Create a new file: `05-conversations/YYYY-MM-DD-<session-title>.md`

```yaml
---
type: conversation
created: YYYY-MM-DD
updated: YYYY-MM-DD
project: <project-slug>
generated-by: claude-code
session: <session title>
confidence: high
tags: [session-summary, <project-slug>]
---
```

Body should include:
- What was built or decided
- Key decisions made and rationale
- Problems encountered and how resolved
- Open threads for the next session

### 2. Append to `00-index/CONVERSATIONS.md`

Add entry:
```
### YYYY-MM-DD — <session title>
- **Project**: <project-slug>
- **Agent**: claude-code
- **Key outcomes**: one-line summary
- **Open threads**: unresolved items for next session
- **Full summary**: [[05-conversations/YYYY-MM-DD-session-title]]
```

### 3. Update project activity

In `00-index/PROJECTS.md`, update `last-activity` for any touched project.

### 4. Update vault health

In `00-index/INDEX.md`, update `Last agent session` date.

### 5. File any findings

If research or discoveries were made, create notes in `06-findings/` with proper frontmatter.
