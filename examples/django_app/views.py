"""A view that converses with memory inside the request's transaction.

With ``ATOMIC_REQUESTS`` (or the explicit ``transaction.atomic`` below), if the
request fails after saving a memory, the memory is rolled back too.

PT: Uma view que conversa com memória dentro da transação do request.

Com ``ATOMIC_REQUESTS`` (ou o ``transaction.atomic`` explícito abaixo), se o
request falhar depois de gravar uma memória, a memória também é desfeita.
"""

from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from examples.agent_flow import converse
from examples.django_app.memory import tenant_memory


def identify(request: HttpRequest) -> tuple[str, str]:
    """The request's tenant and owner; in your app, take them from authentication, never the body.

    PT: Tenant e dono do request; na sua app, venha da autenticação, nunca do corpo.
    """
    return request.headers["X-Tenant"], request.headers["X-User"]


@require_POST
@transaction.atomic
def chat(request: HttpRequest) -> JsonResponse:
    """Takes ``{"project": ..., "question": ...}`` and returns the agent's answer.

    PT: Recebe ``{"project": ..., "question": ...}`` e devolve a resposta do agente.
    """
    tenant_id, owner_id = identify(request)
    data = json.loads(request.body)
    answer = converse(tenant_memory(tenant_id), owner_id, data["project"], data["question"])
    return JsonResponse({"answer": answer})
