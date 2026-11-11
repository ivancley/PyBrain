"""Scenario: a preference changes. Supersede × the three query modes.

PT: Cenário: uma preferência muda. Substituir × os três modos de consulta.
"""

from __future__ import annotations

from memory_lifecycle import Memory
from tests.conftest import ManualClock


def test_supersede_changes_the_present_and_keeps_the_past(
    memory: Memory, owner: str, clock: ManualClock
):
    v1 = memory.remember(owner, "prefers short answers", kind="preference")
    # June.
    # PT: Junho.
    clock.advance(days=150)
    v2 = memory.supersede(owner, v1.memory_id, "prefers detailed answers")
    # July.
    # PT: Julho.
    clock.advance(days=30)

    now = memory.recall(owner, kind="preference")
    assert [r.version.content for r in now] == ["prefers detailed answers"]

    march = memory.recall(owner, kind="preference", as_of=clock.at(days=60))
    assert [r.version.content for r in march] == ["prefers short answers"]

    may = memory.recall(owner, kind="preference", known_at=clock.at(days=120))
    assert [r.version.version_id for r in may] == [v1.version_id]

    # The original stays intact with its record closed; the bounded copy carries the
    # end of validity; the new one points to the copy (ADR 0002).
    # PT: A original fica intacta com o registro fechado; a cópia limitada carrega o fim
    # PT: da validade; a nova aponta para a cópia (ADR 0002).
    original, copy, new = memory.history(owner, v1.memory_id)
    assert original.version_id == v1.version_id
    assert original.valid_to is None
    assert original.superseded_at == clock.at(days=150)
    assert (copy.content, copy.valid_to) == ("prefers short answers", clock.at(days=150))
    assert copy.previous_version_id == v1.version_id
    assert new.version_id == v2.version_id
    assert v2.previous_version_id == copy.version_id


def test_supersede_inherits_the_scope(memory: Memory, owner: str, clock: ManualClock):
    v1 = memory.remember(owner, "a", kind="note", entity_id="e-1", context_id="c-1")
    # A validity must last longer than zero.
    # PT: Uma validade precisa durar mais que zero.
    clock.advance(days=1)
    v2 = memory.supersede(owner, v1.memory_id, "b")
    assert (v2.entity_id, v2.context_id, v2.kind) == ("e-1", "c-1", "note")


def test_retroactive_and_future_supersede(memory: Memory, owner: str, clock: ManualClock):
    v1 = memory.remember(owner, "a", kind="note")
    clock.advance(days=100)
    # On day 100 it turns out the fact changed on day 40.
    # PT: Descobre-se no dia 100 que o fato mudou no dia 40.
    memory.supersede(owner, v1.memory_id, "b", valid_from=clock.at(days=40))
    assert [r.version.content for r in memory.recall(owner, as_of=clock.at(days=50))] == ["b"]
    assert [r.version.content for r in memory.recall(owner, known_at=clock.at(days=50))] == ["a"]

    # And a change is scheduled for day 200: until then, "b" holds.
    # PT: E agenda-se uma mudança para o dia 200: até lá, vale "b".
    memory.supersede(owner, v1.memory_id, "c", valid_from=clock.at(days=200))
    assert [r.version.content for r in memory.recall(owner)] == ["b"]
    assert [r.version.content for r in memory.recall(owner, as_of=clock.at(days=250))] == ["c"]
