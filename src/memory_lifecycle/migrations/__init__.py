"""The migration runner: numbered SQL files, applied in order, once each.

Without an ORM, the library owns its schema (ADR 0008). Each ``NNNN_<subject>.sql``
file in this package is rendered with the schema name (validated and quoted) and the
vector dimension, applied and recorded in ``schema_version`` with its sha256. An
advisory lock serializes two simultaneous calls.

PT: O executor de migrações: arquivos SQL numerados, aplicados em ordem, uma vez cada.

Sem ORM, a biblioteca é dona do seu schema (ADR 0008). Cada arquivo
``NNNN_<assunto>.sql`` deste pacote é renderizado com o nome do schema (validado e
citado) e a dimensão do vetor, aplicado e registrado em ``schema_version`` com
o seu sha256. Uma trava consultiva serializa duas chamadas simultâneas.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable

from memory_lifecycle._sql import quote, sqlstate
from memory_lifecycle.connection import Cursor
from memory_lifecycle.exceptions import (
    ConfigurationError,
    EmbeddingDimensionError,
    MigrationError,
)

_FILE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
#: A single lock for every schema: `CREATE EXTENSION` is database-wide too.
#: PT: Uma trava só para todos os schemas: `CREATE EXTENSION` também é do banco inteiro.
_LOCK = "memory_lifecycle:migrate"


@dataclass(frozen=True, slots=True)
class Migration:
    """A migration file read from the package; ``sha256`` is of the raw file.

    PT: Um arquivo de migração lido do pacote; ``sha256`` é do arquivo cru.
    """

    number: int
    name: str
    sha256: str
    sql: str


def discover(source: Traversable | None = None) -> list[Migration]:
    """Read the package's migrations (or ``source``'s) in order; a repeated number is an error.

    PT: Lê as migrações do pacote (ou de ``source``) em ordem; número repetido é erro.
    """
    found: dict[int, Migration] = {}
    folder = source if source is not None else resources.files(__package__)
    for item in folder.iterdir():
        match = _FILE.match(item.name)
        if match is None:
            continue
        sql = item.read_text(encoding="utf-8")
        migration = Migration(
            number=int(match.group(1)),
            name=item.name,
            sha256=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            sql=sql,
        )
        if migration.number in found:
            raise MigrationError(
                f"two migrations numbered {migration.number:04d}: "
                f"{found[migration.number].name} and {migration.name}"
            )
        found[migration.number] = migration
    return [found[number] for number in sorted(found)]


def render(sql: str, schema: str, dimension: int) -> str:
    """Replace ``{schema}`` with the quoted identifier and ``{dimension}`` with the integer.

    PT: Troca ``{schema}`` pelo identificador citado e ``{dimension}`` pelo inteiro.
    """
    return sql.replace("{schema}", f'"{schema}"').replace("{dimension}", str(int(dimension)))


def apply(cur: Cursor, schema: str, dimension: int) -> int:
    """Apply the pending migrations to ``schema`` and return how many were applied.

    ``schema`` arrives already validated. Idempotent: a second call returns 0. Before
    applying anything, checks that every already-applied migration still has the same
    sha256 and exists in the package; afterwards, that the recorded dimension is the
    embedding provider's.

    PT: Aplica as migrações pendentes no ``schema`` e devolve quantas aplicou.

    ``schema`` já chega validado. Idempotente: uma segunda chamada devolve 0.
    Antes de aplicar qualquer coisa, confere que toda migração já aplicada ainda
    tem o mesmo sha256 e existe no pacote; depois, que a dimensão registrada é a
    do provedor de embeddings.
    """
    table = quote(schema, "schema_version")
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (_LOCK,))
    _ensure_extension(cur)
    cur.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,))
    if cur.fetchone() is None:
        cur.execute(f'CREATE SCHEMA "{schema}"')
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS {table} ("
        "number int PRIMARY KEY, name text NOT NULL, sha256 text NOT NULL, "
        "applied_at timestamptz NOT NULL)"
    )
    cur.execute(f"SELECT number, sha256 FROM {table}")
    applied = {int(number): str(sha) for number, sha in cur.fetchall()}
    migrations = discover()
    _check_applied(applied, migrations)
    count = 0
    for migration in migrations:
        if migration.number in applied:
            continue
        try:
            cur.execute(render(migration.sql, schema, dimension))
        except Exception as error:
            raise MigrationError(
                f"migration {migration.name} failed to apply; nothing was stored if the "
                "transaction is rolled back"
            ) from error
        cur.execute(
            f"INSERT INTO {table} (number, name, sha256, applied_at) VALUES (%s, %s, %s, now())",
            (migration.number, migration.name, migration.sha256),
        )
        count += 1
    recorded = read_dimension(cur, schema)
    if recorded != dimension:
        raise EmbeddingDimensionError(
            f"schema {schema!r} was created for {recorded}-dimensional vectors; the embedding "
            f"provider produces {dimension}. Use another schema or the original provider."
        )
    return count


def read_dimension(cur: Cursor, schema: str) -> int:
    """The dimension recorded in the schema; an unmigrated schema is ``ConfigurationError``.

    Queries ``to_regclass`` first, so that a missing schema does not become a database
    error, which would abort the app's transaction in ``PARTICIPATE`` mode.

    PT: A dimensão registrada no schema; schema não migrado é ``ConfigurationError``.

    Consulta ``to_regclass`` antes, para que um schema ausente não vire erro de
    banco, que abortaria a transação do app no modo ``PARTICIPATE``.
    """
    settings = quote(schema, "settings")
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (settings,))
    row = cur.fetchone()
    if row is None or not row[0]:
        raise ConfigurationError(
            f"memory schema {schema!r} was not migrated; call Memory.migrate()"
        )
    cur.execute(f"SELECT value FROM {settings} WHERE key = 'dimension'")
    row = cur.fetchone()
    if row is None:
        raise ConfigurationError(f"schema {schema!r} has no recorded dimension")
    return int(row[0])


def _ensure_extension(cur: Cursor) -> None:
    """Install pgvector if missing, without letting a failure abort the app's transaction.

    Tries ``CREATE EXTENSION`` inside its own savepoint: it works for the superuser, for
    a managed service's admin role and for a trusted extension; when it fails, the
    savepoint is rolled back and the error explains what to run.

    PT: Instala o pgvector se faltar, sem deixar uma falha abortar a transação do app.

    Tenta o ``CREATE EXTENSION`` dentro de um savepoint próprio: funciona para o
    superusuário, para o papel administrativo de um serviço gerenciado e para uma
    extensão confiável; quando falha, o savepoint é desfeito e o erro explica o que
    rodar.
    """
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector'),"
        " EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
    )
    row = cur.fetchone()
    installed, available = row if row else (False, False)
    if installed:
        return
    if not available:
        raise ConfigurationError(
            "the PostgreSQL server does not have pgvector; install the pgvector package on "
            "the server and run `CREATE EXTENSION vector;` in this database"
        )
    cur.execute("SAVEPOINT memory_lifecycle_extension")
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as error:
        cur.execute("ROLLBACK TO SAVEPOINT memory_lifecycle_extension")
        if sqlstate(error) == "42501":
            raise ConfigurationError(
                "the pgvector extension is not installed in this database and this user "
                "cannot install it; run `CREATE EXTENSION vector;` as a superuser and call "
                "migrate() again"
            ) from error
        raise
    cur.execute("RELEASE SAVEPOINT memory_lifecycle_extension")


def _check_applied(applied: dict[int, str], migrations: list[Migration]) -> None:
    in_package = {migration.number: migration for migration in migrations}
    for number, sha in sorted(applied.items()):
        migration = in_package.get(number)
        if migration is None:
            raise MigrationError(
                f"the database has migration {number:04d}, which this library version does "
                "not know; upgrade the library before using this schema"
            )
        if migration.sha256 != sha:
            raise MigrationError(
                f"migration {migration.name} changed after being applied (sha256 {sha[:12]}… in "
                f"the database, {migration.sha256[:12]}… in the package); the fix is a new "
                "file, never editing an applied one (ADR 0008)"
            )
