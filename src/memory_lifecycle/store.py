"""As escritas: uma função por instrução, todas filtradas por tenant e dono.

Cada função recebe o cursor da unidade de trabalho e um ``Filtro``; nenhuma abre
conexão, decide transação ou calcula embedding. A guarda ``test_tenant_filter``
confere que toda instrução daqui carrega ``tenant_id`` e ``dono_id``.
"""

from __future__ import annotations

from datetime import datetime

from memory_lifecycle._sql import COLUNAS, Filtro, linha_para_versao
from memory_lifecycle.connection import Cursor
from memory_lifecycle.exceptions import ErroDeConflito, ErroNaoEncontrado
from memory_lifecycle.model import VersaoDeMemoria

#: As colunas que uma versão nova recebe, na ordem dos INSERT abaixo.
_COLUNAS_DE_INSERCAO = (
    "memoria_id, tenant_id, dono_id, categoria, conteudo, entidade_id, contexto_id, origem, "
    "embedding, modelo_embedding, valido_de, valido_ate, registrado_em, versao_anterior_id"
)
#: O que a cópia limitada herda da versão de origem, sem trazer o vetor ao Python.
_HERDADAS = (
    "memoria_id, tenant_id, dono_id, categoria, conteudo, entidade_id, contexto_id, origem, "
    "embedding, modelo_embedding, valido_de"
)

_VIGENTE = """
SELECT {colunas} FROM {tabela}
WHERE memoria_id = %s::uuid AND substituido_em IS NULL AND tenant_id = %s AND dono_id = %s
ORDER BY valido_de DESC
LIMIT 1
"""

_FECHAR_REGISTRO = """
UPDATE {tabela} SET substituido_em = %s
WHERE versao_id = %s::uuid AND substituido_em IS NULL AND tenant_id = %s AND dono_id = %s
"""

_COPIA_LIMITADA = """
INSERT INTO {tabela} ({inserir})
SELECT {herdadas}, %s, %s, versao_id FROM {tabela}
WHERE versao_id = %s::uuid AND tenant_id = %s AND dono_id = %s
RETURNING {colunas}
"""

_ENCERRAR_CONTEXTO = """
WITH fechadas AS (
  UPDATE {tabela} SET substituido_em = %s
  WHERE contexto_id = %s AND substituido_em IS NULL AND (valido_ate IS NULL OR valido_ate > %s)
    AND tenant_id = %s AND dono_id = %s
  RETURNING versao_id, {herdadas}
), copias AS (
  INSERT INTO {tabela} ({inserir})
  SELECT {herdadas}, %s, %s, versao_id FROM fechadas WHERE valido_de < %s
  RETURNING 1
)
SELECT count(*) FROM fechadas
"""

#: Rodadas de ``_ENCERRAR_CONTEXTO`` antes de desistir de um contexto que não para
#: de receber escritas.
_RODADAS_DE_ENCERRAMENTO = 5

_APAGAR_MEMORIA = """
DELETE FROM {tabela} WHERE memoria_id = %s::uuid AND tenant_id = %s AND dono_id = %s
"""

_APAGAR_POR_ENTIDADE = """
DELETE FROM {tabela}
WHERE tenant_id = %s AND dono_id = %s AND memoria_id IN (
  SELECT memoria_id FROM {tabela} WHERE entidade_id = %s AND tenant_id = %s AND dono_id = %s
)
"""

_APAGAR_TUDO = """
DELETE FROM {tabela} WHERE tenant_id = %s AND dono_id = %s
"""

_INSERIR = """
INSERT INTO {tabela} (
  memoria_id, tenant_id, dono_id, categoria, conteudo, entidade_id, contexto_id, origem,
  embedding, modelo_embedding, valido_de, valido_ate, registrado_em, versao_anterior_id
) VALUES (
  COALESCE(%s::uuid, gen_random_uuid()), %s, %s, %s, %s, %s, %s, %s,
  %s::vector, %s, %s, %s, %s, %s::uuid
)
RETURNING {colunas}
"""


def inserir(  # noqa: PLR0913 — uma coluna por argumento, todos nomeados
    cur: Cursor,
    f: Filtro,
    *,
    memoria_id: str | None,
    conteudo: str,
    categoria: str,
    entidade_id: str | None,
    contexto_id: str | None,
    origem: str | None,
    vetor: str,
    modelo: str,
    valido_de: datetime,
    valido_ate: datetime | None,
    registrado_em: datetime,
    versao_anterior_id: str | None,
) -> VersaoDeMemoria:
    """Insere uma versão; sem ``memoria_id``, nasce uma memória nova."""
    cur.execute(
        _INSERIR.format(tabela=f.tabela, colunas=COLUNAS),
        (
            memoria_id,
            f.tenant_id,
            f.dono_id,
            categoria,
            conteudo,
            entidade_id,
            contexto_id,
            origem,
            vetor,
            modelo,
            valido_de,
            valido_ate,
            registrado_em,
            versao_anterior_id,
        ),
    )
    return linha_para_versao(cur.fetchone())


def buscar_vigente(cur: Cursor, f: Filtro, memoria_id: str) -> VersaoDeMemoria:
    """A versão vigente: registro aberto e maior ``valido_de`` (ADR 0002)."""
    cur.execute(
        _VIGENTE.format(colunas=COLUNAS, tabela=f.tabela), (memoria_id, f.tenant_id, f.dono_id)
    )
    linha = cur.fetchone()
    if linha is None:
        raise ErroNaoEncontrado("memória não encontrada para este tenant e dono")
    return linha_para_versao(linha)


def fechar_registro(cur: Cursor, f: Filtro, versao_id: str, agora: datetime) -> None:
    """Fecha ``substituido_em``; se outro escritor fechou antes, ``ErroDeConflito``.

    É a trava de concorrência: o segundo escritor espera o lock da linha e, depois
    do commit do primeiro, reavalia o ``WHERE`` e afeta zero linhas.
    """
    cur.execute(
        _FECHAR_REGISTRO.format(tabela=f.tabela), (agora, versao_id, f.tenant_id, f.dono_id)
    )
    if cur.rowcount != 1:
        raise ErroDeConflito(
            "outra escrita mudou esta memória primeiro; releia com historico e decida"
        )


def inserir_copia_limitada(
    cur: Cursor, f: Filtro, origem_id: str, valido_ate: datetime, agora: datetime
) -> VersaoDeMemoria:
    """Insere a cópia de ``origem_id`` com ``valido_ate``, ligada a ela; o vetor fica no banco."""
    cur.execute(
        _COPIA_LIMITADA.format(
            tabela=f.tabela, inserir=_COLUNAS_DE_INSERCAO, herdadas=_HERDADAS, colunas=COLUNAS
        ),
        (valido_ate, agora, origem_id, f.tenant_id, f.dono_id),
    )
    return linha_para_versao(cur.fetchone())


def encerrar_contexto(
    cur: Cursor, f: Filtro, contexto_id: str, valido_ate: datetime, agora: datetime
) -> int:
    """Encerra em ``valido_ate`` toda crença atual do contexto que valeria depois; devolve quantas.

    Fecha o registro de cada uma e, nas que já começaram, insere a cópia limitada;
    as que só começariam depois ficam sem cópia, porque nunca valeram. Roda ao
    menos duas vezes e repete até nada mudar: em READ COMMITTED a versão nova de
    um ``substituir`` concorrente não está no instantâneo da primeira rodada.
    """
    total = 0
    for rodada in range(_RODADAS_DE_ENCERRAMENTO):
        cur.execute(
            _ENCERRAR_CONTEXTO.format(
                tabela=f.tabela, inserir=_COLUNAS_DE_INSERCAO, herdadas=_HERDADAS
            ),
            (agora, contexto_id, valido_ate, f.tenant_id, f.dono_id, valido_ate, agora, valido_ate),
        )
        linha = cur.fetchone()
        encerradas = int(linha[0]) if linha else 0
        # Uma rodada que esperou o lock de outro escritor pode não encerrar nada e,
        # ainda assim, haver a versão nova dele: só a rodada seguinte a enxerga.
        if encerradas == 0 and rodada > 0:
            return total
        total += encerradas
    raise ErroDeConflito(
        f"o contexto {contexto_id!r} continuou recebendo escritas durante a invalidação; "
        "tente de novo"
    )


def apagar(
    cur: Cursor, f: Filtro, *, memoria_id: str | None, entidade_id: str | None, tudo: bool
) -> int:
    """Apaga fisicamente toda versão do alvo; por entidade, a memória inteira sai."""
    if memoria_id is not None:
        cur.execute(_APAGAR_MEMORIA.format(tabela=f.tabela), (memoria_id, f.tenant_id, f.dono_id))
    elif entidade_id is not None:
        cur.execute(
            _APAGAR_POR_ENTIDADE.format(tabela=f.tabela),
            (f.tenant_id, f.dono_id, entidade_id, f.tenant_id, f.dono_id),
        )
    elif tudo:
        cur.execute(_APAGAR_TUDO.format(tabela=f.tabela), (f.tenant_id, f.dono_id))
    else:
        return 0
    return cur.rowcount
