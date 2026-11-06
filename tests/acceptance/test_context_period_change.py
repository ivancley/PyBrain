"""Cenário: um contexto muda de período. Memórias de um período não vazam no seguinte.

O escopo é estrito: uma memória sem contexto só entra quando ``contextos`` inclui
``None`` como membro; ``contextos=None`` não filtra por este eixo.
"""

from __future__ import annotations

from memory_lifecycle import Memoria
from tests.conftest import RelogioManual


def test_periodo_anterior_sai_do_escopo_mas_nao_some(memoria: Memoria, dono: str):
    antiga = memoria.lembrar(
        dono, "tem dificuldade com o tópico A", categoria="observacao", contexto_id="p-2026"
    )
    memoria.lembrar(dono, "sempre pontual", categoria="preferencia")  # sem contexto

    # O período seguinte não enxerga o anterior; a memória sem contexto só entra
    # quando o escopo diz que None está ativo.
    assert memoria.recuperar(dono, contextos=["p-2027"]) == []
    proximo_periodo = memoria.recuperar(dono, contextos=["p-2027", None])
    assert [r.versao.conteudo for r in proximo_periodo] == ["sempre pontual"]

    anterior = memoria.recuperar(dono, contextos=["p-2026", None])
    assert {r.versao.conteudo for r in anterior} == {
        "tem dificuldade com o tópico A",
        "sempre pontual",
    }
    so_o_periodo = memoria.recuperar(dono, contextos=["p-2026"])
    assert [r.versao.conteudo for r in so_o_periodo] == ["tem dificuldade com o tópico A"]
    assert len(memoria.historico(dono, antiga.memoria_id)) == 1  # sair do escopo não escreve


def test_invalidar_contexto_e_um_encerrar_explicito(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    memoria.lembrar(dono, "a", categoria="nota", contexto_id="c-1")
    memoria.lembrar(dono, "b", categoria="nota", contexto_id="c-1")
    memoria.lembrar(dono, "c", categoria="nota", contexto_id="c-2")
    relogio.avancar(days=10)

    assert memoria.invalidar_contexto(dono, "c-1") == 2
    agora = memoria.recuperar(dono, contextos=["c-1", "c-2"])
    assert [r.versao.conteudo for r in agora] == ["c"]
    antes = memoria.recuperar(dono, contextos=["c-1", "c-2"], como_em=relogio.em(days=5))
    assert {r.versao.conteudo for r in antes} == {"a", "b", "c"}
