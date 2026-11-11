"""`CLAUDE.md` § File size: 300 lines ask for the boundary; 500 is declared debt.

The hook (`scripts/hooks/file_size.py`) warns on write; the pre-commit check
(`scripts/check_file_size.py`) fails at 300 on the touched file; this guard is the
last net, over the whole tree, at 500 — the limit that only passes with the debt
written in `ABOVE_500`.

PT: `CLAUDE.md` § Tamanho de arquivo: 300 linhas pedem a fronteira; 500 é dívida declarada.

O hook (`scripts/hooks/file_size.py`) avisa na escrita; a checagem de pre-commit
(`scripts/check_file_size.py`) falha em 300 no arquivo tocado; esta guarda é a
última rede, sobre a árvore inteira, em 500 — o limite que só passa com a dívida
escrita em `ABOVE_500`.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 500
SWEPT = ("src", "scripts")

# Path relative to the root → why it may stay above the limit, and until when.
# PT: Caminho relativo à raiz → por que pode ficar acima do limite, e até quando.
ABOVE_500: dict[str, str] = {}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for folder in SWEPT:
        files.extend(p for p in (ROOT / folder).rglob("*") if p.suffix in {".py", ".sql"})
    return sorted(files)


def test_the_scan_reaches_something():
    assert len(_source_files()) >= 5


def test_no_source_file_above_the_limit():
    oversized = {
        str(p.relative_to(ROOT)): n
        for p in _source_files()
        if str(p.relative_to(ROOT)) not in ABOVE_500
        and (n := len(p.read_text(encoding="utf-8", errors="ignore").splitlines())) > LIMIT
    }
    assert not oversized, (
        f"file above {LIMIT} lines without debt declared in ABOVE_500: {oversized}"
    )


def test_declared_debt_still_exists():
    orphans = sorted(
        p
        for p in ABOVE_500
        if not (ROOT / p).is_file()
        or len((ROOT / p).read_text(encoding="utf-8", errors="ignore").splitlines()) <= LIMIT
    )
    assert not orphans, (
        f"ABOVE_500 names a file that is gone or already small — delete the entry: {orphans}"
    )
    short = [p for p, reason in ABOVE_500.items() if len(reason) < 40]
    assert not short, f"debt without a written reason: {short}"
