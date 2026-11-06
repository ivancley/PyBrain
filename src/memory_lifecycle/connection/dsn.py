"""``ProvedorDSN``: uma conexão própria por operação, a partir de um DSN.

Para scripts, jobs e testes, onde não há pool da aplicação para emprestar. Abre
com psycopg 3 (extra ``psycopg``), sempre no modo ``PROPRIA`` e com autocommit
desligado, e fecha a conexão ao fim de cada operação.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Conexao, ModoDeTransacao
from memory_lifecycle.exceptions import ErroExtraNaoInstalado


class ProvedorDSN:
    """Provedor de conexão por DSN; não use dentro de um request que já tem pool."""

    modo_de_transacao = ModoDeTransacao.PROPRIA

    def __init__(self, dsn: str, *, prazo_de_conexao: float = 10.0) -> None:
        try:
            import psycopg
        except ModuleNotFoundError as erro:
            if (erro.name or "").partition(".")[0] != "psycopg":
                raise
            raise ErroExtraNaoInstalado(
                'ProvedorDSN precisa do psycopg 3: pip install "memory-lifecycle[psycopg]"'
            ) from erro
        self._psycopg: Any = psycopg
        self._dsn = dsn
        self._prazo = prazo_de_conexao

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        """Abre uma conexão nova com autocommit desligado e a fecha ao sair."""
        conexao = self._psycopg.connect(
            self._dsn, autocommit=False, connect_timeout=max(1, round(self._prazo))
        )
        try:
            yield conexao
        finally:
            conexao.close()
