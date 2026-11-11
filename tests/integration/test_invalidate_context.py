"""``invalidate_context`` (spec ``temporal-operations``; reports/review-change-core.md, importants 2 and 3).

PT: ``invalidate_context`` (spec ``temporal-operations``; reports/review-change-core.md, importantes 2 e 3).
"""

from __future__ import annotations

import threading
import time

import pytest

from memory_lifecycle import FakeEmbeddingProvider, Memory, store
from memory_lifecycle.connection.dsn import DSNProvider
from tests.conftest import ManualClock


def _contents(memory: Memory, owner: str, **moment: object) -> set[str]:
    return {r.version.content for r in memory.recall(owner, contexts=["c"], **moment)}  # type: ignore[arg-type]


def test_also_expires_what_has_not_started_yet(memory: Memory, owner: str, clock: ManualClock):
    memory.remember(owner, "futura", kind="nota", context_id="c", valid_from=clock.at(days=10))
    assert memory.invalidate_context(owner, "c") == 1
    assert _contents(memory, owner, as_of=clock.at(days=20)) == set()


def test_shortens_what_would_end_later(memory: Memory, owner: str, clock: ManualClock):
    memory.remember(
        owner, "até o fim do ano", kind="nota", context_id="c", valid_to=clock.at(days=300)
    )
    clock.advance(days=100)
    assert memory.invalidate_context(owner, "c") == 1
    assert _contents(memory, owner, as_of=clock.at(days=50)) == {"até o fim do ano"}
    assert _contents(memory, owner, as_of=clock.at(days=200)) == set()


def test_known_at_is_retroactive(memory: Memory, owner: str, clock: ManualClock):
    memory.remember(owner, "a", kind="nota", context_id="c")
    clock.advance(days=100)
    assert memory.invalidate_context(owner, "c", valid_to=clock.at(days=30)) == 1
    assert _contents(memory, owner, as_of=clock.at(days=60)) == set()
    assert _contents(memory, owner, as_of=clock.at(days=10)) == {"a"}
    # At D=60 the system did not yet know about the retroactive end: "a" held.
    # PT: Em D=60 o sistema ainda não sabia do fim retroativo: "a" valia.
    assert _contents(memory, owner, known_at=clock.at(days=60)) == {"a"}


def test_reaches_the_version_of_a_concurrent_supersede(
    memory: Memory,
    owner: str,
    clock: ManualClock,
    dsn: str,
    schema: str,
    monkeypatch: pytest.MonkeyPatch,
):
    original = memory.remember(owner, "v1", kind="nota", context_id="c")
    clock.advance(days=1)
    closed = threading.Event()
    real_copy = store.insert_bounded_copy

    def copy_and_wait(*args, **kwargs):
        result = real_copy(*args, **kwargs)
        closed.set()
        # Meanwhile the invalidation is stuck on the row's lock.
        # PT: A invalidação fica presa no lock da linha enquanto isso.
        time.sleep(0.5)
        return result

    monkeypatch.setattr(store, "insert_bounded_copy", copy_and_wait)

    def fresh() -> Memory:
        return Memory(
            connection=DSNProvider(dsn),
            embeddings=FakeEmbeddingProvider(dimension=8),
            tenant_id=memory.tenant_id,
            schema=schema,
            clock=clock,
        )

    supersession = threading.Thread(
        target=lambda: fresh().supersede(owner, original.memory_id, "v2")
    )
    supersession.start()
    assert closed.wait(timeout=10)
    fresh().invalidate_context(owner, "c")
    supersession.join(timeout=10)

    clock.advance(days=1)
    assert _contents(memory, owner) == set(), "the concurrent supersede's version escaped"
