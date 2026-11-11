"""The writes: one function per statement, all filtered by tenant and owner.

Each function receives the unit of work's cursor and a ``Filter``; none opens a
connection, decides the transaction or computes an embedding. The
``test_tenant_filter`` guard checks that every statement here carries ``tenant_id``
and ``owner_id``.

PT: As escritas: uma função por instrução, todas filtradas por tenant e dono.

Cada função recebe o cursor da unidade de trabalho e um ``Filter``; nenhuma abre
conexão, decide transação ou calcula embedding. A guarda ``test_tenant_filter``
confere que toda instrução daqui carrega ``tenant_id`` e ``owner_id``.
"""

from __future__ import annotations

from datetime import datetime

from memory_lifecycle._sql import COLUMNS, Filter, row_to_version
from memory_lifecycle.connection import Cursor
from memory_lifecycle.exceptions import ConflictError, NotFoundError
from memory_lifecycle.model import MemoryVersion

#: The columns a new version receives, in the order of the INSERTs below.
#: PT: As colunas que uma versão nova recebe, na ordem dos INSERT abaixo.
_INSERT_COLUMNS = (
    "memory_id, tenant_id, owner_id, kind, content, entity_id, context_id, source, "
    "embedding, embedding_model, valid_from, valid_to, recorded_at, previous_version_id"
)
#: What the bounded copy inherits from the source version, without bringing the vector to Python.
#: PT: O que a cópia limitada herda da versão de origem, sem trazer o vetor ao Python.
_INHERITED = (
    "memory_id, tenant_id, owner_id, kind, content, entity_id, context_id, source, "
    "embedding, embedding_model, valid_from"
)

_CURRENT = """
SELECT {columns} FROM {table}
WHERE memory_id = %s::uuid AND superseded_at IS NULL AND tenant_id = %s AND owner_id = %s
ORDER BY valid_from DESC
LIMIT 1
"""

_CLOSE_RECORD = """
UPDATE {table} SET superseded_at = %s
WHERE version_id = %s::uuid AND superseded_at IS NULL AND tenant_id = %s AND owner_id = %s
"""

_BOUNDED_COPY = """
INSERT INTO {table} ({insert})
SELECT {inherited}, %s, %s, version_id FROM {table}
WHERE version_id = %s::uuid AND tenant_id = %s AND owner_id = %s
RETURNING {columns}
"""

_EXPIRE_CONTEXT = """
WITH closed AS (
  UPDATE {table} SET superseded_at = %s
  WHERE context_id = %s AND superseded_at IS NULL AND (valid_to IS NULL OR valid_to > %s)
    AND tenant_id = %s AND owner_id = %s
  RETURNING version_id, {inherited}
), copies AS (
  INSERT INTO {table} ({insert})
  SELECT {inherited}, %s, %s, version_id FROM closed WHERE valid_from < %s
  RETURNING 1
)
SELECT count(*) FROM closed
"""

#: Rounds of ``_EXPIRE_CONTEXT`` before giving up on a context that keeps receiving writes.
#: PT: Rodadas de ``_EXPIRE_CONTEXT`` antes de desistir de um contexto que não para
#: PT: de receber escritas.
_EXPIRE_ROUNDS = 5

_DELETE_MEMORY = """
DELETE FROM {table} WHERE memory_id = %s::uuid AND tenant_id = %s AND owner_id = %s
"""

_DELETE_BY_ENTITY = """
DELETE FROM {table}
WHERE tenant_id = %s AND owner_id = %s AND memory_id IN (
  SELECT memory_id FROM {table} WHERE entity_id = %s AND tenant_id = %s AND owner_id = %s
)
"""

_DELETE_ALL = """
DELETE FROM {table} WHERE tenant_id = %s AND owner_id = %s
"""

_INSERT = """
INSERT INTO {table} (
  memory_id, tenant_id, owner_id, kind, content, entity_id, context_id, source,
  embedding, embedding_model, valid_from, valid_to, recorded_at, previous_version_id
) VALUES (
  COALESCE(%s::uuid, gen_random_uuid()), %s, %s, %s, %s, %s, %s, %s,
  %s::vector, %s, %s, %s, %s, %s::uuid
)
RETURNING {columns}
"""


def insert(  # noqa: PLR0913 — one column per argument, all keyword-only / uma coluna por argumento
    cur: Cursor,
    f: Filter,
    *,
    memory_id: str | None,
    content: str,
    kind: str,
    entity_id: str | None,
    context_id: str | None,
    source: str | None,
    vector: str,
    model: str,
    valid_from: datetime,
    valid_to: datetime | None,
    recorded_at: datetime,
    previous_version_id: str | None,
) -> MemoryVersion:
    """Insert a version; without ``memory_id``, a new memory is born.

    PT: Insere uma versão; sem ``memory_id``, nasce uma memória nova.
    """
    cur.execute(
        _INSERT.format(table=f.table, columns=COLUMNS),
        (
            memory_id,
            f.tenant_id,
            f.owner_id,
            kind,
            content,
            entity_id,
            context_id,
            source,
            vector,
            model,
            valid_from,
            valid_to,
            recorded_at,
            previous_version_id,
        ),
    )
    return row_to_version(cur.fetchone())


def fetch_current(cur: Cursor, f: Filter, memory_id: str) -> MemoryVersion:
    """The current version: open record and greatest ``valid_from`` (ADR 0002).

    PT: A versão vigente: registro aberto e maior ``valid_from`` (ADR 0002).
    """
    cur.execute(
        _CURRENT.format(columns=COLUMNS, table=f.table), (memory_id, f.tenant_id, f.owner_id)
    )
    row = cur.fetchone()
    if row is None:
        raise NotFoundError("memory not found for this tenant and owner")
    return row_to_version(row)


def close_record(cur: Cursor, f: Filter, version_id: str, now: datetime) -> None:
    """Close ``superseded_at``; if another writer closed it first, ``ConflictError``.

    This is the concurrency lock: the second writer waits for the row lock and, after
    the first one commits, re-evaluates the ``WHERE`` and affects zero rows.

    PT: Fecha ``superseded_at``; se outro escritor fechou antes, ``ConflictError``.

    É a trava de concorrência: o segundo escritor espera o lock da linha e, depois
    do commit do primeiro, reavalia o ``WHERE`` e afeta zero linhas.
    """
    cur.execute(_CLOSE_RECORD.format(table=f.table), (now, version_id, f.tenant_id, f.owner_id))
    if cur.rowcount != 1:
        raise ConflictError(
            "another write changed this memory first; reread with history and decide"
        )


def insert_bounded_copy(
    cur: Cursor, f: Filter, from_version_id: str, valid_to: datetime, now: datetime
) -> MemoryVersion:
    """Insert the copy of ``from_version_id`` with ``valid_to``, linked to it; the vector stays in the database.

    PT: Insere a cópia de ``from_version_id`` com ``valid_to``, ligada a ela; o vetor fica no banco.
    """
    cur.execute(
        _BOUNDED_COPY.format(
            table=f.table, insert=_INSERT_COLUMNS, inherited=_INHERITED, columns=COLUMNS
        ),
        (valid_to, now, from_version_id, f.tenant_id, f.owner_id),
    )
    return row_to_version(cur.fetchone())


def expire_context(
    cur: Cursor, f: Filter, context_id: str, valid_to: datetime, now: datetime
) -> int:
    """Expire at ``valid_to`` every current belief of the context that would hold afterwards; return how many.

    Closes each one's record and, for those already started, inserts the bounded copy;
    those that would only start later get no copy, because they never held. Runs at
    least twice and repeats until nothing changes: under READ COMMITTED the new version
    of a concurrent ``supersede`` is not in the first round's snapshot.

    PT: Encerra em ``valid_to`` toda crença atual do contexto que valeria depois; devolve quantas.

    Fecha o registro de cada uma e, nas que já começaram, insere a cópia limitada;
    as que só começariam depois ficam sem cópia, porque nunca valeram. Roda ao
    menos duas vezes e repete até nada mudar: em READ COMMITTED a versão nova de
    um ``supersede`` concorrente não está no instantâneo da primeira rodada.
    """
    total = 0
    for round_number in range(_EXPIRE_ROUNDS):
        cur.execute(
            _EXPIRE_CONTEXT.format(table=f.table, insert=_INSERT_COLUMNS, inherited=_INHERITED),
            (now, context_id, valid_to, f.tenant_id, f.owner_id, valid_to, now, valid_to),
        )
        row = cur.fetchone()
        expired = int(row[0]) if row else 0
        # A round that waited for another writer's lock may expire nothing and still
        # leave that writer's new version behind: only the next round sees it.
        # PT: Uma rodada que esperou o lock de outro escritor pode não encerrar nada e,
        # PT: ainda assim, haver a versão nova dele: só a rodada seguinte a enxerga.
        if expired == 0 and round_number > 0:
            return total
        total += expired
    raise ConflictError(
        f"context {context_id!r} kept receiving writes during the invalidation; try again"
    )


def delete(
    cur: Cursor, f: Filter, *, memory_id: str | None, entity_id: str | None, everything: bool
) -> int:
    """Physically delete every version of the target; by entity, the whole memory goes.

    PT: Apaga fisicamente toda versão do alvo; por entidade, a memória inteira sai.
    """
    if memory_id is not None:
        cur.execute(_DELETE_MEMORY.format(table=f.table), (memory_id, f.tenant_id, f.owner_id))
    elif entity_id is not None:
        cur.execute(
            _DELETE_BY_ENTITY.format(table=f.table),
            (f.tenant_id, f.owner_id, entity_id, f.tenant_id, f.owner_id),
        )
    elif everything:
        cur.execute(_DELETE_ALL.format(table=f.table), (f.tenant_id, f.owner_id))
    else:
        return 0
    return cur.rowcount
