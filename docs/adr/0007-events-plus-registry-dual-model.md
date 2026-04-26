# ADR 0007: Service registry + event bus as dual coordination model

**Status:** Accepted
**Date:** 2026-04-22

## Context

Plugins need to coordinate without knowing about each other. Two fundamentally different coordination styles exist:

- **Synchronous lookup:** "I need an embedding right now; find whoever provides embeddings."
- **Asynchronous notification:** "A run just completed; anyone who cares can react."

A system that supports only one forces plugins to fake the other, producing brittle patterns (polling for async, shared singletons for sync).

## Decision

kvault-mcp ships **both** coordination primitives as first-class kernel capabilities:

- **Service registry** — synchronous, protocol-based lookup. `kernel.get_active(Protocol) -> P | None`. For request/response.
- **Event bus** — asynchronous, topic-based pub/sub. `kernel.publish(event, payload)`, `kernel.subscribe(event, handler)`. For notifications and fan-out.

Every plugin interacts with the kernel through one or both of these. Plugin-to-plugin imports are forbidden.

## Rationale

- **Different semantics need different mechanisms.** Forcing sync lookups through events breaks the plugin's call graph (it has to block on a reply somehow). Forcing async notifications through the registry forces consumers to poll.
- **Each primitive is small and composable.** Registry = "who is active for this protocol?" Bus = "notify subscribers." No other kernel coordination primitive should be needed.
- **Testing clarity.** A plugin's dependencies are exactly what it pulls from the registry and what it subscribes to. Nothing hidden.
- **Protocol-typed registry.** Using Python Protocols (structural typing) means plugins don't import each other's classes — they depend on shape, not identity.

## Consequences

### Positive

- A retriever needs an embedder: it calls `kernel.get_active(EmbeddingProvider)`. No import.
- A manifest builder wants to rebuild on run completion: it subscribes to `vault.run.completed`. No import.
- Plugins can be swapped, stacked, or disabled without touching consumers.

### Negative

- Two primitives to learn instead of one. Mitigation: plugin docs make the "when to use which" decision mechanical (see [`../concepts/events.md`](../concepts/events.md) and [`../concepts/service-registry.md`](../concepts/service-registry.md)).
- Event payloads need schemas. Mitigation: event schemas are part of the emitting plugin's contract; `audit-schemas` validates them.
- No transactional guarantees — events are fire-and-forget. Mitigation: documented clearly; plugins that need durability persist to manifests.

## Alternatives considered

- **Registry only.** Rejected: forces async patterns to become sync (poll-based), which creates coupling and performance problems.
- **Events only.** Rejected: forces sync lookup to become "emit request event, wait for response event," which is a reinvented RPC with worse ergonomics.
- **Dependency injection container.** Rejected: adds framework weight. The registry is a minimal subset of DI, which is all we need.

## Related

- [`../concepts/events.md`](../concepts/events.md)
- [`../concepts/service-registry.md`](../concepts/service-registry.md)
- [`../concepts/plugins.md`](../concepts/plugins.md) (golden rule)
