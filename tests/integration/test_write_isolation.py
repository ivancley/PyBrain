"""Writes that reach several rows by context or entity respect tenant and owner.

reports/review-change-core.md, important 4: with ``OR true`` in the owner filter, the
earlier tests stayed green, because the other owner had neither the same context nor
the same entity.

PT: As escritas que alcançam várias linhas por contexto ou entidade respeitam tenant e dono.

reports/review-change-core.md, importante 4: com ``OR true`` no filtro de dono, os
testes anteriores continuavam verdes, porque o outro dono não tinha o mesmo
contexto nem a mesma entidade.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import Memory, NotFoundError
from tests.conftest import ManualClock


@pytest.fixture
def foreign(memory: Memory, other_tenant_memory: Memory, other_owner: str, owner: str):
    """Same context and same entity, under another owner and under another tenant.

    PT: Mesmo contexto e mesma entidade, em outro dono e em outro tenant.
    """
    memory.remember(other_owner, "do outro dono", kind="nota", context_id="c", entity_id="e")
    other_tenant_memory.remember(
        owner, "do outro tenant", kind="nota", context_id="c", entity_id="e"
    )


def test_invalidate_context_does_not_touch_what_is_foreign(
    memory: Memory, other_tenant_memory: Memory, owner: str, other_owner: str, foreign
):
    memory.remember(owner, "minha", kind="nota", context_id="c")
    assert memory.invalidate_context(owner, "c") == 1
    assert [r.version.content for r in memory.recall(other_owner)] == ["do outro dono"]
    assert [r.version.content for r in other_tenant_memory.recall(owner)] == ["do outro tenant"]


def test_forget_by_entity_does_not_touch_what_is_foreign(
    memory: Memory, other_tenant_memory: Memory, owner: str, other_owner: str, foreign
):
    memory.remember(owner, "minha", kind="nota", entity_id="e")
    assert memory.forget(owner, entity_id="e") == 1
    assert [r.version.content for r in memory.recall(other_owner)] == ["do outro dono"]
    assert [r.version.content for r in other_tenant_memory.recall(owner)] == ["do outro tenant"]


def test_correct_and_expire_on_a_foreign_memory_is_not_found(
    memory: Memory, owner: str, other_owner: str, clock: ManualClock
):
    foreign_memory = memory.remember(other_owner, "alheia", kind="nota")
    clock.advance(days=1)
    with pytest.raises(NotFoundError):
        memory.correct(owner, foreign_memory.memory_id, "invadida")
    with pytest.raises(NotFoundError):
        memory.expire(owner, foreign_memory.memory_id)
    assert memory.history(other_owner, foreign_memory.memory_id) == [foreign_memory]
