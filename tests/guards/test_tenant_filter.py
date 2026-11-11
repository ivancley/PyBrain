"""`CLAUDE.md` rule 1 and § Conventions: every statement filters `tenant_id` and `owner_id`.

Scans by AST the constants of `store.py` and `retrieval.py` that are statements on the
versions table (`FROM {table}`, `UPDATE {table}`, `INSERT INTO {table}`,
`DELETE FROM {table}`). An `INSERT … VALUES` must write both columns; every other
statement needs the predicate `tenant_id = %s AND owner_id = %s`, with no `OR` next to
it: `(tenant_id = %s OR true)` passed the previous version of this guard
(reports/review-change-core.md, importante 4). Docstrings are prose and stay out.

Guard contract (`tests/guards/README.md`): the set comes from the scan, exceptions
carry a written reason, an orphan exception fails.

PT: `CLAUDE.md` regra 1 e § Convenções: toda instrução filtra `tenant_id` e `owner_id`.

Varre por AST as constantes de `store.py` e `retrieval.py` que são instruções sobre a
tabela de versões (`FROM {table}`, `UPDATE {table}`, `INSERT INTO {table}`,
`DELETE FROM {table}`). Um `INSERT … VALUES` precisa gravar as duas colunas; toda
outra instrução precisa do predicado `tenant_id = %s AND owner_id = %s`, sem `OR`
encostado nele: `(tenant_id = %s OR true)` passava na versão anterior desta guarda
(reports/review-change-core.md, importante 4). Docstrings são prosa e ficam de fora.

Contrato das guardas (`tests/guards/README.md`): o conjunto vem da varredura,
exceções carregam razão escrita, exceção órfã falha.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "memory_lifecycle"
SCANNED = ("store.py", "retrieval.py")
STATEMENT = re.compile(r"\b(FROM|UPDATE|INSERT INTO|DELETE FROM)\s+\{table\}")
VALUES_ONLY = re.compile(r"\bINSERT INTO\s+\{table\}.*\bVALUES\b", re.S)
PREDICATE = re.compile(r"(?<!\bOR )\btenant_id = %s AND owner_id = %s\b(?!\s+OR\b)")
COLUMNS = re.compile(r"\btenant_id,\s*owner_id\b")

# "file:CONSTANT" → why the statement may skip the tenant and owner filter.
# PT: "arquivo:CONSTANTE" → por que a instrução pode não filtrar tenant e dono.
UNFILTERED: dict[str, str] = {}


def _statements() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in SCANNED:
        tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and STATEMENT.search(node.value.value)
            ):
                found[f"{name}:{node.targets[0].id}"] = node.value.value
    return found


def test_the_scan_reaches_something():
    files = {key.split(":")[0] for key in _statements()}
    assert files == set(SCANNED), f"no statement found in {set(SCANNED) - files}"


def test_every_statement_filters_tenant_and_owner():
    missing = []
    for key, sql in _statements().items():
        if key in UNFILTERED:
            continue
        required = COLUMNS if VALUES_ONLY.search(sql) else PREDICATE
        if not required.search(sql):
            missing.append(key)
    assert not missing, f"statement without `tenant_id = %s AND owner_id = %s`: {missing}"


def test_exceptions_are_not_orphans():
    orphans = [key for key in UNFILTERED if key not in _statements()]
    assert not orphans, f"UNFILTERED names statements that no longer exist: {orphans}"
    short = [key for key, reason in UNFILTERED.items() if len(reason) < 30]
    assert not short, f"exception without a written reason: {short}"
