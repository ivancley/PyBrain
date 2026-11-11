"""The library's typed errors, all in a single module.

Callers catch ``MemoryLifecycleError`` to handle anything the library raises, or a
subclass to handle one situation. The type says what happened and whether retrying
helps; the message says where. No code path raises a bare ``Exception``
(CLAUDE.md § Convenções).

PT: Os erros tipados da biblioteca, todos num único módulo.

Quem chama captura ``MemoryLifecycleError`` para tratar qualquer coisa que a
biblioteca levante, ou uma subclasse para tratar uma situação. O tipo diz o que
aconteceu e se repetir ajuda; a mensagem diz onde. Nenhum caminho de código
levanta um ``Exception`` puro (CLAUDE.md § Convenções).
"""

from __future__ import annotations


class MemoryLifecycleError(Exception):
    """Base of every error raised by the library.

    PT: Base de todo erro levantado pela biblioteca.
    """


class InvalidArgumentError(MemoryLifecycleError, ValueError):
    """The caller passed something the contract forbids.

    Examples: a naive ``datetime``, ``as_of`` and ``known_at`` together, a ``forget``
    without a target, an empty ``content``. It is also a ``ValueError`` so that generic
    input validation keeps catching it.

    PT: Quem chamou passou algo que o contrato proíbe.

    Exemplos: um ``datetime`` sem fuso, ``as_of`` e ``known_at`` juntos, um
    ``forget`` sem alvo, um ``content`` vazio. Também é ``ValueError`` para que
    uma validação genérica de entrada continue capturando.
    """


class NotFoundError(MemoryLifecycleError):
    """There is no current version of the memory for this tenant and owner.

    Raised by ``supersede``, ``correct``, ``expire`` and ``history`` when the
    ``memory_id`` is unknown, belongs to someone else, or was forgotten. The message
    never says which of the three, so that a cross-tenant probe learns nothing.

    PT: Não existe versão vigente da memória para este tenant e dono.

    Levantado por ``supersede``, ``correct``, ``expire`` e ``history`` quando o
    ``memory_id`` é desconhecido, pertence a outro, ou foi esquecido. A mensagem
    nunca diz qual dos três, para que uma sondagem entre tenants não aprenda nada.
    """


class ConflictError(MemoryLifecycleError):
    """The version to close was closed first by another writer.

    Closing a time bound is conditional on the bound still being open; zero affected
    rows means another writer won. Also raised when ``expected_version_id`` no longer
    names the current version. The caller rereads and decides; the library never
    retries on its own.

    PT: A versão a fechar foi fechada antes por outro escritor.

    Fechar um limite de tempo é condicional ao limite ainda estar aberto; zero
    linhas afetadas significa que outro escritor venceu. Também levantado quando
    ``expected_version_id`` já não nomeia a versão vigente. Quem chamou relê e
    decide; a biblioteca nunca tenta de novo por conta própria.
    """


class EmbeddingError(MemoryLifecycleError):
    """The embedding provider could not produce a vector (usually transient).

    PT: O provedor de embeddings não conseguiu produzir um vetor (em geral, transitório).
    """


class EmbeddingDimensionError(EmbeddingError):
    """The provider's dimension differs from the one recorded in the schema (permanent).

    A different model, or the same model reconfigured, cannot share the vector column.
    The fix is a new schema or re-embedding, never a silent cast.

    PT: A dimensão do provedor difere da registrada no schema (permanente).

    Um modelo diferente, ou o mesmo modelo reconfigurado, não pode compartilhar a
    coluna de vetores. A solução é um schema novo ou reprocessar os embeddings,
    nunca um cast silencioso.
    """


class ConfigurationError(MemoryLifecycleError):
    """The library cannot run as configured.

    Examples: the schema was never migrated, the connection provider named by the
    environment does not load, the provider does not honor the protocol.

    PT: A biblioteca não consegue rodar como foi configurada.

    Exemplos: o schema nunca foi migrado, o provedor de conexão nomeado pelo
    ambiente não carrega, o provedor não honra o protocolo.
    """


class ExtraNotInstalledError(ConfigurationError, ImportError):
    """An optional dependency is missing; the message names the extra to install.

    PT: Falta uma dependência opcional; a mensagem nomeia o extra a instalar.
    """


class MigrationError(MemoryLifecycleError):
    """The migration set is inconsistent: an applied file changed or a number is duplicated.

    PT: O conjunto de migrações é inconsistente: arquivo aplicado alterado ou número duplicado.
    """
