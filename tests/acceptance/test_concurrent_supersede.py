"""Cenário: duas substituições da mesma versão. Uma vence; a outra falha alto.

A Etapa 1 expressa a corrida por ``versao_esperada_id``: os dois escritores
seguram a mesma versão vigente. A Etapa 3 acrescenta a variante com duas
conexões, que exercita o próprio fechamento condicional.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroDeConflito, Memoria
from tests.conftest import RelogioManual


def test_segundo_escritor_entra_em_conflito(memoria: Memoria, dono: str, relogio: RelogioManual):
    vigente = memoria.lembrar(dono, "v1", categoria="nota")
    relogio.avancar(days=1)  # uma validade precisa durar mais que zero

    vencedora = memoria.substituir(
        dono, vigente.memoria_id, "v2", versao_esperada_id=vigente.versao_id
    )
    with pytest.raises(ErroDeConflito):
        memoria.substituir(dono, vigente.memoria_id, "v2'", versao_esperada_id=vigente.versao_id)

    # Só as linhas da substituição vencedora: a original, a cópia e a nova.
    historico = memoria.historico(dono, vigente.memoria_id)
    assert len(historico) == 3
    assert (historico[0].versao_id, historico[-1].versao_id) == (
        vigente.versao_id,
        vencedora.versao_id,
    )
