#!/usr/bin/env python3
"""Falha se um arquivo-fonte passa do limite de linhas (CLAUDE.md, 'Tamanho de arquivo').

Força a divisão por assunto (`temporal.py`, `store.py`, `connection/<adaptador>.py`)
em vez de módulos monolíticos. Testes são isentos: crescem por natureza.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_LINES = 300
EXEMPT = ("/tests/", "test_", "conftest.py")


def is_exempt(path: str) -> bool:
    return any(token in path for token in EXEMPT)


def main(paths: list[str]) -> int:
    offenders: list[tuple[str, int]] = []
    for raw in paths:
        if not raw.endswith((".py", ".sql")) or is_exempt(raw):
            continue
        p = Path(raw)
        if not p.is_file():
            continue
        n = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
        if n > MAX_LINES:
            offenders.append((raw, n))

    for path, n in offenders:
        print(
            f"{path}: {n} linhas (> {MAX_LINES}). Divida em módulos menores — CLAUDE.md, Tamanho de arquivo."
        )

    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
