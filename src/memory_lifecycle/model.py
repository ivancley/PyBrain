"""The version record and its derived status.

A memory is a ``memory_id`` with many immutable versions. A version carries the
content, the ids that locate it and the two time axes. Nothing here touches the
database; it is the shape every other module exchanges.

PT: O registro de versão e seu status derivado.

Uma memória é um ``memory_id`` com muitas versões imutáveis. Uma versão carrega
o conteúdo, os ids que a localizam e os dois eixos de tempo. Nada aqui toca o
banco; é a forma que todos os outros módulos trocam entre si.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Status(StrEnum):
    """What a version is, read from its time bounds and its successor; never stored.

    PT: O que uma versão é, lido dos seus limites de tempo e da sucessora; nunca armazenado.
    """

    ACTIVE = "active"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    CORRECTED = "corrected"


@dataclass(frozen=True, slots=True)
class MemoryVersion:
    """One row of history: the content, when it was true and when we believed it.

    ``None`` in ``valid_to`` or ``superseded_at`` means *open*, never unknown. Every
    ``datetime`` is timezone-aware. ``entity_id`` and ``context_id`` are opaque: the
    application gives them meaning. Once written, the only thing that changes in the
    row is ``superseded_at`` closing. ``previous_version_id`` points to the version
    whose record the operation that created this one closed (ADR 0002).

    PT: Uma linha do histórico: o conteúdo, quando era verdade e quando acreditamos nele.

    ``None`` em ``valid_to`` ou ``superseded_at`` significa *aberto*, nunca
    desconhecido. Todo ``datetime`` tem fuso. ``entity_id`` e ``context_id``
    são opacos: a aplicação dá o significado. Depois de escrita, a única coisa
    que muda na linha é ``superseded_at`` fechar. ``previous_version_id`` aponta
    para a versão cujo registro a operação que criou esta fechou (ADR 0002).
    """

    version_id: str
    memory_id: str
    tenant_id: str
    owner_id: str
    kind: str
    content: str
    entity_id: str | None
    context_id: str | None
    source: str | None
    embedding_model: str | None
    valid_from: datetime
    valid_to: datetime | None
    recorded_at: datetime
    superseded_at: datetime | None
    previous_version_id: str | None


@dataclass(frozen=True, slots=True)
class RecallResult:
    """One result of ``recall``: the version and how similar it is to the query.

    ``score`` is in ``[0, 1]``, higher is closer, and is ``None`` when the recall had
    no ``query`` (structured filters only).

    PT: Um resultado de ``recall``: a versão e quão parecida ela é com a consulta.

    ``score`` está em ``[0, 1]``, maior é mais próximo, e é ``None`` quando a
    recuperação não teve ``query`` (só filtros estruturados).
    """

    version: MemoryVersion
    score: float | None


def derive_status(
    version: MemoryVersion,
    *,
    now: datetime,
    successor: MemoryVersion | None = None,
) -> Status:
    """Derive a version's status at ``now``; the only place that does it.

    - ``CORRECTED``: record closed and the successor has the same ``valid_from`` and
      ``valid_to`` (the world did not change; the record was wrong).
    - ``SUPERSEDED``: record closed and the successor changes validity (``expire`` or
      ``supersede``), or record open with a successor (a new fact came later).
    - ``EXPIRED``: record open, no successor, ``valid_to`` at or before ``now``.
    - ``ACTIVE``: record open, no successor, not expired at ``now`` (includes one that
      has yet to start).

    ``successor`` is the version whose ``previous_version_id`` is this one, when the
    caller has it (it is in ``history``). A closed record with no known successor
    derives as ``SUPERSEDED``.

    PT: Deriva o status de uma versão em ``now``; o único lugar que faz isso.

    - ``CORRECTED``: registro fechado e a sucessora tem os mesmos ``valid_from`` e
      ``valid_to`` (o mundo não mudou; o registro estava errado).
    - ``SUPERSEDED``: registro fechado e a sucessora muda a validade (``expire``
      ou ``supersede``), ou registro aberto com sucessora (um fato novo veio depois).
    - ``EXPIRED``: registro aberto, sem sucessora, ``valid_to`` em ou antes de ``now``.
    - ``ACTIVE``: registro aberto, sem sucessora, não encerrada em ``now``
      (inclui a que ainda vai começar).

    ``successor`` é a versão cujo ``previous_version_id`` é esta, quando quem chama
    a tem (está em ``history``). Registro fechado sem sucessora conhecida deriva
    como ``SUPERSEDED``.
    """
    if version.superseded_at is not None:
        same_validity = successor is not None and (
            (successor.valid_from, successor.valid_to) == (version.valid_from, version.valid_to)
        )
        return Status.CORRECTED if same_validity else Status.SUPERSEDED
    if successor is not None:
        return Status.SUPERSEDED
    if version.valid_to is not None and version.valid_to <= now:
        return Status.EXPIRED
    return Status.ACTIVE
