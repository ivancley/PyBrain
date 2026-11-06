"""As leituras: ``recuperar`` e ``historico``.

Toda instrução filtra tenant e dono antes de qualquer outro predicado (guarda
``test_tenant_filter``). O escopo é estrito (ADR 0003): ``None`` como membro da
lista inclui as versões sem contexto ou sem entidade. Nada aqui escreve.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any

from memory_lifecycle._sql import COLUNAS, Filtro, linha_para_versao, predicado
from memory_lifecycle.connection import Cursor
from memory_lifecycle.exceptions import ErroDeArgumentoInvalido, ErroNaoEncontrado
from memory_lifecycle.model import ResultadoDeRecuperacao, VersaoDeMemoria
from memory_lifecycle.temporal import Momento

_RECUPERAR = """
SELECT {selecao} FROM {tabela} AS v
WHERE tenant_id = %s AND dono_id = %s AND {filtros}
ORDER BY {ordem}
LIMIT %s
"""
_PONTUACAO = ", 1 - (embedding <=> %s::vector) / 2"
# `v.versao_id` qualificado: sem o alias, `versao_id` seria a coluna de saída
# `versao_id::text`, e o desempate não usaria o índice `ix_versoes_ordem_registro`.
_ORDEM_POR_SIMILARIDADE = "v.embedding <=> %s::vector, v.registrado_em DESC, v.versao_id"
_ORDEM_POR_REGISTRO = "v.registrado_em DESC, v.versao_id"
_FILTRO_CONTEXTO = "(contexto_id = ANY(%s::text[]) OR (%s AND contexto_id IS NULL))"
_FILTRO_ENTIDADE = "(entidade_id = ANY(%s::text[]) OR (%s AND entidade_id IS NULL))"
_FILTRO_CATEGORIA = "categoria = %s"

#: Quantas colunas de ``COLUNAS`` formam a versão; a pontuação, quando há, vem depois.
_CAMPOS_DA_VERSAO = len(fields(VersaoDeMemoria))

_HISTORICO = """
SELECT {colunas} FROM {tabela}
WHERE memoria_id = %s::uuid AND tenant_id = %s AND dono_id = %s
ORDER BY registrado_em, valido_de, substituido_em IS NULL, versao_id
"""


@dataclass(frozen=True, slots=True)
class EixoDeEscopo:
    """Um eixo do escopo já resolvido: os ids e se as versões sem id entram."""

    ids: tuple[str, ...]
    incluir_nulo: bool


def montar_eixo(valores: Sequence[str | None] | None) -> EixoDeEscopo | None:
    """``None`` não filtra; ``[]`` não devolve nada; ``["a", None]`` é ``a`` e os sem id."""
    if valores is None:
        return None
    if isinstance(valores, str):
        raise ErroDeArgumentoInvalido(
            "o escopo é uma lista de ids, não uma string: use contextos=[...]"
        )
    ids = tuple(valor for valor in valores if valor is not None)
    return EixoDeEscopo(ids=ids, incluir_nulo=any(valor is None for valor in valores))


def recuperar(  # noqa: PLR0913 — os filtros da consulta, todos nomeados
    cur: Cursor,
    f: Filtro,
    momento: Momento,
    *,
    vetor_consulta: str | None,
    contextos: EixoDeEscopo | None,
    entidades: EixoDeEscopo | None,
    categoria: str | None,
    limite: int,
) -> list[ResultadoDeRecuperacao]:
    """Uma instrução: tenant e dono, o predicado do modo, o escopo, a categoria e a ordem."""
    texto_do_modo, parametros_do_modo = predicado(momento)
    filtros = [texto_do_modo]
    parametros_do_filtro: list[Any] = [*parametros_do_modo]
    for texto, eixo in ((_FILTRO_CONTEXTO, contextos), (_FILTRO_ENTIDADE, entidades)):
        if eixo is not None:
            filtros.append(texto)
            parametros_do_filtro += [list(eixo.ids), eixo.incluir_nulo]
    if categoria is not None:
        filtros.append(_FILTRO_CATEGORIA)
        parametros_do_filtro.append(categoria)

    com_consulta = vetor_consulta is not None
    sql = _RECUPERAR.format(
        selecao=COLUNAS + (_PONTUACAO if com_consulta else ""),
        tabela=f.tabela,
        filtros=" AND ".join(filtros),
        ordem=_ORDEM_POR_SIMILARIDADE if com_consulta else _ORDEM_POR_REGISTRO,
    )
    parametros: list[Any] = [vetor_consulta] if com_consulta else []
    parametros += [f.tenant_id, f.dono_id, *parametros_do_filtro]
    parametros += [vetor_consulta] if com_consulta else []
    parametros.append(limite)
    cur.execute(sql, parametros)
    return [
        ResultadoDeRecuperacao(
            versao=linha_para_versao(linha[:_CAMPOS_DA_VERSAO]),
            pontuacao=float(linha[_CAMPOS_DA_VERSAO]) if com_consulta else None,
        )
        for linha in cur.fetchall()
    ]


def historico(cur: Cursor, f: Filtro, memoria_id: str) -> list[VersaoDeMemoria]:
    """Toda versão da memória deste tenant e dono; nenhuma é ``ErroNaoEncontrado``.

    No empate de ``registrado_em``, vem antes a de ``valido_de`` menor e, no
    empate dos dois, a de registro fechado antes da aberta: a vigente é sempre a
    última, mesmo com o relógio congelado.
    """
    cur.execute(
        _HISTORICO.format(colunas=COLUNAS, tabela=f.tabela),
        (memoria_id, f.tenant_id, f.dono_id),
    )
    versoes = [linha_para_versao(linha) for linha in cur.fetchall()]
    if not versoes:
        raise ErroNaoEncontrado("memória não encontrada para este tenant e dono")
    return versoes
