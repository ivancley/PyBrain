"""O texto SQL compartilhado: identificadores, colunas e conversões de valor.

Valores viajam sempre como ``%s``. Identificadores não podem viajar assim, então o
nome do schema é validado uma vez por uma expressão estrita e citado aqui; nenhum
outro módulo monta identificador. Vetores e uuids viajam como texto para que
psycopg2 e psycopg 3 se comportem igual sem adaptador registrado (ADR 0007).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from memory_lifecycle.exceptions import (
    ErroDeConfiguracao,
    ErroDeConflito,
    ErroDeDimensaoDeEmbedding,
    ErroMemoryLifecycle,
)
from memory_lifecycle.model import VersaoDeMemoria
from memory_lifecycle.temporal import Modo, Momento

_SCHEMA = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

#: Colunas na ordem de ``VersaoDeMemoria``; uuids lidos como texto.
COLUNAS: Final = (
    "versao_id::text, memoria_id::text, tenant_id, dono_id, categoria, conteudo, "
    "entidade_id, contexto_id, origem, modelo_embedding, valido_de, valido_ate, "
    "registrado_em, substituido_em, versao_anterior_id::text"
)


#: O predicado de cada modo (ADR 0002) e quantas vezes o instante entra nele.
_PREDICADOS: Final[Mapping[Modo, tuple[str, int]]] = {
    "como_em": (
        "substituido_em IS NULL AND valido_de <= %s AND (valido_ate IS NULL OR valido_ate > %s)",
        2,
    ),
    "sabido_em": (
        "registrado_em <= %s AND (substituido_em IS NULL OR substituido_em > %s) "
        "AND valido_de <= %s AND (valido_ate IS NULL OR valido_ate > %s)",
        4,
    ),
}


@dataclass(frozen=True, slots=True)
class Filtro:
    """Tenant e dono de toda instrução, e a tabela de versões já citada."""

    tabela: str
    tenant_id: str
    dono_id: str


def validar_schema(nome: str) -> str:
    """Devolve ``nome`` se for um identificador simples; senão ``ErroDeConfiguracao``."""
    if not _SCHEMA.fullmatch(nome):
        raise ErroDeConfiguracao(
            f"nome de schema inválido: {nome!r}; use letras minúsculas, dígitos e _ "
            "(até 63 caracteres, sem começar por dígito)"
        )
    return nome


def citar(schema: str, objeto: str) -> str:
    """Identificador qualificado e citado: ``"schema"."objeto"``; só após validar."""
    return f'"{validar_schema(schema)}"."{objeto}"'


def vetor_como_texto(vetor: Sequence[float]) -> str:
    """O literal de texto do pgvector, ``[0.1,0.2]``, sem perder precisão."""
    return "[" + ",".join(repr(float(valor)) for valor in vetor) + "]"


def linha_para_versao(linha: Sequence[Any]) -> VersaoDeMemoria:
    """Converte uma linha lida com ``COLUNAS`` no registro de versão."""
    return VersaoDeMemoria(*linha)


def predicado(momento: Momento) -> tuple[str, tuple[datetime, ...]]:
    """O texto do predicado do modo e os seus parâmetros, na ordem dos ``%s``."""
    texto, vezes = _PREDICADOS[momento.modo]
    return texto, (momento.instante,) * vezes


def e_uuid(texto: str) -> bool:
    """Diz se ``texto`` é um uuid; um id inválido nunca vai ao banco.

    Um valor inválido em ``%s::uuid`` é erro no Postgres e abortaria a transação
    do app no modo ``PARTICIPAR``; por isso a checagem acontece antes, e só aceita
    a forma canônica de 8-4-4-4-12 dígitos, que o Postgres sempre aceita.
    """
    return isinstance(texto, str) and _UUID.fullmatch(texto) is not None


def normalizar_uuid(texto: str) -> str:
    """A forma em que o banco devolve um uuid (minúsculas), para comparar com ``==``."""
    return str(uuid.UUID(texto))


def sqlstate(erro: BaseException) -> str | None:
    """O SQLSTATE de um erro de driver: ``.sqlstate`` (psycopg 3) ou ``.pgcode`` (psycopg2)."""
    for atributo in ("sqlstate", "pgcode"):
        valor = getattr(erro, atributo, None)
        if isinstance(valor, str):
            return valor
    return None


def _restricao(erro: BaseException) -> str | None:
    """O nome da restrição violada, que os dois drivers expõem em ``erro.diag``."""
    return getattr(getattr(erro, "diag", None), "constraint_name", None)


def traduzir(erro: BaseException) -> ErroMemoryLifecycle | None:
    """O erro tipado que um erro de banco significa para quem chama, ou ``None``.

    Só traduz o que tem consequência conhecida; o resto sobe como veio, nunca
    engolido nem rebatizado de genérico.
    """
    codigo = sqlstate(erro)
    if codigo == "23505" and _restricao(erro) == "ux_versoes_vigente":
        return ErroDeConflito(
            "outra escrita gravou esta versão primeiro; releia com historico e decida"
        )
    if codigo in ("40001", "40P01"):
        return ErroDeConflito(
            "o banco desfez a operação por conflito com outra transação (serialização ou "
            "deadlock); releia com historico e decida"
        )
    if codigo in ("42P01", "3F000"):
        return ErroDeConfiguracao(
            "o schema da memória não existe ou não foi migrado; chame Memoria.migrar()"
        )
    if codigo == "22000" and "dimensions" in str(erro):
        return ErroDeDimensaoDeEmbedding(
            "o vetor não tem a dimensão da coluna do schema; o provedor de embeddings mudou"
        )
    return None
