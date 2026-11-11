"""The per-fragment changelog tooling (`scripts/changelog`), against a throwaway git repository.

PT: O ferramental de changelog por fragmento (`scripts/changelog`), contra um repositório git
descartável.
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from scripts.changelog import build as build_mod
from scripts.changelog import bump as bump_mod
from scripts.changelog import core, fragments, untouched

PYPROJECT = 'name = "x"\n[project]\nname = "memory-lifecycle"\nversion = "0.0.0"\n'
CHANGELOG = "# Changelog\n\n## [Não lançado]\n"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "dev")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def _committed_fragment(repo: Path, branch: str, body: str) -> Path:
    path, _ = fragments.create(repo, branch)
    path.write_text(body, encoding="utf-8")
    _git(repo, "add", str(path))
    _git(repo, "commit", "-qm", f"fragment {branch}")
    return path


# ---------- classification ----------
# PT: ---------- classificação ----------


@pytest.mark.parametrize(
    "branch, kind",
    [
        ("feat/recall-as-of", core.DELIVERY),
        ("hotfix/runner-hash", core.DELIVERY),
        ("release/v0.1.0", core.INTEGRATION),
        ("merge/main-into-dev", core.INTEGRATION),
        ("main", core.OFF_CONVENTION),
        ("wip/thing", core.OFF_CONVENTION),
    ],
)
def test_classifies_branch(branch, kind):
    assert core.classify_branch(branch) == kind


def test_branch_slug_never_escapes_the_fragments_directory():
    assert core.branch_slug("feat/../../etc") == "feat-..-..-etc"
    assert "/" not in core.branch_slug("fix/a/b")


# ---------- parsing ----------
# PT: ---------- leitura ----------


def test_parsing_ignores_the_instructions_comment_and_stops_at_a_version_heading():
    text = fragments.template("feat/x").replace(
        "### Adicionado\n-\n", "### Adicionado\n- um\n  continuação\n- dois\n"
    )
    text += "\n## [0.1.0] - 2026-01-01\n### Corrigido\n- antigo\n"
    sections = core.parse_sections(text)
    assert sections["Adicionado"] == ["- um\n  continuação", "- dois"]
    assert sections["Corrigido"] == []


def test_rendering_orders_canonical_first_and_keeps_the_extras():
    rendered = core.render_sections(
        {"Testes": ["- t"], "Corrigido": ["- c"], "Adicionado": ["- a"], "Removido": []}
    )
    assert (
        rendered.index("### Adicionado")
        < rendered.index("### Corrigido")
        < rendered.index("### Testes")
    )
    assert "### Removido" not in rendered


# ---------- check ----------


def test_check_fails_without_fragment_and_with_empty_fragment(repo):
    with pytest.raises(core.ChangelogError, match="ausente"):
        fragments.check(repo, "feat/x")
    fragments.create(repo, "feat/x")
    with pytest.raises(core.ChangelogError, match="vazio"):
        fragments.check(repo, "feat/x")


def test_check_warns_about_non_canonical_section_but_passes(repo):
    path, _ = fragments.create(repo, "feat/x")
    path.write_text("### Testes\n- coberto\n", encoding="utf-8")
    assert fragments.check(repo, "feat/x").startswith("AVISO")


def test_check_passes_integration_and_warns_off_convention(repo):
    assert "integração" in fragments.check(repo, "release/v0.1.0")
    assert fragments.check(repo, "wip").startswith("AVISO")


# ---------- build ----------


def test_build_reads_only_committed_fragments_and_deletes_them(repo):
    _committed_fragment(repo, "feat/a", "### Adicionado\n- a\n")
    loose, _ = fragments.create(repo, "feat/b")
    loose.write_text("### Adicionado\n- b\n", encoding="utf-8")

    message = build_mod.build(repo)

    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "- a" in text and "- b" not in text
    assert not (repo / "changelog/unreleased/feat-a.md").exists()
    assert loose.exists() and "fora do git" in message


def test_build_is_deterministic_and_removes_duplicates(repo):
    _committed_fragment(repo, "feat/a", "### Corrigido\n- mesmo\n")
    _committed_fragment(repo, "feat/b", "### Corrigido\n- mesmo\n- outro\n")
    build_mod.build(repo)
    body = build_mod.unreleased_body((repo / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert body["Corrigido"] == ["- mesmo", "- outro"]


def test_build_rejects_fragments_without_items(repo):
    _committed_fragment(repo, "feat/a", fragments.template("feat/a"))
    with pytest.raises(core.ChangelogError, match="nenhum item"):
        build_mod.build(repo)


# ---------- bump ----------


@pytest.mark.parametrize(
    "kind, expected", [("major", "1.0.0"), ("minor", "0.1.0"), ("patch", "0.0.1")]
)
def test_next_version(kind, expected):
    assert bump_mod.next_version("0.0.0", kind) == expected


def test_version_read_rejects_misleading_first_version_line(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.x]\nversion = "9.9.9"\n[project]\nversion = "0.0.0"\n'
    )
    with pytest.raises(core.ChangelogError, match="primeira"):
        bump_mod.read_version(tmp_path)


def test_bump_closes_unreleased_and_writes_the_version(repo):
    _committed_fragment(repo, "feat/a", "### Adicionado\n- a\n")
    build_mod.build(repo)
    bump_mod.bump(repo, "minor", day=date(2026, 11, 6))
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Não lançado]\n\n## [0.1.0] - 2026-11-06" in text
    assert 'version = "0.1.0"' in (repo / "pyproject.toml").read_text(encoding="utf-8")


def test_bump_rejects_with_pending_fragments_or_empty_unreleased(repo):
    with pytest.raises(core.ChangelogError, match="vazia"):
        bump_mod.bump(repo, "patch")
    _committed_fragment(repo, "feat/a", "### Adicionado\n- a\n")
    with pytest.raises(core.ChangelogError, match="não consolidado"):
        bump_mod.bump(repo, "patch")


# ---------- untouched ----------
# PT: ---------- intactos ----------


def test_violations_only_for_delivery_branches():
    diff = '+version = "0.2.0"\n-version = "0.1.0"\n'
    assert untouched.violations("feat/x", ["CHANGELOG.md"], diff) == [
        "CHANGELOG.md foi editado",
        "a versão em pyproject.toml foi alterada",
    ]
    assert untouched.violations("release/v1", ["CHANGELOG.md"], diff) == []
    assert untouched.violations("feat/x", ["README.md"], "+target-version = 'py311'") == []
