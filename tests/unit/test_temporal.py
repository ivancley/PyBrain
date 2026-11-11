"""The pure time rules (ADR 0002), without a database.

PT: As regras puras de tempo (ADR 0002), sem banco.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from memory_lifecycle import ConflictError, InvalidArgumentError, MemoryVersion
from memory_lifecycle.temporal import (
    Moment,
    holds_at,
    require_interval,
    require_text,
    require_timezone,
    require_validity_close,
    resolve_moment,
    resolve_now,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
DAY = timedelta(days=1)


def version(**overrides: object) -> MemoryVersion:
    base = MemoryVersion(
        version_id="v1",
        memory_id="m1",
        tenant_id="t",
        owner_id="d",
        kind="note",
        content="x",
        entity_id=None,
        context_id=None,
        source=None,
        embedding_model="fake",
        valid_from=T0,
        valid_to=None,
        recorded_at=T0,
        superseded_at=None,
        previous_version_id=None,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def test_naive_datetime_is_rejected():
    with pytest.raises(InvalidArgumentError, match="timezone"):
        require_timezone("valid_from", datetime(2026, 1, 1))
    require_timezone("valid_from", None)
    require_timezone("valid_from", T0)


def test_naive_clock_is_rejected():
    with pytest.raises(InvalidArgumentError):
        resolve_now(lambda: datetime(2026, 1, 1))
    assert resolve_now(lambda: T0) == T0
    assert resolve_now(None).tzinfo is not None


@pytest.mark.parametrize("empty", ["", "   ", "\n"])
def test_empty_text_is_rejected(empty: str):
    with pytest.raises(InvalidArgumentError, match="content"):
        require_text("content", empty)


def test_as_of_and_known_at_together_are_rejected():
    with pytest.raises(InvalidArgumentError):
        resolve_moment(T0, T0, T0)


def test_no_instant_is_as_of_now():
    assert resolve_moment(T0, None, None) == Moment("as_of", T0)
    assert resolve_moment(T0, T0 - DAY, None) == Moment("as_of", T0 - DAY)
    assert resolve_moment(T0, None, T0 - DAY) == Moment("known_at", T0 - DAY)


def test_empty_or_inverted_interval_is_rejected():
    with pytest.raises(InvalidArgumentError):
        require_interval(T0, T0)
    with pytest.raises(InvalidArgumentError):
        require_interval(T0, T0 - DAY)
    require_interval(T0, None)
    require_interval(T0, T0 + DAY)


def test_expiring_an_already_expired_current_version_conflicts():
    with pytest.raises(ConflictError, match="remember"):
        require_validity_close(version(valid_to=T0 + DAY), T0 + 2 * DAY)


def test_end_at_or_before_start_is_invalid_argument():
    with pytest.raises(InvalidArgumentError):
        require_validity_close(version(), T0)


def test_validity_intervals_are_half_open():
    v = version(valid_to=T0 + DAY)
    assert holds_at(v, Moment("as_of", T0))
    assert not holds_at(v, Moment("as_of", T0 + DAY))
    assert not holds_at(v, Moment("as_of", T0 - DAY))


def test_as_of_only_reads_the_open_record():
    assert not holds_at(version(superseded_at=T0 + DAY), Moment("as_of", T0))


def test_known_at_reads_the_record_of_the_time_and_the_validity_at_d():
    v = version(recorded_at=T0 + DAY, superseded_at=T0 + 3 * DAY, valid_to=T0 + 2 * DAY)
    # Not recorded yet.
    # PT: Ainda não registrada.
    assert not holds_at(v, Moment("known_at", T0))
    # Recorded and valid.
    # PT: Registrada e válida.
    assert holds_at(v, Moment("known_at", T0 + DAY))
    # Known, but not valid at D.
    # PT: Sabida, mas não válida em D.
    assert not holds_at(v, Moment("known_at", T0 + 2 * DAY))
    # Record already closed.
    # PT: Registro já fechado.
    assert not holds_at(v, Moment("known_at", T0 + 3 * DAY))
