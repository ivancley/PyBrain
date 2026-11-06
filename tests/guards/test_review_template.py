"""Padrão único de revisão: um template de comentário, lido por todo revisor que publica num PR.

Decisão em `.claude/skills/code-review/comment.md` (`code-review` é dona do formato;
`review` só roteia e consolida). Sem a guarda, cada revisão volta ao próprio
formato, e a seção que some é o ponto que ninguém sabe se foi olhado.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# `.claude/` é gitignored (contexto local do agente): num checkout sem ele, como a
# CI, estas guardas não têm o que varrer e pulam com a razão visível. Rodam onde o
# harness existe, que é toda máquina de desenvolvedor e o `make quality`.
pytestmark = pytest.mark.skipif(
    not (ROOT / ".claude").is_dir(), reason=".claude/ não está neste checkout (gitignored)"
)
CLAUDE = ROOT / ".claude"
TEMPLATE = CLAUDE / "skills" / "code-review" / "comment.md"
REVIEW = CLAUDE / "skills" / "review" / "SKILL.md"

# A definição do template (é a decisão, não uma lista de alvos a varrer).
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

# Uma instrução que comenta no PR algo que não é revisão, com a razão. Caminho
# relativo à raiz → por que não segue o template de revisão.
PUBLISHES_SOMETHING_ELSE: dict[str, str] = {
    ".claude/skills/open-pr/SKILL.md": "publica a opinião de risco de quem abre o PR, no formato de open-pr/references/risk.md, não uma revisão",
}


def _template_block() -> str:
    found = re.search(r"```markdown\n(.*?)\n```", TEMPLATE.read_text(encoding="utf-8"), re.S)
    assert found, f"{TEMPLATE.relative_to(ROOT)} sem o bloco ```markdown do template"
    return found.group(1)


def _agent_instructions() -> list[Path]:
    return sorted([*CLAUDE.glob("skills/*/SKILL.md"), *CLAUDE.glob("agents/*.md")])


def _routed_subagents() -> set[str]:
    lines = [ln for ln in REVIEW.read_text(encoding="utf-8").splitlines() if "(subagente)" in ln]
    return {
        name for ln in lines for name in re.findall(r"\*\*`([a-z0-9-]+)`\*\* \(subagente\)", ln)
    }


def test_a_varredura_alcanca_algo():
    publish = [p for p in _agent_instructions() if PUBLISHES_ON_PR.search(p.read_text("utf-8"))]
    assert len(publish) >= 2, publish
    assert len(_routed_subagents()) >= 3


def test_o_template_tem_toda_secao():
    block = _template_block()
    missing = [s for s in REQUIRED_SECTIONS if s not in block]
    assert not missing, f"seção obrigatória fora do template de revisão: {missing}"


def test_quem_publica_no_pr_segue_o_template():
    """Uma skill ou agente que comenta no PR aponta para o template: um formato, venha de onde vier."""
    loose = [
        str(p.relative_to(ROOT))
        for p in _agent_instructions()
        if p != TEMPLATE
        and str(p.relative_to(ROOT)) not in PUBLISHES_SOMETHING_ELSE
        and PUBLISHES_ON_PR.search(text := p.read_text(encoding="utf-8"))
        and "comment.md" not in text
    ]
    assert not loose, f"publica no PR sem seguir code-review/comment.md: {loose}"


def test_todo_subagente_roteado_existe():
    """Um revisor na tabela de `review` sem arquivo em .claude/agents é cobertura que só existe no texto."""
    missing = sorted(
        n for n in _routed_subagents() if not (CLAUDE / "agents" / f"{n}.md").is_file()
    )
    assert not missing, f"subagente roteado por review sem .claude/agents/<nome>.md: {missing}"


def test_a_excecao_de_publicacao_ainda_vale():
    """Uma exceção cujo arquivo sumiu ou parou de publicar no PR é órfã: apague a linha."""
    orphans = sorted(
        c
        for c in PUBLISHES_SOMETHING_ELSE
        if not (ROOT / c).is_file()
        or not PUBLISHES_ON_PR.search((ROOT / c).read_text(encoding="utf-8"))
    )
    assert not orphans, (
        f"PUBLISHES_SOMETHING_ELSE aponta para o que não publica mais no PR: {orphans}"
    )
    short = [c for c, reason in PUBLISHES_SOMETHING_ELSE.items() if len(reason) < 40]
    assert not short, f"exceção sem razão escrita: {short}"
