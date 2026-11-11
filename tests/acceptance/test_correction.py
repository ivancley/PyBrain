"""Scenario: correction. Correct × the three query modes keeps the audit trail.

PT: Cenário: correção. Corrigir × os três modos de consulta mantém a trilha de auditoria.
"""

from __future__ import annotations

from memory_lifecycle import Memory, Status, derive_status
from tests.conftest import ManualClock


def test_correct_rewrites_the_past_but_not_the_record(
    memory: Memory, owner: str, clock: ManualClock
):
    wrong = memory.remember(owner, "born in 1990", kind="fact")
    # June.
    # PT: Junho.
    clock.advance(days=150)
    right = memory.correct(owner, wrong.memory_id, "born in 1991")
    clock.advance(days=30)

    assert right.valid_from == wrong.valid_from
    assert [r.version.content for r in memory.recall(owner)] == ["born in 1991"]
    march = memory.recall(owner, as_of=clock.at(days=60))
    assert [r.version.content for r in march] == ["born in 1991"]
    may = memory.recall(owner, known_at=clock.at(days=120))
    assert [r.version.content for r in may] == ["born in 1990"]

    history = memory.history(owner, wrong.memory_id)
    assert derive_status(history[0], now=clock(), successor=history[1]) is Status.CORRECTED
    assert derive_status(history[1], now=clock()) is Status.ACTIVE
