"""Os adaptadores de conexão (ADR 0004): o que cada um promete além da paridade.

A paridade (os 16 cenários por todo provedor) roda em ``tests/acceptance`` pela
parametrização do ``conftest``. Aqui fica o comportamento próprio de cada um: o
rollback do request no Django, o commit da sessão no SQLAlchemy, a carga por
variável de ambiente e a mensagem do extra que falta.
"""

from __future__ import annotations

import sys

import pytest

from memory_lifecycle import (
    ErroDeConfiguracao,
    ErroExtraNaoInstalado,
    Memoria,
    ModoDeTransacao,
    ProvedorDeEmbeddingsFalso,
)
from memory_lifecycle.connection import VARIAVEL_AMBIENTE_PROVEDOR, carregar_provedor
from memory_lifecycle.connection.dsn import ProvedorDSN
from tests.conftest import url_sqlalchemy


def _no_mesmo_schema(referencia: Memoria, provedor: object) -> Memoria:
    return Memoria(
        conexao=provedor,  # type: ignore[arg-type]
        embeddings=ProvedorDeEmbeddingsFalso(dimensao=8),
        tenant_id=referencia.tenant_id,
        schema=referencia.schema,
        relogio=referencia.relogio,
    )


def _conteudos(memoria: Memoria, dono: str) -> list[str]:
    return [r.versao.conteudo for r in memoria.recuperar(dono)]


def test_django_desfaz_a_memoria_com_o_request(
    memoria: Memoria, dono: str, django_configurado: None
):
    from django.db import transaction

    from memory_lifecycle.connection.django import ProvedorDjango

    app = _no_mesmo_schema(memoria, ProvedorDjango())
    with pytest.raises(RuntimeError), transaction.atomic():
        app.lembrar(dono, "do request que falhou", categoria="nota")
        raise RuntimeError("o request falhou depois de lembrar")
    with transaction.atomic():
        app.lembrar(dono, "do request que deu certo", categoria="nota")
    assert _conteudos(memoria, dono) == ["do request que deu certo"]
    assert app.conexao.modo_de_transacao is ModoDeTransacao.PARTICIPAR


def test_sqlalchemy_sessao_so_grava_no_commit_do_app(memoria: Memoria, dono: str, dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from memory_lifecycle.connection.sqlalchemy import ProvedorSQLAlchemy

    engine = create_engine(url_sqlalchemy(dsn))
    try:
        with Session(engine) as sessao:
            app = _no_mesmo_schema(memoria, ProvedorSQLAlchemy.de_sessao(sessao))
            app.lembrar(dono, "descartada", categoria="nota")
            assert _conteudos(app, dono) == ["descartada"]
            assert _conteudos(memoria, dono) == []
            sessao.rollback()
            app.lembrar(dono, "confirmada", categoria="nota")
            sessao.commit()
    finally:
        engine.dispose()
    assert _conteudos(memoria, dono) == ["confirmada"]


def test_sqlalchemy_engine_faz_commit_por_operacao(memoria: Memoria, dono: str, dsn: str):
    from sqlalchemy import create_engine

    from memory_lifecycle.connection.sqlalchemy import ProvedorSQLAlchemy

    engine = create_engine(url_sqlalchemy(dsn))
    try:
        app = _no_mesmo_schema(memoria, ProvedorSQLAlchemy(engine))
        app.lembrar(dono, "gravada", categoria="nota")
    finally:
        engine.dispose()
    assert _conteudos(memoria, dono) == ["gravada"]


def fabrica_de_teste() -> ProvedorDSN:
    """Usada por caminho pontuado no teste de ``carregar_provedor``."""
    import os

    return ProvedorDSN(os.environ["MEMORY_LIFECYCLE_DSN_TESTE"])


def nao_e_provedor() -> object:
    return object()


class _ProvedorDeModoInvalido:
    modo_de_transacao = "automatico"

    def conexao(self) -> object:
        raise AssertionError("não deveria ser chamado")


def modo_invalido() -> object:
    return _ProvedorDeModoInvalido()


NAO_CHAMAVEL = 42


def test_carregar_provedor_pelo_ambiente(monkeypatch: pytest.MonkeyPatch, dsn: str):
    monkeypatch.setenv("MEMORY_LIFECYCLE_DSN_TESTE", dsn)
    monkeypatch.setenv(VARIAVEL_AMBIENTE_PROVEDOR, f"{__name__}:fabrica_de_teste")
    assert isinstance(carregar_provedor(), ProvedorDSN)
    assert isinstance(carregar_provedor(f"{__name__}:fabrica_de_teste"), ProvedorDSN)


@pytest.mark.parametrize(
    ("caminho", "trecho"),
    [
        (None, VARIAVEL_AMBIENTE_PROVEDOR),
        ("sem_dois_pontos", "malformado"),
        ("modulo.que.nao.existe:f", "não existe"),
        (f"{__name__}:NAO_CHAMAVEL", "função"),
        (f"{__name__}:nao_e_provedor", "não é um ProvedorDeConexao"),
        (f"{__name__}:modo_invalido", "modo_de_transacao"),
    ],
)
def test_carregar_provedor_explica_o_erro(
    monkeypatch: pytest.MonkeyPatch, caminho: str | None, trecho: str
):
    monkeypatch.delenv(VARIAVEL_AMBIENTE_PROVEDOR, raising=False)
    with pytest.raises(ErroDeConfiguracao, match=trecho):
        carregar_provedor(caminho)


@pytest.mark.parametrize(
    ("modulo", "classe", "extra"),
    [
        ("psycopg", "memory_lifecycle.connection.dsn:ProvedorDSN", "psycopg"),
        ("psycopg_pool", "memory_lifecycle.connection.psycopg_pool:ProvedorPoolPsycopg", "psycopg"),
        ("django", "memory_lifecycle.connection.django:ProvedorDjango", "django"),
        ("sqlalchemy", "memory_lifecycle.connection.sqlalchemy:ProvedorSQLAlchemy", "sqlalchemy"),
    ],
)
def test_extra_ausente_nomeia_o_que_instalar(
    monkeypatch: pytest.MonkeyPatch, modulo: str, classe: str, extra: str
):
    import importlib

    caminho, nome = classe.split(":")
    cls = getattr(importlib.import_module(caminho), nome)
    for carregado in [m for m in sys.modules if m == modulo or m.startswith(f"{modulo}.")]:
        monkeypatch.setitem(sys.modules, carregado, None)
    monkeypatch.setitem(sys.modules, modulo, None)
    with pytest.raises(ErroExtraNaoInstalado, match=rf"memory-lifecycle\[{extra}\]"):
        cls("argumento")


def test_sessao_sqlalchemy_sobrevive_a_um_erro_da_biblioteca(
    memoria: Memoria, dono: str, dsn: str, monkeypatch: pytest.MonkeyPatch
):
    # Regressão (reports/review-change-core.md, importante 1): sem savepoint, um erro
    # de banco da biblioteca abortava a sessão, e o `commit` do app desfazia tudo mudo.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from memory_lifecycle import store
    from memory_lifecycle.connection.sqlalchemy import ProvedorSQLAlchemy

    def instrucao_que_falha(cur, *argumentos, **nomeados):
        cur.execute("SELECT 1 / 0")

    engine = create_engine(url_sqlalchemy(dsn))
    try:
        with Session(engine) as sessao:
            app = _no_mesmo_schema(memoria, ProvedorSQLAlchemy.de_sessao(sessao))
            app.lembrar(dono, "antes do erro", categoria="nota")
            monkeypatch.setattr(store, "inserir", instrucao_que_falha)
            with pytest.raises(Exception, match="division by zero"):
                app.lembrar(dono, "a que falha", categoria="nota")
            monkeypatch.undo()
            sessao.commit()
    finally:
        engine.dispose()
    assert _conteudos(memoria, dono) == ["antes do erro"]
