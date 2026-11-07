"""Configuração da app de teste: tudo vem do ambiente ou de ``app_de_teste/.env``.

A app não tem models do Django: o único dado persistente é a memória do agente,
que mora no schema da biblioteca dentro do mesmo Postgres. Por isso não há
``contrib.auth`` nem ``contrib.sessions``, e ``manage.py migrate`` não é preciso.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

PASTA = Path(__file__).resolve().parent.parent


def _carregar_env(arquivo: Path) -> None:
    """Lê ``CHAVE=valor`` de um ``.env`` sem sobrescrever o que o ambiente já tem."""
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip("\"'"))


def _banco(url: str) -> dict[str, object]:
    """Converte ``postgresql://usuario:senha@host:porta/banco`` no dicionário do Django."""
    partes = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": partes.path.lstrip("/"),
        "USER": unquote(partes.username or ""),
        "PASSWORD": unquote(partes.password or ""),
        "HOST": partes.hostname or "localhost",
        "PORT": str(partes.port or 5432),
    }


_carregar_env(PASTA / ".env")

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "so-para-teste-local-nao-use-em-producao")
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = ["chat"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
ROOT_URLCONF = "config.urls"
# Cookies com nome próprio: o navegador compartilha cookies de 127.0.0.1 entre
# portas, e outro app local com um "csrftoken" ou um logout que limpa cookies
# levaria a identidade desta app junto.
CSRF_COOKIE_NAME = "chat_teste_csrftoken"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]
DATABASES = {
    "default": _banco(
        os.environ.get(
            "CHAT_DATABASE_URL",
            "postgresql://memory:memory@localhost:5433/memory_lifecycle",
        )
    )
}
USE_TZ = True
TIME_ZONE = "America/Sao_Paulo"
LANGUAGE_CODE = "pt-br"

# --- OpenRouter: troque os modelos pelo .env, sem mexer no código ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = os.environ.get("OPENROUTER_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODELO = os.environ.get("OPENROUTER_MODELO", "openai/gpt-4o-mini")
OPENROUTER_MODELO_EXTRATOR = os.environ.get("OPENROUTER_MODELO_EXTRATOR", OPENROUTER_MODELO)
OPENROUTER_TIMEOUT = float(os.environ.get("OPENROUTER_TIMEOUT", "60"))

# --- Embeddings: "openrouter" (padrão) ou "falso" (sem rede, sem semântica) ---
EMBEDDINGS = os.environ.get("EMBEDDINGS", "openrouter")
OPENROUTER_MODELO_EMBEDDING = os.environ.get(
    "OPENROUTER_MODELO_EMBEDDING", "openai/text-embedding-3-small"
)
OPENROUTER_DIMENSAO_EMBEDDING = int(os.environ.get("OPENROUTER_DIMENSAO_EMBEDDING", "1536"))

# --- Memória ---
# A dimensão do vetor fica gravada no schema: trocar de modelo de embedding com
# outra dimensão pede outro schema (ou apagar este).
MEMORIA_SCHEMA = os.environ.get("MEMORIA_SCHEMA", "chat_teste")
MEMORIA_TENANT = os.environ.get("MEMORIA_TENANT", "app-de-teste")

# --- Pessoas de teste: o seletor no topo da tela troca entre elas ---
# uuids fixos, para que a memória de cada uma sobreviva a reinícios e a cookies
# perdidos. A Ana usa o uuid do roteiro de testes já em andamento.
PESSOAS = {
    "Ana": "6c7ac6c9-11f5-4728-8b41-51dba17a5912",
    "Bruno": "1265502d-8ed7-41f9-9873-c7d0cfff83f0",
    "Carla": "366dfdef-9336-4ce7-b745-a57b5dcb607f",
}
