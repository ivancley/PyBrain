# ADR 0001 — Modelo de memória: ids opacos, versões imutáveis, status derivado

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regras 1, 2 e 3 do `CLAUDE.md`; Definição de Pronto 1
- **Módulos afetados:** `model`, `api`, `store`, `retrieval`, `migrations`

## Contexto

Etapa 1, decisão 1 de `.data/planejamento-macro.md`. O primeiro consumidor é uma
aplicação com usuários, agentes, pessoas sobre quem eles falam e períodos aos
quais esses fatos pertencem. A biblioteca precisa servi-la sem aprender nenhuma
dessas palavras, e precisa responder "o que era verdade" e "no que acreditávamos"
meses depois sem uma migração reescrevendo o histórico.

## Decisão

Uma memória é um `memoria_id` estável com uma ou mais **versões imutáveis**. Toda
versão carrega: `tenant_id` e `dono_id` (filtros obrigatórios); `entidade_id` e
`contexto_id` (opacos, opcionais); `categoria`, `conteudo`, `origem` (texto livre
do app); `embedding` e `modelo_embedding`; o eixo de validade (`valido_de`,
`valido_ate`); o eixo de registro (`registrado_em`, `substituido_em`); e
`versao_anterior_id`. **O status é derivado** por uma única função a partir dos
limites e da sucessora, nunca armazenado. Nada numa linha muda depois de
escrita, salvo fechar `substituido_em`: até o fim da validade é registrado como
uma versão nova (a cópia limitada do ADR 0002), para que "o que sabíamos" nunca
seja reescrito.

Obrigatórios em `lembrar`: `dono_id`, `conteudo`, `categoria`. Opcionais:
`entidade_id`, `contexto_id`, `origem`, `valido_de` (padrão agora), `valido_ate`
(padrão aberto).

## Consequências

**Fica mais fácil**
- Qualquer pergunta sobre o passado é um predicado sobre limites; sem tabela de
  auditoria.
- O agnosticismo de domínio é estrutural: não há coluna para os substantivos do app.
- Um status derivado não pode divergir dos limites que o definem.

**Fica mais difícil**
- A tabela de versões só cresce; `esquecer` é o único jeito de encolhê-la.
- Rotular uma versão histórica (`substituída` vs `corrigida`) exige a sua sucessora.

## Alternativas consideradas

### Linhas mutáveis mais uma tabela de auditoria
- **Prós:** familiar; a tabela principal fica pequena.
- **Contras:** a tabela de auditoria é um segundo modelo a manter em sincronia;
  consultas "como em" juntam dois formatos; um bug na sincronia perde histórico
  em silêncio.
- **Rejeitada porque:** o ciclo de vida é o produto, não um efeito colateral.

### Coluna de status armazenada
- **Prós:** barata de filtrar.
- **Contras:** uma segunda fonte de verdade; "encerrada" vira um job que vira
  flags em vez de um limite que sempre esteve lá.
- **Rejeitada porque:** a regra 2 diz que o status é derivado; um índice parcial
  sobre limites abertos dá o mesmo filtro barato.

### JSON de metadados livre em toda versão
- **Prós:** apps anexam qualquer coisa.
- **Contras:** convida o domínio do app a entrar pela porta dos fundos; filtros
  sem tipo.
- **Rejeitada para a 0.1:** `categoria` e `origem` cobrem as necessidades
  conhecidas. Revisitar sob demanda.

## Em aberto

- `categoria` é obrigatória e texto livre; o app decide o catálogo (confirmado
  pelo dono em 2026-11-06). Um catálogo por tenant só se dois consumidores pedirem.
- JSON de metadados, se dois consumidores pedirem.

## Revisitar quando

Um consumidor precisar de um campo que não é um destes e não pode ser expresso
como uma memória separada.
