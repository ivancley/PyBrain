"""The unit of work's error flow, with a fake connection just for control.

The behavior against the database is in ``tests/integration/test_transaction.py``;
here lives what a real database will not let us provoke: ``close`` and ``rollback`` failing.

PT: O fluxo de erro da unidade de trabalho, com uma conexão de mentira só para o controle.

O comportamento contra o banco está em ``tests/integration/test_transaction.py``;
aqui fica o que um banco real não deixa provocar: o ``close`` e o ``rollback`` falhando.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from memory_lifecycle import TransactionMode
from memory_lifecycle.connection._unit_of_work import unit_of_work


class CursorThatWontClose:
    rowcount = 0

    def close(self) -> None:
        raise OSError("the connection dropped while closing the cursor")


class ConnectionThatWontRollBack:
    autocommit = False

    def cursor(self) -> CursorThatWontClose:
        return CursorThatWontClose()

    def commit(self) -> None:
        raise AssertionError("should not reach commit")

    def rollback(self) -> None:
        raise OSError("the connection dropped during rollback")


class Provider:
    transaction_mode = TransactionMode.OWN

    @contextmanager
    def connection(self) -> Iterator[ConnectionThatWontRollBack]:
        yield ConnectionThatWontRollBack()


def test_close_and_rollback_failures_become_notes_on_the_original_error():
    # Regression (reports/silent-failure-fatia-10.md, finding 10): the `finally: close()`
    # replaced the operation's error with the close error.
    # PT: Regressão (reports/silent-failure-fatia-10.md, achado 10): o `finally: close()`
    # PT: trocava o erro da operação pelo erro de fechamento.
    with pytest.raises(ValueError, match="the operation's error") as error:
        with unit_of_work(Provider()):  # type: ignore[arg-type]
            raise ValueError("the operation's error")
    notes = " ".join(getattr(error.value, "__notes__", []))
    assert "closing the cursor also failed" in notes
    assert "the rollback also failed" in notes
