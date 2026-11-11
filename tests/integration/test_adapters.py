"""The connection adapters (ADR 0004): what each one promises beyond parity.

Parity (the 16 scenarios on every provider) runs in ``tests/acceptance`` through the
``conftest`` parametrization. Here lives each one's own behavior: the request rollback
in Django, the session commit in SQLAlchemy, loading through an environment variable
and the message for the missing extra.

PT: Os adaptadores de conexão (ADR 0004): o que cada um promete além da paridade.

A paridade (os 16 cenários por todo provedor) roda em ``tests/acceptance`` pela
parametrização do ``conftest``. Aqui fica o comportamento próprio de cada um: o
rollback do request no Django, o commit da sessão no SQLAlchemy, a carga por
variável de ambiente e a mensagem do extra que falta.
"""

from __future__ import annotations

import sys

import pytest

from memory_lifecycle import (
    ConfigurationError,
    ExtraNotInstalledError,
    FakeEmbeddingProvider,
    Memory,
    TransactionMode,
)
from memory_lifecycle.connection import PROVIDER_ENV_VAR, load_provider
from memory_lifecycle.connection.dsn import DSNProvider
from tests.conftest import sqlalchemy_url


def _in_the_same_schema(reference: Memory, provider: object) -> Memory:
    return Memory(
        connection=provider,  # type: ignore[arg-type]
        embeddings=FakeEmbeddingProvider(dimension=8),
        tenant_id=reference.tenant_id,
        schema=reference.schema,
        clock=reference.clock,
    )


def _contents(memory: Memory, owner: str) -> list[str]:
    return [r.version.content for r in memory.recall(owner)]


def test_django_undoes_the_memory_with_the_request(
    memory: Memory, owner: str, django_configured: None
):
    from django.db import transaction

    from memory_lifecycle.connection.django import DjangoProvider

    app = _in_the_same_schema(memory, DjangoProvider())
    with pytest.raises(RuntimeError), transaction.atomic():
        app.remember(owner, "from the request that failed", kind="note")
        raise RuntimeError("the request failed after remember")
    with transaction.atomic():
        app.remember(owner, "from the request that succeeded", kind="note")
    assert _contents(memory, owner) == ["from the request that succeeded"]
    assert app.connection.transaction_mode is TransactionMode.PARTICIPATE


def test_sqlalchemy_session_only_stores_on_the_app_commit(memory: Memory, owner: str, dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from memory_lifecycle.connection.sqlalchemy import SQLAlchemyProvider

    engine = create_engine(sqlalchemy_url(dsn))
    try:
        with Session(engine) as session:
            app = _in_the_same_schema(memory, SQLAlchemyProvider.from_session(session))
            app.remember(owner, "discarded", kind="note")
            assert _contents(app, owner) == ["discarded"]
            assert _contents(memory, owner) == []
            session.rollback()
            app.remember(owner, "committed", kind="note")
            session.commit()
    finally:
        engine.dispose()
    assert _contents(memory, owner) == ["committed"]


def test_sqlalchemy_engine_commits_per_operation(memory: Memory, owner: str, dsn: str):
    from sqlalchemy import create_engine

    from memory_lifecycle.connection.sqlalchemy import SQLAlchemyProvider

    engine = create_engine(sqlalchemy_url(dsn))
    try:
        app = _in_the_same_schema(memory, SQLAlchemyProvider(engine))
        app.remember(owner, "stored", kind="note")
    finally:
        engine.dispose()
    assert _contents(memory, owner) == ["stored"]


def factory_for_test() -> DSNProvider:
    """Used by dotted path in the ``load_provider`` test.

    PT: Usada por caminho pontuado no teste de ``load_provider``.
    """
    import os

    return DSNProvider(os.environ["MEMORY_LIFECYCLE_TEST_DSN"])


def not_a_provider() -> object:
    return object()


class _InvalidModeProvider:
    transaction_mode = "automatic"

    def connection(self) -> object:
        raise AssertionError("should not be called")


def invalid_mode() -> object:
    return _InvalidModeProvider()


NOT_CALLABLE = 42


def test_load_provider_from_the_environment(monkeypatch: pytest.MonkeyPatch, dsn: str):
    monkeypatch.setenv("MEMORY_LIFECYCLE_TEST_DSN", dsn)
    monkeypatch.setenv(PROVIDER_ENV_VAR, f"{__name__}:factory_for_test")
    assert isinstance(load_provider(), DSNProvider)
    assert isinstance(load_provider(f"{__name__}:factory_for_test"), DSNProvider)


@pytest.mark.parametrize(
    ("path", "snippet"),
    [
        (None, PROVIDER_ENV_VAR),
        ("no_colon", "malformed"),
        ("module.that.does.not.exist:f", "does not exist"),
        (f"{__name__}:NOT_CALLABLE", "function"),
        (f"{__name__}:not_a_provider", "not a ConnectionProvider"),
        (f"{__name__}:invalid_mode", "transaction_mode"),
    ],
)
def test_load_provider_explains_the_error(
    monkeypatch: pytest.MonkeyPatch, path: str | None, snippet: str
):
    monkeypatch.delenv(PROVIDER_ENV_VAR, raising=False)
    with pytest.raises(ConfigurationError, match=snippet):
        load_provider(path)


@pytest.mark.parametrize(
    ("module", "cls_path", "extra"),
    [
        ("psycopg", "memory_lifecycle.connection.dsn:DSNProvider", "psycopg"),
        ("psycopg_pool", "memory_lifecycle.connection.psycopg_pool:PsycopgPoolProvider", "psycopg"),
        ("django", "memory_lifecycle.connection.django:DjangoProvider", "django"),
        ("sqlalchemy", "memory_lifecycle.connection.sqlalchemy:SQLAlchemyProvider", "sqlalchemy"),
    ],
)
def test_missing_extra_names_what_to_install(
    monkeypatch: pytest.MonkeyPatch, module: str, cls_path: str, extra: str
):
    import importlib

    path, name = cls_path.split(":")
    cls = getattr(importlib.import_module(path), name)
    for loaded in [m for m in sys.modules if m == module or m.startswith(f"{module}.")]:
        monkeypatch.setitem(sys.modules, loaded, None)
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(ExtraNotInstalledError, match=rf"memory-lifecycle\[{extra}\]"):
        cls("argument")


def test_sqlalchemy_session_survives_a_library_error(
    memory: Memory, owner: str, dsn: str, monkeypatch: pytest.MonkeyPatch
):
    # Regression (reports/review-change-core.md, important 1): without a savepoint, a
    # library database error aborted the session, and the app's `commit` silently undid it all.
    # PT: Regressão (reports/review-change-core.md, importante 1): sem savepoint, um erro
    # PT: de banco da biblioteca abortava a sessão, e o `commit` do app desfazia tudo mudo.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from memory_lifecycle import store
    from memory_lifecycle.connection.sqlalchemy import SQLAlchemyProvider

    def failing_statement(cur, *args, **kwargs):
        cur.execute("SELECT 1 / 0")

    engine = create_engine(sqlalchemy_url(dsn))
    try:
        with Session(engine) as session:
            app = _in_the_same_schema(memory, SQLAlchemyProvider.from_session(session))
            app.remember(owner, "before the error", kind="note")
            monkeypatch.setattr(store, "insert", failing_statement)
            with pytest.raises(Exception, match="division by zero"):
                app.remember(owner, "the failing one", kind="note")
            monkeypatch.undo()
            session.commit()
    finally:
        engine.dispose()
    assert _contents(memory, owner) == ["before the error"]
