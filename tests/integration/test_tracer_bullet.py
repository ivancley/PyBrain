"""Slice 1: ``remember`` and ``recall()`` end to end against the real Postgres.

PT: Fatia 1: ``remember`` e ``recall()`` de ponta a ponta contra o Postgres real.
"""

from __future__ import annotations

from memory_lifecycle import Memory
from tests.conftest import T0, ManualClock


def test_what_was_remembered_comes_back_in_recall(memory: Memory, owner: str):
    remembered = memory.remember(owner, "prefere respostas curtas", kind="preferencia")

    [result] = memory.recall(owner)

    assert result.version == remembered
    assert result.score is None
    assert (remembered.tenant_id, remembered.owner_id) == (memory.tenant_id, owner)
    assert remembered.previous_version_id is None
    assert remembered.superseded_at is None and remembered.valid_to is None
    assert remembered.embedding_model == "fake"


def test_recorded_at_comes_from_the_injected_clock(memory: Memory, owner: str, clock: ManualClock):
    clock.advance(days=3)

    remembered = memory.remember(owner, "x", kind="nota")

    assert remembered.recorded_at == T0.replace(day=4)
    assert remembered.valid_from == remembered.recorded_at


def test_the_most_recent_comes_first_and_the_limit_cuts(
    memory: Memory, owner: str, clock: ManualClock
):
    for content in ("a", "b", "c"):
        memory.remember(owner, content, kind="nota")
        clock.advance(days=1)

    assert [r.version.content for r in memory.recall(owner, limit=2)] == ["c", "b"]


def test_migrating_again_applies_nothing(memory: Memory):
    assert memory.migrate() == 0
