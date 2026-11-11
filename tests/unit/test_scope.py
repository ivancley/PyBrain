"""Building the strict scope of ``recall`` (ADR 0003).

PT: A montagem do escopo estrito de ``recall`` (ADR 0003).
"""

from __future__ import annotations

import pytest

from memory_lifecycle import InvalidArgumentError
from memory_lifecycle.retrieval import ScopeAxis, build_axis


def test_none_does_not_filter():
    assert build_axis(None) is None


def test_empty_list_returns_nothing():
    assert build_axis([]) == ScopeAxis(ids=(), include_null=False)


def test_none_as_member_includes_those_without_id():
    assert build_axis(["p-2027", None]) == ScopeAxis(ids=("p-2027",), include_null=True)
    assert build_axis([None]) == ScopeAxis(ids=(), include_null=True)


def test_bare_string_is_rejected():
    with pytest.raises(InvalidArgumentError, match="list"):
        build_axis("p-2027")  # type: ignore[arg-type]
