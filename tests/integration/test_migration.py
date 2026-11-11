"""``migrate``: idempotent, append-only, fixed dimension and safe in parallel (ADR 0008).

PT: ``migrate``: idempotente, append-only, dimensão fixa e seguro em paralelo (ADR 0008).
"""

from __future__ import annotations

import threading
import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from memory_lifecycle import (
    ConfigurationError,
    EmbeddingDimensionError,
    FakeEmbeddingProvider,
    Memory,
    MigrationError,
)
from memory_lifecycle.connection.dsn import DSNProvider
from memory_lifecycle.migrations import discover


def _new(dsn: str, schema: str, dimension: int = 8) -> Memory:
    return Memory(
        connection=DSNProvider(dsn),
        embeddings=FakeEmbeddingProvider(dimension=dimension),
        tenant_id="t",
        schema=schema,
    )


def _catalog(dsn: str, schema: str) -> list[tuple[str, ...]]:
    with psycopg.connect(dsn) as connection:
        columns = connection.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = %s ORDER BY 1, 2",
            (schema,),
        ).fetchall()
        indexes = connection.execute(
            "SELECT indexname, indexdef, '' FROM pg_indexes WHERE schemaname = %s ORDER BY 1",
            (schema,),
        ).fetchall()
    return [tuple(map(str, row)) for row in [*columns, *indexes]]


def _execute(dsn: str, sql: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql)


def test_applying_from_scratch_twice_gives_the_same_schema(dsn: str, schema: str):
    memory = _new(dsn, schema)
    assert memory.migrate() == len(discover())
    before = _catalog(dsn, schema)
    assert memory.migrate() == 0
    assert _catalog(dsn, schema) == before
    assert any("ux_versions_current" in row[0] for row in before)


def test_changed_hash_is_rejected(dsn: str, schema: str):
    memory = _new(dsn, schema)
    memory.migrate()
    _execute(dsn, f"UPDATE \"{schema}\".schema_version SET sha256 = repeat('0', 64)")
    with pytest.raises(MigrationError, match="changed after being applied"):
        memory.migrate()


def test_unknown_migration_in_the_database_is_rejected(dsn: str, schema: str):
    memory = _new(dsn, schema)
    memory.migrate()
    _execute(
        dsn,
        f"INSERT INTO \"{schema}\".schema_version VALUES (9999, 'from_the_future.sql', 'x', now())",
    )
    with pytest.raises(MigrationError, match="9999"):
        memory.migrate()


def test_another_dimension_is_rejected_on_migrate_and_on_write(dsn: str, schema: str):
    _new(dsn, schema, dimension=8).migrate()
    other = _new(dsn, schema, dimension=16)
    with pytest.raises(EmbeddingDimensionError):
        other.migrate()
    with pytest.raises(EmbeddingDimensionError):
        other.remember("d", "x", kind="note")
    with pytest.raises(EmbeddingDimensionError):
        other.recall("d", query="x")


def test_operating_without_migrating_is_a_configuration_error(dsn: str, schema: str):
    memory = _new(dsn, schema)
    with pytest.raises(ConfigurationError, match="migrate"):
        memory.remember("d", "x", kind="note")
    with pytest.raises(ConfigurationError, match="migrate"):
        memory.recall("d")
    with pytest.raises(ConfigurationError, match="migrate"):
        memory.expire("d", str(uuid.uuid4()))


def test_two_simultaneous_migrations(dsn: str, schema: str):
    results: list[int] = []

    def migrate() -> None:
        results.append(_new(dsn, schema).migrate())

    threads = [threading.Thread(target=migrate) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(results) == [0, len(discover())]


def test_missing_extension_without_privilege_explains_what_to_run(dsn: str):
    suffix = uuid.uuid4().hex[:8]
    role, database = f"ml_no_priv_{suffix}", f"ml_no_vector_{suffix}"
    _execute(dsn, f"CREATE ROLE {role} LOGIN PASSWORD 'secret' NOSUPERUSER")
    _execute(dsn, f"CREATE DATABASE {database} OWNER {role}")
    parts = urlsplit(dsn)
    restricted_dsn = urlunsplit(
        (parts.scheme, f"{role}:secret@{parts.hostname}:{parts.port}", f"/{database}", "", "")
    )
    try:
        with pytest.raises(ConfigurationError, match="CREATE EXTENSION vector"):
            _new(restricted_dsn, "memory_lifecycle").migrate()
    finally:
        _execute(dsn, f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
        _execute(dsn, f"DROP ROLE IF EXISTS {role}")


def test_failure_mid_migration_names_the_file(
    dsn: str, schema: str, monkeypatch: pytest.MonkeyPatch
):
    # Regression (reports/silent-failure-fatia-10.md, finding 7): the error surfaced raw.
    # PT: Regressão (reports/silent-failure-fatia-10.md, achado 7): o erro subia cru.
    from memory_lifecycle import migrations

    broken = migrations.Migration(number=1, name="0001_broken.sql", sha256="x", sql="SELEC 1;")
    monkeypatch.setattr(migrations, "discover", lambda source=None: [broken])
    with pytest.raises(MigrationError, match="0001_broken.sql"):
        _new(dsn, schema).migrate()


def test_migrating_again_without_privilege_to_create_schema(dsn: str):
    # Regression (finding 5): `CREATE SCHEMA IF NOT EXISTS` requires CREATE on the database
    # even when the schema already exists, so migrate() was not idempotent for this user.
    # PT: Regressão (achado 5): `CREATE SCHEMA IF NOT EXISTS` exige CREATE no banco mesmo
    # PT: quando o schema já existe, então migrate() não era idempotente para esse usuário.
    suffix = uuid.uuid4().hex[:8]
    role, database, schema = f"ml_app_{suffix}", f"ml_app_{suffix}", "app_memory"
    _execute(dsn, f"CREATE ROLE {role} LOGIN PASSWORD 'secret' NOSUPERUSER")
    _execute(dsn, f"CREATE DATABASE {database}")
    parts = urlsplit(dsn)
    admin_dsn = urlunsplit((parts.scheme, parts.netloc, f"/{database}", "", ""))
    app_dsn = urlunsplit(
        (parts.scheme, f"{role}:secret@{parts.hostname}:{parts.port}", f"/{database}", "", "")
    )
    try:
        assert _new(admin_dsn, schema).migrate() >= 1
        _execute(
            admin_dsn,
            f"GRANT USAGE, CREATE ON SCHEMA {schema} TO {role}; "
            f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {role}",
        )
        assert _new(app_dsn, schema).migrate() == 0
    finally:
        _execute(dsn, f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
        _execute(dsn, f"DROP ROLE IF EXISTS {role}")


def test_every_foreign_key_has_an_index(dsn: str, schema: str):
    # Regression (reports/sql-perf-escritas.md, critical): without an index on
    # previous_version_id, every row deleted by `forget` scanned the table.
    # PT: Regressão (reports/sql-perf-escritas.md, crítico): sem índice em
    # PT: previous_version_id, cada linha apagada por `forget` varria a tabela.
    _new(dsn, schema).migrate()
    with psycopg.connect(dsn) as connection:
        without_index = connection.execute(
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
    assert without_index == []
