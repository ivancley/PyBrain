# ADR 0006 — Esquecer é o único delete físico, e apaga toda versão

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regra 3 do `CLAUDE.md`
- **Módulos afetados:** `api`, `store`

## Contexto

Etapa 1, decisões 6 e 7. Versões imutáveis são o histórico; um pedido de
privacidade ("apague o que sabe sobre mim") é o único caso em que o histórico
precisa ir embora, e precisa ir por completo: uma consulta `sabido_em` que ainda
devolve o conteúdo apagado é uma violação, não um recurso de auditoria.

## Decisão

`esquecer(dono_id, *, memoria_id | entidade_id | tudo=True)` apaga **toda
versão** do alvo numa transação e devolve a contagem. Exatamente um seletor é
obrigatório; nenhum é `ErroDeArgumentoInvalido`. Nenhum outro método apaga uma
linha. Toda instrução, inclusive esta, filtra `tenant_id` e `dono_id`;
permissões além disso são da aplicação.

## Consequências

**Fica mais fácil**
- Um só lugar para auditar apagamento; um teste prova que nada sobrevive.
- O resto da biblioteca pode assumir que linhas nunca somem debaixo dela, exceto
  aqui.

**Fica mais difícil**
- Uma memória esquecida só deixa `versao_anterior_id` pendurado dentro do
  conjunto apagado, por construção; uma sucessora nunca fica sem a sua cadeia
  porque a cadeia compartilha o `memoria_id`.

## Alternativas consideradas

### Soft delete (um limite `apagado_em`)
- **Prós:** reversível; mantém a auditoria.
- **Contras:** o conteúdo fica em disco; não é apagamento sob um pedido de
  privacidade.
- **Rejeitada porque:** o requisito é apagar.

### Apagar por contexto também
- **Prós:** simétrico com `invalidar_contexto`.
- **Contras:** o fim de um contexto costuma ser um `encerrar`, não um
  apagamento; fácil de usar errado.
- **Rejeitada para a 0.1:** acrescentar quando um consumidor tiver o caso de
  privacidade para isso.

## Em aberto

- Esquecer por `contexto_id`.
- Se `esquecer` deve ser registrado em log por contagem (nunca por conteúdo)
  para conformidade.

## Revisitar quando

Um consumidor precisar provar o apagamento a um terceiro.
