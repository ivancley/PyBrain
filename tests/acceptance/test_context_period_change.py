"""Scenario: a context changes period. Memories from one period do not leak into the next.

The scope is strict: a memory without a context only comes in when ``contexts``
includes ``None`` as a member; ``contexts=None`` does not filter on this axis.

PT: Cenário: um contexto muda de período. Memórias de um período não vazam no seguinte.

O escopo é estrito: uma memória sem contexto só entra quando ``contexts`` inclui
``None`` como membro; ``contexts=None`` não filtra por este eixo.
"""

from __future__ import annotations

from memory_lifecycle import Memory
from tests.conftest import ManualClock


def test_previous_period_leaves_scope_but_does_not_vanish(memory: Memory, owner: str):
    old = memory.remember(owner, "struggles with topic A", kind="observation", context_id="p-2026")
    # No context.
    # PT: Sem contexto.
    memory.remember(owner, "always on time", kind="preference")

    # The next period does not see the previous one; the memory without a context only
    # comes in when the scope says None is active.
    # PT: O período seguinte não enxerga o anterior; a memória sem contexto só entra
    # PT: quando o escopo diz que None está ativo.
    assert memory.recall(owner, contexts=["p-2027"]) == []
    next_period = memory.recall(owner, contexts=["p-2027", None])
    assert [r.version.content for r in next_period] == ["always on time"]

    previous = memory.recall(owner, contexts=["p-2026", None])
    assert {r.version.content for r in previous} == {
        "struggles with topic A",
        "always on time",
    }
    period_only = memory.recall(owner, contexts=["p-2026"])
    assert [r.version.content for r in period_only] == ["struggles with topic A"]
    # Leaving the scope does not write.
    # PT: Sair do escopo não escreve.
    assert len(memory.history(owner, old.memory_id)) == 1


def test_invalidate_context_is_an_explicit_expire(memory: Memory, owner: str, clock: ManualClock):
    memory.remember(owner, "a", kind="note", context_id="c-1")
    memory.remember(owner, "b", kind="note", context_id="c-1")
    memory.remember(owner, "c", kind="note", context_id="c-2")
    clock.advance(days=10)

    assert memory.invalidate_context(owner, "c-1") == 2
    now = memory.recall(owner, contexts=["c-1", "c-2"])
    assert [r.version.content for r in now] == ["c"]
    before = memory.recall(owner, contexts=["c-1", "c-2"], as_of=clock.at(days=5))
    assert {r.version.content for r in before} == {"a", "b", "c"}
