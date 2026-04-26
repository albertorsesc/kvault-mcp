# Event bus

The async coordination surface. Plugins publish events without knowing who listens; plugins subscribe without knowing who publishes. This is how workflows compose without direct references.

## When to use events (vs service registry)

Use **events** when:

- A workflow triggers work in N independent handlers, and you don't need the results synchronously.
- A plugin reacts to something that happened elsewhere (e.g., "a new rule was proposed → update the rule-proposals manifest").
- Multiple plugins of the same kind should ALL run in response to something (e.g., every consolidator reacts to `vault.consolidation.requested`).

Use the **service registry** (see [`service-registry.md`](service-registry.md)) when:

- You need a value back from a plugin synchronously (e.g., an MCP tool needs the active retriever to answer a query).

In practice: tools use registry lookups; workflows use events.

## Event naming

Past-tense subject.verb format: `vault.<subject>.<verb>`.

Examples:

- `vault.manifest.built`
- `vault.audit.completed`
- `vault.findings.emitted`
- `vault.rule.proposed`
- `vault.rule.approved`
- `vault.rule.retired`
- `vault.proposal.written`
- `vault.consolidation.requested` (imperative exception — this is a USER-triggered intent; most events are past-tense facts)
- `vault.capability.registered`
- `vault.embedding.rebuilt`

A plugin's `plugin.toml` declares what it emits and consumes:

```toml
emits_events = ["vault.findings.emitted"]
consumes_events = ["vault.consolidation.requested"]
```

The kernel uses these declarations for two things: lifecycle (subscribing the plugin at load time) and a reachability report (running `vault.plugins.graph` tells you which plugins respond to which events — great for debugging).

## Publish + subscribe

From inside a plugin, via the kernel API:

```python
class MyConsolidator(Consolidator):
    def on_consolidation_requested(self, payload: dict) -> None:
        # ... find patterns ...
        self.kernel.publish("vault.proposal.written", {
            "id": "...",
            "type": "repeated_findings",
            "summary": "...",
        })
```

Subscription is wired by the kernel at registration time based on `consumes_events`. The plugin declares the handler method via naming convention (`on_<event_with_underscores>`) or via an explicit `@subscribes("event.name")` decorator — both supported.

## Event payload schemas

Each event type has a JSON Schema under `schemas/events/<event-name>.schema.json`. The kernel validates every published event against the schema before dispatching. A plugin publishing a malformed event is logged and the event is dropped — never broadcasted.

This keeps the event contract stable across plugin versions and makes it safe to add new consumers.

## Delivery guarantees

- **In-process only.** Events are not persisted; if no one is subscribed, they are dropped.
- **Fire-and-forget.** Publishers do not wait for subscribers. Handlers run on the kernel's worker pool.
- **At-most-once.** An event is delivered to each subscriber exactly once per publish, or not at all if the kernel is shutting down.
- **Ordered per publisher.** Events from one plugin are delivered to each subscriber in publish order.

For workflows that require durability (e.g., rule proposals), the plugin writes to disk (proposals.jsonl) and publishes an event as a notification. The disk record is the source of truth; the event is a signal.

## Failures in handlers

A subscriber that raises is caught by the kernel, logged with context (event type, payload summary, subscriber plugin ID, traceback), and does not affect other subscribers. The event is marked delivered to every subscriber except the failing one.

Chronic handler failures surface in `vault.plugins.list()` as health warnings.

## Not what this is

- Not a message queue. No retries. No persistence. No acknowledgements.
- Not inter-process. Events are in the kernel's process space.
- Not ordered across publishers. Use explicit ordering (timestamps, sequence numbers in payload) if needed.

When you need durable, cross-process messaging, write to a manifest file and publish an event as a notification; other plugins read the file. The file is the truth; the event is the ping.
