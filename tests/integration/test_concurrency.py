"""Two supersedes of the same version, on two connections at the same time (ADR 0002).

A barrier holds both threads after they read the current version and before they close
the record: both try to close the same row. The conditional close lets one win and the
other raise ``ConflictError``; nothing is overwritten silently.

PT: Duas substituições da mesma versão, em duas conexões ao mesmo tempo (ADR 0002).

Uma barreira segura as duas threads depois de lerem a vigente e antes de fecharem
o registro: as duas tentam fechar a mesma linha. O fechamento condicional deixa
uma vencer e a outra levantar ``ConflictError``; nada é sobrescrito em silêncio.
"""

from __future__ import annotations

import threading

import pytest

from memory_lifecycle import ConflictError, FakeEmbeddingProvider, Memory, store
from memory_lifecycle.connection.dsn import DSNProvider
from tests.conftest import ManualClock


def test_two_supersedes_on_two_connections(
    memory: Memory,
    owner: str,
    clock: ManualClock,
    dsn: str,
    schema: str,
    monkeypatch: pytest.MonkeyPatch,
):
    original = memory.remember(owner, "v1", kind="note")
    clock.advance(days=1)
    barrier = threading.Barrier(2, timeout=10)
    real_close = store.close_record

    def close_after_barrier(*args, **kwargs):
        barrier.wait()
        return real_close(*args, **kwargs)

    monkeypatch.setattr(store, "close_record", close_after_barrier)
    results: dict[str, object] = {}

    def writer(name: str) -> None:
        own = Memory(
            connection=DSNProvider(dsn),
            embeddings=FakeEmbeddingProvider(dimension=8),
            tenant_id=memory.tenant_id,
            schema=schema,
            clock=clock,
        )
        try:
            results[name] = own.supersede(owner, original.memory_id, f"from {name}")
        # The test inspects the type below.
        # PT: O teste inspeciona o tipo abaixo.
        except Exception as error:
            results[name] = error

    threads = [threading.Thread(target=writer, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    conflicts = [r for r in results.values() if isinstance(r, ConflictError)]
    winners = [r for r in results.values() if not isinstance(r, Exception)]
    assert (len(conflicts), len(winners)) == (1, 1), results
    history = memory.history(owner, original.memory_id)
    assert len(history) == 3
    assert history[-1] == winners[0]


def test_two_expires_on_two_connections(
    memory: Memory,
    owner: str,
    clock: ManualClock,
    dsn: str,
    schema: str,
    monkeypatch: pytest.MonkeyPatch,
):
    original = memory.remember(owner, "v1", kind="note")
    clock.advance(days=1)
    barrier = threading.Barrier(2, timeout=10)
    real_close = store.close_record

    def close_after_barrier(*args, **kwargs):
        barrier.wait()
        return real_close(*args, **kwargs)

    monkeypatch.setattr(store, "close_record", close_after_barrier)
    results: list[object] = []

    def writer() -> None:
        own = Memory(
            connection=DSNProvider(dsn),
            embeddings=FakeEmbeddingProvider(dimension=8),
            tenant_id=memory.tenant_id,
            schema=schema,
            clock=clock,
        )
        try:
            results.append(own.expire(owner, original.memory_id))
        # The test inspects the type below.
        # PT: O teste inspeciona o tipo abaixo.
        except Exception as error:
            results.append(error)

    threads = [threading.Thread(target=writer) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sum(isinstance(r, ConflictError) for r in results) == 1, results
    assert len(memory.history(owner, original.memory_id)) == 2
