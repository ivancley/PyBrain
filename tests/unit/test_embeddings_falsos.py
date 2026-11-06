"""O provedor de embeddings falso e ``vetorizar`` (design.md § D8)."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from memory_lifecycle import (
    ErroDeDimensaoDeEmbedding,
    ErroDeEmbedding,
    ErroExtraNaoInstalado,
    ProvedorDeEmbeddingsFalso,
)
from memory_lifecycle.embeddings import vetorizar


class ProvedorQueFalha(ProvedorDeEmbeddingsFalso):
    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        raise TimeoutError("o provedor não respondeu")


class ProvedorDeDimensaoErrada(ProvedorDeEmbeddingsFalso):
    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        return [[1.0] * (self.dimensao + 1) for _ in textos]


def test_mesmo_texto_mesmo_vetor_e_textos_diferentes_vetores_diferentes():
    provedor = ProvedorDeEmbeddingsFalso(dimensao=16)
    a, a_de_novo, b = provedor.gerar(["a", "a", "b"])
    assert a == a_de_novo
    assert a != b


@pytest.mark.parametrize("dimensao", [1, 8, 33, 1536])
def test_vetor_tem_a_dimensao_pedida_e_norma_um(dimensao: int):
    [vetor] = ProvedorDeEmbeddingsFalso(dimensao=dimensao).gerar(["qualquer texto"])
    assert len(vetor) == dimensao
    assert math.isclose(math.sqrt(sum(v * v for v in vetor)), 1.0, rel_tol=1e-9)


def test_falha_do_provedor_vira_erro_de_embedding_encadeado():
    with pytest.raises(ErroDeEmbedding) as erro:
        vetorizar(ProvedorQueFalha(), ["segredo do usuário"])
    assert isinstance(erro.value.__cause__, TimeoutError)
    assert "segredo" not in str(erro.value)


def test_tamanho_errado_vira_erro_de_dimensao():
    with pytest.raises(ErroDeDimensaoDeEmbedding):
        vetorizar(ProvedorDeDimensaoErrada(dimensao=4), ["x"])


class ProvedorComBug(ProvedorDeEmbeddingsFalso):
    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        return [[None] * self.dimensao]  # type: ignore[list-item]  # um bug, não uma falha de rede


class ProvedorComNaN(ProvedorDeEmbeddingsFalso):
    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        return [[float("nan")] * self.dimensao for _ in textos]


class ProvedorSemExtra(ProvedorDeEmbeddingsFalso):
    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        raise ErroExtraNaoInstalado('pip install "memory-lifecycle[algum]"')


def test_bug_do_provedor_sobe_intacto():
    # Regressão (achado 2): um TypeError do provedor virava "o provedor falhou".
    with pytest.raises(TypeError):
        vetorizar(ProvedorComBug(dimensao=2), ["x"])


def test_erro_da_biblioteca_no_provedor_sobe_intacto():
    with pytest.raises(ErroExtraNaoInstalado):
        vetorizar(ProvedorSemExtra(), ["x"])


def test_vetor_com_nan_vira_erro_de_embedding():
    with pytest.raises(ErroDeEmbedding, match="NaN"):
        vetorizar(ProvedorComNaN(dimensao=2), ["x"])
