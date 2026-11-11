"""``DSNProvider``: one connection of its own per operation, from a DSN.

For scripts, jobs and tests, where there is no application pool to borrow from. Opens
with psycopg 3 (``psycopg`` extra), always in ``OWN`` mode and with autocommit off,
and closes the connection at the end of each operation.

PT: ``DSNProvider``: uma conexão própria por operação, a partir de um DSN.

Para scripts, jobs e testes, onde não há pool da aplicação para emprestar. Abre
com psycopg 3 (extra ``psycopg``), sempre no modo ``OWN`` e com autocommit
desligado, e fecha a conexão ao fim de cada operação.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Connection, TransactionMode
from memory_lifecycle.exceptions import ExtraNotInstalledError


class DSNProvider:
    """Connection provider by DSN; do not use inside a request that already has a pool.

    PT: Provedor de conexão por DSN; não use dentro de um request que já tem pool.
    """

    transaction_mode = TransactionMode.OWN

    def __init__(self, dsn: str, *, connect_timeout: float = 10.0) -> None:
        try:
            import psycopg
        except ModuleNotFoundError as error:
            if (error.name or "").partition(".")[0] != "psycopg":
                raise
            raise ExtraNotInstalledError(
                'DSNProvider needs psycopg 3: pip install "memory-lifecycle[psycopg]"'
            ) from error
        self._psycopg: Any = psycopg
        self._dsn = dsn
        self._timeout = connect_timeout

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Open a new connection with autocommit off and close it on exit.

        PT: Abre uma conexão nova com autocommit desligado e a fecha ao sair.
        """
        connection = self._psycopg.connect(
            self._dsn, autocommit=False, connect_timeout=max(1, round(self._timeout))
        )
        try:
            yield connection
        finally:
            connection.close()
