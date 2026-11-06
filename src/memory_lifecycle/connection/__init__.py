"""O contrato do provedor de conexão: a aplicação é dona da conexão.

A biblioteca nunca abre um pool próprio. Ela pede ao provedor uma conexão
DB-API, executa suas instruções e ou faz commit (``PROPRIA``) ou deixa a
transação com a aplicação (``PARTICIPAR``). Adaptadores para DSN, pool do
psycopg, Django e SQLAlchemy são extras opcionais em módulos irmãos
(``.claude/rules/adapters.md``).
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Sequence
from contextlib import AbstractContextManager
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from memory_lifecycle.exceptions import ErroDeConfiguracao

#: Caminho pontuado (``pacote.modulo:funcao``) de um callable sem argumentos que
#: devolve um ``ProvedorDeConexao``. Só o caminho viaja pelo ambiente; um objeto de
#: pool nunca.
VARIAVEL_AMBIENTE_PROVEDOR = "MEMORY_LIFECYCLE_PROVEDOR_CONEXAO"


class ModoDeTransacao(StrEnum):
    """Quem faz commit.

    ``PARTICIPAR``: a aplicação faz; a biblioteca nunca chama ``commit`` nem
    ``rollback``, então uma escrita de memória entra junto com o request que a
    causou. Uma conexão em autocommit não tem transação para participar: a
    biblioteca levanta ``ErroDeConfiguracao`` antes de escrever (ADR 0004).
    ``PROPRIA``: a biblioteca faz commit no sucesso e rollback no erro.
    """

    PARTICIPAR = "participar"
    PROPRIA = "propria"


class Cursor(Protocol):
    """A fatia do DB-API 2.0 que a biblioteca usa; psycopg2 e psycopg 3 cabem nela."""

    @property
    def rowcount(self) -> int:
        """Linhas afetadas pela última instrução; conferido em todo fechamento condicional."""
        ...

    def execute(self, operation: str, parameters: Sequence[Any] | None = None, /) -> Any:
        """Executa uma instrução com marcadores ``%s``; parâmetros sempre posicionais."""
        ...

    def fetchone(self) -> Any:
        """Devolve a próxima linha ou ``None``."""
        ...

    def fetchall(self) -> Sequence[Any]:
        """Devolve as linhas restantes."""
        ...

    def close(self) -> None:
        """Libera o cursor."""
        ...


class Conexao(Protocol):
    """A fatia de uma conexão DB-API 2.0 que a biblioteca usa."""

    def cursor(self) -> Cursor:
        """Abre um cursor; a biblioteca o fecha."""
        ...

    def commit(self) -> None:
        """Commit; chamado só em ``ModoDeTransacao.PROPRIA``."""
        ...

    def rollback(self) -> None:
        """Rollback; chamado só em ``ModoDeTransacao.PROPRIA``."""
        ...


@runtime_checkable
class ProvedorDeConexao(Protocol):
    """Entrega uma conexão à biblioteca e diz se ela pode fazer commit nela.

    ``conexao()`` é um gerenciador de contexto: a biblioteca segura a conexão só
    durante uma operação e nunca durante uma chamada ao provedor de embeddings.
    """

    modo_de_transacao: ModoDeTransacao

    def conexao(self) -> AbstractContextManager[Conexao]:
        """Cede uma conexão DB-API; o provedor decide pool e liberação."""
        ...


def carregar_provedor(caminho_pontuado: str | None = None) -> ProvedorDeConexao:
    """Carrega o provedor nomeado por ``caminho_pontuado`` ou por ``VARIAVEL_AMBIENTE_PROVEDOR``.

    O caminho tem a forma ``pacote.modulo:funcao``, e a função, sem argumentos,
    devolve o provedor; assim o app decide pool e configuração no seu código, e
    só o caminho viaja pelo ambiente. Levanta ``ErroDeConfiguracao`` quando o
    caminho falta, está malformado, não importa, ou o objeto devolvido não honra
    ``ProvedorDeConexao``.
    """
    caminho = caminho_pontuado or os.environ.get(VARIAVEL_AMBIENTE_PROVEDOR)
    if not caminho:
        raise ErroDeConfiguracao(
            f"nenhum provedor de conexão: passe um, ou defina {VARIAVEL_AMBIENTE_PROVEDOR} "
            "com 'pacote.modulo:funcao'"
        )
    nome_do_modulo, separador, atributo = caminho.partition(":")
    if not separador or not nome_do_modulo or not atributo:
        raise ErroDeConfiguracao(
            f"caminho de provedor malformado: {caminho!r}; use 'pacote.modulo:funcao'"
        )
    try:
        modulo = importlib.import_module(nome_do_modulo)
    except ModuleNotFoundError as erro:
        if erro.name and nome_do_modulo.startswith(erro.name):
            raise ErroDeConfiguracao(
                f"o módulo {nome_do_modulo!r} de {caminho!r} não existe"
            ) from erro
        raise ErroDeConfiguracao(
            f"o módulo {nome_do_modulo!r} existe, mas falta a dependência {erro.name!r} dele"
        ) from erro
    fabrica = getattr(modulo, atributo, None)
    if not callable(fabrica):
        raise ErroDeConfiguracao(f"{caminho!r} não aponta para uma função")
    provedor = fabrica()
    if not isinstance(provedor, ProvedorDeConexao):
        raise ErroDeConfiguracao(
            f"{caminho!r} devolveu {type(provedor).__name__}, que não é um ProvedorDeConexao "
            "(precisa de modo_de_transacao e conexao())"
        )
    from memory_lifecycle.connection._unidade import modo_do_provedor

    modo_do_provedor(provedor)
    return provedor


__all__ = [
    "VARIAVEL_AMBIENTE_PROVEDOR",
    "Conexao",
    "Cursor",
    "ModoDeTransacao",
    "ProvedorDeConexao",
    "carregar_provedor",
]
