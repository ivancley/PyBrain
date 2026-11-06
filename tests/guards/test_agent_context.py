"""`CLAUDE.md` § Trabalhando com o agente: contexto em camadas, nunca um arquivo gordo.

A raiz é o mapa e a regra global (até 200 linhas — acima disso o agente lê
convenções que não está tocando e adere menos); o que pertence a um tipo de
arquivo mora em `.claude/rules/` com `paths:`. Uma regra sem `paths` carrega
sempre e é a raiz gorda com outro nome; um glob que não casa com nada é uma
regra morta.

Contrato das guardas (`tests/guards/README.md`): os conjuntos vêm do disco
(`rglob`), exceções carregam razão escrita, e uma exceção órfã falha.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# `.claude/` está no gitignore (contexto local do agente): num checkout sem ela, como
# a CI, estas guardas não têm o que varrer e pulam com a razão visível. Rodam onde o
# harness existe, que é toda máquina de desenvolvedor e o `make quality`.
pytestmark = pytest.mark.skipif(
    not (ROOT / ".claude").is_dir(),
    reason=".claude/ não está neste checkout (está no gitignore)",
)
LINE_LIMIT = 200
RULES = ROOT / ".claude" / "rules"
SKILLS = ROOT / ".claude" / "skills"
AGENTS = ROOT / ".claude" / "agents"

# Globs que apontam para código que o plano ainda não criou, com a etapa que os cria.
# Assim que o glob casar com um arquivo real, a entrada é órfã e deve ser apagada.
PLANNED_GLOBS: dict[str, str] = {}


def _frontmatter(arquivo: Path) -> str:
    texto = arquivo.read_text(encoding="utf-8")
    if not texto.startswith("---\n"):
        return ""
    fim = texto.find("\n---", 4)
    return texto[4:fim] if fim > 0 else ""


def _globs(frontmatter: str) -> list[str]:
    bloco = re.search(r"^paths:\n((?:[ \t]+-[^\n]*\n?)+)", frontmatter, re.M)
    if not bloco:
        return []
    return [
        linha.strip().lstrip("-").strip().strip("\"'")
        for linha in bloco.group(1).splitlines()
        if linha.strip()
    ]


def _casa_com_algo(glob: str) -> bool:
    return any(ROOT.glob(glob))


def _mortos(globs: list[str]) -> list[str]:
    return [g for g in globs if not _casa_com_algo(g) and g not in PLANNED_GLOBS]


def test_a_varredura_alcanca_algo():
    assert len(list(RULES.glob("*.md"))) >= 3
    assert len(list(SKILLS.glob("*/SKILL.md"))) >= 10
    assert len(list(AGENTS.glob("*.md"))) >= 3


def test_a_raiz_e_um_mapa_nao_uma_enciclopedia():
    linhas = len((ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
    assert linhas <= LINE_LIMIT, (
        f"o CLAUDE.md da raiz tem {linhas} linhas (limite {LINE_LIMIT}). O que pertence a um "
        "tipo de arquivo vai para .claude/rules/; o que é procedimento vira skill."
    )


def test_toda_regra_tem_paths_que_casam_com_algo():
    problemas = []
    for regra in sorted(RULES.glob("*.md")):
        globs = _globs(_frontmatter(regra))
        if not globs:
            problemas.append(f"{regra.name}: sem `paths:` no frontmatter (carregaria sempre)")
            continue
        if mortos := _mortos(globs):
            problemas.append(f"{regra.name}: glob que não casa com nenhum arquivo: {mortos}")
    assert not problemas, problemas


def test_paths_de_skill_casam_com_algo():
    """Uma skill com `paths:` carrega pelo arquivo tocado; um glob morto é um auto-load que nunca acontece."""
    mortos = {}
    for skill in sorted(SKILLS.glob("*/SKILL.md")):
        if ruins := _mortos(_globs(_frontmatter(skill))):
            mortos[skill.parent.name] = ruins
    assert not mortos, mortos


def test_toda_skill_e_agente_tem_nome_e_descricao():
    """O ponteiro é o texto sempre carregado; sem descrição a skill nunca é buscada."""
    faltando = []
    for arquivo in [*SKILLS.glob("*/SKILL.md"), *AGENTS.glob("*.md")]:
        fm = _frontmatter(arquivo)
        if not re.search(r"^name:\s*\S", fm, re.M) or not re.search(
            r"^description:\s*\S", fm, re.M
        ):
            faltando.append(str(arquivo.relative_to(ROOT)))
    assert not faltando, f"frontmatter sem name ou description: {faltando}"


def test_globs_planejados_continuam_planejados():
    """Um glob planejado que agora casa com um arquivo é exceção órfã: apague a entrada."""
    resolvidos = sorted(g for g in PLANNED_GLOBS if _casa_com_algo(g))
    assert not resolvidos, f"o código já existe — remova de PLANNED_GLOBS: {resolvidos}"
    curtas = [g for g, razao in PLANNED_GLOBS.items() if len(razao) < 30]
    assert not curtas, f"exceção sem razão escrita: {curtas}"
    referenciados = {
        g
        for f in [*RULES.glob("*.md"), *SKILLS.glob("*/SKILL.md")]
        for g in _globs(_frontmatter(f))
    }
    sem_uso = sorted(set(PLANNED_GLOBS) - referenciados)
    assert not sem_uso, f"PLANNED_GLOBS nomeia um glob que nenhuma regra ou skill usa: {sem_uso}"
