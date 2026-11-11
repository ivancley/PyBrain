"""``SQLAlchemyProvider``: reuses the app's engine or session (``sqlalchemy`` extra).

- ``SQLAlchemyProvider(engine)``: one connection from the engine's pool per operation,
  in ``OWN`` mode.
- ``SQLAlchemyProvider.from_session(session)``: the connection of the session's
  transaction, in ``PARTICIPATE`` mode; each operation runs in a savepoint
  (``begin_nested``), and the write only counts when the app calls
  ``session.commit()``.

In both cases the library talks to the driver connection underneath SQLAlchemy
(psycopg 3 or psycopg2), registering nothing on it (ADR 0007).

PT: ``SQLAlchemyProvider``: reaproveita o engine ou a sessão do app (extra ``sqlalchemy``).

- ``SQLAlchemyProvider(engine)``: uma conexão do pool do engine por operação, no
  modo ``OWN``.
- ``SQLAlchemyProvider.from_session(session)``: a conexão da transação da sessão, no
  modo ``PARTICIPATE``; cada operação roda num savepoint (``begin_nested``), e a
  escrita só vale quando o app faz ``session.commit()``.

Nos dois casos a biblioteca fala com a conexão do driver por baixo do SQLAlchemy
(psycopg 3 ou psycopg2), sem registrar nada nela (ADR 0007).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Connection, TransactionMode
from memory_lifecycle.exceptions import ExtraNotInstalledError


def _require_sqlalchemy() -> None:
    try:
        import sqlalchemy  # noqa: F401 — only to give the extra's message early / só para avisar cedo
    except ModuleNotFoundError as error:
        if (error.name or "").partition(".")[0] != "sqlalchemy":
            raise
        raise ExtraNotInstalledError(
            'SQLAlchemyProvider needs SQLAlchemy: pip install "memory-lifecycle[sqlalchemy]"'
        ) from error


class SQLAlchemyProvider:
    """Provider over an ``Engine`` (``OWN``) or a ``Session`` (``PARTICIPATE``).

    PT: Provedor sobre um ``Engine`` (``OWN``) ou uma ``Session`` (``PARTICIPATE``).
    """

    def __init__(self, engine: Any) -> None:
        _require_sqlalchemy()
        self._engine = engine
        self._session: Any = None
        self.transaction_mode = TransactionMode.OWN

    @classmethod
    def from_session(cls, session: Any) -> SQLAlchemyProvider:
        """Participate in the session's transaction; the app commits.

        PT: Participa da transação da sessão; quem faz commit é o app.
        """
        provider = cls(session.get_bind())
        provider._session = session
        provider.transaction_mode = TransactionMode.PARTICIPATE
        return provider

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Yield the driver connection: the session's, or one borrowed from the engine's pool.

        PT: Cede a conexão do driver: da sessão, ou emprestada do pool do engine.
        """
        if self._session is not None:
            # Savepoint: an error in the operation undoes only it. Without it, a database
            # error would abort the session's transaction and the app's `commit` would
            # turn into a silent rollback.
            # PT: Savepoint: um erro da operação desfaz só ela. Sem ele, um erro de banco
            # PT: abortaria a transação da sessão e o `commit` do app viraria rollback mudo.
            with self._session.begin_nested():
                yield self._session.connection().connection.driver_connection
            return
        borrowed = self._engine.raw_connection()
        try:
            yield borrowed.driver_connection
        finally:
            borrowed.close()
