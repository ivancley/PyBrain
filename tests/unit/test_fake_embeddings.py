"""The fake embedding provider and ``vectorize`` (design.md § D8).

PT: O provedor de embeddings falso e ``vectorize`` (design.md § D8).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from memory_lifecycle import (
    EmbeddingDimensionError,
    EmbeddingError,
    ExtraNotInstalledError,
    FakeEmbeddingProvider,
)
from memory_lifecycle.embeddings import vectorize


class FailingProvider(FakeEmbeddingProvider):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise TimeoutError("the provider did not respond")


class WrongDimensionProvider(FakeEmbeddingProvider):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] * (self.dimension + 1) for _ in texts]


def test_same_text_same_vector_and_different_texts_different_vectors():
    provider = FakeEmbeddingProvider(dimension=16)
    a, a_again, b = provider.embed(["a", "a", "b"])
    assert a == a_again
    assert a != b


@pytest.mark.parametrize("dimension", [1, 8, 33, 1536])
def test_vector_has_the_requested_dimension_and_unit_norm(dimension: int):
    [vector] = FakeEmbeddingProvider(dimension=dimension).embed(["any text"])
    assert len(vector) == dimension
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-9)


def test_provider_failure_becomes_chained_embedding_error():
    with pytest.raises(EmbeddingError) as error:
        vectorize(FailingProvider(), ["user secret"])
    assert isinstance(error.value.__cause__, TimeoutError)
    assert "secret" not in str(error.value)


def test_wrong_size_becomes_dimension_error():
    with pytest.raises(EmbeddingDimensionError):
        vectorize(WrongDimensionProvider(dimension=4), ["x"])


class BuggyProvider(FakeEmbeddingProvider):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        # A bug, not a network failure.
        # PT: Um bug, não uma falha de rede.
        return [[None] * self.dimension]  # type: ignore[list-item]


class NaNProvider(FakeEmbeddingProvider):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float("nan")] * self.dimension for _ in texts]


class MissingExtraProvider(FakeEmbeddingProvider):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise ExtraNotInstalledError('pip install "memory-lifecycle[some]"')


def test_provider_bug_propagates_intact():
    # Regression (finding 2): a TypeError from the provider became "the provider failed".
    # PT: Regressão (achado 2): um TypeError do provedor virava "o provedor falhou".
    with pytest.raises(TypeError):
        vectorize(BuggyProvider(dimension=2), ["x"])


def test_library_error_in_provider_propagates_intact():
    with pytest.raises(ExtraNotInstalledError):
        vectorize(MissingExtraProvider(), ["x"])


def test_vector_with_nan_becomes_embedding_error():
    with pytest.raises(EmbeddingError, match="NaN"):
        vectorize(NaNProvider(dimension=2), ["x"])
