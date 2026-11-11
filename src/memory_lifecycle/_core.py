"""The core of ``Memory``: construction and the steps shared by every operation.

Split from ``api.py`` only for size (CLAUDE.md, Tamanho de arquivo): here lives what
no user calls — the tenant and owner filter, the schema check, the embedding before
the connection, a memory's current version and the skeleton of ``supersede`` and
``correct``. The public surface is ``api.Memory``.

PT: O núcleo de ``Memory``: construção e os passos comuns a toda operação.

Separado de ``api.py`` só pelo tamanho (CLAUDE.md, Tamanho de arquivo): aqui fica
o que nenhum usuário chama — o filtro de tenant e dono, a conferência do schema,
o embedding antes da conexão, a vigente de uma memória e o esqueleto de
``supersede`` e ``correct``. A superfície pública é ``api.Memory``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from memory_lifecycle import migrations, store, temporal
from memory_lifecycle._sql import (
    Filter,
    is_uuid,
    normalize_uuid,
    quote,
    validate_schema,
    vector_as_text,
)
from memory_lifecycle.connection import ConnectionProvider, Cursor
from memory_lifecycle.connection._unit_of_work import unit_of_work
from memory_lifecycle.embeddings import EmbeddingProvider, vectorize
from memory_lifecycle.exceptions import (
    ConflictError,
    EmbeddingDimensionError,
    InvalidArgumentError,
    NotFoundError,
)
from memory_lifecycle.model import MemoryVersion

#: The PostgreSQL schema where the library keeps its tables, inside the app's database.
#: PT: O schema PostgreSQL em que a biblioteca mantém suas tabelas, dentro do banco do app.
DEFAULT_SCHEMA = "memory_lifecycle"

#: ``recall`` always has a limit; this is the one used when the caller gives none.
#: PT: ``recall`` sempre tem limite; este é o usado quando quem chama não dá nenhum.
DEFAULT_RECALL_LIMIT = 20


@dataclass(frozen=True, slots=True)
class Change:
    """What ``supersede`` and ``correct`` bring; ``None`` inherits from the current version.

    PT: O que ``supersede`` e ``correct`` trazem; ``None`` herda da versão vigente.
    """

    content: str
    kind: str | None
    entity_id: str | None
    context_id: str | None
    source: str | None


def _or(new: str | None, inherited: str | None) -> str | None:
    return new if new is not None else inherited


class Core:
    """The base of ``Memory``: instance state and the operations' internal steps.

    PT: A base de ``Memory``: estado da instância e passos internos das operações.
    """

    def __init__(
        self,
        *,
        connection: ConnectionProvider,
        embeddings: EmbeddingProvider,
        tenant_id: str,
        schema: str = DEFAULT_SCHEMA,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        temporal.require_text("tenant_id", tenant_id)
        self.connection = connection
        self.embeddings = embeddings
        self.tenant_id = tenant_id
        self.schema = validate_schema(schema)
        self.clock = clock
        self._table = quote(self.schema, "memory_versions")
        self._recorded_dimension: int | None = None

    def _filter(self, owner_id: str) -> Filter:
        """The operation's tenant and owner; an invalid ``owner_id`` is rejected before the connection.

        PT: Tenant e dono da operação; ``owner_id`` inválido é recusado antes da conexão.
        """
        temporal.require_text("owner_id", owner_id)
        return Filter(table=self._table, tenant_id=self.tenant_id, owner_id=owner_id)

    def _prepare(self, cur: Cursor, *, with_vector: bool) -> None:
        """First statement of every operation: check the schema and, with a vector, the dimension.

        Reads ``settings`` once per instance, via ``to_regclass``: an unmigrated schema
        becomes ``ConfigurationError`` without any statement failing, which in
        ``PARTICIPATE`` mode would abort the app's transaction.

        PT: Primeira instrução de toda operação: confere o schema e, com vetor, a dimensão.

        Lê ``settings`` uma vez por instância, via ``to_regclass``: um schema
        não migrado vira ``ConfigurationError`` sem nenhuma instrução falhar, o que
        no modo ``PARTICIPATE`` abortaria a transação do app.
        """
        if self._recorded_dimension is None:
            self._recorded_dimension = migrations.read_dimension(cur, self.schema)
        if with_vector and self._recorded_dimension != self.embeddings.dimension:
            raise EmbeddingDimensionError(
                f"schema {self.schema!r} stores {self._recorded_dimension}-dimensional "
                f"vectors; the embedding provider produces {self.embeddings.dimension}"
            )

    def _embed(self, text: str) -> str:
        """The text's embedding, as a pgvector literal; always before the connection.

        PT: Embedding do texto, como literal do pgvector; sempre antes da conexão.
        """
        [vector] = vectorize(self.embeddings, [text])
        return vector_as_text(vector)

    @staticmethod
    def _current(
        cur: Cursor, f: Filter, memory_id: str, expected_version_id: str | None
    ) -> MemoryVersion:
        """The memory's current version; an invalid id never reaches the database (see ``is_uuid``).

        PT: A vigente da memória; um id inválido não vai ao banco (ver ``is_uuid``).
        """
        if not is_uuid(memory_id):
            raise NotFoundError("memory not found for this tenant and owner")
        if expected_version_id is not None and not is_uuid(expected_version_id):
            raise InvalidArgumentError("expected_version_id must be a uuid")
        current = store.fetch_current(cur, f, memory_id)
        if expected_version_id is not None and current.version_id != normalize_uuid(
            expected_version_id
        ):
            raise ConflictError(
                "the current version is no longer the expected one; reread with history and decide"
            )
        return current

    def _rewrite(
        self,
        owner_id: str,
        memory_id: str,
        change: Change,
        *,
        expected_version_id: str | None,
        correct: bool,
        valid_from: datetime | None,
    ) -> MemoryVersion:
        """The skeleton of ``supersede`` (with a bounded copy) and ``correct`` (without one).

        On a correction, the new version inherits the current one's bounds and points to
        it. On a supersession, the current version gets the bounded copy up to
        ``valid_from`` (now, by default) and the new one starts there, pointing to the
        copy (ADR 0002).

        PT: O esqueleto de ``supersede`` (com cópia limitada) e ``correct`` (sem ela).

        Na correção, a versão nova herda os limites da vigente e aponta para ela. Na
        substituição, a vigente ganha a cópia limitada até ``valid_from`` (o agora,
        por padrão) e a nova começa ali, apontando para a cópia (ADR 0002).
        """
        temporal.require_text("content", change.content)
        if change.kind is not None:
            temporal.require_text("kind", change.kind)
        now = temporal.resolve_now(self.clock)
        f = self._filter(owner_id)
        vector = self._embed(change.content)
        with unit_of_work(self.connection) as cur:
            self._prepare(cur, with_vector=True)
            current = self._current(cur, f, memory_id, expected_version_id)
            if correct:
                start, end, previous_id = current.valid_from, current.valid_to, current.version_id
                store.close_record(cur, f, current.version_id, now)
            else:
                start, end = (valid_from if valid_from is not None else now), None
                temporal.require_validity_close(current, start)
                store.close_record(cur, f, current.version_id, now)
                copy = store.insert_bounded_copy(cur, f, current.version_id, start, now)
                previous_id = copy.version_id
            return store.insert(
                cur,
                f,
                memory_id=current.memory_id,
                content=change.content,
                kind=change.kind or current.kind,
                entity_id=_or(change.entity_id, current.entity_id),
                context_id=_or(change.context_id, current.context_id),
                source=_or(change.source, current.source),
                vector=vector,
                model=self.embeddings.model_name,
                valid_from=start,
                valid_to=end,
                recorded_at=now,
                previous_version_id=previous_id,
            )
