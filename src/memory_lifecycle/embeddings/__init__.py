"""O contrato do provedor de embeddings e o provedor falso para testes.

O núcleo conhece este protocolo e nada sobre nenhum provedor. Provedores chegam
como extras opcionais em módulos irmãos e importam sua dependência de forma
preguiçosa (``.claude/rules/adapters.md``). O provedor é sempre chamado **antes**
de uma conexão com o banco ser obtida.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from memory_lifecycle.exceptions import (
    ErroDeDimensaoDeEmbedding,
    ErroDeEmbedding,
    ErroMemoryLifecycle,
)

#: Erros que indicam bug ou contrato quebrado, não falha do provedor: sobem intactos.
_ERROS_DE_PROGRAMACAO = (TypeError, AttributeError, NameError, AssertionError, LookupError)
#: O maior valor que o pgvector guarda (float4); acima disso o banco recusa.
_MAIOR_FLOAT4 = 3.4028234663852886e38


@runtime_checkable
class ProvedorDeEmbeddings(Protocol):
    """Transforma textos em vetores e diz qual modelo fez isso e com que largura."""

    @property
    def dimensao(self) -> int:
        """Tamanho de todo vetor que este provedor devolve; fixo para o schema."""
        ...

    @property
    def nome_do_modelo(self) -> str:
        """Identificador gravado em cada versão, para que uma tabela mista seja detectável."""
        ...

    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        """Devolve um vetor por texto, na mesma ordem, cada um com ``dimensao`` floats.

        Levanta ``ErroDeEmbedding`` em falha do provedor. Nunca registra os textos em log.
        """
        ...


class ProvedorDeEmbeddingsFalso:
    """Provedor determinístico sem rede: o mesmo texto sempre dá o mesmo vetor.

    Vive aqui, não em ``tests/``, porque as aplicações consumidoras o usam nas
    suas próprias suítes. Textos parecidos não têm garantia de ficar próximos;
    textos idênticos têm garantia de ser idênticos.
    """

    def __init__(self, dimensao: int = 8, nome_do_modelo: str = "falso") -> None:
        self._dimensao = dimensao
        self._nome_do_modelo = nome_do_modelo

    @property
    def dimensao(self) -> int:
        """Tamanho dos vetores; o schema é criado com ele."""
        return self._dimensao

    @property
    def nome_do_modelo(self) -> str:
        """Gravado em cada versão escrita com este provedor."""
        return self._nome_do_modelo

    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        """Devolve, por texto, um vetor de norma 1 derivado do sha256 do texto."""
        return [_vetor_deterministico(texto, self._dimensao) for texto in textos]


def _vetor_deterministico(texto: str, dimensao: int) -> list[float]:
    valores: list[float] = []
    bloco = 0
    while len(valores) < dimensao:
        resumo = hashlib.sha256(f"{bloco}:{texto}".encode()).digest()
        valores.extend(byte / 127.5 - 1.0 for byte in resumo)
        bloco += 1
    valores = valores[:dimensao]
    norma = math.sqrt(sum(valor * valor for valor in valores)) or 1.0
    return [valor / norma for valor in valores]


def vetorizar(provedor: ProvedorDeEmbeddings, textos: Sequence[str]) -> list[list[float]]:
    """Chama o provedor e confere o que voltou; sempre antes de obter uma conexão.

    Uma falha do provedor vira ``ErroDeEmbedding`` (encadeada, sem os textos na
    mensagem); um erro da própria biblioteca e um erro de programação
    (``TypeError``, ``AttributeError``…) sobem intactos. Um vetor com NaN ou
    infinito vira ``ErroDeEmbedding``; um de tamanho diferente de ``dimensao``,
    ``ErroDeDimensaoDeEmbedding``.
    """
    try:
        vetores = provedor.gerar(textos)
    except (ErroMemoryLifecycle, *_ERROS_DE_PROGRAMACAO):
        raise
    except Exception as erro:
        raise ErroDeEmbedding(
            f"o provedor {provedor.nome_do_modelo!r} falhou ao gerar {len(textos)} embedding(s)"
        ) from erro
    if len(vetores) != len(textos):
        raise ErroDeEmbedding(
            f"o provedor {provedor.nome_do_modelo!r} devolveu {len(vetores)} vetor(es) "
            f"para {len(textos)} texto(s)"
        )
    for vetor in vetores:
        if not all(math.isfinite(valor) and abs(valor) <= _MAIOR_FLOAT4 for valor in vetor):
            raise ErroDeEmbedding(
                f"o provedor {provedor.nome_do_modelo!r} devolveu um vetor com NaN, infinito "
                "ou valor fora da faixa do float4"
            )
        if len(vetor) != provedor.dimensao:
            raise ErroDeDimensaoDeEmbedding(
                f"o provedor {provedor.nome_do_modelo!r} devolveu um vetor de {len(vetor)} "
                f"posições; a dimensão declarada é {provedor.dimensao}"
            )
    return vetores


__all__ = ["ProvedorDeEmbeddings", "ProvedorDeEmbeddingsFalso", "vetorizar"]
