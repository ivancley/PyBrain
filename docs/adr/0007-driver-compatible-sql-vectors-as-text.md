# ADR 0007 — SQL compatível com psycopg2 e psycopg 3; vetores viajam como texto

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regra 6 do `CLAUDE.md`; `.claude/rules/adapters.md`
- **Módulos afetados:** `store`, `retrieval`, `connection`, `embeddings`

## Contexto

Etapa 1, decisão 8. Apps Django ainda rodam em psycopg2 e em psycopg 3; engines
SQLAlchemy embrulham qualquer um dos dois. O auxiliar Python do pgvector registra
um adaptador de tipo na conexão, que a biblioteca não possui e não deve alterar.

## Decisão

Toda instrução usa placeholders `%s` e a fatia do DB-API declarada em
`connection/__init__.py`: `cursor()`, `execute`, `fetchone`, `fetchall`,
`rowcount`, `commit`, `rollback`. Vetores são enviados na sua forma textual e
convertidos no SQL (`%s::vector`), e lidos de volta como texto e interpretados.
A biblioteca nunca chama `register_vector` nem qualquer registro de adaptador.
Embeddings são calculados antes de obter a conexão, para que um provedor lento
nunca segure uma conexão do pool.

## Consequências

**Fica mais fácil**
- Um dialeto SQL; a mesma suíte roda nos dois drivers (paridade entre
  adaptadores, Definição de Pronto 1).
- Nada que a biblioteca faz sobrevive à operação na conexão do app.

**Fica mais difícil**
- A ida e volta de um vetor como texto custa uma interpretação por linha; com
  1536 dimensões e `limite` de 20 é desprezível, e a coluna de embedding não é
  selecionada em `recuperar` a menos que pedida.

## Alternativas consideradas

### Depender do psycopg 3 e do seu adaptador de vetor
- **Prós:** vetores tipados, menos conversões.
- **Contras:** exclui apps em psycopg2; registra um adaptador numa conexão
  alheia.
- **Rejeitada porque:** regra 4 (zero dependências obrigatórias) e regra 6.

### Um query builder ou ORM
- **Prós:** abstração de dialeto.
- **Contras:** uma dependência obrigatória e um segundo modelo de pool ou
  sessão.
- **Rejeitada porque:** regra 4.

## Revisitar quando

O psycopg2 chegar ao fim de vida para os consumidores, ou o pgvector mudar o seu
formato textual.
