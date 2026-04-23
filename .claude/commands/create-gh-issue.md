Create one or more GitHub issues on the current repo from a `tasks/` file path or from a plain description typed by the user.

**Rules:**
- Every issue must have a single, focused responsibility (one thing to change or decide).
- Issues must be linked: list blocking issues in the body of each dependent issue (`Depends on #N`).
- Create blocking issues first so their numbers are available when writing dependents.
- Never create an issue that duplicates an already-open one — check with `rtk gh issue list` first.

---

## Step 1 — Identify the source

If the user passed a file path (e.g. `tasks/2026-04-23-web-ui-ifu-vercel.md`):
- Read the file with the Read tool.
- Use "Files to modify" and "Verification steps" as the raw material.

If the user passed a free-text description:
- Use it directly as the raw material.

If the source is ambiguous, ask before proceeding.

---

## Step 2 — Check existing issues

Run:
```bash
rtk gh issue list --state open --limit 50
```

Note any issues that overlap with the planned work. Skip duplicates.

---

## Step 3 — Decompose into issues

From the raw material, derive a flat list of small issues. Apply these decomposition rules:

- **One file changed = one candidate issue.** If a single file change has two distinct concerns, split further.
- **New files** (scripts, configs, workflows) each get their own issue.
- **Verification / QA** tasks that span multiple changes can be grouped into one "validation" issue at the end.
- **Refactors that are prerequisites** for other issues must be separate issues placed before their dependents.

For each issue, note:
- `title` — imperative sentence, ≤ 72 chars (e.g. "Refactor yuh_csv_ifu.py to expose process() function")
- `body` — 3–6 bullet points describing exactly what changes; end with a `Depends on` line if applicable
- `labels` — pick from: `enhancement`, `bug`, `refactor`, `ci`, `docs`, `infra` (use only labels that already exist or are clearly standard)
- `depends_on` — list of titles of issues this one requires to be merged first (resolved to numbers after creation)

Show the full planned list to the user and ask for confirmation before creating anything. If the user requests changes, revise and ask again.

---

## Step 4 — Create issues in dependency order

Sort issues: issues with no dependencies first, then issues that depend on already-created ones.

For each issue, run:
```bash
rtk gh issue create \
  --title "<title>" \
  --body "$(cat <<'EOF'
<body>

Depends on: #N, #M   ← omit line if no dependencies
EOF
)"
```

After each creation, record the issue number from the output URL (the trailing integer).

---

## Step 5 — Report

Print a table:

| # | Title | Depends on |
|---|-------|-----------|
| N | ...   | #X, #Y    |

End with the total count and the repo URL for the issues list.
