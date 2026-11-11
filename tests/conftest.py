"""Root fixtures: the suite's database, the shared cast, the clock and the embeddings.

Integration and acceptance tests talk to a real PostgreSQL with pgvector, reached
through ``MEMORY_LIFECYCLE_TEST_DSN``. Without it, they skip with the reason visible;
they never fake the database (``.claude/rules/tests.md``).

The cast (``tenant``, ``other_tenant``, ``owner``, ``other_owner``) is minimal on
purpose: 1 fixture = 1 scenario, and a test module never redefines them. ``clock``
lets a scenario place writes at chosen instants without sleeping. ``schema`` gives each
test its own schema, created empty and dropped at the end: tests do not see each
other, and ``OWN`` mode and concurrency work (a per-test rollback would not work with
them).

PT: Fixtures da raiz: o banco da suíte, o elenco compartilhado, o relógio e os embeddings.

Testes de integração e de aceitação falam com um PostgreSQL real com pgvector,
alcançado por ``MEMORY_LIFECYCLE_TEST_DSN``. Sem ela, pulam com a razão visível;
nunca falsificam o banco (``.claude/rules/tests.md``).

O elenco (``tenant``, ``other_tenant``, ``owner``, ``other_owner``) é mínimo de
propósito: 1 fixture = 1 cenário, e um módulo de teste nunca redefine essas.
``clock`` deixa um cenário colocar escritas em instantes escolhidos sem dormir.
``schema`` dá a cada teste um schema próprio, criado vazio e apagado no fim: os
testes não se enxergam, e o modo ``OWN`` e a concorrência funcionam (um
rollback por teste não funcionaria com eles).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import pytest

from memory_lifecycle import FakeEmbeddingProvider, Memory, TransactionMode
from memory_lifecycle.connection import Connection, ConnectionProvider
from memory_lifecycle.connection.dsn import DSNProvider

#: Providers for the whole suite: both drivers (driver parity, ADR 0007).
#: PT: Provedores de toda a suíte: os dois drivers (paridade de driver, ADR 0007).
PROVIDERS = ("psycopg", "psycopg2")
#: Acceptance also runs through every adapter (adapter parity, DoD 1).
#: PT: A aceitação roda também por todo adaptador (paridade de adaptadores, DoD 1).
ACCEPTANCE_PROVIDERS = (
    *PROVIDERS,
    "psycopg_pool",
    "django",
    "sqlalchemy_engine",
    "sqlalchemy_session",
)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "provider" in metafunc.fixturenames:
        acceptance = "acceptance" in metafunc.definition.path.parts
        metafunc.parametrize(
            "provider", ACCEPTANCE_PROVIDERS if acceptance else PROVIDERS, indirect=True
        )


T0 = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class ManualClock:
    """A clock the test moves by hand: ``clock.advance(days=30)``.

    PT: Um relógio que o teste move à mão: ``clock.advance(days=30)``.
    """

    now: datetime = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: int) -> datetime:
        self.now = self.now + timedelta(**delta)
        return self.now

    def at(self, **delta: int) -> datetime:
        """An instant relative to T0 without moving the clock.

        PT: Um instante relativo a T0 sem mover o relógio.
        """
        return T0 + timedelta(**delta)


@pytest.fixture(scope="session")
def dsn() -> str:
    value = os.environ.get("MEMORY_LIFECYCLE_TEST_DSN")
    if not value:
        pytest.skip("MEMORY_LIFECYCLE_TEST_DSN is not set: `make db-up` and copy .env.example")
    return value


@pytest.fixture
def schema(dsn: str) -> Iterator[str]:
    """A schema for this test only; dropped with everything inside on teardown.

    PT: Um schema só deste teste; apagado com tudo dentro no teardown.
    """
    import psycopg

    name = f"test_{uuid.uuid4().hex[:12]}"
    yield name
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')


class Psycopg2Provider:
    """Test-only provider over psycopg2: proves the SQL runs the same on both drivers.

    PT: Provedor só de teste sobre o psycopg2: prova que o SQL roda igual nos dois drivers.
    """

    transaction_mode = TransactionMode.OWN

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        import psycopg2

        connection = psycopg2.connect(self._dsn)
        try:
            yield connection
        finally:
            connection.close()


def sqlalchemy_url(dsn: str) -> str:
    return dsn.replace("postgresql://", "postgresql+psycopg://", 1)


@pytest.fixture(scope="session")
def django_configured(dsn: str) -> Iterator[None]:
    """Configure Django once, with the suite's database as ``default``.

    PT: Configura o Django uma vez, com o banco da suíte como ``default``.
    """
    import django
    from django.conf import settings

    parts = urlsplit(dsn)
    if not settings.configured:
        settings.configure(
            USE_TZ=True,
            INSTALLED_APPS=[],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": parts.path.lstrip("/"),
                    "USER": parts.username,
                    "PASSWORD": parts.password,
                    "HOST": parts.hostname,
                    "PORT": str(parts.port),
                }
            },
        )
        django.setup()
    yield
    from django.db import connections

    connections.close_all()


@pytest.fixture
def provider(request: pytest.FixtureRequest, dsn: str, schema: str) -> Iterator[ConnectionProvider]:
    """The parameter's provider; depends on ``schema`` so it closes before the DROP.

    PT: O provedor do parâmetro; depende de ``schema`` para fechar antes do DROP.
    """
    name: str = request.param
    if name == "psycopg":
        yield DSNProvider(dsn)
    elif name == "psycopg2":
        yield Psycopg2Provider(dsn)
    elif name == "psycopg_pool":
        from psycopg_pool import ConnectionPool

        from memory_lifecycle.connection.psycopg_pool import PsycopgPoolProvider

        with ConnectionPool(dsn, min_size=1, max_size=2, open=True) as pool:
            yield PsycopgPoolProvider(pool)
    elif name == "django":
        request.getfixturevalue("django_configured")
        from django.db import connections

        from memory_lifecycle.connection.django import DjangoProvider

        yield DjangoProvider()
        connections.close_all()
    else:
        yield from _sqlalchemy_provider(name, dsn)


def _sqlalchemy_provider(name: str, dsn: str) -> Iterator[ConnectionProvider]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from memory_lifecycle.connection.sqlalchemy import SQLAlchemyProvider

    engine: Any = create_engine(sqlalchemy_url(dsn))
    try:
        if name == "sqlalchemy_engine":
            yield SQLAlchemyProvider(engine)
        else:
            with Session(engine) as session:
                yield SQLAlchemyProvider.from_session(session)
                session.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider(dimension=8)


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def tenant() -> str:
    return "tenant-a"


@pytest.fixture
def other_tenant() -> str:
    return "tenant-b"


@pytest.fixture
def owner() -> str:
    return "owner-1"


@pytest.fixture
def other_owner() -> str:
    return "owner-2"


@pytest.fixture
def memory(
    provider: ConnectionProvider,
    fake_embeddings: FakeEmbeddingProvider,
    tenant: str,
    clock: ManualClock,
    schema: str,
) -> Memory:
    """A ``Memory`` for ``tenant``, migrated in this test's schema.

    PT: Uma ``Memory`` de ``tenant``, migrada no schema deste teste.
    """
    instance = Memory(
        connection=provider,
        embeddings=fake_embeddings,
        tenant_id=tenant,
        schema=schema,
        clock=clock,
    )
    instance.migrate()
    return instance


@pytest.fixture
def other_tenant_memory(
    memory: Memory,
    provider: ConnectionProvider,
    fake_embeddings: FakeEmbeddingProvider,
    other_tenant: str,
    clock: ManualClock,
    schema: str,
) -> Memory:
    """Another tenant in the same schema (already migrated by ``memory``): the isolation case.

    PT: Outro tenant no mesmo schema (já migrado por ``memory``): o caso do isolamento.
    """
    return Memory(
        connection=provider,
        embeddings=fake_embeddings,
        tenant_id=other_tenant,
        schema=schema,
        clock=clock,
    )
