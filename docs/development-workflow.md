# Fluxo de desenvolvimento com o agente

Como uma funcionalidade sai da ideia e chega à `main` neste repositório, e o que
precisa estar instalado na sua máquina para isso funcionar. O agente é o Claude
Code; tudo o que ele usa aqui vive em `.claude/`, que é gitignored (local a cada
máquina, como `.data/`); o `CLAUDE.md` da raiz é o ponto de entrada versionado.

## O caminho

| passo | o que usar | o que sai |
|---|---|---|
| 1. Refinar a ideia | skill `grill-me` | `openspec/changes/<slug>/refinement.md` |
| 2. Especificar e fatiar | skill `software-factory` (4 etapas, aprovação em cada uma) sobre o OpenSpec | `proposal.md`, `specs/`, `design.md`, `program-design.md`, `tasks.md` |
| 3. Construir, fatia a fatia | `openspec-apply-change` retoma de onde parou | código + testes + migração |
| 4. Fechar cada fatia | `make quality` contra um Postgres real (`make db-up`) | gate verde + cenários de aceitação |
| 5. Abrir o PR | skills `pr-description` e `open-pr` | descrição no template, parecer de risco, checks acompanhados |
| 6. Revisar a mudança | skill `review` | relatório no template único (`code-review/comment.md`), no PR quando pedido, + uma linha em `.claude/review.md` |
| 7. Promover a spec | `openspec-archive-change` | `openspec/specs/` atualizado |

Um ajuste trivial (texto, renomeação, configuração de uma linha) não passa por
isso: faça, rode `make quality` e revise com `code-review`.

## O que carrega sozinho

- **Regras por tipo de arquivo** (`.claude/rules/`): testes, migrações, adaptadores.
  Carregam quando o agente toca um arquivo daquele tipo.
- **Skills de padrão** (`bitemporal-model`, `postgres-patterns`, `pytest-patterns`):
  a mesma coisa, por caminho.
- **Hook de tamanho de arquivo**: avisa na escrita quando um arquivo passa de 300
  linhas, bloqueia em 500.

## Revisão

`review` escolhe os revisores pelo que o diff tocou:

- `code-review`, sempre;
- agente `temporal-semantics` quando `temporal.py`, `model.py`, `store.py`,
  `retrieval.py`, uma migração ou uma spec muda — verifica os dois eixos, as três
  operações e os três modos de consulta, e roda os cenários de aceitação;
- agente `sql-performance` quando uma instrução ou um índice muda — `EXPLAIN` com
  volume;
- agente `silent-failure` quando `except`, retry, fallback ou um adaptador muda.

Toda revisão sai no mesmo template (`.claude/skills/code-review/comment.md`):
veredito, estratégia, processo, bloqueadores, importantes, sugestões, pontos
fortes, plano de ação e cobertura. Só entra achado verificado na linha (confiança
≥ 80), com link permanente por SHA. No PR, só quando o dono do projeto pede. A
guarda `test_review_template` impõe o template e quem publica.

Um revisor que precisava rodar e não rodou (Postgres fora, DSN não definido)
aparece no relatório como "não rodou: falta X", nunca em silêncio.

## Melhorar o ambiente e trocar de sessão

- **`/retro`**: lê o log de uma sessão e propõe uma guarda, regra, skill ou
  permissão. Sob demanda, de preferência na sessão que deu errado; você escolhe
  o que entra.
- **`/handoff`**: passa o trabalho para outra sessão. Numa mudança OpenSpec, vai
  em `status.md`.
- **`writing-for-agents`**: carrega sozinha ao editar uma skill, regra, agente ou
  `CLAUDE.md`.

## Antes de fazer commit

`make quality`: ruff, format, guardas e a suíte. Nada entra em vermelho. O
pre-commit ainda impõe o tamanho de arquivo e o índice de `.claude/review.md`; o
`post-checkout` cria o fragmento de changelog da branch.

## Preparação, uma vez por máquina

```bash
pipx install pre-commit uv
make install      # .venv com o grupo dev
make hooks        # git hooks
make db-up        # Postgres + pgvector na porta 5433
cp .env.example .env
npm install -g @fission-ai/openspec   # a CLI do OpenSpec, se `openspec --version` falhar
```
