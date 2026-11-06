"""Cenário: uma entidade sai do escopo. Fora do escopo não é encerrada; ela volta.

O escopo é estrito: uma memória sem entidade só entra quando ``entidades`` inclui
``None`` como membro; ``entidades=[]`` não devolve nada neste eixo.
"""

from __future__ import annotations

from memory_lifecycle import Memoria


def test_entidade_fora_do_escopo_some_e_volta(memoria: Memoria, dono: str):
    sobre = memoria.lembrar(
        dono, "precisa de apoio extra", categoria="observacao", entidade_id="e-1"
    )
    memoria.lembrar(dono, "aprende rápido", categoria="observacao", entidade_id="e-2")
    memoria.lembrar(dono, "vale para qualquer entidade", categoria="nota")  # sem entidade

    sem = memoria.recuperar(dono, entidades=["e-2"])
    assert [r.versao.entidade_id for r in sem] == ["e-2"]

    de_volta = memoria.recuperar(dono, entidades=["e-1", "e-2"])
    assert {r.versao.entidade_id for r in de_volta} == {"e-1", "e-2"}

    com_sem_entidade = memoria.recuperar(dono, entidades=["e-1", "e-2", None])
    assert {r.versao.entidade_id for r in com_sem_entidade} == {"e-1", "e-2", None}

    assert memoria.recuperar(dono, entidades=[]) == []
    assert len(memoria.historico(dono, sobre.memoria_id)) == 1  # sair do escopo não escreve
