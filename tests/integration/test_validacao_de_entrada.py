"""Entradas inválidas são recusadas antes de qualquer instrução (reports/review-change-core.md, importante 5).

Antes, chegavam ao banco como erro cru do driver e, no modo ``PARTICIPAR``,
abortavam a transação do app.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroDeArgumentoInvalido, Memoria, ProvedorDeEmbeddingsFalso
from memory_lifecycle.connection.dsn import ProvedorDSN
from tests.conftest import RelogioManual


@pytest.mark.parametrize("dono_id", [None, "", "  ", 42])
def test_dono_invalido_e_recusado(memoria: Memoria, dono_id: object):
    with pytest.raises(ErroDeArgumentoInvalido, match="dono_id"):
        memoria.lembrar(dono_id, "x", categoria="nota")  # type: ignore[arg-type]
    with pytest.raises(ErroDeArgumentoInvalido, match="dono_id"):
        memoria.recuperar(dono_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("tenant_id", [None, "", " "])
def test_tenant_invalido_e_recusado_na_construcao(dsn: str, tenant_id: object):
    with pytest.raises(ErroDeArgumentoInvalido, match="tenant_id"):
        Memoria(
            conexao=ProvedorDSN(dsn),
            embeddings=ProvedorDeEmbeddingsFalso(),
            tenant_id=tenant_id,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("categoria", ["", "   "])
def test_categoria_vazia_em_substituir_e_corrigir(
    memoria: Memoria, dono: str, relogio: RelogioManual, categoria: str
):
    v = memoria.lembrar(dono, "a", categoria="nota")
    relogio.avancar(days=1)
    with pytest.raises(ErroDeArgumentoInvalido, match="categoria"):
        memoria.substituir(dono, v.memoria_id, "b", categoria=categoria)
    with pytest.raises(ErroDeArgumentoInvalido, match="categoria"):
        memoria.corrigir(dono, v.memoria_id, "b", categoria=categoria)
    assert memoria.historico(dono, v.memoria_id) == [v]


def test_esquecer_com_mais_de_um_alvo_e_recusado(memoria: Memoria, dono: str):
    v = memoria.lembrar(dono, "a", categoria="nota", entidade_id="e")
    with pytest.raises(ErroDeArgumentoInvalido, match="exatamente um alvo"):
        memoria.esquecer(dono, memoria_id=v.memoria_id, tudo=True)
    assert memoria.historico(dono, v.memoria_id) == [v]


def test_historico_com_relogio_congelado_termina_na_vigente(memoria: Memoria, dono: str):
    # Regressão (reports/temporal-change-core.md, P2): no empate de registrado_em a
    # última versão do histórico era a errada em metade das execuções.
    for _ in range(10):
        v = memoria.lembrar(dono, "errada", categoria="nota")
        certa = memoria.corrigir(dono, v.memoria_id, "certa")
        assert memoria.historico(dono, v.memoria_id)[-1] == certa
