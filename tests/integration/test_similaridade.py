"""Spec ``recall``: com ``consulta``, ordem por similaridade e pontuação em [0, 1] (ADR 0009)."""

from __future__ import annotations

import math

import pytest

from memory_lifecycle import ErroDeArgumentoInvalido, Memoria
from tests.conftest import RelogioManual

TEXTOS = ["prefere respostas curtas", "mora em Lisboa", "gosta de exemplos", "usa Python"]


def test_texto_identico_vem_primeiro_com_pontuacao_um(memoria: Memoria, dono: str):
    for texto in TEXTOS:
        memoria.lembrar(dono, texto, categoria="nota")

    resultados = memoria.recuperar(dono, consulta="mora em Lisboa")

    assert resultados[0].versao.conteudo == "mora em Lisboa"
    assert resultados[0].pontuacao is not None
    assert math.isclose(resultados[0].pontuacao, 1.0, abs_tol=1e-6)
    pontuacoes = [r.pontuacao for r in resultados]
    assert all(p is not None and 0.0 <= p <= 1.0 for p in pontuacoes)
    assert pontuacoes == sorted(pontuacoes, reverse=True)  # type: ignore[type-var]
    assert len(resultados) == len(TEXTOS)


def test_consulta_respeita_escopo_modo_e_limite(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    memoria.lembrar(dono, "mora em Lisboa", categoria="nota", contexto_id="c1")
    relogio.avancar(days=1)
    porto = memoria.lembrar(dono, "mora no Porto", categoria="nota")
    relogio.avancar(days=1)
    memoria.encerrar(dono, porto.memoria_id)

    no_escopo = memoria.recuperar(dono, consulta="mora em Lisboa", contextos=[None])
    assert no_escopo == []
    ontem = memoria.recuperar(dono, consulta="mora", como_em=relogio.em(days=1), limite=1)
    assert len(ontem) == 1


def test_consulta_vazia_e_recusada(memoria: Memoria, dono: str):
    with pytest.raises(ErroDeArgumentoInvalido):
        memoria.recuperar(dono, consulta="  ")
