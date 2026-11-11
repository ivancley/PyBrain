"""Specs ``memory-versions`` and ``recall``: the edges of ``remember`` and ``recall``.

PT: Spec ``memory-versions`` e ``recall``: as bordas de ``remember`` e ``recall``.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from memory_lifecycle import InvalidArgumentError, Memory, NotFoundError
from tests.conftest import ManualClock


def test_remember_with_explicit_validity(memory: Memory, owner: str, clock: ManualClock):
    clock.advance(days=100)
    v = memory.remember(
        owner, "x", kind="nota", valid_from=clock.at(days=10), valid_to=clock.at(days=200)
    )
    assert (v.valid_from, v.valid_to) == (clock.at(days=10), clock.at(days=200))
    assert [r.version for r in memory.recall(owner, as_of=clock.at(days=50))] == [v]
    assert memory.recall(owner, as_of=clock.at(days=5)) == []
    assert memory.recall(owner, as_of=clock.at(days=200)) == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"content": ""},
        {"kind": " "},
        {"valid_from": datetime(2026, 1, 1)},
        {"valid_to": datetime(2026, 1, 1)},
    ],
)
def test_invalid_remember_records_nothing(memory: Memory, owner: str, arguments: dict):
    call = {"content": "x", "kind": "nota", **arguments}
    with pytest.raises(InvalidArgumentError):
        memory.remember(owner, **call)
    assert memory.recall(owner) == []


def test_inverted_validity_is_refused(memory: Memory, owner: str, clock: ManualClock):
    with pytest.raises(InvalidArgumentError):
        memory.remember(owner, "x", kind="nota", valid_to=clock.at(days=-1))


def test_strict_scope_by_context_and_entity(memory: Memory, owner: str):
    memory.remember(owner, "solta", kind="nota")
    memory.remember(owner, "do c1", kind="nota", context_id="c1")
    memory.remember(owner, "da e1", kind="nota", entity_id="e1")

    def contents(**scope: object) -> set[str]:
        return {r.version.content for r in memory.recall(owner, **scope)}  # type: ignore[arg-type]

    assert contents() == {"solta", "do c1", "da e1"}
    assert contents(contexts=["c1"]) == {"do c1"}
    assert contents(contexts=["c1", None]) == {"solta", "do c1", "da e1"}
    assert contents(contexts=[]) == set()
    assert contents(entities=["e1"]) == {"da e1"}
    assert contents(entities=[None]) == {"solta", "do c1"}
    assert contents(contexts=[None], entities=[None]) == {"solta"}


def test_filter_by_kind(memory: Memory, owner: str):
    memory.remember(owner, "a", kind="preferencia")
    memory.remember(owner, "b", kind="fato")
    assert [r.version.content for r in memory.recall(owner, kind="fato")] == ["b"]


@pytest.mark.parametrize("limit", [0, -1, True, 2.5])
def test_limit_must_be_a_positive_integer(memory: Memory, owner: str, limit: object):
    with pytest.raises(InvalidArgumentError):
        memory.recall(owner, limit=limit)  # type: ignore[arg-type]


def test_as_of_and_known_at_together(memory: Memory, owner: str, clock: ManualClock):
    with pytest.raises(InvalidArgumentError):
        memory.recall(owner, as_of=clock(), known_at=clock())


def test_history_of_an_unknown_or_invalid_id(memory: Memory, owner: str):
    for memory_id in ("nao-e-uuid", "00000000-0000-0000-0000-000000000000"):
        with pytest.raises(NotFoundError):
            memory.history(owner, memory_id)


def test_history_does_not_reveal_the_memory_exists_in_another_tenant(
    memory: Memory, other_tenant_memory: Memory, owner: str
):
    foreign = memory.remember(owner, "x", kind="nota")
    with pytest.raises(NotFoundError) as foreign_error:
        other_tenant_memory.history(owner, foreign.memory_id)
    with pytest.raises(NotFoundError) as missing_error:
        other_tenant_memory.history(owner, "00000000-0000-0000-0000-000000000000")
    assert str(foreign_error.value) == str(missing_error.value)
