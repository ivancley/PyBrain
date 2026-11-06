"""Cenário: um fato deixa de ser verdade. Encerrar × os três modos de consulta, e conflito."""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroDeConflito, Memoria
from tests.conftest import RelogioManual


def test_encerrar_sai_do_presente_e_fica_no_passado(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    v1 = memoria.lembrar(dono, "mora em Lisboa", categoria="fato")
    relogio.avancar(days=150)  # junho
    fechada = memoria.encerrar(dono, v1.memoria_id)
    relogio.avancar(days=30)

    assert fechada.valido_ate == relogio.em(days=150)
    assert fechada.versao_anterior_id == v1.versao_id
    assert memoria.recuperar(dono) == []
    # Pelo que sabemos hoje, em março valia a cópia encerrada; em maio, o sistema
    # sabia da versão de janeiro, ainda sem fim.
    marco = memoria.recuperar(dono, como_em=relogio.em(days=60))
    assert [r.versao.versao_id for r in marco] == [fechada.versao_id]
    maio = memoria.recuperar(dono, sabido_em=relogio.em(days=120))
    assert [r.versao.versao_id for r in maio] == [v1.versao_id]
    assert [v.versao_id for v in memoria.historico(dono, v1.memoria_id)] == [
        v1.versao_id,
        fechada.versao_id,
    ]


def test_encerramento_retroativo_nao_reescreve_o_que_se_sabia(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    v1 = memoria.lembrar(dono, "trabalha no projeto X", categoria="fato")
    relogio.avancar(days=180)  # julho: descobre-se que acabou em março
    memoria.encerrar(dono, v1.memoria_id, valido_ate=relogio.em(days=60))

    assert memoria.recuperar(dono, como_em=relogio.em(days=90)) == []  # abril
    maio = memoria.recuperar(dono, sabido_em=relogio.em(days=120))
    assert [r.versao.versao_id for r in maio] == [v1.versao_id]


def test_encerrar_duas_vezes_entra_em_conflito(memoria: Memoria, dono: str, relogio: RelogioManual):
    v1 = memoria.lembrar(dono, "x", categoria="fato")
    relogio.avancar(days=1)  # uma validade precisa durar mais que zero
    memoria.encerrar(dono, v1.memoria_id)
    with pytest.raises(ErroDeConflito):
        memoria.encerrar(dono, v1.memoria_id)
