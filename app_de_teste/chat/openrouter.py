"""Cliente mínimo da API do OpenRouter (compatível com a da OpenAI), só com a stdlib.

Dois usos: completar uma conversa (``completar``) e gerar embeddings
(``ProvedorDeEmbeddingsOpenRouter``, que cumpre o protocolo da biblioteca). A
chave nunca aparece numa mensagem de erro.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from django.conf import settings


class ErroDoOpenRouter(Exception):
    """A chamada ao OpenRouter falhou: rede, status HTTP de erro ou resposta sem conteúdo."""


def _postar(caminho: str, corpo: dict[str, Any]) -> dict[str, Any]:
    if not settings.OPENROUTER_API_KEY:
        raise ErroDoOpenRouter("OPENROUTER_API_KEY não definida (veja app_de_teste/.env.example)")
    requisicao = urllib.request.Request(
        f"{settings.OPENROUTER_URL.rstrip('/')}/{caminho}",
        data=json.dumps(corpo).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "X-Title": "memory-lifecycle - app de teste",
        },
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=settings.OPENROUTER_TIMEOUT) as resposta:
            dados: dict[str, Any] = json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode(errors="replace")[:300]
        raise ErroDoOpenRouter(f"HTTP {erro.code} em /{caminho}: {detalhe}") from erro
    except (urllib.error.URLError, TimeoutError) as erro:
        raise ErroDoOpenRouter(f"sem resposta do OpenRouter em /{caminho}: {erro}") from erro
    if "error" in dados:
        raise ErroDoOpenRouter(f"erro do OpenRouter em /{caminho}: {dados['error']}")
    return dados


def completar(
    mensagens: list[dict[str, str]],
    *,
    modelo: str | None = None,
    temperatura: float = 0.8,
    json_estrito: bool = False,
) -> str:
    """Devolve o texto da resposta do modelo para a conversa ``mensagens``."""
    corpo: dict[str, Any] = {
        "model": modelo or settings.OPENROUTER_MODELO,
        "messages": mensagens,
        "temperature": temperatura,
    }
    if json_estrito:
        corpo["response_format"] = {"type": "json_object"}
    dados = _postar("chat/completions", corpo)
    try:
        conteudo = dados["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as erro:
        raise ErroDoOpenRouter(f"resposta sem conteúdo: {str(dados)[:300]}") from erro
    if not isinstance(conteudo, str) or not conteudo.strip():
        raise ErroDoOpenRouter("o modelo devolveu uma resposta vazia")
    return conteudo.strip()


class ProvedorDeEmbeddingsOpenRouter:
    """Embeddings pelo endpoint ``/embeddings`` do OpenRouter; cumpre ``EmbeddingProvider``."""

    def __init__(self, modelo: str, dimensao: int) -> None:
        self._modelo = modelo
        self._dimensao = dimensao

    @property
    def dimension(self) -> int:
        """Largura declarada no .env; a biblioteca confere cada vetor contra ela."""
        return self._dimensao

    @property
    def model_name(self) -> str:
        """Gravado em cada versão escrita com este provedor."""
        return self._modelo

    def embed(self, textos: Sequence[str]) -> list[list[float]]:
        """Um vetor por texto, na mesma ordem (a API devolve ``index`` em cada item)."""
        dados = _postar("embeddings", {"model": self._modelo, "input": list(textos)})
        itens = sorted(dados.get("data", []), key=lambda item: item.get("index", 0))
        return [list(map(float, item["embedding"])) for item in itens]
