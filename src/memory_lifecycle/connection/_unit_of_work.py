"""The unit of work: one operation, one borrowed connection, one transaction.

Concentrates the ADR 0004 rule in a single place. The connection comes from the
provider and is given back at the end of the operation. A connection in autocommit
is rejected in both modes, before any statement: without a transaction, a
multi-statement operation would be left half-done. In ``OWN`` mode the library
commits on success and rolls back on any exception; in ``PARTICIPATE`` it does
neither, and the transaction belongs to the app. A database error with a known
consequence propagates translated (``_sql.translate``), chained to the original; the
others propagate untouched.

PT: A unidade de trabalho: uma operação, uma conexão emprestada, uma transação.

Concentra a regra do ADR 0004 num lugar só. A conexão vem do provedor e é
devolvida ao fim da operação. Uma conexão em autocommit é recusada nos dois modos,
antes de qualquer instrução: sem transação, uma operação de várias instruções
ficaria pela metade. No modo ``OWN`` a biblioteca faz commit no sucesso e
rollback em qualquer exceção; no ``PARTICIPATE`` não faz nenhum dos dois, e a
transação é do app. Um erro de banco com consequência conhecida sobe traduzido
(``_sql.translate``), encadeado ao original; os demais sobem intactos.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from memory_lifecycle._sql import translate
from memory_lifecycle.connection import ConnectionProvider, Cursor, TransactionMode
from memory_lifecycle.exceptions import ConfigurationError


@contextmanager
def unit_of_work(provider: ConnectionProvider) -> Iterator[Cursor]:
    """Yield a cursor inside a transaction, according to the provider's mode.

    PT: Cede um cursor dentro de uma transação, conforme o modo do provedor.
    """
    mode = provider_mode(provider)
    own = mode is TransactionMode.OWN
    with provider.connection() as connection:
        if getattr(connection, "autocommit", False):
            raise ConfigurationError(
                f"the provider's connection is in autocommit; mode {mode.value} needs a "
                "transaction: turn autocommit off in the provider or use your framework's "
                "adapter (ADR 0004)"
            )
        cursor = connection.cursor()
        try:
            yield cursor
            if own:
                connection.commit()
        except BaseException as error:
            _close(cursor, error)
            if own:
                _rollback(connection, error)
            translated = translate(error) if isinstance(error, Exception) else None
            if translated is not None:
                raise translated from error
            raise
        else:
            cursor.close()


def provider_mode(provider: object) -> TransactionMode:
    """The mode the provider declares, as the enum; a value outside it is rejected.

    Comparing by identity with a value that is not the enum would treat ``"own"`` as
    ``PARTICIPATE``, and the write would vanish with no commit and no error.

    PT: O modo declarado pelo provedor, como enum; um valor fora dele é recusado.

    Comparar por identidade com um valor que não é o enum trataria ``"own"``
    como ``PARTICIPATE``, e a escrita sumiria sem commit e sem erro.
    """
    try:
        return TransactionMode(getattr(provider, "transaction_mode"))  # noqa: B009
    except (AttributeError, ValueError) as error:
        raise ConfigurationError(
            "the connection provider must declare transaction_mode as "
            f"TransactionMode.OWN or TransactionMode.PARTICIPATE ({error})"
        ) from error


def _close(cursor: Cursor, error: BaseException) -> None:
    """Close the cursor without swapping the in-flight error for a close error.

    PT: Fecha o cursor sem trocar o erro em voo por um erro de fechamento.
    """
    try:
        cursor.close()
    except Exception as close_failure:
        error.add_note(f"closing the cursor also failed: {close_failure!r}")


def _rollback(connection: object, error: BaseException) -> None:
    """Roll back without ever hiding the original error: a failure here becomes a note on it.

    PT: Rollback que nunca esconde o erro original: uma falha aqui vira nota nele.
    """
    try:
        connection.rollback()  # type: ignore[attr-defined]
    except Exception as rollback_failure:
        error.add_note(f"the rollback also failed: {rollback_failure!r}")
