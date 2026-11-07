"""A tela única e as chamadas JSON que ela faz.

A pessoa é uma das três de ``settings.PESSOAS``, escolhida no seletor do topo e
lembrada num cookie assinado; trocar de pessoa testa o isolamento entre donos
sem login. Toda escrita da memória usa o ``ProvedorDjango`` (modo ``PARTICIPAR``):
cada operação é uma transação curta, porque nenhuma view abre ``atomic``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from django.conf import settings
from django.core.signing import BadSignature
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from chat import agente
from chat.memoria import memoria
from chat.openrouter import ErroDoOpenRouter
from memory_lifecycle import ErroMemoryLifecycle, ErroNaoEncontrado, VersaoDeMemoria, derivar_status

COOKIE = "chat_teste_dono_id"
UM_ANO = 365 * 24 * 3600


def _dono(request: HttpRequest) -> str:
    """A pessoa do cookie, se for uma das cadastradas; senão a primeira (Ana)."""
    try:
        dono_id = request.get_signed_cookie(COOKIE, default=None)
    except BadSignature:
        dono_id = None
    return (
        dono_id if dono_id in settings.PESSOAS.values() else next(iter(settings.PESSOAS.values()))
    )


def _com_dono(resposta: HttpResponse, dono_id: str) -> HttpResponse:
    resposta.set_signed_cookie(COOKIE, dono_id, max_age=UM_ANO, httponly=True, samesite="Lax")
    return resposta


def _iso(momento: datetime | None) -> str | None:
    return timezone.localtime(momento).isoformat(timespec="seconds") if momento else None


def _versao(versao: VersaoDeMemoria) -> dict[str, Any]:
    return {
        "versao_id": versao.versao_id,
        "memoria_id": versao.memoria_id,
        "categoria": versao.categoria,
        "conteudo": versao.conteudo,
        "origem": versao.origem,
        "valido_de": _iso(versao.valido_de),
        "valido_ate": _iso(versao.valido_ate),
        "registrado_em": _iso(versao.registrado_em),
        "substituido_em": _iso(versao.substituido_em),
    }


def _erro(mensagem: str, status: int) -> JsonResponse:
    return JsonResponse({"erro": mensagem}, status=status)


def _erro_da_memoria(erro: ErroMemoryLifecycle) -> JsonResponse:
    """A biblioteca encadeia a causa sem expô-la; numa app de teste, ela é o que importa."""
    causa = f" (causa: {erro.__cause__})" if erro.__cause__ else ""
    return _erro(f"memória: {type(erro).__name__}: {erro}{causa}", 500)


@require_GET
def tela(request: HttpRequest) -> HttpResponse:
    """A tela do chat, aberta na pessoa do cookie (ou na Ana)."""
    dono_id = _dono(request)
    contexto = {"dono_id": dono_id, "pessoas": settings.PESSOAS.items()}
    return _com_dono(render(request, "chat/tela.html", contexto), dono_id)


@require_POST
def mensagem(request: HttpRequest) -> JsonResponse:
    """Recebe ``{"pergunta", "historico"}`` e devolve a resposta e os eventos de memória."""
    try:
        dono_id = _dono(request)
        dados = json.loads(request.body)
        pergunta = str(dados.get("pergunta", "")).strip()
        if not pergunta:
            return _erro("escreva alguma coisa", 400)
        turno = agente.conversar(memoria(), dono_id, pergunta, dados.get("historico"))
    except (ValueError, AttributeError):
        return _erro("corpo inválido: mande JSON com 'pergunta'", 400)
    except ErroDoOpenRouter as erro:
        return _erro(f"OpenRouter: {erro}", 502)
    except ErroMemoryLifecycle as erro:
        return _erro_da_memoria(erro)
    return JsonResponse(
        {"resposta": turno.resposta, "eventos": turno.eventos, "lembradas": turno.lembradas}
    )


def _instante(texto: str) -> datetime:
    """``datetime-local`` do navegador (sem fuso) é lido no fuso da app."""
    momento = datetime.fromisoformat(texto)
    if momento.tzinfo is None:
        momento = timezone.make_aware(momento)
    return momento.astimezone(UTC)


@require_GET
def memorias(request: HttpRequest) -> JsonResponse:
    """Memórias do dono: ``?modo=agora|como_em|sabido_em&instante=<ISO>``."""
    modo = request.GET.get("modo", "agora")
    try:
        dono_id = _dono(request)
        momento: dict[str, datetime] = {}
        if modo in {"como_em", "sabido_em"}:
            momento[modo] = _instante(request.GET["instante"])
        resultados = memoria().recuperar(dono_id, limite=100, **momento)
    except (KeyError, ValueError):
        return _erro("informe um instante válido para este modo", 400)
    except ErroMemoryLifecycle as erro:
        return _erro_da_memoria(erro)
    return JsonResponse({"modo": modo, "memorias": [_versao(r.versao) for r in resultados]})


@require_GET
def historico(request: HttpRequest, memoria_id: str) -> JsonResponse:
    """Toda versão de uma memória, com o status derivado de cada uma."""
    try:
        versoes = memoria().historico(_dono(request), memoria_id)
    except ErroNaoEncontrado:
        return _erro("memória não encontrada", 404)
    sucessoras = {v.versao_anterior_id: v for v in versoes if v.versao_anterior_id}
    agora = datetime.now(UTC)
    return JsonResponse(
        {
            "versoes": [
                {
                    **_versao(v),
                    "status": derivar_status(
                        v, agora=agora, sucessora=sucessoras.get(v.versao_id)
                    ).value,
                }
                for v in versoes
            ]
        }
    )


@require_POST
def esquecer(request: HttpRequest) -> JsonResponse:
    """Apaga fisicamente tudo o que o agente sabe desta pessoa (``esquecer(tudo=True)``)."""
    apagadas = memoria().esquecer(_dono(request), tudo=True)
    return JsonResponse({"apagadas": apagadas})


@require_POST
def escolher_pessoa(request: HttpRequest) -> HttpResponse:
    """Troca a pessoa da conversa; só aceita um ``dono_id`` de ``settings.PESSOAS``."""
    try:
        dono_id = str(json.loads(request.body).get("dono_id", ""))
    except (ValueError, AttributeError):
        dono_id = ""
    if dono_id not in settings.PESSOAS.values():
        return _erro("pessoa desconhecida", 400)
    return _com_dono(JsonResponse({"dono_id": dono_id}), dono_id)
