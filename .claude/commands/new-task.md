Create a new task planning file under `tasks/`. Do NOT write any code — this is planning only.

**Never assume or guess.** If any detail is unclear or missing, ask the user before proceeding. It is better to ask too many questions than to write a task file that misrepresents the intent.

Steps:
1. Ask the user what the task is about. Do not infer or guess the title, scope, or approach — wait for explicit answers. Ask follow-up questions until you have enough detail to write a complete, accurate spec.
2. Confirm the task title with the user before deriving the slug.
3. Derive a short kebab-case slug from the confirmed title (e.g. `fix-dividend-rounding`).
4. Name the file `tasks/$CURRENT_DATE_$SLUG.md` where `$CURRENT_DATE` is today in `YYYY-MM-DD` format.
5. Write the file using this structure:

```markdown
# Task: <Title>

Created: <YYYY-MM-DD>

## Problem

<What is broken or missing, and why it matters.>

## Proposed solution

<High-level approach. No code. Describe the logic, data flow, or algorithm in plain language.>

## Files to modify

- [ ] `<path/to/file>` — <what changes and why>

## Verification steps

- [ ] <How to confirm the change is correct once implemented.>
```

6. Before creating the file, show the user the planned content and ask for confirmation. If anything is wrong or incomplete, revise and ask again.
7. Do not open, edit, or run any source files.
8. Report the path of the created task file and summarise its content in 2–3 sentences.
