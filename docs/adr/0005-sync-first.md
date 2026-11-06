# ADR 0005 — Síncrono primeiro; assíncrono é uma superfície posterior sobre o mesmo núcleo

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** `CLAUDE.md` § Convenções (a API pública é síncrona primeiro)
- **Módulos afetados:** `api`, `connection`, `embeddings`

## Contexto

Etapa 1, decisão 5. O primeiro consumidor chama a biblioteca de uma requisição
Django síncrona e de comandos de gerenciamento. O psycopg 3 oferece as duas
superfícies; oferecer as duas na 0.1 dobra cada adaptador, cada teste e cada
docstring antes de existir um consumidor para a segunda.

## Decisão

A API pública, o protocolo do provedor de conexão e o protocolo do provedor de
embeddings são **síncronos** na 0.1. As partes puras (`temporal`, `model`) são
escritas de modo que uma superfície assíncrona as reutilize sem mudança; a
superfície assíncrona é o item 5 da Etapa 10.

## Consequências

**Fica mais fácil**
- Uma superfície para especificar, testar e documentar; a conexão do ORM do
  Django cabe como está.

**Fica mais difícil**
- Um app ASGI precisa rodar as chamadas numa thread até a superfície assíncrona
  existir.

## Alternativas consideradas

### Só assíncrono
- **Prós:** uma superfície, moderna.
- **Contras:** o primeiro consumidor embrulharia cada chamada; a conexão do
  Django é síncrona.
- **Rejeitada porque:** não serve a ninguém hoje.

### As duas desde o primeiro dia
- **Prós:** completo.
- **Contras:** o dobro da matriz de adaptadores e testes sem um segundo
  consumidor.
- **Rejeitada porque:** custo sem usuário.

## Revisitar quando

Aparecer um consumidor numa stack assíncrona, ou a superfície síncrona estiver
estável (pós 0.1).
