"""The reads: ``recall`` and ``history``.

Every statement filters tenant and owner before any other predicate (guard
``test_tenant_filter``). The scope is strict (ADR 0003): ``None`` as a list member
includes the versions with no context or no entity. Nothing here writes.

PT: As leituras: ``recall`` e ``history``.

Toda instrução filtra tenant e dono antes de qualquer outro predicado (guarda
``test_tenant_filter``). O escopo é estrito (ADR 0003): ``None`` como membro da
lista inclui as versões sem contexto ou sem entidade. Nada aqui escreve.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any

from memory_lifecycle._sql import COLUMNS, Filter, predicate, row_to_version
from memory_lifecycle.connection import Cursor
from memory_lifecycle.exceptions import InvalidArgumentError, NotFoundError
from memory_lifecycle.model import MemoryVersion, RecallResult
from memory_lifecycle.temporal import Moment

_RECALL = """
SELECT {selection} FROM {table} AS v
WHERE tenant_id = %s AND owner_id = %s AND {filters}
ORDER BY {order}
LIMIT %s
"""
_SCORE = ", 1 - (embedding <=> %s::vector) / 2"
# `v.version_id` qualified: without the alias, `version_id` would be the output column
# `version_id::text`, and the tie-break would not use the `ix_versions_record_order` index.
# PT: `v.version_id` qualificado: sem o alias, `version_id` seria a coluna de saída
# PT: `version_id::text`, e o desempate não usaria o índice `ix_versions_record_order`.
_ORDER_BY_SIMILARITY = "v.embedding <=> %s::vector, v.recorded_at DESC, v.version_id"
_ORDER_BY_RECORD = "v.recorded_at DESC, v.version_id"
_CONTEXT_FILTER = "(context_id = ANY(%s::text[]) OR (%s AND context_id IS NULL))"
_ENTITY_FILTER = "(entity_id = ANY(%s::text[]) OR (%s AND entity_id IS NULL))"
_KIND_FILTER = "kind = %s"

#: How many ``COLUMNS`` columns form the version; the score, when present, comes after.
#: PT: Quantas colunas de ``COLUMNS`` formam a versão; a pontuação, quando há, vem depois.
_VERSION_FIELDS = len(fields(MemoryVersion))

_HISTORY = """
SELECT {columns} FROM {table}
WHERE memory_id = %s::uuid AND tenant_id = %s AND owner_id = %s
ORDER BY recorded_at, valid_from, superseded_at IS NULL, version_id
"""


@dataclass(frozen=True, slots=True)
class ScopeAxis:
    """One already-resolved scope axis: the ids and whether versions without an id are included.

    PT: Um eixo do escopo já resolvido: os ids e se as versões sem id entram.
    """

    ids: tuple[str, ...]
    include_null: bool


def build_axis(values: Sequence[str | None] | None) -> ScopeAxis | None:
    """``None`` does not filter; ``[]`` returns nothing; ``["a", None]`` is ``a`` plus those without an id.

    PT: ``None`` não filtra; ``[]`` não devolve nada; ``["a", None]`` é ``a`` e os sem id.
    """
    if values is None:
        return None
    if isinstance(values, str):
        raise InvalidArgumentError("the scope is a list of ids, not a string: use contexts=[...]")
    ids = tuple(value for value in values if value is not None)
    return ScopeAxis(ids=ids, include_null=any(value is None for value in values))


def recall(  # noqa: PLR0913 — the query's filters, all keyword-only / os filtros da consulta
    cur: Cursor,
    f: Filter,
    moment: Moment,
    *,
    query_vector: str | None,
    contexts: ScopeAxis | None,
    entities: ScopeAxis | None,
    kind: str | None,
    limit: int,
) -> list[RecallResult]:
    """One statement: tenant and owner, the mode's predicate, the scope, the kind and the order.

    PT: Uma instrução: tenant e dono, o predicado do modo, o escopo, a categoria e a ordem.
    """
    mode_text, mode_parameters = predicate(moment)
    filters = [mode_text]
    filter_parameters: list[Any] = [*mode_parameters]
    for text, axis in ((_CONTEXT_FILTER, contexts), (_ENTITY_FILTER, entities)):
        if axis is not None:
            filters.append(text)
            filter_parameters += [list(axis.ids), axis.include_null]
    if kind is not None:
        filters.append(_KIND_FILTER)
        filter_parameters.append(kind)

    with_query = query_vector is not None
    sql = _RECALL.format(
        selection=COLUMNS + (_SCORE if with_query else ""),
        table=f.table,
        filters=" AND ".join(filters),
        order=_ORDER_BY_SIMILARITY if with_query else _ORDER_BY_RECORD,
    )
    parameters: list[Any] = [query_vector] if with_query else []
    parameters += [f.tenant_id, f.owner_id, *filter_parameters]
    parameters += [query_vector] if with_query else []
    parameters.append(limit)
    cur.execute(sql, parameters)
    return [
        RecallResult(
            version=row_to_version(row[:_VERSION_FIELDS]),
            score=float(row[_VERSION_FIELDS]) if with_query else None,
        )
        for row in cur.fetchall()
    ]


def history(cur: Cursor, f: Filter, memory_id: str) -> list[MemoryVersion]:
    """Every version of this tenant and owner's memory; none is ``NotFoundError``.

    On a ``recorded_at`` tie, the one with the smaller ``valid_from`` comes first and,
    on a tie of both, the closed record before the open one: the current version is
    always last, even with a frozen clock.

    PT: Toda versão da memória deste tenant e dono; nenhuma é ``NotFoundError``.

    No empate de ``recorded_at``, vem antes a de ``valid_from`` menor e, no
    empate dos dois, a de registro fechado antes da aberta: a vigente é sempre a
    última, mesmo com o relógio congelado.
    """
    cur.execute(
        _HISTORY.format(columns=COLUMNS, table=f.table),
        (memory_id, f.tenant_id, f.owner_id),
    )
    versions = [row_to_version(row) for row in cur.fetchall()]
    if not versions:
        raise NotFoundError("memory not found for this tenant and owner")
    return versions
