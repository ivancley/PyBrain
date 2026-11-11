"""The status table of ADRs 0001/0002, as executable examples of ``derive_status``.

PT: A tabela de status dos ADR 0001/0002, como exemplos executáveis de ``derive_status``.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from memory_lifecycle import MemoryVersion, Status, derive_status

T0 = datetime(2026, 1, 1, tzinfo=UTC)
NOW = T0 + timedelta(days=200)


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


def test_open_bounds_are_active():
    assert derive_status(version(), now=NOW) is Status.ACTIVE


def test_valid_to_closed_in_the_past_is_expired():
    closed = version(valid_to=T0 + timedelta(days=10))
    assert derive_status(closed, now=NOW) is Status.EXPIRED


def test_valid_to_closed_in_the_future_is_still_active():
    closed = version(valid_to=NOW + timedelta(days=1))
    assert derive_status(closed, now=NOW) is Status.ACTIVE


def test_open_record_with_a_later_new_fact_is_superseded():
    copy = version(valid_to=T0 + timedelta(days=150))
    new = version(version_id="v2", valid_from=T0 + timedelta(days=150), previous_version_id="v1")
    assert derive_status(copy, now=NOW, successor=new) is Status.SUPERSEDED


def test_closed_record_and_successor_with_same_bounds_is_corrected():
    wrong = version(superseded_at=T0 + timedelta(days=150))
    right = version(version_id="v2", content="y", previous_version_id="v1")
    assert derive_status(wrong, now=NOW, successor=right) is Status.CORRECTED


def test_closed_record_and_successor_that_changes_validity_is_superseded():
    original = version(superseded_at=T0 + timedelta(days=150))
    copy = version(version_id="v2", valid_to=T0 + timedelta(days=150), previous_version_id="v1")
    assert derive_status(original, now=NOW, successor=copy) is Status.SUPERSEDED


def test_closed_record_without_known_successor_is_superseded():
    old = version(superseded_at=T0 + timedelta(days=150))
    assert derive_status(old, now=NOW) is Status.SUPERSEDED
