"""A ``Memoria`` da app: uma por processo, migrada na primeira vez que é usada."""

from __future__ import annotations

import threading

from django.conf import settings

from chat.openrouter import ProvedorDeEmbeddingsOpenRouter
from memory_lifecycle import Memoria, ProvedorDeEmbeddings, ProvedorDeEmbeddingsFalso
from memory_lifecycle.connection.django import ProvedorDjango

_trava = threading.Lock()
_memoria: Memoria | None = None


def _embeddings() -> ProvedorDeEmbeddings:
    if settings.EMBEDDINGS == "falso":
        return ProvedorDeEmbeddingsFalso(dimensao=settings.OPENROUTER_DIMENSAO_EMBEDDING)
    return ProvedorDeEmbeddingsOpenRouter(
        settings.OPENROUTER_MODELO_EMBEDDING, settings.OPENROUTER_DIMENSAO_EMBEDDING
    )


def memoria() -> Memoria:
    """A memória do tenant de teste; o ``migrar`` é idempotente e roda uma vez por processo."""
    global _memoria
    with _trava:
        if _memoria is None:
            nova = Memoria(
                conexao=ProvedorDjango(),
                embeddings=_embeddings(),
                tenant_id=settings.MEMORIA_TENANT,
                schema=settings.MEMORIA_SCHEMA,
            )
            nova.migrar()
            _memoria = nova
        return _memoria
