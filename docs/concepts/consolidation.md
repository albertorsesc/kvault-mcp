# Consolidation

Consolidation is the process of turning raw episodic memory — every tool invocation, every conversational fragment — into durable, referenceable knowledge. It is how the vault grows from use without human bookkeeping on every turn.

## The flow

```
episodic events  ──►  consolidation plugin  ──►  proposals  ──►  human review  ──►  active state
(run-log.jsonl)                                (proposals.jsonl)                   (notes, rules, manifests)
```

Four stages:

1. **Capture** — kernel writes every tool invocation to `memory/episodic/run-log.jsonl`. Plugins may write domain-specific events elsewhere under `memory/episodic/`.
2. **Detect** — a consolidation plugin scans episodic data for patterns worth promoting (e.g., "user gave the same correction 3 times" → candidate rule).
3. **Propose** — the plugin writes a proposal line to `memory/semantic/proposals.jsonl`. No vault content is modified.
4. **Review** — a human reviews proposals and approves, rejects, or edits. Approval triggers a follow-up action (create rule, create note, update hub).

Consolidation is always opt-in and always advisory. The kernel does not consolidate. The kernel provides the event stream and the proposal sink; plugins provide the detection logic.

## Proposal format

```json
{
  "proposal_id": "prop-2026-04-22-001",
  "proposed_at": "2026-04-22T14:30:00Z",
  "proposer": "consolidation-rules",
  "category": "rule_candidate",
  "evidence": [
    {"ref": "run-log:2026-04-15:042", "note": "User said 'don't mock the DB' during test review"},
    {"ref": "run-log:2026-04-18:017", "note": "User said 'use real DB' in integration test PR"}
  ],
  "suggestion": {
    "type": "rule",
    "title": "Integration tests must hit a real database",
    "body": "..."
  },
  "status": "awaiting_review"
}
```

Every proposal carries its evidence. A human reviewing it can trace back to the exact episodic events that triggered the detection. No proposal is ever conjured from nothing.

## Detection strategies

Different consolidation plugins use different strategies. Examples:

- **Frequency** — "same phrase appeared in user messages N times" → rule candidate.
- **Correction** — "user said 'don't X' → reframed behavior persisted" → rule candidate.
- **Pattern clustering** — "three incidents with similar root cause" → incident pattern candidate.
- **Cross-topic signal** — "three notes across different topics reference unnamed concept" → framework candidate.

The kernel does not prescribe strategies. A plugin ships with its detection logic and its proposal taxonomy.

## Review workflow

A reviewer (human, via MCP tool) reads `proposals.jsonl`:

```
kvault.proposal.list status=awaiting_review
kvault.proposal.show id=prop-2026-04-22-001
kvault.proposal.approve id=prop-2026-04-22-001
kvault.proposal.reject id=prop-2026-04-22-001 reason="not durable enough"
```

Approval dispatches to a follow-up plugin based on `suggestion.type`:

- `rule` → rule-lifecycle plugin creates a proposed rule (see [`rules.md`](rules.md)).
- `note` → opens draft in vault; user completes.
- `manifest_update` → rebuilds the relevant manifest.

Rejection marks the proposal `status: rejected` with reason; it stays in the file as history.

## Why proposals are append-only

Proposals are evidence of what the system noticed. Even rejected proposals carry signal: if the same proposal keeps appearing and getting rejected, the detection heuristic is wrong and needs tuning. Throwing away rejected proposals erases that signal.

If the proposal file grows large, archive to dated files — never truncate silently.

## Cadence

Consolidation runs on demand, not continuously. Triggers:

- MCP tool: `kvault.consolidate.run`.
- Event subscription: a plugin listens for `vault.run.completed` and runs consolidation after every N runs.
- External scheduler: a user cron triggers the MCP tool.

No built-in scheduler. The kernel does not have a clock.

## Scope

Consolidation operates on what's already in the vault. It does not fetch external data. It does not "think" beyond the detection rules the plugin ships. It is pattern detection over episodic memory, nothing more.

For assistants that want richer synthesis (LLM-generated summaries, cross-source analysis), that happens outside kvault-mcp — the assistant reads episodic data via MCP tools, synthesizes in its own context, and writes results back as proposals or notes via MCP tools.

## What consolidation is not

- Not summarization. No free-text rollups of "what happened this week." That's a job for the assistant, not the kernel.
- Not a scheduler. It runs when invoked.
- Not authoritative. Every output is a proposal awaiting human review. The vault is not modified without approval.
