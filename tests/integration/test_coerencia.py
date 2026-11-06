"""O SQL de ``recuperar`` concorda com o oráculo ``temporal.vale_em``, nos dois modos.

Gera históricos aleatórios (semente fixa) com as operações já implementadas,
inclusive retroativas, e compara, para muitos instantes, o conjunto de versões que
o banco devolve com o conjunto que a regra em Python aceita. Acha as bordas que
os cenários escritos à mão não acham.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime, timedelta

from memory_lifecycle import ErroDeArgumentoInvalido, ErroDeConflito, Memoria, VersaoDeMemoria
from memory_lifecycle.temporal import Momento, vale_em
from tests.conftest import T0, RelogioManual

SEMENTE = 20261106
MEMORIAS = 60
INSTANTES = 40
HORA = timedelta(hours=1)


def _instante(sorteio: random.Random, perto_de: datetime) -> datetime:
    return perto_de + sorteio.randint(-24 * 60, 24 * 60) * HORA


def _operacoes(
    memoria: Memoria, dono: str
) -> list[Callable[[random.Random, str, datetime], object]]:
    """As operações que mudam o tempo, sorteadas sobre cada memória."""
    return [
        lambda s, mid, agora: memoria.encerrar(dono, mid, valido_ate=_instante(s, agora)),
        lambda s, mid, agora: memoria.substituir(
            dono, mid, f"sub-{s.random()}", valido_de=_instante(s, agora)
        ),
        lambda s, mid, agora: memoria.corrigir(dono, mid, f"cor-{s.random()}"),
    ]


def _gerar(memoria: Memoria, dono: str, relogio: RelogioManual) -> list[str]:
    sorteio = random.Random(SEMENTE)
    operacoes = _operacoes(memoria, dono)
    ids: list[str] = []
    for i in range(MEMORIAS):
        relogio.avancar(hours=sorteio.randint(1, 48))
        inicio = _instante(sorteio, relogio())
        fim = inicio + sorteio.randint(1, 24 * 90) * HORA if sorteio.random() < 0.3 else None
        ids.append(
            memoria.lembrar(
                dono, f"m{i}", categoria="nota", valido_de=inicio, valido_ate=fim
            ).memoria_id
        )
        for _ in range(sorteio.randint(0, 3)):
            relogio.avancar(hours=sorteio.randint(1, 48))
            operacao = sorteio.choice(operacoes)
            try:
                operacao(sorteio, ids[-1], relogio())
            except (ErroDeConflito, ErroDeArgumentoInvalido):
                pass  # operação recusada pela regra (validade já fechada, limite antes do início)
    return ids


def test_sql_concorda_com_o_oraculo(memoria: Memoria, dono: str, relogio: RelogioManual):
    ids = _gerar(memoria, dono, relogio)
    todas: list[VersaoDeMemoria] = [v for mid in ids for v in memoria.historico(dono, mid)]
    sorteio = random.Random(SEMENTE + 1)
    fim = relogio()
    instantes = [T0 + (fim - T0) * sorteio.random() for _ in range(INSTANTES)]
    instantes += [v.registrado_em for v in todas[:10]] + [v.valido_de for v in todas[:10]]

    divergencias = []
    for instante in instantes:
        for modo in ("como_em", "sabido_em"):
            esperado = {v.versao_id for v in todas if vale_em(v, Momento(modo, instante))}
            obtido = {
                r.versao.versao_id
                for r in memoria.recuperar(dono, limite=10_000, **{modo: instante})
            }
            if esperado != obtido:
                divergencias.append((modo, instante, esperado ^ obtido))
    assert not divergencias, divergencias[:3]
    # Um gerador que só engole erros deixaria o teste verde sem testar nada.
    fechadas = sum(v.substituido_em is not None for v in todas)
    copias = sum(v.versao_anterior_id is not None and v.valido_ate is not None for v in todas)
    assert fechadas >= MEMORIAS // 2, f"só {fechadas} registros fechados em {len(todas)} versões"
    assert copias >= MEMORIAS // 4, f"só {copias} cópias limitadas"
