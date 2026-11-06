# ADR 0008 — Migrações SQL que só acrescentam, com tabela de versão do schema

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regra 7 do `CLAUDE.md`; `.claude/rules/migrations.md`; Definição de Pronto 4
- **Módulos afetados:** `migrations`, `api.migrar`

## Contexto

Sem ORM, a biblioteca é dona do seu schema. Ele vive num schema PostgreSQL
próprio dentro do banco do app, então a ferramenta de migração do app não o vê,
e duas versões da biblioteca podem encontrar o mesmo banco ao longo do tempo.

## Decisão

Arquivos SQL numerados (`NNNN_<subject>.sql`) aplicados em ordem por um executor
que registra o hash de cada arquivo numa tabela de versão dentro do schema da
biblioteca. `Memoria.migrar()` cria o schema se faltar, aplica os arquivos
pendentes e devolve quantos. Aplicar duas vezes não aplica nada. Um arquivo
aplicado cujo hash mudou, ou dois arquivos com o mesmo número, é
`ErroDeMigracao`. A dimensão da coluna de vetor é fixada na primeira migração a
partir de `embeddings.dimensao` e registrada; outra dimensão depois é
`ErroDeDimensaoDeEmbedding`.

## Consequências

**Fica mais fácil**
- O histórico do schema é legível como arquivos; uma correção é visivelmente o
  próximo arquivo.
- A idempotência é testável: aplicar do zero duas vezes, comparar.

**Fica mais difícil**
- Mudar a dimensão do vetor significa um schema novo; não há caminho no lugar.

## Alternativas consideradas

### `CREATE IF NOT EXISTS` no código, sem tabela de versão
- **Prós:** sem executor.
- **Contras:** sem jeito de evoluir uma coluna; divergência silenciosa entre
  versões da biblioteca.
- **Rejeitada porque:** a 0.2 vai precisar de uma mudança e a tabela precisa
  conhecer o seu formato.

### Delegar à ferramenta de migração do app (Django, Alembic)
- **Prós:** uma ferramenta por app.
- **Contras:** amarra o núcleo a um framework; duas ferramentas para suportar.
- **Rejeitada porque:** regra 4. Um adaptador pode expor o SQL a essas
  ferramentas depois.

## Em aberto

- Um ponto de entrada de CLI para `migrar` fora de uma aplicação.
- Várias dimensões de embedding num banco (um schema por provedor de
  embeddings?).

## Revisitar quando

Um consumidor precisar de dois provedores de embeddings contra um banco.
