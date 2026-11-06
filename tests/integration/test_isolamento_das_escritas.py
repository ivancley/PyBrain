"""As escritas que alcançam várias linhas por contexto ou entidade respeitam tenant e dono.

reports/review-change-core.md, importante 4: com ``OR true`` no filtro de dono, os
testes anteriores continuavam verdes, porque o outro dono não tinha o mesmo
contexto nem a mesma entidade.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroNaoEncontrado, Memoria
from tests.conftest import RelogioManual


@pytest.fixture
def alheias(memoria: Memoria, memoria_outro_tenant: Memoria, outro_dono: str, dono: str):
    """Mesmo contexto e mesma entidade, em outro dono e em outro tenant."""
    memoria.lembrar(outro_dono, "do outro dono", categoria="nota", contexto_id="c", entidade_id="e")
    memoria_outro_tenant.lembrar(
        dono, "do outro tenant", categoria="nota", contexto_id="c", entidade_id="e"
    )


def test_invalidar_contexto_nao_toca_o_que_e_alheio(
    memoria: Memoria, memoria_outro_tenant: Memoria, dono: str, outro_dono: str, alheias
):
    memoria.lembrar(dono, "minha", categoria="nota", contexto_id="c")
    assert memoria.invalidar_contexto(dono, "c") == 1
    assert [r.versao.conteudo for r in memoria.recuperar(outro_dono)] == ["do outro dono"]
    assert [r.versao.conteudo for r in memoria_outro_tenant.recuperar(dono)] == ["do outro tenant"]


def test_esquecer_por_entidade_nao_toca_o_que_e_alheio(
    memoria: Memoria, memoria_outro_tenant: Memoria, dono: str, outro_dono: str, alheias
):
    memoria.lembrar(dono, "minha", categoria="nota", entidade_id="e")
    assert memoria.esquecer(dono, entidade_id="e") == 1
    assert [r.versao.conteudo for r in memoria.recuperar(outro_dono)] == ["do outro dono"]
    assert [r.versao.conteudo for r in memoria_outro_tenant.recuperar(dono)] == ["do outro tenant"]


def test_corrigir_e_encerrar_memoria_alheia_e_nao_encontrada(
    memoria: Memoria, dono: str, outro_dono: str, relogio: RelogioManual
):
    alheia = memoria.lembrar(outro_dono, "alheia", categoria="nota")
    relogio.avancar(days=1)
    with pytest.raises(ErroNaoEncontrado):
        memoria.corrigir(dono, alheia.memoria_id, "invadida")
    with pytest.raises(ErroNaoEncontrado):
        memoria.encerrar(dono, alheia.memoria_id)
    assert memoria.historico(outro_dono, alheia.memoria_id) == [alheia]
