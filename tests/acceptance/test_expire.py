"""Scenario: a fact stops being true. Expire × the three query modes, and conflict.

PT: Cenário: um fato deixa de ser verdade. Encerrar × os três modos de consulta, e conflito.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import ConflictError, Memory
from tests.conftest import ManualClock


def test_expire_leaves_the_present_and_stays_in_the_past(
    memory: Memory, owner: str, clock: ManualClock
):
    v1 = memory.remember(owner, "lives in Lisbon", kind="fact")
    # June.
    # PT: Junho.
    clock.advance(days=150)
    closed = memory.expire(owner, v1.memory_id)
    clock.advance(days=30)

    assert closed.valid_to == clock.at(days=150)
    assert closed.previous_version_id == v1.version_id
    assert memory.recall(owner) == []
    # By what we know today, in March the expired copy held; in May, the system
    # knew of the January version, still without an end.
    # PT: Pelo que sabemos hoje, em março valia a cópia encerrada; em maio, o sistema
    # PT: sabia da versão de janeiro, ainda sem fim.
    march = memory.recall(owner, as_of=clock.at(days=60))
    assert [r.version.version_id for r in march] == [closed.version_id]
    may = memory.recall(owner, known_at=clock.at(days=120))
    assert [r.version.version_id for r in may] == [v1.version_id]
    assert [v.version_id for v in memory.history(owner, v1.memory_id)] == [
        v1.version_id,
        closed.version_id,
    ]


def test_retroactive_expire_does_not_rewrite_what_was_known(
    memory: Memory, owner: str, clock: ManualClock
):
    v1 = memory.remember(owner, "works on project X", kind="fact")
    # July: it turns out it ended in March.
    # PT: Julho: descobre-se que acabou em março.
    clock.advance(days=180)
    memory.expire(owner, v1.memory_id, valid_to=clock.at(days=60))

    # April.
    # PT: Abril.
    assert memory.recall(owner, as_of=clock.at(days=90)) == []
    may = memory.recall(owner, known_at=clock.at(days=120))
    assert [r.version.version_id for r in may] == [v1.version_id]


def test_expire_twice_conflicts(memory: Memory, owner: str, clock: ManualClock):
    v1 = memory.remember(owner, "x", kind="fact")
    # A validity must last longer than zero.
    # PT: Uma validade precisa durar mais que zero.
    clock.advance(days=1)
    memory.expire(owner, v1.memory_id)
    with pytest.raises(ConflictError):
        memory.expire(owner, v1.memory_id)
