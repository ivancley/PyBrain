"""Cenário: isolamento. Nada de um tenant ou de um dono alcança outro, em nenhum modo."""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroNaoEncontrado, Memoria
from tests.conftest import RelogioManual


def test_dois_tenants_mesmo_dono_id(
    memoria: Memoria, memoria_outro_tenant: Memoria, dono: str, relogio: RelogioManual
):
    minha = memoria.lembrar(dono, "minha", categoria="nota")
    memoria_outro_tenant.lembrar(dono, "deles", categoria="nota")
    relogio.avancar(days=1)

    for argumentos in ({}, {"como_em": relogio()}, {"sabido_em": relogio()}):
        assert [r.versao.conteudo for r in memoria.recuperar(dono, **argumentos)] == ["minha"]
        assert [r.versao.conteudo for r in memoria_outro_tenant.recuperar(dono, **argumentos)] == [
            "deles"
        ]

    with pytest.raises(ErroNaoEncontrado):
        memoria_outro_tenant.historico(dono, minha.memoria_id)


def test_dois_donos_mesmo_tenant(memoria: Memoria, dono: str, outro_dono: str):
    minha = memoria.lembrar(dono, "minha", categoria="nota")
    memoria.lembrar(outro_dono, "deles", categoria="nota")

    assert [r.versao.conteudo for r in memoria.recuperar(outro_dono)] == ["deles"]
    with pytest.raises(ErroNaoEncontrado):
        memoria.substituir(outro_dono, minha.memoria_id, "sequestrada")
    assert [v.conteudo for v in memoria.historico(dono, minha.memoria_id)] == ["minha"]
