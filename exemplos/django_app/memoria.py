"""Uma ``Memoria`` por tenant, criada uma vez por processo e compartilhada entre requests.

A ``Memoria`` não segura conexão: o ``ProvedorDjango`` empresta a do request, então
a escrita da memória entra na mesma transação que o resto do request.
"""

from __future__ import annotations

from functools import cache

from django.conf import settings

from memory_lifecycle import SCHEMA_PADRAO, Memoria, ProvedorDeEmbeddingsFalso
from memory_lifecycle.connection.django import ProvedorDjango


@cache
def memoria_do_tenant(tenant_id: str) -> Memoria:
    """A memória do tenant; em produção, troque o provedor de embeddings pelo seu."""
    return Memoria(
        conexao=ProvedorDjango(),
        embeddings=ProvedorDeEmbeddingsFalso(),
        tenant_id=tenant_id,
        schema=getattr(settings, "MEMORIA_SCHEMA", SCHEMA_PADRAO),
    )


def migrar_memoria(apps: object, schema_editor: object) -> None:
    """Para um ``migrations.RunPython`` numa migração do app; idempotente.

    Assim o schema da memória acompanha o ``manage.py migrate`` do projeto.
    """
    memoria_do_tenant("migracao").migrar()
