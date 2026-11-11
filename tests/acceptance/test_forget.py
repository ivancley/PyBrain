"""Scenario: forget. After it, no version exists, in any query mode.

PT: Cenário: esquecer. Depois dele, nenhuma versão existe, em nenhum modo de consulta.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import InvalidArgumentError, Memory, NotFoundError
from tests.conftest import ManualClock


def test_forget_one_memory_deletes_every_version(memory: Memory, owner: str, clock: ManualClock):
    v1 = memory.remember(owner, "a", kind="note")
    clock.advance(days=1)
    memory.supersede(owner, v1.memory_id, "b")
    clock.advance(days=1)
    memory.correct(owner, v1.memory_id, "c")
    clock.advance(days=1)

    # remember (1) + supersede (copy and new: 2) + correct (1) = 4 rows
    # PT: lembrar (1) + substituir (cópia e nova: 2) + corrigir (1) = 4 linhas
    assert memory.forget(owner, memory_id=v1.memory_id) == 4
    with pytest.raises(NotFoundError):
        memory.history(owner, v1.memory_id)
    for arguments in ({}, {"as_of": clock.at(days=1)}, {"known_at": clock.at(days=1)}):
        assert memory.recall(owner, **arguments) == []


def test_forget_by_entity_and_everything(memory: Memory, owner: str, other_owner: str):
    memory.remember(owner, "about e-1", kind="note", entity_id="e-1")
    memory.remember(owner, "about e-2", kind="note", entity_id="e-2")
    memory.remember(other_owner, "untouched", kind="note")

    assert memory.forget(owner, entity_id="e-1") == 1
    assert [r.version.entity_id for r in memory.recall(owner)] == ["e-2"]
    assert memory.forget(owner, everything=True) == 1
    assert memory.recall(owner) == []
    assert [r.version.content for r in memory.recall(other_owner)] == ["untouched"]


def test_forget_requires_exactly_one_target(memory: Memory, owner: str):
    with pytest.raises(InvalidArgumentError):
        memory.forget(owner)
    assert memory.forget(owner, memory_id="never-existed") == 0
