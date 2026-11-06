"""Fatia 1: ``lembrar`` e ``recuperar()`` de ponta a ponta contra o Postgres real."""

from __future__ import annotations

from memory_lifecycle import Memoria
from tests.conftest import T0, RelogioManual


def test_o_que_foi_lembrado_volta_em_recuperar(memoria: Memoria, dono: str):
    lembrada = memoria.lembrar(dono, "prefere respostas curtas", categoria="preferencia")

    [resultado] = memoria.recuperar(dono)

    assert resultado.versao == lembrada
    assert resultado.pontuacao is None
    assert (lembrada.tenant_id, lembrada.dono_id) == (memoria.tenant_id, dono)
    assert lembrada.versao_anterior_id is None
    assert lembrada.substituido_em is None and lembrada.valido_ate is None
    assert lembrada.modelo_embedding == "falso"


def test_registrado_em_vem_do_relogio_injetado(memoria: Memoria, dono: str, relogio: RelogioManual):
    relogio.avancar(days=3)

    lembrada = memoria.lembrar(dono, "x", categoria="nota")

    assert lembrada.registrado_em == T0.replace(day=4)
    assert lembrada.valido_de == lembrada.registrado_em


def test_o_mais_recente_vem_primeiro_e_o_limite_corta(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    for conteudo in ("a", "b", "c"):
        memoria.lembrar(dono, conteudo, categoria="nota")
        relogio.avancar(days=1)

    assert [r.versao.conteudo for r in memoria.recuperar(dono, limite=2)] == ["c", "b"]


def test_migrar_de_novo_nao_aplica_nada(memoria: Memoria):
    assert memoria.migrar() == 0
