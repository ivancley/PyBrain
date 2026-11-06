"""A unidade de trabalho: uma operação, uma conexão emprestada, uma transação.

Concentra a regra do ADR 0004 num lugar só. A conexão vem do provedor e é
devolvida ao fim da operação. Uma conexão em autocommit é recusada nos dois modos,
antes de qualquer instrução: sem transação, uma operação de várias instruções
ficaria pela metade. No modo ``PROPRIA`` a biblioteca faz commit no sucesso e
rollback em qualquer exceção; no ``PARTICIPAR`` não faz nenhum dos dois, e a
transação é do app. Um erro de banco com consequência conhecida sobe traduzido
(``_sql.traduzir``), encadeado ao original; os demais sobem intactos.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from memory_lifecycle._sql import traduzir
from memory_lifecycle.connection import Cursor, ModoDeTransacao, ProvedorDeConexao
from memory_lifecycle.exceptions import ErroDeConfiguracao


@contextmanager
def unidade_de_trabalho(provedor: ProvedorDeConexao) -> Iterator[Cursor]:
    """Cede um cursor dentro de uma transação, conforme o modo do provedor."""
    modo = modo_do_provedor(provedor)
    propria = modo is ModoDeTransacao.PROPRIA
    with provedor.conexao() as conexao:
        if getattr(conexao, "autocommit", False):
            raise ErroDeConfiguracao(
                f"a conexão do provedor está em autocommit; o modo {modo.value} precisa de "
                "uma transação: desligue o autocommit no provedor ou use o adaptador do "
                "seu framework (ADR 0004)"
            )
        cursor = conexao.cursor()
        try:
            yield cursor
            if propria:
                conexao.commit()
        except BaseException as erro:
            _fechar(cursor, erro)
            if propria:
                _desfazer(conexao, erro)
            traduzido = traduzir(erro) if isinstance(erro, Exception) else None
            if traduzido is not None:
                raise traduzido from erro
            raise
        else:
            cursor.close()


def modo_do_provedor(provedor: object) -> ModoDeTransacao:
    """O modo declarado pelo provedor, como enum; um valor fora dele é recusado.

    Comparar por identidade com um valor que não é o enum trataria ``"propria"``
    como ``PARTICIPAR``, e a escrita sumiria sem commit e sem erro.
    """
    try:
        return ModoDeTransacao(getattr(provedor, "modo_de_transacao"))  # noqa: B009
    except (AttributeError, ValueError) as erro:
        raise ErroDeConfiguracao(
            "o provedor de conexão precisa declarar modo_de_transacao como "
            f"ModoDeTransacao.PROPRIA ou ModoDeTransacao.PARTICIPAR ({erro})"
        ) from erro


def _fechar(cursor: Cursor, erro: BaseException) -> None:
    """Fecha o cursor sem trocar o erro em voo por um erro de fechamento."""
    try:
        cursor.close()
    except Exception as falha_ao_fechar:
        erro.add_note(f"fechar o cursor também falhou: {falha_ao_fechar!r}")


def _desfazer(conexao: object, erro: BaseException) -> None:
    """Rollback que nunca esconde o erro original: uma falha aqui vira nota nele."""
    try:
        conexao.rollback()  # type: ignore[attr-defined]
    except Exception as falha_no_rollback:
        erro.add_note(f"o rollback também falhou: {falha_no_rollback!r}")
