"""The reads of ``Memory``: ``recall`` and ``history``.

Split from ``api.py`` only for size (CLAUDE.md, Tamanho de arquivo); library users
call ``Memory.recall`` and ``Memory.history``.

PT: As leituras de ``Memory``: ``recall`` e ``history``.

Separadas de ``api.py`` só pelo tamanho (CLAUDE.md, Tamanho de arquivo); quem
usa a biblioteca chama ``Memory.recall`` e ``Memory.history``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from memory_lifecycle import retrieval, temporal
from memory_lifecycle._core import DEFAULT_RECALL_LIMIT, Core
from memory_lifecycle._sql import is_uuid
from memory_lifecycle.connection._unit_of_work import unit_of_work
from memory_lifecycle.exceptions import InvalidArgumentError, NotFoundError
from memory_lifecycle.model import MemoryVersion, RecallResult


class Reads(Core):
    """``recall`` and ``history``, on top of the ``Memory`` core.

    PT: ``recall`` e ``history``, sobre o núcleo da ``Memory``.
    """

    def recall(
        self,
        owner_id: str,
        *,
        query: str | None = None,
        contexts: Sequence[str | None] | None = None,
        entities: Sequence[str | None] | None = None,
        kind: str | None = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        as_of: datetime | None = None,
        known_at: datetime | None = None,
    ) -> list[RecallResult]:
        """Return the owner's memories that fit the requested scope and moment.

        **Scope** belongs to the application, and it is strict: ``contexts`` and
        ``entities`` are the ids active in this query. A version is returned only if its
        ``context_id`` is in ``contexts``; ``None`` as a list member includes the
        versions with no context (``contexts=["p-2027", None]``). ``contexts=None``
        means "do not filter on this axis"; ``[]`` returns nothing on this axis. Same
        rule for entities. Leaving an id out of scope is not a write: the memory stays.

        **Moment** picks one of three modes: no argument is "what is true now";
        ``as_of`` is "what was true at that instant, as we know it today"; ``known_at``
        is "what, at that instant, the system knew to be true at that instant" — what
        the agent knew when it answered. Both together raise ``InvalidArgumentError``.

        With ``query`` the results are ordered by similarity and carry ``score``;
        without it, by ``recorded_at`` descending with ``score=None``. ``limit`` must be
        positive. The query's embedding is computed before obtaining a connection. The
        vector search is exact and reads the vector of every version that passes the
        filters (ADR 0009): pass the scope for owners with many memories.

        PT: Devolve as memórias do dono que cabem no escopo e no momento pedidos.

        **Escopo** é da aplicação, e é estrito: ``contexts`` e ``entities`` são
        os ids ativos nesta consulta. Uma versão é devolvida só se o seu
        ``context_id`` está em ``contexts``; ``None`` como membro da lista
        inclui as versões sem contexto (``contexts=["p-2027", None]``).
        ``contexts=None`` significa "não filtrar por este eixo"; ``[]`` não
        devolve nada neste eixo. Mesma regra para entidades. Deixar um id fora do
        escopo não é uma escrita: a memória fica.

        **Momento** escolhe um de três modos: nenhum argumento é "o que é verdade
        agora"; ``as_of`` é "o que era verdade naquele instante, pelo que sabemos
        hoje"; ``known_at`` é "o que, naquele instante, o sistema sabia ser verdade
        naquele instante" — o que o agente sabia quando respondeu. Os dois juntos
        levantam ``InvalidArgumentError``.

        Com ``query`` os resultados vêm ordenados por similaridade e carregam
        ``score``; sem ela, por ``recorded_at`` decrescente com ``score=None``.
        ``limit`` deve ser positivo. O embedding da consulta é calculado antes de
        obter uma conexão. A busca vetorial é exata e lê o vetor de cada versão que
        passa nos filtros (ADR 0009): passe o escopo para donos com muitas memórias.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise InvalidArgumentError("limit must be a positive integer")
        moment = temporal.resolve_moment(temporal.resolve_now(self.clock), as_of, known_at)
        context_axis = retrieval.build_axis(contexts)
        entity_axis = retrieval.build_axis(entities)
        if query is not None:
            temporal.require_text("query", query)
        f = self._filter(owner_id)
        query_vector = self._embed(query) if query is not None else None
        with unit_of_work(self.connection) as cur:
            self._prepare(cur, with_vector=query_vector is not None)
            return retrieval.recall(
                cur,
                f,
                moment,
                query_vector=query_vector,
                contexts=context_axis,
                entities=entity_axis,
                kind=kind,
                limit=limit,
            )

    def history(self, owner_id: str, memory_id: str) -> list[MemoryVersion]:
        """Return every version of a memory, by ``recorded_at`` and then ``valid_from``.

        Includes the closed-record versions and the bounded copies that ``expire`` and
        ``supersede`` insert. A version's successor is the one whose
        ``previous_version_id`` equals its ``version_id``; pass it to ``derive_status``
        to label. Raises ``NotFoundError`` when no version exists for this tenant and
        owner.

        PT: Devolve toda versão de uma memória, por ``recorded_at`` e depois ``valid_from``.

        Inclui as versões de registro fechado e as cópias limitadas que ``expire``
        e ``supersede`` inserem. A sucessora de uma versão é a que tem
        ``previous_version_id`` igual ao seu ``version_id``; passe-a a
        ``derive_status`` para rotular. Levanta ``NotFoundError`` quando não
        existe versão para este tenant e dono.
        """
        f = self._filter(owner_id)
        if not is_uuid(memory_id):
            raise NotFoundError("memory not found for this tenant and owner")
        with unit_of_work(self.connection) as cur:
            self._prepare(cur, with_vector=False)
            return retrieval.history(cur, f, memory_id)
