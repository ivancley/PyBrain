"""O executor de migrações: arquivos SQL numerados, aplicados em ordem, uma vez cada.

Sem ORM, a biblioteca é dona do seu schema (ADR 0008). Cada arquivo
``NNNN_<assunto>.sql`` deste pacote é renderizado com o nome do schema (validado e
citado) e a dimensão do vetor, aplicado e registrado em ``versao_do_schema`` com
o seu sha256. Uma trava consultiva serializa duas chamadas simultâneas.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable

from memory_lifecycle._sql import citar, sqlstate
from memory_lifecycle.connection import Cursor
from memory_lifecycle.exceptions import (
    ErroDeConfiguracao,
    ErroDeDimensaoDeEmbedding,
    ErroDeMigracao,
)

_ARQUIVO = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
#: Uma trava só para todos os schemas: `CREATE EXTENSION` também é do banco inteiro.
_TRAVA = "memory_lifecycle:migrar"


@dataclass(frozen=True, slots=True)
class Migracao:
    """Um arquivo de migração lido do pacote; ``sha256`` é do arquivo cru."""

    numero: int
    nome: str
    sha256: str
    sql: str


def descobrir(origem: Traversable | None = None) -> list[Migracao]:
    """Lê as migrações do pacote (ou de ``origem``) em ordem; número repetido é erro."""
    encontradas: dict[int, Migracao] = {}
    pasta = origem if origem is not None else resources.files(__package__)
    for item in pasta.iterdir():
        casamento = _ARQUIVO.match(item.name)
        if casamento is None:
            continue
        sql = item.read_text(encoding="utf-8")
        migracao = Migracao(
            numero=int(casamento.group(1)),
            nome=item.name,
            sha256=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            sql=sql,
        )
        if migracao.numero in encontradas:
            raise ErroDeMigracao(
                f"duas migrações com o número {migracao.numero:04d}: "
                f"{encontradas[migracao.numero].nome} e {migracao.nome}"
            )
        encontradas[migracao.numero] = migracao
    return [encontradas[numero] for numero in sorted(encontradas)]


def renderizar(sql: str, schema: str, dimensao: int) -> str:
    """Troca ``{schema}`` pelo identificador citado e ``{dimensao}`` pelo inteiro."""
    return sql.replace("{schema}", f'"{schema}"').replace("{dimensao}", str(int(dimensao)))


def aplicar(cur: Cursor, schema: str, dimensao: int) -> int:
    """Aplica as migrações pendentes no ``schema`` e devolve quantas aplicou.

    ``schema`` já chega validado. Idempotente: uma segunda chamada devolve 0.
    Antes de aplicar qualquer coisa, confere que toda migração já aplicada ainda
    tem o mesmo sha256 e existe no pacote; depois, que a dimensão registrada é a
    do provedor de embeddings.
    """
    tabela = citar(schema, "versao_do_schema")
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (_TRAVA,))
    _garantir_extensao(cur)
    cur.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,))
    if cur.fetchone() is None:
        cur.execute(f'CREATE SCHEMA "{schema}"')
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS {tabela} ("
        "numero int PRIMARY KEY, nome text NOT NULL, sha256 text NOT NULL, "
        "aplicada_em timestamptz NOT NULL)"
    )
    cur.execute(f"SELECT numero, sha256 FROM {tabela}")
    aplicadas = {int(numero): str(sha) for numero, sha in cur.fetchall()}
    migracoes = descobrir()
    _conferir_aplicadas(aplicadas, migracoes)
    contagem = 0
    for migracao in migracoes:
        if migracao.numero in aplicadas:
            continue
        try:
            cur.execute(renderizar(migracao.sql, schema, dimensao))
        except Exception as erro:
            raise ErroDeMigracao(
                f"a migração {migracao.nome} falhou ao ser aplicada; nada foi gravado se a "
                "transação for desfeita"
            ) from erro
        cur.execute(
            f"INSERT INTO {tabela} (numero, nome, sha256, aplicada_em) VALUES (%s, %s, %s, now())",
            (migracao.numero, migracao.nome, migracao.sha256),
        )
        contagem += 1
    registrada = ler_dimensao(cur, schema)
    if registrada != dimensao:
        raise ErroDeDimensaoDeEmbedding(
            f"o schema {schema!r} foi criado para vetores de {registrada} dimensões; o provedor "
            f"de embeddings gera {dimensao}. Use outro schema ou o provedor original."
        )
    return contagem


def ler_dimensao(cur: Cursor, schema: str) -> int:
    """A dimensão registrada no schema; schema não migrado é ``ErroDeConfiguracao``.

    Consulta ``to_regclass`` antes, para que um schema ausente não vire erro de
    banco, que abortaria a transação do app no modo ``PARTICIPAR``.
    """
    configuracao = citar(schema, "configuracao")
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (configuracao,))
    linha = cur.fetchone()
    if linha is None or not linha[0]:
        raise ErroDeConfiguracao(
            f"o schema {schema!r} da memória não foi migrado; chame Memoria.migrar()"
        )
    cur.execute(f"SELECT valor FROM {configuracao} WHERE chave = 'dimensao'")
    linha = cur.fetchone()
    if linha is None:
        raise ErroDeConfiguracao(f"o schema {schema!r} não tem a dimensão registrada")
    return int(linha[0])


def _garantir_extensao(cur: Cursor) -> None:
    """Instala o pgvector se faltar, sem deixar uma falha abortar a transação do app.

    Tenta o ``CREATE EXTENSION`` dentro de um savepoint próprio: funciona para o
    superusuário, para o papel administrativo de um serviço gerenciado e para uma
    extensão confiável; quando falha, o savepoint é desfeito e o erro explica o que
    rodar.
    """
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector'),"
        " EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
    )
    linha = cur.fetchone()
    instalada, disponivel = linha if linha else (False, False)
    if instalada:
        return
    if not disponivel:
        raise ErroDeConfiguracao(
            "o servidor PostgreSQL não tem o pgvector; instale o pacote do pgvector no "
            "servidor e rode `CREATE EXTENSION vector;` neste banco"
        )
    cur.execute("SAVEPOINT memory_lifecycle_extensao")
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as erro:
        cur.execute("ROLLBACK TO SAVEPOINT memory_lifecycle_extensao")
        if sqlstate(erro) == "42501":
            raise ErroDeConfiguracao(
                "a extensão pgvector não está instalada neste banco e este usuário não pode "
                "instalá-la; rode `CREATE EXTENSION vector;` como superusuário e chame "
                "migrar() de novo"
            ) from erro
        raise
    cur.execute("RELEASE SAVEPOINT memory_lifecycle_extensao")


def _conferir_aplicadas(aplicadas: dict[int, str], migracoes: list[Migracao]) -> None:
    no_pacote = {migracao.numero: migracao for migracao in migracoes}
    for numero, sha in sorted(aplicadas.items()):
        migracao = no_pacote.get(numero)
        if migracao is None:
            raise ErroDeMigracao(
                f"o banco tem a migração {numero:04d}, que esta versão da biblioteca não "
                "conhece; atualize a biblioteca antes de usar este schema"
            )
        if migracao.sha256 != sha:
            raise ErroDeMigracao(
                f"a migração {migracao.nome} mudou depois de aplicada (sha256 {sha[:12]}… no "
                f"banco, {migracao.sha256[:12]}… no pacote); a correção é um arquivo novo, "
                "nunca editar um aplicado (ADR 0008)"
            )
