#!/usr/bin/env python3
"""Reprova se existe uma revisão em `reports/` que o índice em `.claude/review.md` não cita.

`reports/` está no `.gitignore` de propósito: os relatórios citam dados reais e
instruções reais. O efeito colateral é que **a revisão só existe na máquina de
quem a rodou**: outro checkout não tem nenhuma delas.

Então o índice não é um ponteiro, é o registro. Se o arquivo some com a máquina,
a linha do índice é tudo o que resta — e ela precisa carregar a conclusão.

O arquivo esquecido é exatamente o que NÃO está no commit, então filtrar por
arquivo tocado nunca o veria: esta verificação sempre roda sobre a pasta inteira.
"""

from __future__ import annotations

import sys
from pathlib import Path

INDICE = Path(".claude/review.md")
RELATORIOS = Path("reports")

#: O título da seção de `.claude/review.md` em que cada revisão ganha sua linha.
SECAO_INDICE = "## 3. Índice"


def main() -> int:
    if not INDICE.exists() or not RELATORIOS.is_dir():
        return 0

    texto = INDICE.read_text(encoding="utf-8")
    faltando = [p.name for p in sorted(RELATORIOS.glob("*.md")) if p.name not in texto]
    if not faltando:
        return 0

    print(f"Revisão em reports/ que {INDICE} não registra:")
    for nome in faltando:
        print(f"  {nome}")
    print(
        f"\nAcrescente uma linha à seção `{SECAO_INDICE}` com a CONCLUSÃO, não só o caminho:"
        "\nreports/ é gitignored, então o arquivo não sobrevive à máquina."
        "\nSe o achado pertence a uma classe já listada na seção 1, acrescente a"
        "\nocorrência lá — a contagem é o que justifica uma guarda."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
