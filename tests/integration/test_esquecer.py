"""Spec ``forget``: depois de esquecer, nenhuma linha fica no banco, nem nas cópias."""

from __future__ import annotations

import psycopg

from memory_lifecycle import Memoria
from tests.conftest import RelogioManual


def _linhas_no_banco(dsn: str, schema: str, memoria_id: str) -> int:
    with psycopg.connect(dsn) as conexao:
        linha = conexao.execute(
            f'SELECT count(*) FROM "{schema}".versoes_de_memoria WHERE memoria_id = %s::uuid',
            (memoria_id,),
        ).fetchone()
    assert linha is not None
    return int(linha[0])


def test_esquecer_nao_deixa_linha_nenhuma(
    memoria: Memoria, dono: str, relogio: RelogioManual, dsn: str, schema: str
):
    v = memoria.lembrar(dono, "a", categoria="nota", entidade_id="e-1")
    relogio.avancar(days=1)
    memoria.substituir(dono, v.memoria_id, "b", entidade_id="e-2")
    relogio.avancar(days=1)
    memoria.encerrar(dono, v.memoria_id)
    # lembrar (1) + substituir (cópia e nova: 2) + encerrar (cópia: 1)
    assert _linhas_no_banco(dsn, schema, v.memoria_id) == 4

    # Por entidade, a memória inteira sai, mesmo as versões que já citam outra entidade.
    assert memoria.esquecer(dono, entidade_id="e-1") == 4
    assert _linhas_no_banco(dsn, schema, v.memoria_id) == 0


def test_esquecer_nao_toca_outro_tenant(
    memoria: Memoria, memoria_outro_tenant: Memoria, dono: str, dsn: str, schema: str
):
    alheia = memoria_outro_tenant.lembrar(dono, "do outro tenant", categoria="nota")
    assert memoria.esquecer(dono, tudo=True) == 0
    assert memoria.esquecer(dono, memoria_id=alheia.memoria_id) == 0
    assert _linhas_no_banco(dsn, schema, alheia.memoria_id) == 1
