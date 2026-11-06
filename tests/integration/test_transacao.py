"""ADR 0004: os dois modos de transação, a recusa de autocommit e o embedding antes da conexão."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import psycopg
import pytest

from memory_lifecycle import (
    ErroDeConfiguracao,
    ErroDeEmbedding,
    Memoria,
    ModoDeTransacao,
    ProvedorDeEmbeddingsFalso,
    store,
)
from memory_lifecycle.connection import Conexao
from memory_lifecycle.connection.dsn import ProvedorDSN
from tests.conftest import RelogioManual


class ProvedorDeConexaoUnica:
    """Empresta sempre a mesma conexão, que o teste (o "app") abre e fecha."""

    def __init__(self, conexao: psycopg.Connection, modo: ModoDeTransacao) -> None:
        self._conexao = conexao
        self.modo_de_transacao = modo

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        yield self._conexao  # type: ignore[misc]


class ProvedorEspiao:
    """Anota em ``eventos`` quando a conexão é pedida."""

    def __init__(self, dsn: str, eventos: list[str]) -> None:
        self._real = ProvedorDSN(dsn)
        self._eventos = eventos
        self.modo_de_transacao = ModoDeTransacao.PROPRIA

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        self._eventos.append("conexao")
        with self._real.conexao() as conexao:
            yield conexao


class EmbeddingsEspiao(ProvedorDeEmbeddingsFalso):
    def __init__(self, eventos: list[str], falhar: bool = False) -> None:
        super().__init__(dimensao=8)
        self._eventos = eventos
        self._falhar = falhar

    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        self._eventos.append("gerar")
        if self._falhar:
            raise TimeoutError("o provedor não respondeu")
        return super().gerar(textos)


def _memoria(
    provedor: object,
    referencia: Memoria,
    embeddings: ProvedorDeEmbeddingsFalso | None = None,
) -> Memoria:
    """Uma ``Memoria`` do "app" no mesmo schema, tenant e relógio da ``referencia``."""
    return Memoria(
        conexao=provedor,  # type: ignore[arg-type]
        embeddings=embeddings or ProvedorDeEmbeddingsFalso(dimensao=8),
        tenant_id=referencia.tenant_id,
        schema=referencia.schema,
        relogio=referencia.relogio,
    )


@pytest.mark.parametrize("modo", list(ModoDeTransacao))
def test_conexao_em_autocommit_e_recusada(memoria: Memoria, dsn: str, schema: str, modo):
    with psycopg.connect(dsn, autocommit=True) as conexao:
        app = _memoria(ProvedorDeConexaoUnica(conexao, modo), memoria)
        with pytest.raises(ErroDeConfiguracao, match="autocommit"):
            app.lembrar("dono-1", "x", categoria="nota")
    assert memoria.recuperar("dono-1") == []


def test_participar_some_com_o_rollback_do_app(memoria: Memoria, dsn: str, schema: str):
    with psycopg.connect(dsn) as conexao:
        app = _memoria(ProvedorDeConexaoUnica(conexao, ModoDeTransacao.PARTICIPAR), memoria)
        app.lembrar("dono-1", "desfeita", categoria="nota")
        assert [r.versao.conteudo for r in app.recuperar("dono-1")] == ["desfeita"]
        conexao.rollback()
        app.lembrar("dono-1", "confirmada", categoria="nota")
        conexao.commit()
    assert [r.versao.conteudo for r in memoria.recuperar("dono-1")] == ["confirmada"]


def test_participar_nunca_faz_commit_sozinho(memoria: Memoria, dsn: str, schema: str):
    with psycopg.connect(dsn) as conexao:
        app = _memoria(ProvedorDeConexaoUnica(conexao, ModoDeTransacao.PARTICIPAR), memoria)
        app.lembrar("dono-1", "pendente", categoria="nota")
        assert [r.versao.conteudo for r in app.recuperar("dono-1")] == ["pendente"]
        assert memoria.recuperar("dono-1") == []  # outra conexão não vê nada ainda
        conexao.rollback()


def test_propria_desfaz_a_operacao_que_falha_no_meio(
    memoria: Memoria, dono: str, relogio: RelogioManual, monkeypatch: pytest.MonkeyPatch
):
    original = memoria.lembrar(dono, "v1", categoria="nota")
    relogio.avancar(days=1)

    def falhar(*argumentos, **nomeados):
        raise RuntimeError("falha injetada depois de fechar o registro e inserir a cópia")

    monkeypatch.setattr(store, "inserir", falhar)
    with pytest.raises(RuntimeError, match="falha injetada"):
        memoria.substituir(dono, original.memoria_id, "v2")
    monkeypatch.undo()

    assert memoria.historico(dono, original.memoria_id) == [original]


def test_embedding_vem_antes_da_conexao(memoria: Memoria, dsn: str, schema: str):
    eventos: list[str] = []
    app = _memoria(ProvedorEspiao(dsn, eventos), memoria, EmbeddingsEspiao(eventos))
    app.lembrar("dono-1", "x", categoria="nota")
    assert eventos == ["gerar", "conexao"]


def test_falha_do_provedor_de_embeddings_nao_custa_conexao(memoria: Memoria, dsn: str):
    eventos: list[str] = []
    app = _memoria(ProvedorEspiao(dsn, eventos), memoria, EmbeddingsEspiao(eventos, falhar=True))
    with pytest.raises(ErroDeEmbedding):
        app.lembrar("dono-1", "x", categoria="nota")
    assert eventos == ["gerar"]


def test_schema_nao_migrado_nao_aborta_a_transacao_do_app(dsn: str, schema: str):
    # Regressão (reports/silent-failure-fatia-10.md, achado 3): `encerrar` num schema
    # ausente batia em 42P01, que aborta a transação do app no modo PARTICIPAR.
    with psycopg.connect(dsn) as conexao:
        app = Memoria(
            conexao=ProvedorDeConexaoUnica(conexao, ModoDeTransacao.PARTICIPAR),  # type: ignore[arg-type]
            embeddings=ProvedorDeEmbeddingsFalso(dimensao=8),
            tenant_id="t",
            schema=schema,
        )
        with pytest.raises(ErroDeConfiguracao, match="migrar"):
            app.encerrar("d", "00000000-0000-0000-0000-000000000000")
        assert conexao.execute("SELECT 1").fetchone() == (1,)  # a transação segue viva
        conexao.rollback()


def test_versao_esperada_em_maiusculas_ainda_e_a_mesma(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    # Regressão (achado 9): um uuid em outra caixa virava ErroDeConflito para sempre.
    vigente = memoria.lembrar(dono, "v1", categoria="nota")
    relogio.avancar(days=1)
    nova = memoria.substituir(
        dono, vigente.memoria_id, "v2", versao_esperada_id=vigente.versao_id.upper()
    )
    assert nova.conteudo == "v2"


class ProvedorComModoEmTexto:
    """Um provedor do app que declara o modo como texto, não como o enum."""

    def __init__(self, dsn: str, modo: str) -> None:
        self._real = ProvedorDSN(dsn)
        self.modo_de_transacao = modo

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        with self._real.conexao() as conexao:
            yield conexao


def test_modo_em_texto_vale_o_mesmo_que_o_enum(memoria: Memoria, dsn: str):
    # Regressão (reports/review-change-core.md, bloqueador 1): "propria" era tratado
    # como PARTICIPAR, e a escrita sumia sem commit e sem erro.
    app = _memoria(ProvedorComModoEmTexto(dsn, "propria"), memoria)
    app.lembrar("dono-1", "gravada", categoria="nota")
    assert [r.versao.conteudo for r in memoria.recuperar("dono-1")] == ["gravada"]


def test_modo_invalido_e_recusado(memoria: Memoria, dsn: str):
    app = _memoria(ProvedorComModoEmTexto(dsn, "automatico"), memoria)
    with pytest.raises(ErroDeConfiguracao, match="modo_de_transacao"):
        app.lembrar("dono-1", "x", categoria="nota")
