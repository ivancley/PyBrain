"""One ``Memory`` per tenant, built once per process and shared across requests.

The ``Memory`` holds no connection: the ``DjangoProvider`` borrows the request's, so
the memory's write joins the same transaction as the rest of the request.

PT: Uma ``Memory`` por tenant, criada uma vez por processo e compartilhada entre requests.

A ``Memory`` não segura conexão: o ``DjangoProvider`` empresta a do request, então
a escrita da memória entra na mesma transação que o resto do request.
"""

from __future__ import annotations

from functools import cache

from django.conf import settings

from memory_lifecycle import DEFAULT_SCHEMA, FakeEmbeddingProvider, Memory
from memory_lifecycle.connection.django import DjangoProvider


@cache
def tenant_memory(tenant_id: str) -> Memory:
    """The tenant's memory; in production, swap the embedding provider for yours.

    PT: A memória do tenant; em produção, troque o provedor de embeddings pelo seu.
    """
    return Memory(
        connection=DjangoProvider(),
        embeddings=FakeEmbeddingProvider(),
        tenant_id=tenant_id,
        schema=getattr(settings, "MEMORY_SCHEMA", DEFAULT_SCHEMA),
    )


def migrate_memory(apps: object, schema_editor: object) -> None:
    """For a ``migrations.RunPython`` in one of the app's migrations; idempotent.

    This way the memory's schema follows the project's ``manage.py migrate``.

    PT: Para um ``migrations.RunPython`` numa migração do app; idempotente.

    Assim o schema da memória acompanha o ``manage.py migrate`` do projeto.
    """
    tenant_memory("migration").migrate()
