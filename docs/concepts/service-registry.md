# Service registry

The synchronous coordination surface. Plugins declare what they provide; the kernel keeps them indexed by protocol; callers ask for the one they need and get a typed reference back.

## The two queries

The registry answers two questions:

```python
kernel.get_active(Retriever) -> Retriever | None
kernel.get_all(Audit) -> list[Audit]
```

- `get_active(protocol)` — returns the single plugin marked active for that protocol in config. Used when the system operates under a "there can be only one" constraint (one active retriever, one active vector store, etc.).
- `get_all(protocol)` — returns every registered plugin of that protocol. Used when the system runs each in sequence or in parallel (all audits, all consolidators).

Which protocols are `get_active` vs `get_all` is declared by the protocol itself (a flag on the `Protocol` class). Plugins don't decide; the kernel enforces.

## When to use the registry (vs events)

Use the **registry** when:

- The caller needs a result back synchronously.
- There is a defined "active" implementation chosen by config.
- The contract is request/response, not notification.

Use **events** (see [`events.md`](events.md)) when:

- Multiple handlers should run independently in response to something.
- You don't need the result back.

In practice: MCP tool handlers use the registry; workflows and reactions use events.

## Example — MCP tool handler

`vault.advisory.query` is an MCP tool that answers *"give me knowledge relevant to this situation"*. Its handler:

```python
class AdvisoryQueryTool(Tool):
    def handle(self, situation: str, k: int = 5) -> dict:
        retriever = self.kernel.get_active(Retriever)
        if retriever is None:
            return {"error": "no active retriever"}
        results = retriever.query(situation, k=k)
        return {"results": [r.to_dict() for r in results]}
```

The handler does not know whether the retriever is `hybrid_rrf`, `qmd_wrapper`, or something a user wrote this morning. It asks for "the active retriever." Kernel returns whatever is configured.

## Example — running all audits

`vault.audit_all` iterates over every registered audit plugin:

```python
class AuditAllTool(Tool):
    def handle(self) -> dict:
        findings_by_audit = {}
        for audit in self.kernel.get_all(Audit):
            findings_by_audit[audit.id] = audit.run(self.kernel.vault)
        return findings_by_audit
```

Adding a new audit = dropping a plugin. `audit_all` picks it up automatically. No code change in the tool.

## Activation

A plugin's `plugin.toml` can declare itself active by default, but the final decision comes from config:

```toml
# kvault.config.toml
[plugins.retriever.hybrid_rrf]
active = true
```

The kernel resolves: if multiple plugins claim to be active for a `get_active` protocol, it picks the one with explicit `active = true` in config and warns about the conflict. If none is active, `get_active` returns None and the caller handles that explicitly.

## Protocol versioning

Each protocol has a `protocol_version`. Plugins declare which version they target. A plugin targeting `protocol_version = "1.0"` continues to work as long as the kernel still honors v1.0, even after a v2.0 protocol ships. Adapters can sit between protocol versions if needed.

See [`adr/0007-events-plus-registry-dual-model.md`](../adr/0007-events-plus-registry-dual-model.md) for the rationale on maintaining both coordination mechanisms.
