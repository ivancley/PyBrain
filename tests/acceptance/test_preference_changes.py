"""Cenário: uma preferência muda. Substituir × os três modos de consulta."""

from __future__ import annotations

from memory_lifecycle import Memoria
from tests.conftest import RelogioManual


def test_substituir_muda_o_agora_e_mantem_o_passado(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    v1 = memoria.lembrar(dono, "prefere respostas curtas", categoria="preferencia")
    relogio.avancar(days=150)  # junho
    v2 = memoria.substituir(dono, v1.memoria_id, "prefere respostas detalhadas")
    relogio.avancar(days=30)  # julho

    agora = memoria.recuperar(dono, categoria="preferencia")
    assert [r.versao.conteudo for r in agora] == ["prefere respostas detalhadas"]

    marco = memoria.recuperar(dono, categoria="preferencia", como_em=relogio.em(days=60))
    assert [r.versao.conteudo for r in marco] == ["prefere respostas curtas"]

    maio = memoria.recuperar(dono, categoria="preferencia", sabido_em=relogio.em(days=120))
    assert [r.versao.versao_id for r in maio] == [v1.versao_id]

    # A original fica intacta com o registro fechado; a cópia limitada carrega o fim
    # da validade; a nova aponta para a cópia (ADR 0002).
    original, copia, nova = memoria.historico(dono, v1.memoria_id)
    assert original.versao_id == v1.versao_id
    assert original.valido_ate is None
    assert original.substituido_em == relogio.em(days=150)
    assert (copia.conteudo, copia.valido_ate) == ("prefere respostas curtas", relogio.em(days=150))
    assert copia.versao_anterior_id == v1.versao_id
    assert nova.versao_id == v2.versao_id
    assert v2.versao_anterior_id == copia.versao_id


def test_substituir_herda_o_escopo(memoria: Memoria, dono: str, relogio: RelogioManual):
    v1 = memoria.lembrar(dono, "a", categoria="nota", entidade_id="e-1", contexto_id="c-1")
    relogio.avancar(days=1)  # uma validade precisa durar mais que zero
    v2 = memoria.substituir(dono, v1.memoria_id, "b")
    assert (v2.entidade_id, v2.contexto_id, v2.categoria) == ("e-1", "c-1", "nota")


def test_substituir_retroativo_e_futuro(memoria: Memoria, dono: str, relogio: RelogioManual):
    v1 = memoria.lembrar(dono, "a", categoria="nota")
    relogio.avancar(days=100)
    # Descobre-se no dia 100 que o fato mudou no dia 40.
    memoria.substituir(dono, v1.memoria_id, "b", valido_de=relogio.em(days=40))
    assert [r.versao.conteudo for r in memoria.recuperar(dono, como_em=relogio.em(days=50))] == [
        "b"
    ]
    assert [r.versao.conteudo for r in memoria.recuperar(dono, sabido_em=relogio.em(days=50))] == [
        "a"
    ]

    # E agenda-se uma mudança para o dia 200: até lá, vale "b".
    memoria.substituir(dono, v1.memoria_id, "c", valido_de=relogio.em(days=200))
    assert [r.versao.conteudo for r in memoria.recuperar(dono)] == ["b"]
    assert [r.versao.conteudo for r in memoria.recuperar(dono, como_em=relogio.em(days=250))] == [
        "c"
    ]
