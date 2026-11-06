"""Uma view que conversa com memória dentro da transação do request.

Com ``ATOMIC_REQUESTS`` (ou o ``transaction.atomic`` explícito abaixo), se o
request falhar depois de gravar uma memória, a memória também é desfeita.
"""

from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from exemplos.django_app.memoria import memoria_do_tenant
from exemplos.fluxo_do_agente import conversar


def identificar(request: HttpRequest) -> tuple[str, str]:
    """Tenant e dono do request; na sua app, venha da autenticação, nunca do corpo."""
    return request.headers["X-Tenant"], request.headers["X-Usuario"]


@require_POST
@transaction.atomic
def conversa(request: HttpRequest) -> JsonResponse:
    """Recebe ``{"projeto": ..., "pergunta": ...}`` e devolve a resposta do agente."""
    tenant_id, dono_id = identificar(request)
    dados = json.loads(request.body)
    resposta = conversar(memoria_do_tenant(tenant_id), dono_id, dados["projeto"], dados["pergunta"])
    return JsonResponse({"resposta": resposta})
