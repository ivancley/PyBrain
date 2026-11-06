"""Spec ``memory-versions`` e ``recall``: as bordas de ``lembrar`` e ``recuperar``."""

from __future__ import annotations

from datetime import datetime

import pytest

from memory_lifecycle import ErroDeArgumentoInvalido, ErroNaoEncontrado, Memoria
from tests.conftest import RelogioManual


def test_lembrar_com_validade_explicita(memoria: Memoria, dono: str, relogio: RelogioManual):
    relogio.avancar(days=100)
    v = memoria.lembrar(
        dono, "x", categoria="nota", valido_de=relogio.em(days=10), valido_ate=relogio.em(days=200)
    )
    assert (v.valido_de, v.valido_ate) == (relogio.em(days=10), relogio.em(days=200))
    assert [r.versao for r in memoria.recuperar(dono, como_em=relogio.em(days=50))] == [v]
    assert memoria.recuperar(dono, como_em=relogio.em(days=5)) == []
    assert memoria.recuperar(dono, como_em=relogio.em(days=200)) == []


@pytest.mark.parametrize(
    "argumentos",
    [
        {"conteudo": ""},
        {"categoria": " "},
        {"valido_de": datetime(2026, 1, 1)},
        {"valido_ate": datetime(2026, 1, 1)},
    ],
)
def test_lembrar_invalido_nao_registra_nada(memoria: Memoria, dono: str, argumentos: dict):
    chamada = {"conteudo": "x", "categoria": "nota", **argumentos}
    with pytest.raises(ErroDeArgumentoInvalido):
        memoria.lembrar(dono, **chamada)
    assert memoria.recuperar(dono) == []


def test_validade_invertida_e_recusada(memoria: Memoria, dono: str, relogio: RelogioManual):
    with pytest.raises(ErroDeArgumentoInvalido):
        memoria.lembrar(dono, "x", categoria="nota", valido_ate=relogio.em(days=-1))


def test_escopo_estrito_por_contexto_e_entidade(memoria: Memoria, dono: str):
    memoria.lembrar(dono, "solta", categoria="nota")
    memoria.lembrar(dono, "do c1", categoria="nota", contexto_id="c1")
    memoria.lembrar(dono, "da e1", categoria="nota", entidade_id="e1")

    def conteudos(**escopo: object) -> set[str]:
        return {r.versao.conteudo for r in memoria.recuperar(dono, **escopo)}  # type: ignore[arg-type]

    assert conteudos() == {"solta", "do c1", "da e1"}
    assert conteudos(contextos=["c1"]) == {"do c1"}
    assert conteudos(contextos=["c1", None]) == {"solta", "do c1", "da e1"}
    assert conteudos(contextos=[]) == set()
    assert conteudos(entidades=["e1"]) == {"da e1"}
    assert conteudos(entidades=[None]) == {"solta", "do c1"}
    assert conteudos(contextos=[None], entidades=[None]) == {"solta"}


def test_filtro_por_categoria(memoria: Memoria, dono: str):
    memoria.lembrar(dono, "a", categoria="preferencia")
    memoria.lembrar(dono, "b", categoria="fato")
    assert [r.versao.conteudo for r in memoria.recuperar(dono, categoria="fato")] == ["b"]


@pytest.mark.parametrize("limite", [0, -1, True, 2.5])
def test_limite_precisa_ser_inteiro_positivo(memoria: Memoria, dono: str, limite: object):
    with pytest.raises(ErroDeArgumentoInvalido):
        memoria.recuperar(dono, limite=limite)  # type: ignore[arg-type]


def test_como_em_e_sabido_em_juntos(memoria: Memoria, dono: str, relogio: RelogioManual):
    with pytest.raises(ErroDeArgumentoInvalido):
        memoria.recuperar(dono, como_em=relogio(), sabido_em=relogio())


def test_historico_de_id_desconhecido_ou_invalido(memoria: Memoria, dono: str):
    for memoria_id in ("nao-e-uuid", "00000000-0000-0000-0000-000000000000"):
        with pytest.raises(ErroNaoEncontrado):
            memoria.historico(dono, memoria_id)


def test_historico_nao_diz_que_a_memoria_existe_em_outro_tenant(
    memoria: Memoria, memoria_outro_tenant: Memoria, dono: str
):
    alheia = memoria.lembrar(dono, "x", categoria="nota")
    with pytest.raises(ErroNaoEncontrado) as erro_alheia:
        memoria_outro_tenant.historico(dono, alheia.memoria_id)
    with pytest.raises(ErroNaoEncontrado) as erro_inexistente:
        memoria_outro_tenant.historico(dono, "00000000-0000-0000-0000-000000000000")
    assert str(erro_alheia.value) == str(erro_inexistente.value)
