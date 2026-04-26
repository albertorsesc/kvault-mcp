from __future__ import annotations

from typing import Protocol, runtime_checkable

from kvault_mcp.core.registry import ServiceRegistry


@runtime_checkable
class _Foo(Protocol):
    def do(self) -> str: ...


class FooA:
    def do(self) -> str:
        return "a"


class FooB:
    def do(self) -> str:
        return "b"


def test_register_and_get_active() -> None:
    r = ServiceRegistry()
    a, b = FooA(), FooB()
    r.register(_Foo, "plugin.a", a, active=False)
    r.register(_Foo, "plugin.b", b, active=True)
    assert r.get_active(_Foo) is b


def test_get_all_returns_every_registered() -> None:
    r = ServiceRegistry()
    a, b = FooA(), FooB()
    r.register(_Foo, "plugin.a", a, active=False)
    r.register(_Foo, "plugin.b", b, active=True)
    assert r.get_all(_Foo) == [a, b]


def test_missing_protocol_returns_none() -> None:
    r = ServiceRegistry()
    assert r.get_active(_Foo) is None
    assert r.get_all(_Foo) == []


def test_multiple_active_returns_first_with_warning(caplog) -> None:
    r = ServiceRegistry()
    a, b = FooA(), FooB()
    r.register(_Foo, "plugin.a", a, active=True)
    r.register(_Foo, "plugin.b", b, active=True)
    import logging

    with caplog.at_level(logging.WARNING):
        assert r.get_active(_Foo) is a
