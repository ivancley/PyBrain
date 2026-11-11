"""`CLAUDE.md` § Trabalhando com o agente: layered context, never a fat file.

The root is the map and the global rule (up to 200 lines — beyond that the agent reads
conventions it is not touching and adheres less); what belongs to a file type lives in
`.claude/rules/` with `paths:`. A rule without `paths` always loads and is the fat root
under another name; a glob that matches nothing is a dead rule.

Guard contract (`tests/guards/README.md`): the sets come from disk (`rglob`),
exceptions carry a written reason, and an orphan exception fails.

PT: `CLAUDE.md` § Trabalhando com o agente: contexto em camadas, nunca um arquivo gordo.

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

# `.claude/` is gitignored (the agent's local context): in a checkout without it, such as
# CI, these guards have nothing to scan and skip with the reason visible. They run where
# the harness exists, which is every developer machine and `make quality`.
# PT: `.claude/` está no gitignore (contexto local do agente): num checkout sem ela, como
# PT: a CI, estas guardas não têm o que varrer e pulam com a razão visível. Rodam onde o
# PT: harness existe, que é toda máquina de desenvolvedor e o `make quality`.
pytestmark = pytest.mark.skipif(
    not (ROOT / ".claude").is_dir(),
    reason=".claude/ is not in this checkout (it is gitignored)",
)
LINE_LIMIT = 200
RULES = ROOT / ".claude" / "rules"
SKILLS = ROOT / ".claude" / "skills"
AGENTS = ROOT / ".claude" / "agents"

# Globs pointing at code the plan has not created yet, with the stage that creates them.
# As soon as the glob matches a real file, the entry is an orphan and must be deleted.
# PT: Globs que apontam para código que o plano ainda não criou, com a etapa que os cria.
# PT: Assim que o glob casar com um arquivo real, a entrada é órfã e deve ser apagada.
PLANNED_GLOBS: dict[str, str] = {}


def _frontmatter(file: Path) -> str:
    text = file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end > 0 else ""


def _globs(frontmatter: str) -> list[str]:
    block = re.search(r"^paths:\n((?:[ \t]+-[^\n]*\n?)+)", frontmatter, re.M)
    if not block:
        return []
    return [
        line.strip().lstrip("-").strip().strip("\"'")
        for line in block.group(1).splitlines()
        if line.strip()
    ]


def _matches_something(glob: str) -> bool:
    return any(ROOT.glob(glob))


def _dead(globs: list[str]) -> list[str]:
    return [g for g in globs if not _matches_something(g) and g not in PLANNED_GLOBS]


def test_the_scan_reaches_something():
    assert len(list(RULES.glob("*.md"))) >= 3
    assert len(list(SKILLS.glob("*/SKILL.md"))) >= 10
    assert len(list(AGENTS.glob("*.md"))) >= 3


def test_the_root_is_a_map_not_an_encyclopedia():
    lines = len((ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
    assert lines <= LINE_LIMIT, (
        f"the root CLAUDE.md has {lines} lines (limit {LINE_LIMIT}). What belongs to a "
        "file type goes to .claude/rules/; what is a procedure becomes a skill."
    )


def test_every_rule_has_paths_that_match_something():
    problems = []
    for rule in sorted(RULES.glob("*.md")):
        globs = _globs(_frontmatter(rule))
        if not globs:
            problems.append(f"{rule.name}: no `paths:` in the frontmatter (it would always load)")
            continue
        if dead := _dead(globs):
            problems.append(f"{rule.name}: glob that matches no file: {dead}")
    assert not problems, problems


def test_skill_paths_match_something():
    """A skill with `paths:` loads by the touched file; a dead glob is an auto-load that never happens.

    PT: Uma skill com `paths:` carrega pelo arquivo tocado; um glob morto é um auto-load que nunca acontece.
    """
    dead = {}
    for skill in sorted(SKILLS.glob("*/SKILL.md")):
        if bad := _dead(_globs(_frontmatter(skill))):
            dead[skill.parent.name] = bad
    assert not dead, dead


def test_every_skill_and_agent_has_name_and_description():
    """The pointer is the always-loaded text; without a description the skill is never looked up.

    PT: O ponteiro é o texto sempre carregado; sem descrição a skill nunca é buscada.
    """
    missing = []
    for file in [*SKILLS.glob("*/SKILL.md"), *AGENTS.glob("*.md")]:
        fm = _frontmatter(file)
        if not re.search(r"^name:\s*\S", fm, re.M) or not re.search(
            r"^description:\s*\S", fm, re.M
        ):
            missing.append(str(file.relative_to(ROOT)))
    assert not missing, f"frontmatter without name or description: {missing}"


def test_planned_globs_are_still_planned():
    """A planned glob that now matches a file is an orphan exception: delete the entry.

    PT: Um glob planejado que agora casa com um arquivo é exceção órfã: apague a entrada.
    """
    resolved = sorted(g for g in PLANNED_GLOBS if _matches_something(g))
    assert not resolved, f"the code already exists — remove from PLANNED_GLOBS: {resolved}"
    short = [g for g, reason in PLANNED_GLOBS.items() if len(reason) < 30]
    assert not short, f"exception without a written reason: {short}"
    referenced = {
        g
        for f in [*RULES.glob("*.md"), *SKILLS.glob("*/SKILL.md")]
        for g in _globs(_frontmatter(f))
    }
    unused = sorted(set(PLANNED_GLOBS) - referenced)
    assert not unused, f"PLANNED_GLOBS names a glob that no rule or skill uses: {unused}"
