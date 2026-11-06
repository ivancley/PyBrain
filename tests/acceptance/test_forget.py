"""Cenário: esquecer. Depois dele, nenhuma versão existe, em nenhum modo de consulta."""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroDeArgumentoInvalido, ErroNaoEncontrado, Memoria
from tests.conftest import RelogioManual


def test_esquecer_uma_memoria_apaga_toda_versao(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    v1 = memoria.lembrar(dono, "a", categoria="nota")
    relogio.avancar(days=1)
    memoria.substituir(dono, v1.memoria_id, "b")
    relogio.avancar(days=1)
    memoria.corrigir(dono, v1.memoria_id, "c")
    relogio.avancar(days=1)

    # lembrar (1) + substituir (cópia e nova: 2) + corrigir (1) = 4 linhas
    assert memoria.esquecer(dono, memoria_id=v1.memoria_id) == 4
    with pytest.raises(ErroNaoEncontrado):
        memoria.historico(dono, v1.memoria_id)
    for argumentos in ({}, {"como_em": relogio.em(days=1)}, {"sabido_em": relogio.em(days=1)}):
        assert memoria.recuperar(dono, **argumentos) == []


def test_esquecer_por_entidade_e_tudo(memoria: Memoria, dono: str, outro_dono: str):
    memoria.lembrar(dono, "sobre e-1", categoria="nota", entidade_id="e-1")
    memoria.lembrar(dono, "sobre e-2", categoria="nota", entidade_id="e-2")
    memoria.lembrar(outro_dono, "intocada", categoria="nota")

    assert memoria.esquecer(dono, entidade_id="e-1") == 1
    assert [r.versao.entidade_id for r in memoria.recuperar(dono)] == ["e-2"]
    assert memoria.esquecer(dono, tudo=True) == 1
    assert memoria.recuperar(dono) == []
    assert [r.versao.conteudo for r in memoria.recuperar(outro_dono)] == ["intocada"]


def test_esquecer_exige_exatamente_um_alvo(memoria: Memoria, dono: str):
    with pytest.raises(ErroDeArgumentoInvalido):
        memoria.esquecer(dono)
    assert memoria.esquecer(dono, memoria_id="nunca-existiu") == 0
