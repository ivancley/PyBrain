"""A ``Memory`` da app: uma por processo, migrada na primeira vez que é usada."""

from __future__ import annotations

import threading

from django.conf import settings

from chat.openrouter import ProvedorDeEmbeddingsOpenRouter
from memory_lifecycle import EmbeddingProvider, FakeEmbeddingProvider, Memory
from memory_lifecycle.connection.django import DjangoProvider

_trava = threading.Lock()
_memoria: Memory | None = None


def _embeddings() -> EmbeddingProvider:
    if settings.EMBEDDINGS == "falso":
        return FakeEmbeddingProvider(dimension=settings.OPENROUTER_DIMENSAO_EMBEDDING)
    return ProvedorDeEmbeddingsOpenRouter(
        settings.OPENROUTER_MODELO_EMBEDDING, settings.OPENROUTER_DIMENSAO_EMBEDDING
    )


def memoria() -> Memory:
    """A memória do tenant de teste; o ``migrate`` é idempotente e roda uma vez por processo."""
    global _memoria
    with _trava:
        if _memoria is None:
            nova = Memory(
                connection=DjangoProvider(),
                embeddings=_embeddings(),
                tenant_id=settings.MEMORIA_TENANT,
                schema=settings.MEMORIA_SCHEMA,
            )
            nova.migrate()
            _memoria = nova
        return _memoria
