"""Scenario: isolation. Nothing from one tenant or one owner reaches another, in any mode.

PT: Cenário: isolamento. Nada de um tenant ou de um dono alcança outro, em nenhum modo.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import Memory, NotFoundError
from tests.conftest import ManualClock


def test_two_tenants_same_owner_id(
    memory: Memory, other_tenant_memory: Memory, owner: str, clock: ManualClock
):
    mine = memory.remember(owner, "mine", kind="note")
    other_tenant_memory.remember(owner, "theirs", kind="note")
    clock.advance(days=1)

    for arguments in ({}, {"as_of": clock()}, {"known_at": clock()}):
        assert [r.version.content for r in memory.recall(owner, **arguments)] == ["mine"]
        assert [r.version.content for r in other_tenant_memory.recall(owner, **arguments)] == [
            "theirs"
        ]

    with pytest.raises(NotFoundError):
        other_tenant_memory.history(owner, mine.memory_id)


def test_two_owners_same_tenant(memory: Memory, owner: str, other_owner: str):
    mine = memory.remember(owner, "mine", kind="note")
    memory.remember(other_owner, "theirs", kind="note")

    assert [r.version.content for r in memory.recall(other_owner)] == ["theirs"]
    with pytest.raises(NotFoundError):
        memory.supersede(other_owner, mine.memory_id, "hijacked")
    assert [v.content for v in memory.history(owner, mine.memory_id)] == ["mine"]
