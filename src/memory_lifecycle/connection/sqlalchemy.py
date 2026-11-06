"""``ProvedorSQLAlchemy``: reaproveita o engine ou a sessão do app (extra ``sqlalchemy``).

- ``ProvedorSQLAlchemy(engine)``: uma conexão do pool do engine por operação, no
  modo ``PROPRIA``.
- ``ProvedorSQLAlchemy.de_sessao(sessao)``: a conexão da transação da sessão, no
  modo ``PARTICIPAR``; cada operação roda num savepoint (``begin_nested``), e a
  escrita só vale quando o app faz ``sessao.commit()``.

Nos dois casos a biblioteca fala com a conexão do driver por baixo do SQLAlchemy
(psycopg 3 ou psycopg2), sem registrar nada nela (ADR 0007).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from memory_lifecycle.connection import Conexao, ModoDeTransacao
from memory_lifecycle.exceptions import ErroExtraNaoInstalado


def _exigir_sqlalchemy() -> None:
    try:
        import sqlalchemy  # noqa: F401 — só para dar a mensagem do extra cedo
    except ModuleNotFoundError as erro:
        if (erro.name or "").partition(".")[0] != "sqlalchemy":
            raise
        raise ErroExtraNaoInstalado(
            'ProvedorSQLAlchemy precisa do SQLAlchemy: pip install "memory-lifecycle[sqlalchemy]"'
        ) from erro


class ProvedorSQLAlchemy:
    """Provedor sobre um ``Engine`` (``PROPRIA``) ou uma ``Session`` (``PARTICIPAR``)."""

    def __init__(self, engine: Any) -> None:
        _exigir_sqlalchemy()
        self._engine = engine
        self._sessao: Any = None
        self.modo_de_transacao = ModoDeTransacao.PROPRIA

    @classmethod
    def de_sessao(cls, sessao: Any) -> ProvedorSQLAlchemy:
        """Participa da transação da sessão; quem faz commit é o app."""
        provedor = cls(sessao.get_bind())
        provedor._sessao = sessao
        provedor.modo_de_transacao = ModoDeTransacao.PARTICIPAR
        return provedor

    @contextmanager
    def conexao(self) -> Iterator[Conexao]:
        """Cede a conexão do driver: da sessão, ou emprestada do pool do engine."""
        if self._sessao is not None:
            # Savepoint: um erro da operação desfaz só ela. Sem ele, um erro de banco
            # abortaria a transação da sessão e o `commit` do app viraria rollback mudo.
            with self._sessao.begin_nested():
                yield self._sessao.connection().connection.driver_connection
            return
        emprestada = self._engine.raw_connection()
        try:
            yield emprestada.driver_connection
        finally:
            emprestada.close()
