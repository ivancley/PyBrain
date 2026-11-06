"""Cenário: correção. Corrigir × os três modos de consulta mantém a trilha de auditoria."""

from __future__ import annotations

from memory_lifecycle import Memoria, Status, derivar_status
from tests.conftest import RelogioManual


def test_corrigir_reescreve_o_passado_mas_nao_o_registro(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    errada = memoria.lembrar(dono, "nasceu em 1990", categoria="fato")
    relogio.avancar(days=150)  # junho
    certa = memoria.corrigir(dono, errada.memoria_id, "nasceu em 1991")
    relogio.avancar(days=30)

    assert certa.valido_de == errada.valido_de
    assert [r.versao.conteudo for r in memoria.recuperar(dono)] == ["nasceu em 1991"]
    marco = memoria.recuperar(dono, como_em=relogio.em(days=60))
    assert [r.versao.conteudo for r in marco] == ["nasceu em 1991"]
    maio = memoria.recuperar(dono, sabido_em=relogio.em(days=120))
    assert [r.versao.conteudo for r in maio] == ["nasceu em 1990"]

    historico = memoria.historico(dono, errada.memoria_id)
    assert derivar_status(historico[0], agora=relogio(), sucessora=historico[1]) is Status.CORRIGIDA
    assert derivar_status(historico[1], agora=relogio()) is Status.ATIVA
