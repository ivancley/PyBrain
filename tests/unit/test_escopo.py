"""A montagem do escopo estrito de ``recuperar`` (ADR 0003)."""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroDeArgumentoInvalido
from memory_lifecycle.retrieval import EixoDeEscopo, montar_eixo


def test_none_nao_filtra():
    assert montar_eixo(None) is None


def test_lista_vazia_nao_devolve_nada():
    assert montar_eixo([]) == EixoDeEscopo(ids=(), incluir_nulo=False)


def test_none_como_membro_inclui_os_sem_id():
    assert montar_eixo(["p-2027", None]) == EixoDeEscopo(ids=("p-2027",), incluir_nulo=True)
    assert montar_eixo([None]) == EixoDeEscopo(ids=(), incluir_nulo=True)


def test_string_solta_e_recusada():
    with pytest.raises(ErroDeArgumentoInvalido, match="lista"):
        montar_eixo("p-2027")  # type: ignore[arg-type]
