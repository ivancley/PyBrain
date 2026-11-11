"""Scenario: the three modes disagree about the same history (spec ``recall``).

This scenario exposed the contradiction in the first version of ADR 0002: with the
old version's record closed, ``as_of=March`` did not find the January fact.

PT: Cenário: os três modos discordam sobre o mesmo histórico (spec ``recall``).

Foi este cenário que expôs a contradição da primeira versão do ADR 0002: com a
antiga de registro fechado, ``as_of=março`` não achava o fato de janeiro.
"""

from __future__ import annotations

from memory_lifecycle import Memory, Status, derive_status
from tests.conftest import ManualClock


def test_now_as_of_and_known_at_over_a_chain(memory: Memory, owner: str, clock: ManualClock):
    memory_id = memory.remember(owner, "short", kind="preference").memory_id
    # June 1st.
    # PT: 1º de junho.
    clock.advance(days=151)
    memory.supersede(owner, memory_id, "detailed")
    # July 1st.
    # PT: 1º de julho.
    clock.advance(days=30)
    memory.correct(owner, memory_id, "detailed, with sources")
    clock.advance(days=30)

    def contents(**moment: object) -> list[str]:
        return [r.version.content for r in memory.recall(owner, **moment)]  # type: ignore[arg-type]

    assert contents() == ["detailed, with sources"]
    assert contents(as_of=clock.at(days=60)) == ["short"]
    assert contents(as_of=clock.at(days=165)) == ["detailed, with sources"]
    assert contents(known_at=clock.at(days=120)) == ["short"]
    assert contents(known_at=clock.at(days=165)) == ["detailed"]

    history = memory.history(owner, memory_id)
    successors = {v.previous_version_id: v for v in history}
    status = [
        derive_status(v, now=clock(), successor=successors.get(v.version_id)) for v in history
    ]
    assert status == [Status.SUPERSEDED, Status.SUPERSEDED, Status.CORRECTED, Status.ACTIVE]
