"""``ProvedorPoolPsycopg``: empresta conexões de um pool do psycopg que o app já tem.

O app constrói e abre o ``psycopg_pool.ConnectionPool`` (extra ``psycopg``); a
biblioteca pega uma conexão por operação e a devolve ao fim. Uma conexão de pool
não carrega a transação de ninguém, então o modo é sempre ``PROPRIA``: para
participar da transação de um request, use o adaptador do framework.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Conexao, ModoDeTransacao
from memory_lifecycle.exceptions import ErroExtraNaoInstalado


class ProvedorPoolPsycopg:
    """Provedor sobre um ``psycopg_pool.ConnectionPool`` aberto pelo app."""

    modo_de_transacao = ModoDeTransacao.PROPRIA

    def __init__(self, pool: Any) -> None:
        try:
            import psycopg_pool  # noqa: F401 — só para dar a mensagem do extra cedo
        except ModuleNotFoundError as erro:
            if (erro.name or "").partition(".")[0] not in {"psycopg_pool", "psycopg"}:
                raise
            raise ErroExtraNaoInstalado(
                'ProvedorPoolPsycopg precisa do psycopg-pool: pip install "memory-lifecycle[psycopg]"'
            ) from erro
        self._pool = pool

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        """Empresta uma conexão do pool pela duração de uma operação."""
        with self._pool.connection() as conexao:
            yield conexao
