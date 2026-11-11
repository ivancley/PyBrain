"""Shared SQL text: identifiers, columns and value conversions.

Values always travel as ``%s``. Identifiers cannot, so the schema name is validated
once by a strict expression and quoted here; no other module builds an identifier.
Vectors and uuids travel as text so that psycopg2 and psycopg 3 behave the same
without a registered adapter (ADR 0007).

PT: O texto SQL compartilhado: identificadores, colunas e conversões de valor.

Valores viajam sempre como ``%s``. Identificadores não podem viajar assim, então o
nome do schema é validado uma vez por uma expressão estrita e citado aqui; nenhum
outro módulo monta identificador. Vetores e uuids viajam como texto para que
psycopg2 e psycopg 3 se comportem igual sem adaptador registrado (ADR 0007).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from memory_lifecycle.exceptions import (
    ConfigurationError,
    ConflictError,
    EmbeddingDimensionError,
    MemoryLifecycleError,
)
from memory_lifecycle.model import MemoryVersion
from memory_lifecycle.temporal import Mode, Moment

_SCHEMA = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

#: Columns in ``MemoryVersion`` order; uuids read as text.
#: PT: Colunas na ordem de ``MemoryVersion``; uuids lidos como texto.
COLUMNS: Final = (
    "version_id::text, memory_id::text, tenant_id, owner_id, kind, content, "
    "entity_id, context_id, source, embedding_model, valid_from, valid_to, "
    "recorded_at, superseded_at, previous_version_id::text"
)


#: Each mode's predicate (ADR 0002) and how many times the instant goes into it.
#: PT: O predicado de cada modo (ADR 0002) e quantas vezes o instante entra nele.
_PREDICATES: Final[Mapping[Mode, tuple[str, int]]] = {
    "as_of": (
        "superseded_at IS NULL AND valid_from <= %s AND (valid_to IS NULL OR valid_to > %s)",
        2,
    ),
    "known_at": (
        "recorded_at <= %s AND (superseded_at IS NULL OR superseded_at > %s) "
        "AND valid_from <= %s AND (valid_to IS NULL OR valid_to > %s)",
        4,
    ),
}


@dataclass(frozen=True, slots=True)
class Filter:
    """Tenant and owner of every statement, and the already-quoted versions table.

    PT: Tenant e dono de toda instrução, e a tabela de versões já citada.
    """

    table: str
    tenant_id: str
    owner_id: str


def validate_schema(name: str) -> str:
    """Return ``name`` if it is a simple identifier; otherwise ``ConfigurationError``.

    PT: Devolve ``name`` se for um identificador simples; senão ``ConfigurationError``.
    """
    if not _SCHEMA.fullmatch(name):
        raise ConfigurationError(
            f"invalid schema name: {name!r}; use lowercase letters, digits and _ "
            "(up to 63 characters, not starting with a digit)"
        )
    return name


def quote(schema: str, obj: str) -> str:
    """Qualified, quoted identifier: ``"schema"."obj"``; only after validating.

    PT: Identificador qualificado e citado: ``"schema"."obj"``; só após validar.
    """
    return f'"{validate_schema(schema)}"."{obj}"'


def vector_as_text(vector: Sequence[float]) -> str:
    """The pgvector text literal, ``[0.1,0.2]``, without losing precision.

    PT: O literal de texto do pgvector, ``[0.1,0.2]``, sem perder precisão.
    """
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"


def row_to_version(row: Sequence[Any]) -> MemoryVersion:
    """Convert a row read with ``COLUMNS`` into the version record.

    PT: Converte uma linha lida com ``COLUMNS`` no registro de versão.
    """
    return MemoryVersion(*row)


def predicate(moment: Moment) -> tuple[str, tuple[datetime, ...]]:
    """The mode's predicate text and its parameters, in ``%s`` order.

    PT: O texto do predicado do modo e os seus parâmetros, na ordem dos ``%s``.
    """
    text, times = _PREDICATES[moment.mode]
    return text, (moment.instant,) * times


def is_uuid(text: str) -> bool:
    """Tell whether ``text`` is a uuid; an invalid id never reaches the database.

    An invalid value in ``%s::uuid`` is a Postgres error and would abort the app's
    transaction in ``PARTICIPATE`` mode; that is why the check happens first, and it
    only accepts the canonical 8-4-4-4-12 form, which Postgres always accepts.

    PT: Diz se ``text`` é um uuid; um id inválido nunca vai ao banco.

    Um valor inválido em ``%s::uuid`` é erro no Postgres e abortaria a transação
    do app no modo ``PARTICIPATE``; por isso a checagem acontece antes, e só aceita
    a forma canônica de 8-4-4-4-12 dígitos, que o Postgres sempre aceita.
    """
    return isinstance(text, str) and _UUID.fullmatch(text) is not None


def normalize_uuid(text: str) -> str:
    """The form in which the database returns a uuid (lowercase), to compare with ``==``.

    PT: A forma em que o banco devolve um uuid (minúsculas), para comparar com ``==``.
    """
    return str(uuid.UUID(text))


def sqlstate(error: BaseException) -> str | None:
    """A driver error's SQLSTATE: ``.sqlstate`` (psycopg 3) or ``.pgcode`` (psycopg2).

    PT: O SQLSTATE de um erro de driver: ``.sqlstate`` (psycopg 3) ou ``.pgcode`` (psycopg2).
    """
    for attribute in ("sqlstate", "pgcode"):
        value = getattr(error, attribute, None)
        if isinstance(value, str):
            return value
    return None


def _constraint(error: BaseException) -> str | None:
    """The violated constraint's name, which both drivers expose in ``error.diag``.

    PT: O nome da restrição violada, que os dois drivers expõem em ``error.diag``.
    """
    return getattr(getattr(error, "diag", None), "constraint_name", None)


def translate(error: BaseException) -> MemoryLifecycleError | None:
    """The typed error a database error means to the caller, or ``None``.

    Only translates what has a known consequence; the rest propagates as it came,
    never swallowed nor renamed to something generic.

    PT: O erro tipado que um erro de banco significa para quem chama, ou ``None``.

    Só traduz o que tem consequência conhecida; o resto sobe como veio, nunca
    engolido nem rebatizado de genérico.
    """
    code = sqlstate(error)
    if code == "23505" and _constraint(error) == "ux_versions_current":
        return ConflictError(
            "another write stored this version first; reread with history and decide"
        )
    if code in ("40001", "40P01"):
        return ConflictError(
            "the database rolled back the operation over a conflict with another transaction "
            "(serialization or deadlock); reread with history and decide"
        )
    if code in ("42P01", "3F000"):
        return ConfigurationError(
            "the memory schema does not exist or was not migrated; call Memory.migrate()"
        )
    if code == "22000" and "dimensions" in str(error):
        return EmbeddingDimensionError(
            "the vector does not have the schema column's dimension; the embedding provider changed"
        )
    return None
