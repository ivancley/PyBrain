"""Scenario: an entity leaves the scope. Out of scope is not expired; it comes back.

The scope is strict: a memory without an entity only comes in when ``entities``
includes ``None`` as a member; ``entities=[]`` returns nothing on this axis.

PT: Cenário: uma entidade sai do escopo. Fora do escopo não é encerrada; ela volta.

O escopo é estrito: uma memória sem entidade só entra quando ``entities`` inclui
``None`` como membro; ``entities=[]`` não devolve nada neste eixo.
"""

from __future__ import annotations

from memory_lifecycle import Memory


def test_entity_out_of_scope_vanishes_and_comes_back(memory: Memory, owner: str):
    about = memory.remember(owner, "needs extra support", kind="observation", entity_id="e-1")
    memory.remember(owner, "learns fast", kind="observation", entity_id="e-2")
    # No entity.
    # PT: Sem entidade.
    memory.remember(owner, "applies to any entity", kind="note")

    without = memory.recall(owner, entities=["e-2"])
    assert [r.version.entity_id for r in without] == ["e-2"]

    back = memory.recall(owner, entities=["e-1", "e-2"])
    assert {r.version.entity_id for r in back} == {"e-1", "e-2"}

    with_no_entity = memory.recall(owner, entities=["e-1", "e-2", None])
    assert {r.version.entity_id for r in with_no_entity} == {"e-1", "e-2", None}

    assert memory.recall(owner, entities=[]) == []
    # Leaving the scope does not write.
    # PT: Sair do escopo não escreve.
    assert len(memory.history(owner, about.memory_id)) == 1
