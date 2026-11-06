"""Duas substituições da mesma versão, em duas conexões ao mesmo tempo (ADR 0002).

Uma barreira segura as duas threads depois de lerem a vigente e antes de fecharem
o registro: as duas tentam fechar a mesma linha. O fechamento condicional deixa
uma vencer e a outra levantar ``ErroDeConflito``; nada é sobrescrito em silêncio.
"""

from __future__ import annotations

import threading

import pytest

from memory_lifecycle import ErroDeConflito, Memoria, ProvedorDeEmbeddingsFalso, store
from memory_lifecycle.connection.dsn import ProvedorDSN
from tests.conftest import RelogioManual


def test_duas_substituicoes_em_duas_conexoes(
    memoria: Memoria,
    dono: str,
    relogio: RelogioManual,
    dsn: str,
    schema: str,
    monkeypatch: pytest.MonkeyPatch,
):
    original = memoria.lembrar(dono, "v1", categoria="nota")
    relogio.avancar(days=1)
    barreira = threading.Barrier(2, timeout=10)
    fechar_de_verdade = store.fechar_registro

    def fechar_depois_da_barreira(*argumentos, **nomeados):
        barreira.wait()
        return fechar_de_verdade(*argumentos, **nomeados)

    monkeypatch.setattr(store, "fechar_registro", fechar_depois_da_barreira)
    resultados: dict[str, object] = {}

    def escritor(nome: str) -> None:
        propria = Memoria(
            conexao=ProvedorDSN(dsn),
            embeddings=ProvedorDeEmbeddingsFalso(dimensao=8),
            tenant_id=memoria.tenant_id,
            schema=schema,
            relogio=relogio,
        )
        try:
            resultados[nome] = propria.substituir(dono, original.memoria_id, f"de {nome}")
        except Exception as erro:  # o teste inspeciona o tipo abaixo
            resultados[nome] = erro

    threads = [threading.Thread(target=escritor, args=(nome,)) for nome in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    conflitos = [r for r in resultados.values() if isinstance(r, ErroDeConflito)]
    vencedoras = [r for r in resultados.values() if not isinstance(r, Exception)]
    assert (len(conflitos), len(vencedoras)) == (1, 1), resultados
    historico = memoria.historico(dono, original.memoria_id)
    assert len(historico) == 3
    assert historico[-1] == vencedoras[0]


def test_dois_encerramentos_em_duas_conexoes(
    memoria: Memoria,
    dono: str,
    relogio: RelogioManual,
    dsn: str,
    schema: str,
    monkeypatch: pytest.MonkeyPatch,
):
    original = memoria.lembrar(dono, "v1", categoria="nota")
    relogio.avancar(days=1)
    barreira = threading.Barrier(2, timeout=10)
    fechar_de_verdade = store.fechar_registro

    def fechar_depois_da_barreira(*argumentos, **nomeados):
        barreira.wait()
        return fechar_de_verdade(*argumentos, **nomeados)

    monkeypatch.setattr(store, "fechar_registro", fechar_depois_da_barreira)
    resultados: list[object] = []

    def escritor() -> None:
        propria = Memoria(
            conexao=ProvedorDSN(dsn),
            embeddings=ProvedorDeEmbeddingsFalso(dimensao=8),
            tenant_id=memoria.tenant_id,
            schema=schema,
            relogio=relogio,
        )
        try:
            resultados.append(propria.encerrar(dono, original.memoria_id))
        except Exception as erro:  # o teste inspeciona o tipo abaixo
            resultados.append(erro)

    threads = [threading.Thread(target=escritor) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sum(isinstance(r, ErroDeConflito) for r in resultados) == 1, resultados
    assert len(memoria.historico(dono, original.memoria_id)) == 2
