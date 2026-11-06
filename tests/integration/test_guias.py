"""Os trechos de código de `docs/conceitos.md` rodam, em ordem, e afirmam o que o texto diz."""

from __future__ import annotations

import re
from pathlib import Path

from memory_lifecycle import Memoria
from tests.conftest import RelogioManual

GUIA = Path(__file__).resolve().parents[2] / "docs" / "conceitos.md"


def test_os_trechos_do_guia_de_conceitos_rodam(memoria: Memoria, relogio: RelogioManual):
    trechos = re.findall(r"```python\n(.*?)```", GUIA.read_text(encoding="utf-8"), re.S)
    assert len(trechos) >= 6
    contexto: dict[str, object] = {"memoria": memoria, "relogio": relogio}
    for numero, trecho in enumerate(trechos, start=1):
        exec(compile(trecho, f"conceitos.md, trecho {numero}", "exec"), contexto)


def test_os_trechos_do_guia_de_integracao_compilam():
    guia = GUIA.with_name("integracao.md").read_text(encoding="utf-8")
    trechos = re.findall(r"```python\n(.*?)```", guia, re.S)
    assert len(trechos) >= 7
    for numero, trecho in enumerate(trechos, start=1):
        compile(trecho, f"integracao.md, trecho {numero}", "exec")
