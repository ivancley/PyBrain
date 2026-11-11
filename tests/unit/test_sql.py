"""``_sql``: identifiers, vectors as text and error translation for both drivers.

PT: ``_sql``: identificadores, vetores como texto e tradução de erros dos dois drivers.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import ConfigurationError, ConflictError, EmbeddingDimensionError
from memory_lifecycle._sql import (
    is_uuid,
    quote,
    sqlstate,
    translate,
    validate_schema,
    vector_as_text,
)


class Psycopg3Error(Exception):
    def __init__(self, code: str, message: str = "error") -> None:
        super().__init__(message)
        self.sqlstate = code


class Psycopg2Error(Exception):
    def __init__(self, code: str, message: str = "error") -> None:
        super().__init__(message)
        self.pgcode = code


@pytest.mark.parametrize("name", ["x; drop table y", "Uppercase", "1starts", "", "a" * 64, 'a"b'])
def test_invalid_schema_is_rejected(name: str):
    with pytest.raises(ConfigurationError):
        validate_schema(name)


def test_quote_qualifies_and_quotes():
    assert quote("memory_lifecycle", "memory_versions") == '"memory_lifecycle"."memory_versions"'


def test_vector_goes_as_text_without_losing_precision():
    values = [0.1, -1 / 3, 1e-300, 123456.789]
    text = vector_as_text(values)
    assert text.startswith("[") and text.endswith("]")
    assert [float(part) for part in text[1:-1].split(",")] == values


def test_sqlstate_of_both_drivers():
    assert sqlstate(Psycopg3Error("23505")) == "23505"
    assert sqlstate(Psycopg2Error("42P01")) == "42P01"
    assert sqlstate(ValueError("no code")) is None


def test_known_translations():
    # Regression (reports/review-change-core.md): REPEATABLE READ raised a raw 40001.
    # PT: Regressão (reports/review-change-core.md): REPEATABLE READ subia 40001 cru.
    assert isinstance(translate(Psycopg3Error("40001")), ConflictError)
    assert isinstance(translate(Psycopg2Error("40P01")), ConflictError)
    assert isinstance(translate(Psycopg2Error("42P01")), ConfigurationError)
    assert isinstance(translate(Psycopg3Error("3F000")), ConfigurationError)
    dimension = Psycopg3Error("22000", "expected 8 dimensions, not 16")
    assert isinstance(translate(dimension), EmbeddingDimensionError)


def test_error_without_known_consequence_is_not_translated():
    assert translate(Psycopg3Error("22000", "another problem")) is None
    # Query canceled: propagates as it came.
    # PT: Consulta cancelada: sobe como veio.
    assert translate(Psycopg3Error("57014")) is None
    assert translate(RuntimeError("not a database error")) is None


def test_is_uuid():
    assert is_uuid("00000000-0000-0000-0000-000000000000")
    assert not is_uuid("never-existed")
    assert not is_uuid("")


@pytest.mark.parametrize(
    "text",
    [
        "urn:uuid:00000000-0000-0000-0000-000000000000",
        "{00000000-0000-0000-0000-000000000000}",
        "0000-0000-0000-0000-0000-0000-0000-0000",
        "00000000000000000000000000000000",
    ],
)
def test_is_uuid_rejects_what_postgres_would_reject_or_is_not_canonical(text: str):
    # Regression (reports/silent-failure-fatia-10.md, finding 1): Python's uuid.UUID
    # accepted forms that Postgres's `::uuid` rejects, aborting the app's transaction.
    # PT: Regressão (reports/silent-failure-fatia-10.md, achado 1): o uuid.UUID do Python
    # PT: aceitava formas que o `::uuid` do Postgres rejeita, abortando a transação do app.
    assert not is_uuid(text)


class Diag:
    def __init__(self, constraint: str | None) -> None:
        self.constraint_name = constraint


def test_unique_violation_only_becomes_conflict_on_the_current_version_index():
    # Regression (finding 8): every 23505 became "another write stored this version first".
    # PT: Regressão (achado 8): todo 23505 virava "outra escrita gravou esta versão primeiro".
    from_current = Psycopg3Error("23505")
    from_current.diag = Diag("ux_versions_current")  # type: ignore[attr-defined]
    other = Psycopg3Error("23505")
    other.diag = Diag("schema_version_pkey")  # type: ignore[attr-defined]
    assert isinstance(translate(from_current), ConflictError)
    assert translate(other) is None
