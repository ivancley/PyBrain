"""`CLAUDE.md` rule 7 and ADR 0008: a published migration is never edited.

The manifest `src/memory_lifecycle/migrations/applied.txt` keeps the sha256 of each
frozen migration. The guard checks that every listed file exists and has the same
hash; the fix for a published schema is always the next file. The runner does the
same check against the database (`MigrationError`); this is the net without a database.

Guard contract (`tests/guards/README.md`): the set comes from disk; a manifest line
without a file is an orphan exception and fails.

PT: `CLAUDE.md` regra 7 e ADR 0008: uma migração publicada nunca é editada.

O manifesto `src/memory_lifecycle/migrations/applied.txt` guarda o sha256 de cada
migração congelada. A guarda confere que cada arquivo listado existe e tem o mesmo
hash; a correção de um schema publicado é sempre o arquivo seguinte. O executor faz
a mesma conferência contra o banco (`MigrationError`); esta é a rede sem banco.

Contrato das guardas (`tests/guards/README.md`): o conjunto vem do disco; uma linha
do manifesto sem arquivo é exceção órfã e falha.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[2] / "src" / "memory_lifecycle" / "migrations"
MANIFEST = FOLDER / "applied.txt"
LINE = re.compile(r"^(\d{4}) ([0-9a-f]{64})$")


def _manifest() -> dict[int, str]:
    frozen: dict[int, str] = {}
    for text in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not text.strip() or text.startswith("#"):
            continue
        match = LINE.match(text)
        assert match, f"malformed line in the manifest: {text!r}"
        frozen[int(match.group(1))] = match.group(2)
    return frozen


def _files() -> dict[int, Path]:
    return {int(file.name[:4]): file for file in FOLDER.glob("[0-9][0-9][0-9][0-9]_*.sql")}


def test_the_scan_reaches_something():
    assert _manifest(), "the manifest freezes no migration"


def test_every_frozen_migration_keeps_its_hash():
    files = _files()
    edited = []
    for number, sha in _manifest().items():
        file = files.get(number)
        assert file is not None, f"the manifest names {number:04d}, which does not exist (orphan)"
        if hashlib.sha256(file.read_bytes()).hexdigest() != sha:
            edited.append(file.name)
    assert not edited, f"published migration edited: {edited}; create the next one instead"


def test_numbering_without_gaps_or_repeats():
    # Counted in a list: a dict keyed by number collapsed two `0002_*.sql` into one
    # (reports/review-change-core.md, importante 8).
    # PT: Contados numa lista: um dict por número colapsava dois `0002_*.sql` num só
    # PT: (reports/review-change-core.md, importante 8).
    numbers = [int(file.name[:4]) for file in FOLDER.glob("[0-9][0-9][0-9][0-9]_*.sql")]
    repeated = sorted(number for number, times in Counter(numbers).items() if times > 1)
    assert not repeated, f"repeated migration number: {repeated}"
    assert sorted(numbers) == list(range(1, len(numbers) + 1)), sorted(numbers)
