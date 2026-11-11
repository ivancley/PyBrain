"""``DjangoProvider``: the memory writes in the Django request's transaction.

Uses the connection Django already opened (``django`` extra), with no second pool.
Each operation runs inside ``transaction.atomic()``: inside an app transaction that is
a savepoint, and the write only counts if the request commits; outside one, it is a
short transaction. That is why the mode is ``PARTICIPATE`` and the library never
commits: ``atomic`` closes it (ADR 0004).

PT: ``DjangoProvider``: a memória escreve na transação do request do Django.

Usa a conexão que o Django já abriu (extra ``django``), sem segundo pool. Cada
operação roda dentro de ``transaction.atomic()``: dentro de uma transação do app
isso é um savepoint, e a escrita só vale se o request fizer commit; fora de uma,
é uma transação curta. Por isso o modo é ``PARTICIPATE`` e a biblioteca nunca faz
commit: quem fecha é o ``atomic`` (ADR 0004).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Connection, TransactionMode
from memory_lifecycle.exceptions import ExtraNotInstalledError


class DjangoProvider:
    """Provider over Django's ``alias`` connection; ``PARTICIPATE`` by design.

    PT: Provedor sobre a conexão ``alias`` do Django; ``PARTICIPATE`` por desenho.
    """

    transaction_mode = TransactionMode.PARTICIPATE

    def __init__(self, alias: str = "default") -> None:
        try:
            from django.db import connections, transaction
        except ModuleNotFoundError as error:
            if (error.name or "").partition(".")[0] != "django":
                raise
            raise ExtraNotInstalledError(
                'DjangoProvider needs Django: pip install "memory-lifecycle[django]"'
            ) from error
        self._connections: Any = connections
        self._transaction: Any = transaction
        self._alias = alias

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Yield Django's DB-API connection inside an ``atomic`` (savepoint or transaction).

        PT: Cede a conexão DB-API do Django dentro de um ``atomic`` (savepoint ou transação).
        """
        with self._transaction.atomic(using=self._alias):
            wrapper = self._connections[self._alias]
            wrapper.ensure_connection()
            yield wrapper.connection
