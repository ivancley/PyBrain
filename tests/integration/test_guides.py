"""The code snippets of `docs/conceitos.md` run, in order, and assert what the text says.

PT: Os trechos de código de `docs/conceitos.md` rodam, em ordem, e afirmam o que o texto diz.
"""

from __future__ import annotations

import re
from pathlib import Path

from memory_lifecycle import Memory
from tests.conftest import ManualClock

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "conceitos.md"


def test_the_concepts_guide_snippets_run(memory: Memory, clock: ManualClock):
    snippets = re.findall(r"```python\n(.*?)```", GUIDE.read_text(encoding="utf-8"), re.S)
    assert len(snippets) >= 6
    context: dict[str, object] = {"memory": memory, "clock": clock}
    for number, snippet in enumerate(snippets, start=1):
        exec(compile(snippet, f"conceitos.md, snippet {number}", "exec"), context)


def test_the_integration_guide_snippets_compile():
    guide = GUIDE.with_name("integracao.md").read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)```", guide, re.S)
    assert len(snippets) >= 7
    for number, snippet in enumerate(snippets, start=1):
        compile(snippet, f"integracao.md, snippet {number}", "exec")
