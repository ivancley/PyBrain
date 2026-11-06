"""``invalidar_contexto`` (spec ``temporal-operations``; reports/review-change-core.md, importantes 2 e 3)."""

from __future__ import annotations

import threading
import time

import pytest

from memory_lifecycle import Memoria, ProvedorDeEmbeddingsFalso, store
from memory_lifecycle.connection.dsn import ProvedorDSN
from tests.conftest import RelogioManual


def _conteudos(memoria: Memoria, dono: str, **momento: object) -> set[str]:
    return {r.versao.conteudo for r in memoria.recuperar(dono, contextos=["c"], **momento)}  # type: ignore[arg-type]


def test_tambem_encerra_o_que_ainda_nao_comecou(
    memoria: Memoria, dono: str, relogio: RelogioManual
):
    memoria.lembrar(
        dono, "futura", categoria="nota", contexto_id="c", valido_de=relogio.em(days=10)
    )
    assert memoria.invalidar_contexto(dono, "c") == 1
    assert _conteudos(memoria, dono, como_em=relogio.em(days=20)) == set()


def test_encurta_o_que_terminaria_depois(memoria: Memoria, dono: str, relogio: RelogioManual):
    memoria.lembrar(
        dono, "até o fim do ano", categoria="nota", contexto_id="c", valido_ate=relogio.em(days=300)
    )
    relogio.avancar(days=100)
    assert memoria.invalidar_contexto(dono, "c") == 1
    assert _conteudos(memoria, dono, como_em=relogio.em(days=50)) == {"até o fim do ano"}
    assert _conteudos(memoria, dono, como_em=relogio.em(days=200)) == set()


def test_sabido_em_e_retroativo(memoria: Memoria, dono: str, relogio: RelogioManual):
    memoria.lembrar(dono, "a", categoria="nota", contexto_id="c")
    relogio.avancar(days=100)
    assert memoria.invalidar_contexto(dono, "c", valido_ate=relogio.em(days=30)) == 1
    assert _conteudos(memoria, dono, como_em=relogio.em(days=60)) == set()
    assert _conteudos(memoria, dono, como_em=relogio.em(days=10)) == {"a"}
    # Em D=60 o sistema ainda não sabia do fim retroativo: "a" valia.
    assert _conteudos(memoria, dono, sabido_em=relogio.em(days=60)) == {"a"}


def test_alcanca_a_versao_de_um_substituir_concorrente(
    memoria: Memoria,
    dono: str,
    relogio: RelogioManual,
    dsn: str,
    schema: str,
    monkeypatch: pytest.MonkeyPatch,
):
    original = memoria.lembrar(dono, "v1", categoria="nota", contexto_id="c")
    relogio.avancar(days=1)
    fechou = threading.Event()
    copia_de_verdade = store.inserir_copia_limitada

    def copia_e_espera(*argumentos, **nomeados):
        resultado = copia_de_verdade(*argumentos, **nomeados)
        fechou.set()
        time.sleep(0.5)  # a invalidação fica presa no lock da linha enquanto isso
        return resultado

    monkeypatch.setattr(store, "inserir_copia_limitada", copia_e_espera)

    def nova() -> Memoria:
        return Memoria(
            conexao=ProvedorDSN(dsn),
            embeddings=ProvedorDeEmbeddingsFalso(dimensao=8),
            tenant_id=memoria.tenant_id,
            schema=schema,
            relogio=relogio,
        )

    substituicao = threading.Thread(
        target=lambda: nova().substituir(dono, original.memoria_id, "v2")
    )
    substituicao.start()
    assert fechou.wait(timeout=10)
    nova().invalidar_contexto(dono, "c")
    substituicao.join(timeout=10)

    relogio.avancar(days=1)
    assert _conteudos(memoria, dono) == set(), "a versão do substituir concorrente escapou"
