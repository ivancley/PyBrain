"""The public surface: a ``Memory`` bound to a tenant, a connection provider and an embedding provider.

Every method takes ``owner_id`` because every statement filters tenant and owner
(CLAUDE.md, regra 1). Every ``datetime`` going in or out is timezone-aware; a naive
one is ``InvalidArgumentError``. Each operation computes the embedding before asking
for the connection, validates what can be validated before the first statement and
runs in a unit of work (``connection/_unit_of_work.py``).

PT: A superfície pública: uma ``Memory`` ligada a um tenant, um provedor de conexão e um de embeddings.

Todo método recebe ``owner_id`` porque toda instrução filtra tenant e dono
(CLAUDE.md, regra 1). Todo ``datetime`` que entra ou sai tem fuso; um sem fuso é
``InvalidArgumentError``. Cada operação calcula o embedding antes de pedir a
conexão, valida o que dá para validar antes da primeira instrução e roda numa
unidade de trabalho (``connection/_unit_of_work.py``).
"""

from __future__ import annotations

from datetime import datetime

from memory_lifecycle import migrations, store, temporal
from memory_lifecycle._core import DEFAULT_RECALL_LIMIT, DEFAULT_SCHEMA, Change
from memory_lifecycle._reads import Reads
from memory_lifecycle._sql import is_uuid
from memory_lifecycle.connection._unit_of_work import unit_of_work
from memory_lifecycle.exceptions import InvalidArgumentError
from memory_lifecycle.model import MemoryVersion


class Memory(Reads):
    """Persistent, contextual and bitemporal memory for one tenant.

    Build one per tenant, usually once per process, and share it: it holds no
    connection, only the provider that lends one per operation. ``clock`` exists so a
    test can place writes at chosen instants; in production it stays empty and the
    library uses the current UTC time.

    The construction arguments, the internal steps and the reads live in ``_core.py``
    and ``_reads.py`` only for size; this class is the surface.

    PT: Memória persistente, contextual e bitemporal de um tenant.

    Construa uma por tenant, em geral uma vez por processo, e compartilhe: ela
    não segura conexão, só o provedor que empresta uma por operação. ``clock``
    existe para que um teste coloque escritas em instantes escolhidos; em
    produção fica vazio e a biblioteca usa o horário UTC atual.

    Os argumentos de construção, os passos internos e as leituras moram em
    ``_core.py`` e ``_reads.py`` só por tamanho; esta classe é a superfície.
    """

    def migrate(self) -> int:
        """Create the schema and apply the pending migrations; return how many were applied.

        Idempotent: a second call applies nothing. The vector dimension comes from
        ``embeddings.dimension`` and is recorded; a later provider with another
        dimension raises ``EmbeddingDimensionError`` on the first write. Raises
        ``MigrationError`` when an applied file changed on disk.

        PT: Cria o schema e aplica as migrações pendentes; devolve quantas aplicou.

        Idempotente: uma segunda chamada não aplica nada. A dimensão do vetor vem
        de ``embeddings.dimension`` e fica registrada; um provedor posterior com
        outra dimensão levanta ``EmbeddingDimensionError`` na primeira escrita.
        Levanta ``MigrationError`` quando um arquivo aplicado mudou em disco.
        """
        with unit_of_work(self.connection) as cur:
            return migrations.apply(cur, self.schema, self.embeddings.dimension)

    # -------------------------------------------------------------- writes / escritas

    def remember(
        self,
        owner_id: str,
        content: str,
        *,
        kind: str,
        entity_id: str | None = None,
        context_id: str | None = None,
        source: str | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> MemoryVersion:
        """Record a new memory and return its first version.

        ``valid_from`` defaults to now; an open ``valid_to`` means "still true". Without
        ``entity_id`` or ``context_id`` the memory only shows up in ``recall`` when the
        scope includes ``None`` on that axis. The embedding is computed before obtaining
        a connection. Raises ``InvalidArgumentError`` on an empty ``content`` or
        ``valid_to <= valid_from``; ``EmbeddingError`` when the provider fails.

        PT: Registra uma memória nova e devolve sua primeira versão.

        ``valid_from`` vale agora por padrão; ``valid_to`` aberto significa "ainda
        é verdade". Sem ``entity_id`` ou ``context_id`` a memória só aparece em
        ``recall`` quando o escopo inclui ``None`` naquele eixo. O embedding é
        calculado antes de obter uma conexão. Levanta ``InvalidArgumentError``
        com ``content`` vazio ou ``valid_to <= valid_from``; ``EmbeddingError``
        quando o provedor falha.
        """
        temporal.require_text("content", content)
        temporal.require_text("kind", kind)
        temporal.require_timezone("valid_from", valid_from)
        temporal.require_timezone("valid_to", valid_to)
        now = temporal.resolve_now(self.clock)
        start = valid_from if valid_from is not None else now
        temporal.require_interval(start, valid_to)
        f = self._filter(owner_id)
        vector = self._embed(content)
        with unit_of_work(self.connection) as cur:
            self._prepare(cur, with_vector=True)
            return store.insert(
                cur,
                f,
                memory_id=None,
                content=content,
                kind=kind,
                entity_id=entity_id,
                context_id=context_id,
                source=source,
                vector=vector,
                model=self.embeddings.model_name,
                valid_from=start,
                valid_to=valid_to,
                recorded_at=now,
                previous_version_id=None,
            )

    def supersede(
        self,
        owner_id: str,
        memory_id: str,
        content: str,
        *,
        kind: str | None = None,
        entity_id: str | None = None,
        context_id: str | None = None,
        source: str | None = None,
        valid_from: datetime | None = None,
        expected_version_id: str | None = None,
    ) -> MemoryVersion:
        """Supersede the current version: a new fact takes the old one's place from ``valid_from``.

        Closes the current version's record and inserts two versions: its copy with
        ``valid_to = valid_from`` and the new one, valid since ``valid_from`` (now, by
        default), linked to the copy. No existing row changes beyond the record closing
        (ADR 0002). ``kind``, ``entity_id``, ``context_id`` and ``source`` left as
        ``None`` are copied from the current version. Afterwards, ``recall`` now returns
        the new content and ``recall(as_of=<before>)`` returns the old one. Returns the
        new version.

        ``expected_version_id`` makes the write conditional on that version still being
        the current one. Raises ``NotFoundError`` when there is no current version;
        ``ConflictError`` when another writer closed it first, the expectation does not
        hold or the current version was already expired (use ``remember``);
        ``InvalidArgumentError`` when ``valid_from`` is not later than the current one's.

        PT: Substitui a versão vigente: um fato novo toma o lugar do antigo a partir de ``valid_from``.

        Fecha o registro da vigente e insere duas versões: a cópia dela com
        ``valid_to = valid_from`` e a nova, válida desde ``valid_from`` (agora, por
        padrão), ligada à cópia. Nenhuma linha existente muda além do fechamento do
        registro (ADR 0002). ``kind``, ``entity_id``, ``context_id`` e
        ``source`` deixados em ``None`` são copiados da vigente. Depois,
        ``recall`` agora devolve o conteúdo novo e ``recall(as_of=<antes>)``
        devolve o antigo. Devolve a versão nova.

        ``expected_version_id`` torna a escrita condicional a essa versão ainda ser
        a vigente. Levanta ``NotFoundError`` quando não há versão vigente;
        ``ConflictError`` quando outro escritor fechou antes, a expectativa não vale
        ou a vigente já estava encerrada (use ``remember``);
        ``InvalidArgumentError`` quando ``valid_from`` não é posterior ao da vigente.
        """
        temporal.require_timezone("valid_from", valid_from)
        return self._rewrite(
            owner_id,
            memory_id,
            Change(content, kind, entity_id, context_id, source),
            expected_version_id=expected_version_id,
            correct=False,
            valid_from=valid_from,
        )

    def correct(
        self,
        owner_id: str,
        memory_id: str,
        content: str,
        *,
        kind: str | None = None,
        entity_id: str | None = None,
        context_id: str | None = None,
        source: str | None = None,
        expected_version_id: str | None = None,
    ) -> MemoryVersion:
        """Replace the current version because it was never true: the record was wrong.

        Closes the current version's record and inserts the right one with the **same**
        ``valid_from`` and ``valid_to``, linked to the wrong one. Afterwards,
        ``recall(as_of=<any date>)`` no longer returns the wrong content, while
        ``recall(known_at=<before>)`` still does: the audit trail stays. Same inheritance
        and same errors as ``supersede``.

        PT: Substitui a versão vigente porque ela nunca foi verdade: o registro estava errado.

        Fecha o registro da versão vigente e insere a certa com os **mesmos**
        ``valid_from`` e ``valid_to``, ligada à errada. Depois,
        ``recall(as_of=<qualquer data>)`` não devolve mais o conteúdo errado,
        enquanto ``recall(known_at=<antes>)`` ainda devolve: a trilha de
        auditoria fica. Mesma herança e mesmos erros de ``supersede``.
        """
        return self._rewrite(
            owner_id,
            memory_id,
            Change(content, kind, entity_id, context_id, source),
            expected_version_id=expected_version_id,
            correct=True,
            valid_from=None,
        )

    def expire(
        self,
        owner_id: str,
        memory_id: str,
        *,
        valid_to: datetime | None = None,
        expected_version_id: str | None = None,
    ) -> MemoryVersion:
        """Record that the current version's fact was true and stopped being so at ``valid_to``.

        Closes the current version's record and inserts its copy with ``valid_to`` (now,
        by default), which is the returned version. ``recall`` now stops returning it;
        ``recall(as_of=<while it was true>)`` returns the copy;
        ``recall(known_at=<before the expiry>)`` returns the then-current version, even
        when ``valid_to`` is retroactive. Raises ``NotFoundError``; ``ConflictError``
        when the current version already had ``valid_to``; ``InvalidArgumentError`` when
        ``valid_to`` is not later than ``valid_from``.

        PT: Registra que o fato da versão vigente era verdade e deixou de ser em ``valid_to``.

        Fecha o registro da vigente e insere a cópia dela com ``valid_to`` (agora,
        por padrão), que é a versão devolvida. ``recall`` agora deixa de
        devolvê-la; ``recall(as_of=<enquanto era verdade>)`` devolve a cópia;
        ``recall(known_at=<antes do encerramento>)`` devolve a vigente de então,
        mesmo que ``valid_to`` seja retroativo. Levanta ``NotFoundError``;
        ``ConflictError`` quando a vigente já tinha ``valid_to``;
        ``InvalidArgumentError`` quando ``valid_to`` não é posterior a ``valid_from``.
        """
        temporal.require_timezone("valid_to", valid_to)
        now = temporal.resolve_now(self.clock)
        end = valid_to if valid_to is not None else now
        f = self._filter(owner_id)
        with unit_of_work(self.connection) as cur:
            self._prepare(cur, with_vector=False)
            current = self._current(cur, f, memory_id, expected_version_id)
            temporal.require_validity_close(current, end)
            store.close_record(cur, f, current.version_id, now)
            return store.insert_bounded_copy(cur, f, current.version_id, end, now)

    def invalidate_context(
        self,
        owner_id: str,
        context_id: str,
        *,
        valid_to: datetime | None = None,
    ) -> int:
        """Expire every current, still-open version of the owner in ``context_id``; return how many.

        A convenience over ``expire``, for when the application knows a context ended.
        Every current belief of the context that would still hold after ``valid_to``
        (now, by default) is expired there: one that already started gets the bounded
        copy; one that would only start later has its record closed, with no copy,
        because it never came to hold. Repeats the statement until nothing else changes,
        to reach the version a concurrent ``supersede`` just stored. It is a write the
        application asks for; taking a context out of a ``recall`` scope never calls it.

        PT: Encerra toda versão vigente e ainda aberta do dono em ``context_id``; devolve quantas.

        Uma conveniência sobre ``expire``, para quando a aplicação sabe que um
        contexto acabou. Toda crença atual do contexto que ainda valeria depois de
        ``valid_to`` (agora, por padrão) é encerrada ali: a que já começou ganha a
        cópia limitada; a que só começaria depois tem o registro fechado, sem cópia,
        porque nunca chegou a valer. Repete a instrução até nada mais mudar, para
        alcançar a versão que um ``supersede`` concorrente acabou de gravar. É uma
        escrita que a aplicação pede; tirar um contexto do escopo de um
        ``recall`` nunca chama isto.
        """
        temporal.require_timezone("valid_to", valid_to)
        now = temporal.resolve_now(self.clock)
        end = valid_to if valid_to is not None else now
        temporal.require_text("context_id", context_id)
        f = self._filter(owner_id)
        with unit_of_work(self.connection) as cur:
            self._prepare(cur, with_vector=False)
            return store.expire_context(cur, f, context_id, end, now)

    def forget(
        self,
        owner_id: str,
        *,
        memory_id: str | None = None,
        entity_id: str | None = None,
        everything: bool = False,
    ) -> int:
        """Physically delete every version of the target, in one transaction; return how many.

        The library's only delete (CLAUDE.md, regra 3): a privacy request deletes the
        audit trail too, so ``known_at`` stops returning the target. Exactly one of
        ``memory_id``, ``entity_id`` or ``everything=True`` (all of the owner's memories)
        must be given; otherwise ``InvalidArgumentError``. By ``entity_id``, the whole
        memory goes for every memory in which some version cites the entity, including
        the versions that already cite another: a privacy request leaves no piece behind.
        An unknown target, or one of another owner or tenant, deletes nothing and
        returns ``0``.

        PT: Apaga fisicamente toda versão do alvo, em uma transação; devolve quantas.

        O único delete da biblioteca (CLAUDE.md, regra 3): um pedido de privacidade
        apaga a trilha de auditoria também, então ``known_at`` deixa de devolver o
        alvo. Exatamente um entre ``memory_id``, ``entity_id`` ou ``everything=True``
        (todas as memórias do dono) deve ser dado; senão ``InvalidArgumentError``.
        Por ``entity_id``, sai a memória inteira de toda memória em que alguma
        versão cite a entidade, inclusive as versões que já citam outra: um pedido
        de privacidade não deixa pedaço. Um alvo desconhecido, ou de outro dono ou
        tenant, não apaga nada e devolve ``0``.
        """
        targets = (memory_id is not None) + (entity_id is not None) + bool(everything)
        if targets != 1:
            raise InvalidArgumentError(
                "forget needs exactly one target: memory_id, entity_id or everything=True"
            )
        f = self._filter(owner_id)
        if entity_id is not None:
            temporal.require_text("entity_id", entity_id)
        if memory_id is not None and not is_uuid(memory_id):
            return 0
        with unit_of_work(self.connection) as cur:
            self._prepare(cur, with_vector=False)
            return store.delete(
                cur,
                f,
                memory_id=memory_id,
                entity_id=entity_id,
                everything=everything,
            )


__all__ = ["DEFAULT_RECALL_LIMIT", "DEFAULT_SCHEMA", "Memory"]
