"""Fixtures da raiz: o banco da suíte, o elenco compartilhado, o relógio e os embeddings.

Testes de integração e de aceitação falam com um PostgreSQL real com pgvector,
alcançado por ``MEMORY_LIFECYCLE_DSN_TESTE``. Sem ela, pulam com a razão visível;
nunca falsificam o banco (``.claude/rules/tests.md``).

O elenco (``tenant``, ``outro_tenant``, ``dono``, ``outro_dono``) é mínimo de
propósito: 1 fixture = 1 cenário, e um módulo de teste nunca redefine essas.
``relogio`` deixa um cenário colocar escritas em instantes escolhidos sem dormir.
``schema`` dá a cada teste um schema próprio, criado vazio e apagado no fim: os
testes não se enxergam, e o modo ``PROPRIA`` e a concorrência funcionam (um
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

from memory_lifecycle import Memoria, ModoDeTransacao, ProvedorDeEmbeddingsFalso
from memory_lifecycle.connection import Conexao, ProvedorDeConexao
from memory_lifecycle.connection.dsn import ProvedorDSN

#: Provedores de toda a suíte: os dois drivers (paridade de driver, ADR 0007).
PROVEDORES = ("psycopg", "psycopg2")
#: A aceitação roda também por todo adaptador (paridade de adaptadores, DoD 1).
PROVEDORES_DE_ACEITACAO = (
    *PROVEDORES,
    "pool_psycopg",
    "django",
    "sqlalchemy_engine",
    "sqlalchemy_sessao",
)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "provedor" in metafunc.fixturenames:
        aceitacao = "acceptance" in metafunc.definition.path.parts
        metafunc.parametrize(
            "provedor", PROVEDORES_DE_ACEITACAO if aceitacao else PROVEDORES, indirect=True
        )


T0 = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class RelogioManual:
    """Um relógio que o teste move à mão: ``relogio.avancar(days=30)``."""

    agora: datetime = T0

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **delta: int) -> datetime:
        self.agora = self.agora + timedelta(**delta)
        return self.agora

    def em(self, **delta: int) -> datetime:
        """Um instante relativo a T0 sem mover o relógio."""
        return T0 + timedelta(**delta)


@pytest.fixture(scope="session")
def dsn() -> str:
    valor = os.environ.get("MEMORY_LIFECYCLE_DSN_TESTE")
    if not valor:
        pytest.skip("MEMORY_LIFECYCLE_DSN_TESTE não definida: `make db-up` e copie o .env.example")
    return valor


@pytest.fixture
def schema(dsn: str) -> Iterator[str]:
    """Um schema só deste teste; apagado com tudo dentro no teardown."""
    import psycopg

    nome = f"teste_{uuid.uuid4().hex[:12]}"
    yield nome
    with psycopg.connect(dsn, autocommit=True) as conexao:
        conexao.execute(f'DROP SCHEMA IF EXISTS "{nome}" CASCADE')


class ProvedorPsycopg2:
    """Provedor só de teste sobre o psycopg2: prova que o SQL roda igual nos dois drivers."""

    modo_de_transacao = ModoDeTransacao.PROPRIA

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        import psycopg2

        conexao = psycopg2.connect(self._dsn)
        try:
            yield conexao
        finally:
            conexao.close()


def url_sqlalchemy(dsn: str) -> str:
    return dsn.replace("postgresql://", "postgresql+psycopg://", 1)


@pytest.fixture(scope="session")
def django_configurado(dsn: str) -> Iterator[None]:
    """Configura o Django uma vez, com o banco da suíte como ``default``."""
    import django
    from django.conf import settings

    partes = urlsplit(dsn)
    if not settings.configured:
        settings.configure(
            USE_TZ=True,
            INSTALLED_APPS=[],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": partes.path.lstrip("/"),
                    "USER": partes.username,
                    "PASSWORD": partes.password,
                    "HOST": partes.hostname,
                    "PORT": str(partes.port),
                }
            },
        )
        django.setup()
    yield
    from django.db import connections

    connections.close_all()


@pytest.fixture
def provedor(request: pytest.FixtureRequest, dsn: str, schema: str) -> Iterator[ProvedorDeConexao]:
    """O provedor do parâmetro; depende de ``schema`` para fechar antes do DROP."""
    nome: str = request.param
    if nome == "psycopg":
        yield ProvedorDSN(dsn)
    elif nome == "psycopg2":
        yield ProvedorPsycopg2(dsn)
    elif nome == "pool_psycopg":
        from psycopg_pool import ConnectionPool

        from memory_lifecycle.connection.psycopg_pool import ProvedorPoolPsycopg

        with ConnectionPool(dsn, min_size=1, max_size=2, open=True) as pool:
            yield ProvedorPoolPsycopg(pool)
    elif nome == "django":
        request.getfixturevalue("django_configurado")
        from django.db import connections

        from memory_lifecycle.connection.django import ProvedorDjango

        yield ProvedorDjango()
        connections.close_all()
    else:
        yield from _provedor_sqlalchemy(nome, dsn)


def _provedor_sqlalchemy(nome: str, dsn: str) -> Iterator[ProvedorDeConexao]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from memory_lifecycle.connection.sqlalchemy import ProvedorSQLAlchemy

    engine: Any = create_engine(url_sqlalchemy(dsn))
    try:
        if nome == "sqlalchemy_engine":
            yield ProvedorSQLAlchemy(engine)
        else:
            with Session(engine) as sessao:
                yield ProvedorSQLAlchemy.de_sessao(sessao)
                sessao.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def embeddings_falsos() -> ProvedorDeEmbeddingsFalso:
    return ProvedorDeEmbeddingsFalso(dimensao=8)


@pytest.fixture
def relogio() -> RelogioManual:
    return RelogioManual()


@pytest.fixture
def tenant() -> str:
    return "tenant-a"


@pytest.fixture
def outro_tenant() -> str:
    return "tenant-b"


@pytest.fixture
def dono() -> str:
    return "dono-1"


@pytest.fixture
def outro_dono() -> str:
    return "dono-2"


@pytest.fixture
def memoria(
    provedor: ProvedorDeConexao,
    embeddings_falsos: ProvedorDeEmbeddingsFalso,
    tenant: str,
    relogio: RelogioManual,
    schema: str,
) -> Memoria:
    """Uma ``Memoria`` de ``tenant``, migrada no schema deste teste."""
    instancia = Memoria(
        conexao=provedor,
        embeddings=embeddings_falsos,
        tenant_id=tenant,
        schema=schema,
        relogio=relogio,
    )
    instancia.migrar()
    return instancia


@pytest.fixture
def memoria_outro_tenant(
    memoria: Memoria,
    provedor: ProvedorDeConexao,
    embeddings_falsos: ProvedorDeEmbeddingsFalso,
    outro_tenant: str,
    relogio: RelogioManual,
    schema: str,
) -> Memoria:
    """Outro tenant no mesmo schema (já migrado por ``memoria``): o caso do isolamento."""
    return Memoria(
        conexao=provedor,
        embeddings=embeddings_falsos,
        tenant_id=outro_tenant,
        schema=schema,
        relogio=relogio,
    )
