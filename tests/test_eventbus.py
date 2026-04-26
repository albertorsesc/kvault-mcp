from __future__ import annotations

from kvault_mcp.core.eventbus import EventBus


def test_publish_reaches_subscribers_in_order() -> None:
    bus = EventBus()
    calls: list[tuple[str, str]] = []
    bus.subscribe("evt.x", lambda e, p: calls.append(("a", p["v"])))
    bus.subscribe("evt.x", lambda e, p: calls.append(("b", p["v"])))
    bus.publish("evt.x", {"v": "1"})
    assert calls == [("a", "1"), ("b", "1")]


def test_subscribers_for_other_events_are_not_called() -> None:
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe("evt.a", lambda e, p: calls.append(e))
    bus.publish("evt.b", {})
    assert calls == []


def test_handler_exception_is_swallowed() -> None:
    bus = EventBus()

    def boom(e: str, p: dict) -> None:
        raise RuntimeError("nope")

    called: list[str] = []
    bus.subscribe("evt.x", boom)
    bus.subscribe("evt.x", lambda e, p: called.append("ok"))
    bus.publish("evt.x", {})
    assert called == ["ok"]


def test_handlers_for_view() -> None:
    bus = EventBus()
    bus.subscribe("evt.x", lambda e, p: None)
    bus.subscribe("evt.x", lambda e, p: None)
    assert len(bus.handlers_for("evt.x")) == 2
    assert bus.handlers_for("evt.y") == []
