"""``ProvedorDjango``: a memória escreve na transação do request do Django.

Usa a conexão que o Django já abriu (extra ``django``), sem segundo pool. Cada
operação roda dentro de ``transaction.atomic()``: dentro de uma transação do app
isso é um savepoint, e a escrita só vale se o request fizer commit; fora de uma,
é uma transação curta. Por isso o modo é ``PARTICIPAR`` e a biblioteca nunca faz
commit: quem fecha é o ``atomic`` (ADR 0004).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Conexao, ModoDeTransacao
from memory_lifecycle.exceptions import ErroExtraNaoInstalado


class ProvedorDjango:
    """Provedor sobre a conexão ``alias`` do Django; ``PARTICIPAR`` por desenho."""

    modo_de_transacao = ModoDeTransacao.PARTICIPAR

    def __init__(self, alias: str = "default") -> None:
        try:
            from django.db import connections, transaction
        except ModuleNotFoundError as erro:
            if (erro.name or "").partition(".")[0] != "django":
                raise
            raise ErroExtraNaoInstalado(
                'ProvedorDjango precisa do Django: pip install "memory-lifecycle[django]"'
            ) from erro
        self._conexoes: Any = connections
        self._transacao: Any = transaction
        self._alias = alias

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        """Cede a conexão DB-API do Django dentro de um ``atomic`` (savepoint ou transação)."""
        with self._transacao.atomic(using=self._alias):
            envoltorio = self._conexoes[self._alias]
            envoltorio.ensure_connection()
            yield envoltorio.connection
