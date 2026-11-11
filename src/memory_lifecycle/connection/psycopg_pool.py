"""``PsycopgPoolProvider``: borrows connections from a psycopg pool the app already has.

The app builds and opens the ``psycopg_pool.ConnectionPool`` (``psycopg`` extra); the
library takes one connection per operation and gives it back at the end. A pool
connection carries nobody's transaction, so the mode is always ``OWN``: to take part
in a request's transaction, use the framework adapter.

PT: ``PsycopgPoolProvider``: empresta conexões de um pool do psycopg que o app já tem.

O app constrói e abre o ``psycopg_pool.ConnectionPool`` (extra ``psycopg``); a
biblioteca pega uma conexão por operação e a devolve ao fim. Uma conexão de pool
não carrega a transação de ninguém, então o modo é sempre ``OWN``: para
participar da transação de um request, use o adaptador do framework.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Connection, TransactionMode
from memory_lifecycle.exceptions import ExtraNotInstalledError


class PsycopgPoolProvider:
    """Provider over a ``psycopg_pool.ConnectionPool`` opened by the app.

    PT: Provedor sobre um ``psycopg_pool.ConnectionPool`` aberto pelo app.
    """

    transaction_mode = TransactionMode.OWN

    def __init__(self, pool: Any) -> None:
        try:
            import psycopg_pool  # noqa: F401 — only to give the extra's message early / só para avisar cedo
        except ModuleNotFoundError as error:
            if (error.name or "").partition(".")[0] not in {"psycopg_pool", "psycopg"}:
                raise
            raise ExtraNotInstalledError(
                'PsycopgPoolProvider needs psycopg-pool: pip install "memory-lifecycle[psycopg]"'
            ) from error
        self._pool = pool

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Borrow a connection from the pool for the duration of one operation.

        PT: Empresta uma conexão do pool pela duração de uma operação.
        """
        with self._pool.connection() as connection:
            yield connection
