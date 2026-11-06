"""Ferramental de changelog por fragmento.

Existe para que duas entregas simultâneas nunca escrevam na mesma linha do
`CHANGELOG.md` nem na `version` do `pyproject.toml` — a origem dos conflitos que
aparecem quando dois PRs abertos miram `dev` ao mesmo tempo. Cada branch escreve
só o próprio fragmento em `changelog/unreleased/<branch>.md`; a consolidação e o
bump acontecem uma vez, na branch de release.

Uso: `python3 -m scripts.changelog <create|build|bump|check|post-checkout> [...]`.
O fluxo completo está em `changelog/README.md`.
"""
