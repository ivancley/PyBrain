"""ADR 0004: both transaction modes, the autocommit rejection and the embedding before the connection.

PT: ADR 0004: os dois modos de transação, a recusa de autocommit e o embedding antes da conexão.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import psycopg
import pytest

from memory_lifecycle import (
    ConfigurationError,
    EmbeddingError,
    FakeEmbeddingProvider,
    Memory,
    TransactionMode,
    store,
)
from memory_lifecycle.connection import Connection
from memory_lifecycle.connection.dsn import DSNProvider
from tests.conftest import ManualClock


class SingleConnectionProvider:
    """Always lends the same connection, which the test (the "app") opens and closes.

    PT: Empresta sempre a mesma conexão, que o teste (o "app") abre e fecha.
    """

    def __init__(self, connection: psycopg.Connection, mode: TransactionMode) -> None:
        self._connection = connection
        self.transaction_mode = mode

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        yield self._connection  # type: ignore[misc]


class SpyProvider:
    """Records in ``events`` when the connection is requested.

    PT: Anota em ``events`` quando a conexão é pedida.
    """

    def __init__(self, dsn: str, events: list[str]) -> None:
        self._real = DSNProvider(dsn)
        self._events = events
        self.transaction_mode = TransactionMode.OWN

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        self._events.append("connection")
        with self._real.connection() as connection:
            yield connection


class SpyEmbeddings(FakeEmbeddingProvider):
    def __init__(self, events: list[str], fail: bool = False) -> None:
        super().__init__(dimension=8)
        self._events = events
        self._fail = fail

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self._events.append("embed")
        if self._fail:
            raise TimeoutError("the provider did not respond")
        return super().embed(texts)


def _memory(
    provider: object,
    reference: Memory,
    embeddings: FakeEmbeddingProvider | None = None,
) -> Memory:
    """An "app" ``Memory`` in the same schema, tenant and clock as ``reference``.

    PT: Uma ``Memory`` do "app" no mesmo schema, tenant e relógio da ``reference``.
    """
    return Memory(
        connection=provider,  # type: ignore[arg-type]
        embeddings=embeddings or FakeEmbeddingProvider(dimension=8),
        tenant_id=reference.tenant_id,
        schema=reference.schema,
        clock=reference.clock,
    )


@pytest.mark.parametrize("mode", list(TransactionMode))
def test_autocommit_connection_is_rejected(memory: Memory, dsn: str, schema: str, mode):
    with psycopg.connect(dsn, autocommit=True) as connection:
        app = _memory(SingleConnectionProvider(connection, mode), memory)
        with pytest.raises(ConfigurationError, match="autocommit"):
            app.remember("owner-1", "x", kind="note")
    assert memory.recall("owner-1") == []


def test_participate_vanishes_with_the_app_rollback(memory: Memory, dsn: str, schema: str):
    with psycopg.connect(dsn) as connection:
        app = _memory(SingleConnectionProvider(connection, TransactionMode.PARTICIPATE), memory)
        app.remember("owner-1", "undone", kind="note")
        assert [r.version.content for r in app.recall("owner-1")] == ["undone"]
        connection.rollback()
        app.remember("owner-1", "committed", kind="note")
        connection.commit()
    assert [r.version.content for r in memory.recall("owner-1")] == ["committed"]


def test_participate_never_commits_on_its_own(memory: Memory, dsn: str, schema: str):
    with psycopg.connect(dsn) as connection:
        app = _memory(SingleConnectionProvider(connection, TransactionMode.PARTICIPATE), memory)
        app.remember("owner-1", "pending", kind="note")
        assert [r.version.content for r in app.recall("owner-1")] == ["pending"]
        # Another connection sees nothing yet.
        # PT: Outra conexão não vê nada ainda.
        assert memory.recall("owner-1") == []
        connection.rollback()


def test_own_undoes_the_operation_that_fails_midway(
    memory: Memory, owner: str, clock: ManualClock, monkeypatch: pytest.MonkeyPatch
):
    original = memory.remember(owner, "v1", kind="note")
    clock.advance(days=1)

    def fail(*args, **kwargs):
        raise RuntimeError("injected failure after closing the record and inserting the copy")

    monkeypatch.setattr(store, "insert", fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        memory.supersede(owner, original.memory_id, "v2")
    monkeypatch.undo()

    assert memory.history(owner, original.memory_id) == [original]


def test_embedding_comes_before_the_connection(memory: Memory, dsn: str, schema: str):
    events: list[str] = []
    app = _memory(SpyProvider(dsn, events), memory, SpyEmbeddings(events))
    app.remember("owner-1", "x", kind="note")
    assert events == ["embed", "connection"]


def test_embedding_provider_failure_costs_no_connection(memory: Memory, dsn: str):
    events: list[str] = []
    app = _memory(SpyProvider(dsn, events), memory, SpyEmbeddings(events, fail=True))
    with pytest.raises(EmbeddingError):
        app.remember("owner-1", "x", kind="note")
    assert events == ["embed"]


def test_unmigrated_schema_does_not_abort_the_app_transaction(dsn: str, schema: str):
    # Regression (reports/silent-failure-fatia-10.md, finding 3): `expire` on a missing
    # schema hit 42P01, which aborts the app's transaction in PARTICIPATE mode.
    # PT: Regressão (reports/silent-failure-fatia-10.md, achado 3): `expire` num schema
    # PT: ausente batia em 42P01, que aborta a transação do app no modo PARTICIPATE.
    with psycopg.connect(dsn) as connection:
        app = Memory(
            connection=SingleConnectionProvider(connection, TransactionMode.PARTICIPATE),  # type: ignore[arg-type]
            embeddings=FakeEmbeddingProvider(dimension=8),
            tenant_id="t",
            schema=schema,
        )
        with pytest.raises(ConfigurationError, match="migrate"):
            app.expire("d", "00000000-0000-0000-0000-000000000000")
        # The transaction is still alive.
        # PT: A transação segue viva.
        assert connection.execute("SELECT 1").fetchone() == (1,)
        connection.rollback()


def test_uppercase_expected_version_is_still_the_same(
    memory: Memory, owner: str, clock: ManualClock
):
    # Regression (finding 9): a uuid in another case became ConflictError forever.
    # PT: Regressão (achado 9): um uuid em outra caixa virava ConflictError para sempre.
    current = memory.remember(owner, "v1", kind="note")
    clock.advance(days=1)
    new = memory.supersede(
        owner, current.memory_id, "v2", expected_version_id=current.version_id.upper()
    )
    assert new.content == "v2"


class TextModeProvider:
    """An app provider that declares the mode as text, not as the enum.

    PT: Um provedor do app que declara o modo como texto, não como o enum.
    """

    def __init__(self, dsn: str, mode: str) -> None:
        self._real = DSNProvider(dsn)
        self.transaction_mode = mode

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        with self._real.connection() as connection:
            yield connection


def test_text_mode_is_worth_the_same_as_the_enum(memory: Memory, dsn: str):
    # Regression (reports/review-change-core.md, blocker 1): "own" was treated as
    # PARTICIPATE, and the write vanished with no commit and no error.
    # PT: Regressão (reports/review-change-core.md, bloqueador 1): "own" era tratado
    # PT: como PARTICIPATE, e a escrita sumia sem commit e sem erro.
    app = _memory(TextModeProvider(dsn, "own"), memory)
    app.remember("owner-1", "stored", kind="note")
    assert [r.version.content for r in memory.recall("owner-1")] == ["stored"]


def test_invalid_mode_is_rejected(memory: Memory, dsn: str):
    app = _memory(TextModeProvider(dsn, "automatic"), memory)
    with pytest.raises(ConfigurationError, match="transaction_mode"):
        app.remember("owner-1", "x", kind="note")
