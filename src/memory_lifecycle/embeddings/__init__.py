"""The embedding provider contract and the fake provider for tests.

The core knows this protocol and nothing about any provider. Providers arrive as
optional extras in sibling modules and import their dependency lazily
(``.claude/rules/adapters.md``). The provider is always called **before** a database
connection is obtained.

PT: O contrato do provedor de embeddings e o provedor falso para testes.

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
    EmbeddingDimensionError,
    EmbeddingError,
    MemoryLifecycleError,
)

#: Errors that signal a bug or a broken contract, not a provider failure: they propagate untouched.
#: PT: Erros que indicam bug ou contrato quebrado, não falha do provedor: sobem intactos.
_PROGRAMMING_ERRORS = (TypeError, AttributeError, NameError, AssertionError, LookupError)
#: The largest value pgvector stores (float4); above it the database refuses.
#: PT: O maior valor que o pgvector guarda (float4); acima disso o banco recusa.
_MAX_FLOAT4 = 3.4028234663852886e38


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turn texts into vectors and say which model did it and with what width.

    PT: Transforma textos em vetores e diz qual modelo fez isso e com que largura.
    """

    @property
    def dimension(self) -> int:
        """Size of every vector this provider returns; fixed for the schema.

        PT: Tamanho de todo vetor que este provedor devolve; fixo para o schema.
        """
        ...

    @property
    def model_name(self) -> str:
        """Identifier stored on each version, so that a mixed table is detectable.

        PT: Identificador gravado em cada versão, para que uma tabela mista seja detectável.
        """
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text, in the same order, each with ``dimension`` floats.

        Raises ``EmbeddingError`` on provider failure. Never logs the texts.

        PT: Devolve um vetor por texto, na mesma ordem, cada um com ``dimension`` floats.

        Levanta ``EmbeddingError`` em falha do provedor. Nunca registra os textos em log.
        """
        ...


class FakeEmbeddingProvider:
    """Deterministic provider with no network: the same text always gives the same vector.

    Lives here, not in ``tests/``, because consuming applications use it in their own
    suites. Similar texts are not guaranteed to land close; identical texts are
    guaranteed to be identical.

    PT: Provedor determinístico sem rede: o mesmo texto sempre dá o mesmo vetor.

    Vive aqui, não em ``tests/``, porque as aplicações consumidoras o usam nas
    suas próprias suítes. Textos parecidos não têm garantia de ficar próximos;
    textos idênticos têm garantia de ser idênticos.
    """

    def __init__(self, dimension: int = 8, model_name: str = "fake") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        """Vector size; the schema is created with it.

        PT: Tamanho dos vetores; o schema é criado com ele.
        """
        return self._dimension

    @property
    def model_name(self) -> str:
        """Stored on each version written with this provider.

        PT: Gravado em cada versão escrita com este provedor.
        """
        return self._model_name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return, per text, a unit-norm vector derived from the text's sha256.

        PT: Devolve, por texto, um vetor de norma 1 derivado do sha256 do texto.
        """
        return [_deterministic_vector(text, self._dimension) for text in texts]


def _deterministic_vector(text: str, dimension: int) -> list[float]:
    values: list[float] = []
    block = 0
    while len(values) < dimension:
        digest = hashlib.sha256(f"{block}:{text}".encode()).digest()
        values.extend(byte / 127.5 - 1.0 for byte in digest)
        block += 1
    values = values[:dimension]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def vectorize(provider: EmbeddingProvider, texts: Sequence[str]) -> list[list[float]]:
    """Call the provider and check what came back; always before obtaining a connection.

    A provider failure becomes ``EmbeddingError`` (chained, without the texts in the
    message); a library error and a programming error (``TypeError``,
    ``AttributeError``…) propagate untouched. A vector with NaN or infinity becomes
    ``EmbeddingError``; one whose length differs from ``dimension``,
    ``EmbeddingDimensionError``.

    PT: Chama o provedor e confere o que voltou; sempre antes de obter uma conexão.

    Uma falha do provedor vira ``EmbeddingError`` (encadeada, sem os textos na
    mensagem); um erro da própria biblioteca e um erro de programação
    (``TypeError``, ``AttributeError``…) sobem intactos. Um vetor com NaN ou
    infinito vira ``EmbeddingError``; um de tamanho diferente de ``dimension``,
    ``EmbeddingDimensionError``.
    """
    try:
        vectors = provider.embed(texts)
    except (MemoryLifecycleError, *_PROGRAMMING_ERRORS):
        raise
    except Exception as error:
        raise EmbeddingError(
            f"provider {provider.model_name!r} failed to produce {len(texts)} embedding(s)"
        ) from error
    if len(vectors) != len(texts):
        raise EmbeddingError(
            f"provider {provider.model_name!r} returned {len(vectors)} vector(s) "
            f"for {len(texts)} text(s)"
        )
    for vector in vectors:
        if not all(math.isfinite(value) and abs(value) <= _MAX_FLOAT4 for value in vector):
            raise EmbeddingError(
                f"provider {provider.model_name!r} returned a vector with NaN, infinity "
                "or a value outside the float4 range"
            )
        if len(vector) != provider.dimension:
            raise EmbeddingDimensionError(
                f"provider {provider.model_name!r} returned a vector of {len(vector)} "
                f"positions; the declared dimension is {provider.dimension}"
            )
    return vectors


__all__ = ["EmbeddingProvider", "FakeEmbeddingProvider", "vectorize"]
