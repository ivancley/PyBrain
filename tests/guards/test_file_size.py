"""`CLAUDE.md` § Tamanho de arquivo: 300 linhas pedem a fronteira; 500 é dívida declarada.

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

# Caminho relativo à raiz → por que pode ficar acima do limite, e até quando.
ABOVE_500: dict[str, str] = {}


def _arquivos_fonte() -> list[Path]:
    arquivos: list[Path] = []
    for pasta in SWEPT:
        arquivos.extend(p for p in (ROOT / pasta).rglob("*") if p.suffix in {".py", ".sql"})
    return sorted(arquivos)


def test_a_varredura_alcanca_algo():
    assert len(_arquivos_fonte()) >= 5


def test_nenhum_arquivo_fonte_acima_do_limite():
    gordos = {
        str(p.relative_to(ROOT)): n
        for p in _arquivos_fonte()
        if str(p.relative_to(ROOT)) not in ABOVE_500
        and (n := len(p.read_text(encoding="utf-8", errors="ignore").splitlines())) > LIMIT
    }
    assert not gordos, (
        f"arquivo acima de {LIMIT} linhas sem dívida declarada em ABOVE_500: {gordos}"
    )


def test_divida_declarada_ainda_existe():
    orfaos = sorted(
        p
        for p in ABOVE_500
        if not (ROOT / p).is_file()
        or len((ROOT / p).read_text(encoding="utf-8", errors="ignore").splitlines()) <= LIMIT
    )
    assert not orfaos, (
        f"ABOVE_500 nomeia um arquivo que sumiu ou já está pequeno — apague a entrada: {orfaos}"
    )
    curtas = [p for p, razao in ABOVE_500.items() if len(razao) < 40]
    assert not curtas, f"dívida sem razão escrita: {curtas}"
