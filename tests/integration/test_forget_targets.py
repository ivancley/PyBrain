"""Spec ``forget``: after forgetting, no row is left in the database, not even the copies.

PT: Spec ``forget``: depois de esquecer, nenhuma linha fica no banco, nem nas cópias.
"""

from __future__ import annotations

import psycopg

from memory_lifecycle import Memory
from tests.conftest import ManualClock


def _rows_in_database(dsn: str, schema: str, memory_id: str) -> int:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            f'SELECT count(*) FROM "{schema}".memory_versions WHERE memory_id = %s::uuid',
            (memory_id,),
        ).fetchone()
    assert row is not None
    return int(row[0])


def test_forget_leaves_no_row_at_all(
    memory: Memory, owner: str, clock: ManualClock, dsn: str, schema: str
):
    v = memory.remember(owner, "a", kind="nota", entity_id="e-1")
    clock.advance(days=1)
    memory.supersede(owner, v.memory_id, "b", entity_id="e-2")
    clock.advance(days=1)
    memory.expire(owner, v.memory_id)
    # remember (1) + supersede (copy and new: 2) + expire (copy: 1)
    # PT: lembrar (1) + substituir (cópia e nova: 2) + encerrar (cópia: 1)
    assert _rows_in_database(dsn, schema, v.memory_id) == 4

    # By entity, the whole memory goes, even the versions that already cite another entity.
    # PT: Por entidade, a memória inteira sai, mesmo as versões que já citam outra entidade.
    assert memory.forget(owner, entity_id="e-1") == 4
    assert _rows_in_database(dsn, schema, v.memory_id) == 0


def test_forget_does_not_touch_another_tenant(
    memory: Memory, other_tenant_memory: Memory, owner: str, dsn: str, schema: str
):
    foreign = other_tenant_memory.remember(owner, "do outro tenant", kind="nota")
    assert memory.forget(owner, everything=True) == 0
    assert memory.forget(owner, memory_id=foreign.memory_id) == 0
    assert _rows_in_database(dsn, schema, foreign.memory_id) == 1
