"""Single review standard: one comment template, read by every reviewer that publishes on a PR.

Decision in `.claude/skills/code-review/comment.md` (`code-review` owns the format;
`review` only routes and consolidates). Without the guard, each review drifts back to
its own format, and the section that disappears is the point nobody knows was checked.

PT: Padrão único de revisão: um template de comentário, lido por todo revisor que publica num PR.

Decisão em `.claude/skills/code-review/comment.md` (`code-review` é dona do formato;
`review` só roteia e consolida). Sem a guarda, cada revisão volta ao próprio
formato, e a seção que some é o ponto que ninguém sabe se foi olhado.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# `.claude/` is gitignored (the agent's local context): in a checkout without it, such as
# CI, these guards have nothing to scan and skip with the reason visible. They run where
# the harness exists, which is every developer machine and `make quality`.
# PT: `.claude/` é gitignored (contexto local do agente): num checkout sem ele, como a
# PT: CI, estas guardas não têm o que varrer e pulam com a razão visível. Rodam onde o
# PT: harness existe, que é toda máquina de desenvolvedor e o `make quality`.
pytestmark = pytest.mark.skipif(
    not (ROOT / ".claude").is_dir(), reason=".claude/ is not in this checkout (gitignored)"
)
CLAUDE = ROOT / ".claude"
TEMPLATE = CLAUDE / "skills" / "code-review" / "comment.md"
REVIEW = CLAUDE / "skills" / "review" / "SKILL.md"

# The template's definition (it is the decision, not a list of targets to scan).
# PT: A definição do template (é a decisão, não uma lista de alvos a varrer).
REQUIRED_SECTIONS = (
    "**Veredito:**",
    "**Estratégia.**",
    "**Processo.**",
    "#### Bloqueadores",
    "#### Importante",
    "#### Sugestões",
    "#### Pontos fortes",
    "#### Plano de ação",
    "**Cobertura.**",
)
PUBLISHES_ON_PR = re.compile(r"gh pr comment|pulls/<n>/comments|pulls/<n>/reviews")

# An instruction that comments on the PR something that is not a review, with the reason.
# Path relative to the root → why it does not follow the review template.
# PT: Uma instrução que comenta no PR algo que não é revisão, com a razão. Caminho
# PT: relativo à raiz → por que não segue o template de revisão.
PUBLISHES_SOMETHING_ELSE: dict[str, str] = {
    ".claude/skills/open-pr/SKILL.md": "publishes the risk opinion of whoever opens the PR, in the open-pr/references/risk.md format, not a review",
}


def _template_block() -> str:
    found = re.search(r"```markdown\n(.*?)\n```", TEMPLATE.read_text(encoding="utf-8"), re.S)
    assert found, f"{TEMPLATE.relative_to(ROOT)} lacks the template's ```markdown block"
    return found.group(1)


def _agent_instructions() -> list[Path]:
    return sorted([*CLAUDE.glob("skills/*/SKILL.md"), *CLAUDE.glob("agents/*.md")])


def _routed_subagents() -> set[str]:
    lines = [ln for ln in REVIEW.read_text(encoding="utf-8").splitlines() if "(subagente)" in ln]
    return {
        name for ln in lines for name in re.findall(r"\*\*`([a-z0-9-]+)`\*\* \(subagente\)", ln)
    }


def test_the_scan_reaches_something():
    publish = [p for p in _agent_instructions() if PUBLISHES_ON_PR.search(p.read_text("utf-8"))]
    assert len(publish) >= 2, publish
    assert len(_routed_subagents()) >= 3


def test_the_template_has_every_section():
    block = _template_block()
    missing = [s for s in REQUIRED_SECTIONS if s not in block]
    assert not missing, f"required section missing from the review template: {missing}"


def test_whoever_publishes_on_the_pr_follows_the_template():
    """A skill or agent that comments on the PR points to the template: one format, wherever it comes from.

    PT: Uma skill ou agente que comenta no PR aponta para o template: um formato, venha de onde vier.
    """
    loose = [
        str(p.relative_to(ROOT))
        for p in _agent_instructions()
        if p != TEMPLATE
        and str(p.relative_to(ROOT)) not in PUBLISHES_SOMETHING_ELSE
        and PUBLISHES_ON_PR.search(text := p.read_text(encoding="utf-8"))
        and "comment.md" not in text
    ]
    assert not loose, f"publishes on the PR without following code-review/comment.md: {loose}"


def test_every_routed_subagent_exists():
    """A reviewer in the `review` table without a file in .claude/agents is coverage that only exists in the text.

    PT: Um revisor na tabela de `review` sem arquivo em .claude/agents é cobertura que só existe no texto.
    """
    missing = sorted(
        n for n in _routed_subagents() if not (CLAUDE / "agents" / f"{n}.md").is_file()
    )
    assert not missing, f"subagent routed by review without .claude/agents/<name>.md: {missing}"


def test_the_publishing_exception_still_holds():
    """An exception whose file is gone or stopped publishing on the PR is an orphan: delete the line.

    PT: Uma exceção cujo arquivo sumiu ou parou de publicar no PR é órfã: apague a linha.
    """
    orphans = sorted(
        c
        for c in PUBLISHES_SOMETHING_ELSE
        if not (ROOT / c).is_file()
        or not PUBLISHES_ON_PR.search((ROOT / c).read_text(encoding="utf-8"))
    )
    assert not orphans, (
        f"PUBLISHES_SOMETHING_ELSE points to something that no longer publishes on the PR: {orphans}"
    )
    short = [c for c, reason in PUBLISHES_SOMETHING_ELSE.items() if len(reason) < 40]
    assert not short, f"exception without a written reason: {short}"
