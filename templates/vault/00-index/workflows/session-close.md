---
type: workflow
created: 2026-03-27
updated: 2026-05-11
tags: [workflow, session, memory, vault-librarian]
---

# Workflow: Session Close

Run this workflow at the end of every Claude session — in claude.ai or Claude Code — to persist what was learned into the vault so the next session can pick up without losing context.

---

## When to run

- End of any productive claude.ai conversation
- End of any Claude Code development session
- Any time a significant decision, discovery, or design was reached

---

## Steps

### Step 1 — Generate the session summary

Paste this prompt into the conversation before closing it:

```
Please write a session summary for my vault using this structure:

---
type: conversation
created: <today's date YYYY-MM-DD>
updated: <today's date YYYY-MM-DD>
project: <project slug>
tags: [<relevant tags>]
generated-by: claude
session: <short descriptive title>
---

# <Session Title>

## What we covered
<3-5 bullet points of the main topics discussed>

## Key decisions
<Any architectural, design, or strategic decisions made — with the reasoning>

## What was built or created
<Files created, code written, structures designed>

## Open threads
<Unresolved questions or next steps that the next session should pick up>

## How to pick up from here
<A short paragraph a future Claude instance can read to get up to speed instantly>
```

---

### Step 2 — Save the summary to the vault

Save the output as a new file:
```
05-sessions/YYYY-MM-DD-<session-title>.md
```

Example:
```
05-sessions/2026-05-11-vault-restructure-phase-4.md
```

---

### Step 3 — Append to the conversation index

Open `00-index/CONVERSATIONS.md` and append this entry under **Sessions**:

```markdown
### YYYY-MM-DD — <Session Title>
- **Project**: <project slug>
- **Agent**: direct chat | claude-code | <agent name>
- **Key outcomes**: <one line summary>
- **Open threads**: <one line on what's unresolved>
- **Full summary**: [[05-sessions/YYYY-MM-DD-session-title]]
```

---

### Step 4 — Update the project file

Open `03-cohort-work/<project-slug>/overview.md` and:
- Check off any completed tasks
- Update the `updated` frontmatter field to today

---

### Step 5 — Update INDEX.md vault health

Open `00-index/INDEX.md` and update:
```
- Last agent session: <today's date>
```

---

## Automating this workflow (future)

Once the MCP file server is running, this entire workflow can be triggered by the `vault-librarian` agent automatically at session end — no manual copy-paste required. The agent reads the conversation context, generates the summary, and writes all three files in one shot.

Until then, run it manually using the prompt in Step 1.
