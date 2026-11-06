"""Cenário: os três modos discordam sobre o mesmo histórico (spec ``recall``).

Foi este cenário que expôs a contradição da primeira versão do ADR 0002: com a
antiga de registro fechado, ``como_em=março`` não achava o fato de janeiro.
"""

from __future__ import annotations

from memory_lifecycle import Memoria, Status, derivar_status
from tests.conftest import RelogioManual


def test_agora_como_em_e_sabido_em_sobre_uma_cadeia(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    memoria_id = memoria.lembrar(dono, "curtas", categoria="preferencia").memoria_id
    relogio.avancar(days=151)  # 1º de junho
    memoria.substituir(dono, memoria_id, "detalhadas")
    relogio.avancar(days=30)  # 1º de julho
    memoria.corrigir(dono, memoria_id, "detalhadas, com fontes")
    relogio.avancar(days=30)

    def conteudos(**momento: object) -> list[str]:
        return [r.versao.conteudo for r in memoria.recuperar(dono, **momento)]  # type: ignore[arg-type]

    assert conteudos() == ["detalhadas, com fontes"]
    assert conteudos(como_em=relogio.em(days=60)) == ["curtas"]
    assert conteudos(como_em=relogio.em(days=165)) == ["detalhadas, com fontes"]
    assert conteudos(sabido_em=relogio.em(days=120)) == ["curtas"]
    assert conteudos(sabido_em=relogio.em(days=165)) == ["detalhadas"]

    historico = memoria.historico(dono, memoria_id)
    sucessoras = {v.versao_anterior_id: v for v in historico}
    status = [
        derivar_status(v, agora=relogio(), sucessora=sucessoras.get(v.versao_id)) for v in historico
    ]
    assert status == [Status.SUBSTITUIDA, Status.SUBSTITUIDA, Status.CORRIGIDA, Status.ATIVA]
