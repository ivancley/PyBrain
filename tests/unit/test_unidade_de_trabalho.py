"""O fluxo de erro da unidade de trabalho, com uma conexão de mentira só para o controle.

O comportamento contra o banco está em ``tests/integration/test_transacao.py``; aqui
fica o que um banco real não deixa provocar: o ``close`` e o ``rollback`` falhando.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from memory_lifecycle import ModoDeTransacao
from memory_lifecycle.connection._unidade import unidade_de_trabalho


class CursorQueNaoFecha:
    rowcount = 0

    def close(self) -> None:
        raise OSError("a conexão caiu ao fechar o cursor")


class ConexaoQueNaoDesfaz:
    autocommit = False

    def cursor(self) -> CursorQueNaoFecha:
        return CursorQueNaoFecha()

    def commit(self) -> None:
        raise AssertionError("não deveria chegar ao commit")

    def rollback(self) -> None:
        raise OSError("a conexão caiu no rollback")


class Provedor:
    modo_de_transacao = ModoDeTransacao.PROPRIA

    @contextmanager
    def conexao(self) -> Iterator[ConexaoQueNaoDesfaz]:
        yield ConexaoQueNaoDesfaz()


def test_falhas_de_close_e_rollback_viram_nota_no_erro_original():
    # Regressão (reports/silent-failure-fatia-10.md, achado 10): o `finally: close()`
    # trocava o erro da operação pelo erro de fechamento.
    with pytest.raises(ValueError, match="o erro da operação") as erro:
        with unidade_de_trabalho(Provedor()):  # type: ignore[arg-type]
            raise ValueError("o erro da operação")
    notas = " ".join(getattr(erro.value, "__notes__", []))
    assert "fechar o cursor também falhou" in notas
    assert "o rollback também falhou" in notas
