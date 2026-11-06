"""``migrar``: idempotente, append-only, dimensão fixa e seguro em paralelo (ADR 0008)."""

from __future__ import annotations

import threading
import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from memory_lifecycle import (
    ErroDeConfiguracao,
    ErroDeDimensaoDeEmbedding,
    ErroDeMigracao,
    Memoria,
    ProvedorDeEmbeddingsFalso,
)
from memory_lifecycle.connection.dsn import ProvedorDSN
from memory_lifecycle.migrations import descobrir


def _nova(dsn: str, schema: str, dimensao: int = 8) -> Memoria:
    return Memoria(
        conexao=ProvedorDSN(dsn),
        embeddings=ProvedorDeEmbeddingsFalso(dimensao=dimensao),
        tenant_id="t",
        schema=schema,
    )


def _catalogo(dsn: str, schema: str) -> list[tuple[str, ...]]:
    with psycopg.connect(dsn) as conexao:
        colunas = conexao.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = %s ORDER BY 1, 2",
            (schema,),
        ).fetchall()
        indices = conexao.execute(
            "SELECT indexname, indexdef, '' FROM pg_indexes WHERE schemaname = %s ORDER BY 1",
            (schema,),
        ).fetchall()
    return [tuple(map(str, linha)) for linha in [*colunas, *indices]]


def _executar(dsn: str, sql: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conexao:
        conexao.execute(sql)


def test_aplicar_do_zero_duas_vezes_da_o_mesmo_schema(dsn: str, schema: str):
    memoria = _nova(dsn, schema)
    assert memoria.migrar() == len(descobrir())
    antes = _catalogo(dsn, schema)
    assert memoria.migrar() == 0
    assert _catalogo(dsn, schema) == antes
    assert any("ux_versoes_vigente" in linha[0] for linha in antes)


def test_hash_alterado_e_recusado(dsn: str, schema: str):
    memoria = _nova(dsn, schema)
    memoria.migrar()
    _executar(dsn, f"UPDATE \"{schema}\".versao_do_schema SET sha256 = repeat('0', 64)")
    with pytest.raises(ErroDeMigracao, match="mudou depois de aplicada"):
        memoria.migrar()


def test_migracao_desconhecida_no_banco_e_recusada(dsn: str, schema: str):
    memoria = _nova(dsn, schema)
    memoria.migrar()
    _executar(
        dsn,
        f"INSERT INTO \"{schema}\".versao_do_schema VALUES (9999, 'do_futuro.sql', 'x', now())",
    )
    with pytest.raises(ErroDeMigracao, match="9999"):
        memoria.migrar()


def test_outra_dimensao_e_recusada_em_migrar_e_na_escrita(dsn: str, schema: str):
    _nova(dsn, schema, dimensao=8).migrar()
    outra = _nova(dsn, schema, dimensao=16)
    with pytest.raises(ErroDeDimensaoDeEmbedding):
        outra.migrar()
    with pytest.raises(ErroDeDimensaoDeEmbedding):
        outra.lembrar("d", "x", categoria="nota")
    with pytest.raises(ErroDeDimensaoDeEmbedding):
        outra.recuperar("d", consulta="x")


def test_operar_sem_migrar_e_erro_de_configuracao(dsn: str, schema: str):
    memoria = _nova(dsn, schema)
    with pytest.raises(ErroDeConfiguracao, match="migrar"):
        memoria.lembrar("d", "x", categoria="nota")
    with pytest.raises(ErroDeConfiguracao, match="migrar"):
        memoria.recuperar("d")
    with pytest.raises(ErroDeConfiguracao, match="migrar"):
        memoria.encerrar("d", str(uuid.uuid4()))


def test_duas_migracoes_simultaneas(dsn: str, schema: str):
    resultados: list[int] = []

    def migrar() -> None:
        resultados.append(_nova(dsn, schema).migrar())

    threads = [threading.Thread(target=migrar) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(resultados) == [0, len(descobrir())]


def test_extensao_ausente_sem_privilegio_explica_o_que_rodar(dsn: str):
    sufixo = uuid.uuid4().hex[:8]
    papel, banco = f"ml_sem_priv_{sufixo}", f"ml_sem_vector_{sufixo}"
    _executar(dsn, f"CREATE ROLE {papel} LOGIN PASSWORD 'senha' NOSUPERUSER")
    _executar(dsn, f"CREATE DATABASE {banco} OWNER {papel}")
    partes = urlsplit(dsn)
    dsn_restrito = urlunsplit(
        (partes.scheme, f"{papel}:senha@{partes.hostname}:{partes.port}", f"/{banco}", "", "")
    )
    try:
        with pytest.raises(ErroDeConfiguracao, match="CREATE EXTENSION vector"):
            _nova(dsn_restrito, "memory_lifecycle").migrar()
    finally:
        _executar(dsn, f"DROP DATABASE IF EXISTS {banco} WITH (FORCE)")
        _executar(dsn, f"DROP ROLE IF EXISTS {papel}")


def test_falha_no_meio_da_migracao_diz_qual_arquivo(
    dsn: str, schema: str, monkeypatch: pytest.MonkeyPatch
):
    # Regressão (reports/silent-failure-fatia-10.md, achado 7): o erro subia cru.
    from memory_lifecycle import migrations

    quebrada = migrations.Migracao(numero=1, nome="0001_quebrada.sql", sha256="x", sql="SELEC 1;")
    monkeypatch.setattr(migrations, "descobrir", lambda origem=None: [quebrada])
    with pytest.raises(ErroDeMigracao, match="0001_quebrada.sql"):
        _nova(dsn, schema).migrar()


def test_migrar_de_novo_sem_privilegio_de_criar_schema(dsn: str):
    # Regressão (achado 5): `CREATE SCHEMA IF NOT EXISTS` exige CREATE no banco mesmo
    # quando o schema já existe, então migrar() não era idempotente para esse usuário.
    sufixo = uuid.uuid4().hex[:8]
    papel, banco, schema = f"ml_app_{sufixo}", f"ml_app_{sufixo}", "memoria_do_app"
    _executar(dsn, f"CREATE ROLE {papel} LOGIN PASSWORD 'senha' NOSUPERUSER")
    _executar(dsn, f"CREATE DATABASE {banco}")
    partes = urlsplit(dsn)
    dsn_admin = urlunsplit((partes.scheme, partes.netloc, f"/{banco}", "", ""))
    dsn_app = urlunsplit(
        (partes.scheme, f"{papel}:senha@{partes.hostname}:{partes.port}", f"/{banco}", "", "")
    )
    try:
        assert _nova(dsn_admin, schema).migrar() >= 1
        _executar(
            dsn_admin,
            f"GRANT USAGE, CREATE ON SCHEMA {schema} TO {papel}; "
            f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {papel}",
        )
        assert _nova(dsn_app, schema).migrar() == 0
    finally:
        _executar(dsn, f"DROP DATABASE IF EXISTS {banco} WITH (FORCE)")
        _executar(dsn, f"DROP ROLE IF EXISTS {papel}")


def test_toda_chave_estrangeira_tem_indice(dsn: str, schema: str):
    # Regressão (reports/sql-perf-escritas.md, crítico): sem índice em
    # versao_anterior_id, cada linha apagada por `esquecer` varria a tabela.
    _nova(dsn, schema).migrar()
    with psycopg.connect(dsn) as conexao:
        sem_indice = conexao.execute(
            """
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE c.contype = 'f' AND n.nspname = %s
              AND NOT EXISTS (
                SELECT 1 FROM pg_index i
                WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1]
              )
            """,
            (schema,),
        ).fetchall()
    assert sem_indice == []
