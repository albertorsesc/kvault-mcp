# Rules

Rules are atomic, durable pieces of guidance that steer an assistant's behavior across sessions. They are captured from conversation, reviewed, approved, and injected into the assistant's instructions. kvault-mcp provides the lifecycle; the assistant decides what to capture and when to apply.

## Lifecycle

```
proposed → active → retired
   ↑          ↓
   └──────────┘  (superseded / invalidated)
```

Four directories under `<vault>/memory/rules/`:

| Directory | Meaning |
|---|---|
| `proposed/` | Captured from conversation; awaiting human review. Not injected. |
| `active/` | Approved. Injected into assistant instructions. |
| `retired/` | Previously active or proposed; no longer applicable. Kept for history. |

There is no `rejected/` — a rule that never made it past proposed is either deleted or moved to retired with a reason.

## Rule file format

```markdown
---
id: feedback_integration_tests_use_real_db
type: feedback                     # user | feedback | project | reference
status: active                     # proposed | active | retired
captured_from: 2026-01-15 session
author: user
created: 2026-01-15
last_updated: 2026-01-20
supersedes: []                     # list of rule IDs this replaces
superseded_by: null                # null unless retired-by-replacement
---

# Integration tests must hit a real database

Don't mock the database in integration tests. Spin up an ephemeral Postgres
container and run the real schema.

**Why:** Mock/prod divergence masked a broken migration in the Q4 release. Mocked
tests passed; the migration failed in staging.

**How to apply:** Whenever a test file is named `test_integration_*.py` or sits
under `tests/integration/`, refuse to introduce or accept a database mock. Use
the `db_real` fixture from `conftest.py`.
```

The `type` field mirrors the auto-memory typology (user / feedback / project / reference), which keeps capture semantics consistent across kvault-mcp and the assistant's memory.

## Capture

A plugin (or the assistant itself via an MCP tool) writes a proposed rule to `memory/rules/proposed/<id>.md`. The kernel does not write rules — it only provides the path and validates the frontmatter against `rules-schema.json`.

Typical capture flow:

1. User gives durable guidance in conversation (e.g., "don't recommend paid tools").
2. Assistant invokes `kvault.rule.propose` with a drafted rule body.
3. Kernel validates frontmatter, writes to `proposed/<id>.md`, emits `vault.rule.proposed`.
4. Assistant surfaces the proposed rule to the user for review.

## Approval

Approval is a human action. There is no auto-approval path.

1. Human reviews `memory/rules/proposed/<id>.md` (in editor or via assistant summary).
2. Assistant invokes `kvault.rule.approve id=<id>` after explicit user confirmation.
3. Kernel moves the file to `active/<id>.md`, updates frontmatter (`status: active`, `last_updated`), emits `vault.rule.activated`.
4. The injection plugin (see below) picks up the event and re-injects the active set.

## Injection

Active rules are injected into the assistant's instruction file (`CLAUDE.md`, `AGENT.md`, or whatever the active harness uses). Injection is scoped by HTML comment markers:

```markdown
<!-- kvault:rules:start -->
<!-- Rendered by kvault-mcp. Do not edit between these markers by hand. -->

## Rules (active)

- **Open-source only by default** — Default to FOSS tools... [feedback_open_source_only]
- **Terse responses** — Cut preamble... [feedback_terse_responses]

<!-- kvault:rules:end -->
```

The injection plugin:
- Reads all files in `memory/rules/active/`.
- Renders them in a configurable format (bullet / full body / grouped by type).
- Replaces the content between markers atomically.
- Never touches content outside the markers.

If markers are missing, the injection plugin appends them to the configured instruction file on first run. If the file does not exist, injection is a no-op and a warning is logged.

## Retirement

A rule retires when:
- **Superseded** by a newer rule — old rule's `superseded_by` points to the new one's ID.
- **Invalidated** — explicit retirement because the guidance no longer applies.
- **Contradicted** — another active rule conflicts; human resolves which stays.

Retirement moves the file to `retired/<id>.md`, updates `status: retired`, and emits `vault.rule.retired`. The injection plugin re-renders without the retired rule.

Retired rules are never deleted by the kernel. They are history. A human can prune `retired/` manually if desired.

## Conflicts

The kernel does not detect rule conflicts. A future `audit-rule-conflicts` plugin can surface them as findings — e.g., two active rules with contradictory `How to apply` lines. The kernel's job is the lifecycle, not semantic analysis.

## Why the kernel doesn't own rule content

Rules are domain-specific. An assistant focused on writing might want rules about tone; one focused on ops might want rules about change management. The kernel provides the storage, lifecycle, events, and injection slots. Everything else — what types exist, how they render, when to propose — is plugin policy.

## Relationship to auto-memory

If the assistant has its own auto-memory system (e.g., Claude Code's `MEMORY.md`), kvault-mcp rules are the **promotion target** for memory entries that have graduated from "remember this" to "always apply this." Not every memory becomes a rule; rules are the subset the user has explicitly endorsed as durable behavioral guidance.
