---
type: workflow
created: 2026-03-27
updated: 2026-05-11
tags: [workflow, session, memory, vault-librarian]
---

# Workflow: Session Close

Run at the end of every session — in claude.ai or Claude Code — to persist what was learned so the next session picks up without losing context.

**Before starting: Determine which environment you are in:**

- **Claude Code** — MCP tools are available. Steps marked `[Claude Code]` use `vault__write_file` and `vault__read_file` directly.
- **claude.ai** — No MCP access. Steps marked `[claude.ai]` require manual file creation by the user.

---

## Step 1 — Generate the session summary

_Same for both environments._

Ask Claude to generate a session summary using this prompt:

```
Generate a session summary for the vault. Use this exact frontmatter format:

---
type: session
created: YYYY-MM-DD
updated: YYYY-MM-DD
project: <primary project slug, or "arcium-platform" if this was a platform design session>
tags: [<3-5 lowercase kebab-case tags describing what was discussed or built>]
generated-by: claude
session: <10-40 char kebab-case title summarizing the main work, e.g. "phase-4-vault-restructure">
---

Then write a concise body (150-300 words) covering:
- What was the goal of this session?
- What decisions were made or finalized?
- What was built, changed, or fixed?
- What is the next action or open question?

Do not include conversation transcripts. Facts and decisions only.
```

---

## Step 2 — Save the session file

Filename convention: `YYYY-MM-DD-<session-title>.md` where `<session-title>` matches the `session:` frontmatter field exactly (already kebab-case, max 40 chars).

Example: `2026-05-11-phase-4-vault-restructure.md`

**[Claude Code]** Write directly to vault:
```
vault__write_file("05-sessions/YYYY-MM-DD-<session-title>.md", <generated content>)
```

**[claude.ai]** Copy the generated content. In your file system, create:
```
~/Documents/arcium-vault/05-sessions/YYYY-MM-DD-<session-title>.md
```
Paste and save. **Do not skip this step — if the file is not saved, the session context is permanently lost.**

---

## Step 3 — Append to CONVERSATIONS.md

Add one line to the session log in `00-index/CONVERSATIONS.md`. The file has a table at the top. Append a new row at the bottom of the table (before any trailing content):

```markdown
| YYYY-MM-DD | <session-title> | <one sentence: what was the primary outcome> |
```

Example:
```markdown
| 2026-05-11 | phase-4-vault-restructure | Migrated all CAST artifacts to 02-marketplace/, built registry builder and Vault Sync Agent |
```

**[Claude Code]** Use `vault__read_file("00-index/CONVERSATIONS.md")` to read current content, append the row, then `vault__write_file` to save.

**[claude.ai]** Open `~/Documents/arcium-vault/00-index/CONVERSATIONS.md` in a text editor. Append the row to the bottom of the table. Save.

---

## Step 4 — Verify audit logs (cohort sessions only)

_Skip this step if no `arcium.workflow.cohort_coordinator` run occurred during this session._

If one or more cohort runs occurred, verify both audit logs were written:

**[Claude Code]**
```
vault__read_file("00-index/COHORT-RUNS.md")
vault__read_file("00-index/COHORT-DECISIONS.md")
```
Confirm the most recent run appears in both files. If a run is missing, the `_vault_librarian()` call may have failed — check the coordinator output for errors.

**[claude.ai]** Open both files and confirm the latest run appears:

- `~/Documents/arcium-vault/00-index/COHORT-RUNS.md` — one row per run
- `~/Documents/arcium-vault/00-index/COHORT-DECISIONS.md` — one entry per run with per-iteration decisions

If either is missing an expected entry, the run record was lost. Note this in the session summary file under "open questions."

---

## Step 5 — Update project overview (conditional)

_Skip this step if no active cohort project was worked on, or if the project has no `03-cohort-work/<slug>/overview.md` file._

If a cohort project was advanced during this session and `03-cohort-work/<slug>/overview.md` exists, append a one-line status update:

```markdown
**YYYY-MM-DD:** <what changed — one sentence>
```

**[Claude Code]** Read the file first, then append.

**[claude.ai]** Open the file and append manually.

If the file does not exist, skip without creating it — overview files are created by the Communications Specialist during cohort execution, not manually.

---

## What gets written automatically (no action needed)

When `CohortCoordinator` runs, `_vault_librarian()` automatically writes:

- `00-index/COHORT-RUNS.md` — one row per completed run
- `00-index/COHORT-DECISIONS.md` — full per-iteration decision log

These do not need to be written manually. Step 4 above only verifies they were written.

---

## Checklist

- [ ] Session file saved to `05-sessions/`
- [ ] Row appended to `00-index/CONVERSATIONS.md`
- [ ] Audit logs verified (if cohort session)
- [ ] Project overview updated (if applicable)
