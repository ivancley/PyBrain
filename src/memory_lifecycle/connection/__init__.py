"""The connection provider contract: the application owns the connection.

The library never opens a pool of its own. It asks the provider for a DB-API
connection, runs its statements and either commits (``OWN``) or leaves the
transaction to the application (``PARTICIPATE``). Adapters for DSN, psycopg pool,
Django and SQLAlchemy are optional extras in sibling modules
(``.claude/rules/adapters.md``).

PT: O contrato do provedor de conexão: a aplicação é dona da conexão.

A biblioteca nunca abre um pool próprio. Ela pede ao provedor uma conexão
DB-API, executa suas instruções e ou faz commit (``OWN``) ou deixa a
transação com a aplicação (``PARTICIPATE``). Adaptadores para DSN, pool do
psycopg, Django e SQLAlchemy são extras opcionais em módulos irmãos
(``.claude/rules/adapters.md``).
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Sequence
from contextlib import AbstractContextManager
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from memory_lifecycle.exceptions import ConfigurationError

#: Dotted path (``package.module:function``) of a no-argument callable that returns a
#: ``ConnectionProvider``. Only the path travels through the environment; a pool object
#: never does.
#: PT: Caminho pontuado (``pacote.modulo:funcao``) de um callable sem argumentos que
#: PT: devolve um ``ConnectionProvider``. Só o caminho viaja pelo ambiente; um objeto de
#: PT: pool nunca.
PROVIDER_ENV_VAR = "MEMORY_LIFECYCLE_CONNECTION_PROVIDER"


class TransactionMode(StrEnum):
    """Who commits.

    ``PARTICIPATE``: the application does; the library never calls ``commit`` or
    ``rollback``, so a memory write lands together with the request that caused it. A
    connection in autocommit has no transaction to participate in: the library raises
    ``ConfigurationError`` before writing (ADR 0004). ``OWN``: the library commits on
    success and rolls back on error.

    PT: Quem faz commit.

    ``PARTICIPATE``: a aplicação faz; a biblioteca nunca chama ``commit`` nem
    ``rollback``, então uma escrita de memória entra junto com o request que a
    causou. Uma conexão em autocommit não tem transação para participar: a
    biblioteca levanta ``ConfigurationError`` antes de escrever (ADR 0004).
    ``OWN``: a biblioteca faz commit no sucesso e rollback no erro.
    """

    PARTICIPATE = "participate"
    OWN = "own"


class Cursor(Protocol):
    """The slice of DB-API 2.0 the library uses; psycopg2 and psycopg 3 fit in it.

    PT: A fatia do DB-API 2.0 que a biblioteca usa; psycopg2 e psycopg 3 cabem nela.
    """

    @property
    def rowcount(self) -> int:
        """Rows affected by the last statement; checked on every conditional close.

        PT: Linhas afetadas pela última instrução; conferido em todo fechamento condicional.
        """
        ...

    def execute(self, operation: str, parameters: Sequence[Any] | None = None, /) -> Any:
        """Execute a statement with ``%s`` placeholders; parameters always positional.

        PT: Executa uma instrução com marcadores ``%s``; parâmetros sempre posicionais.
        """
        ...

    def fetchone(self) -> Any:
        """Return the next row or ``None``.

        PT: Devolve a próxima linha ou ``None``.
        """
        ...

    def fetchall(self) -> Sequence[Any]:
        """Return the remaining rows.

        PT: Devolve as linhas restantes.
        """
        ...

    def close(self) -> None:
        """Release the cursor.

        PT: Libera o cursor.
        """
        ...


class Connection(Protocol):
    """The slice of a DB-API 2.0 connection the library uses.

    PT: A fatia de uma conexão DB-API 2.0 que a biblioteca usa.
    """

    def cursor(self) -> Cursor:
        """Open a cursor; the library closes it.

        PT: Abre um cursor; a biblioteca o fecha.
        """
        ...

    def commit(self) -> None:
        """Commit; called only in ``TransactionMode.OWN``.

        PT: Commit; chamado só em ``TransactionMode.OWN``.
        """
        ...

    def rollback(self) -> None:
        """Roll back; called only in ``TransactionMode.OWN``.

        PT: Rollback; chamado só em ``TransactionMode.OWN``.
        """
        ...


@runtime_checkable
class ConnectionProvider(Protocol):
    """Hand a connection to the library and say whether it may commit on it.

    ``connection()`` is a context manager: the library holds the connection only during
    one operation and never during a call to the embedding provider.

    PT: Entrega uma conexão à biblioteca e diz se ela pode fazer commit nela.

    ``connection()`` é um gerenciador de contexto: a biblioteca segura a conexão só
    durante uma operação e nunca durante uma chamada ao provedor de embeddings.
    """

    transaction_mode: TransactionMode

    def connection(self) -> AbstractContextManager[Connection]:
        """Yield a DB-API connection; the provider decides pooling and release.

        PT: Cede uma conexão DB-API; o provedor decide pool e liberação.
        """
        ...


def load_provider(dotted_path: str | None = None) -> ConnectionProvider:
    """Load the provider named by ``dotted_path`` or by ``PROVIDER_ENV_VAR``.

    The path has the form ``package.module:function``, and the function, with no
    arguments, returns the provider; so the app decides pool and configuration in its
    own code, and only the path travels through the environment. Raises
    ``ConfigurationError`` when the path is missing, malformed, does not import, or the
    returned object does not honor ``ConnectionProvider``.

    PT: Carrega o provedor nomeado por ``dotted_path`` ou por ``PROVIDER_ENV_VAR``.

    O caminho tem a forma ``pacote.modulo:funcao``, e a função, sem argumentos,
    devolve o provedor; assim o app decide pool e configuração no seu código, e
    só o caminho viaja pelo ambiente. Levanta ``ConfigurationError`` quando o
    caminho falta, está malformado, não importa, ou o objeto devolvido não honra
    ``ConnectionProvider``.
    """
    path = dotted_path or os.environ.get(PROVIDER_ENV_VAR)
    if not path:
        raise ConfigurationError(
            f"no connection provider: pass one, or set {PROVIDER_ENV_VAR} "
            "to 'package.module:function'"
        )
    module_name, separator, attribute = path.partition(":")
    if not separator or not module_name or not attribute:
        raise ConfigurationError(
            f"malformed provider path: {path!r}; use 'package.module:function'"
        )
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name and module_name.startswith(error.name):
            raise ConfigurationError(
                f"module {module_name!r} of {path!r} does not exist"
            ) from error
        raise ConfigurationError(
            f"module {module_name!r} exists, but its dependency {error.name!r} is missing"
        ) from error
    factory = getattr(module, attribute, None)
    if not callable(factory):
        raise ConfigurationError(f"{path!r} does not point to a function")
    provider = factory()
    if not isinstance(provider, ConnectionProvider):
        raise ConfigurationError(
            f"{path!r} returned {type(provider).__name__}, which is not a ConnectionProvider "
            "(it needs transaction_mode and connection())"
        )
    from memory_lifecycle.connection._unit_of_work import provider_mode

    provider_mode(provider)
    return provider


__all__ = [
    "PROVIDER_ENV_VAR",
    "Connection",
    "ConnectionProvider",
    "Cursor",
    "TransactionMode",
    "load_provider",
]
