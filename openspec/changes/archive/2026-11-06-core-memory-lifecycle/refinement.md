# Refinamento: ciclo de vida central da memória

Fonte: `.data/inicio.txt` (2026-10-29), `.data/planejamento-macro.md` (2026-11-06),
`CLAUDE.md`, `docs/glossario.md`. A primeira rodada da entrevista não pôde correr
ao vivo (sessão autônoma): cada eixo tomou a recomendação que os documentos
apontavam, com o porquê. Em 2026-11-06 a entrevista foi retomada com o dono e
concluída: toda decisão abaixo está **confirmada pelo dono**, e não resta pergunta
que bloqueie a Etapa 1.

## Decisões
- Problema: uma aplicação quer que o seu agente saiba, por dono, o que é verdade
  agora, o que era verdade numa data e o que o sistema acreditava numa data, sem a
  aplicação escrever SQL bitemporal — hoje ela guarda linhas planas e perde a
  diferença entre "mudou", "deixou de valer" e "estava errado".
- Sucesso: os sete cenários de aceitação da Etapa 7 passam contra um PostgreSQL
  real usando só a API pública; estão escritos em `tests/acceptance/`.
- Consumidor: a aplicação em tempo de requisição e a partir de jobs, de forma
  síncrona, dentro da própria transação quando tem uma (`PARTICIPAR`) ou numa que
  a biblioteca abre (`PROPRIA`) — ADR 0004, ADR 0005.
- `PARTICIPAR` com a conexão em autocommit é **recusado** com `ErroDeConfiguracao`
  antes de qualquer escrita (**confirmado pelo dono**): sem transação do app, uma
  operação de várias instruções ficaria pela metade. O adaptador Django evita o
  erro envolvendo a operação em `atomic()` (savepoint dentro de uma transação,
  transação curta fora dela) — ADR 0004.
- Modelo de memória: tenant ligado no construtor (**confirmado pelo dono**); dono
  em toda chamada; entidade, contexto e origem livres e opacos; `categoria`
  **obrigatória** em `lembrar`, texto livre, o app decide o catálogo
  (**confirmado pelo dono**); status derivado — ADR 0001.
- Tempo: os dois eixos; `recuperar` em três modos exclusivos — `como_em` e
  `sabido_em` nunca juntos (**confirmado pelo dono**); um relógio injetável; só
  datetimes com fuso.
- Operações (**decidido pelo dono em 2026-11-06, na reabertura da Etapa 1**): a
  única mutação de uma linha é fechar `substituido_em`. `encerrar`, `substituir` e
  `corrigir` fecham o registro da vigente e inserem: a cópia limitada (com
  `valido_ate`), a nova, ou a certa. Motivo: a regra anterior fazia `substituir`
  fechar o registro da antiga, e então "como era em março" não a encontrava; a
  alternativa de fechar a validade no lugar reescreveria `sabido_em` num
  encerramento retroativo — ADR 0002.
- `sabido_em(D)` = o que, em D, o sistema sabia ser verdade em D: filtra registro
  e validade em D (**decidido pelo dono em 2026-11-06**). É "o que o agente sabia
  quando respondeu" — ADR 0002.
- Escopo estrito (**confirmado pelo dono**): `recuperar` recebe `contextos` e
  `entidades`. Uma versão sem contexto só é devolvida quando `contextos` inclui
  `None` como membro (`contextos=["p-2027", None]`); `contextos=None` não filtra
  por esse eixo; `contextos=[]` não devolve nada nesse eixo. Mesma regra para
  entidades. Sair do escopo não escreve nada — ADR 0003.
- Bordas: conteúdo vazio, datetime sem fuso, os dois modos de uma vez, `esquecer`
  sem alvo → `ErroDeArgumentoInvalido`; memória desconhecida ou alheia →
  `ErroNaoEncontrado` (a mensagem não diz qual); fechamento concorrente ou
  `versao_esperada_id` defasado → `ErroDeConflito`; `versao_esperada_id` é
  opcional (**confirmado pelo dono**); falha do provedor → `ErroDeEmbedding`;
  dimensão divergente → `ErroDeDimensaoDeEmbedding`.
- Esquecer: delete físico de toda versão por memória, por entidade ou de tudo do
  dono, em uma transação; `sabido_em` deixa de devolver o alvo — ADR 0006.
  Exatamente um alvo entre `memoria_id`, `entidade_id` ou `tudo=True`; sem
  esquecer por contexto na 0.1 (**confirmado pelo dono**).
- Herança em `substituir` e `corrigir`: `categoria`, `entidade_id`, `contexto_id` e
  `origem` deixados em `None` são copiados da versão substituída; não há como
  limpar entidade ou contexto numa substituição, isso é uma memória nova com
  `lembrar` (**confirmado pelo dono**).
- Momento do embedding: na escrita, síncrono, antes de obter a conexão; a consulta
  em `recuperar` idem; embedding em lote ou diferido fica fora da 0.1
  (**confirmado pelo dono**).
- Histórico: `historico(dono_id, memoria_id)` devolve a cadeia da mais antiga à
  vigente; o app rotula as versões com `derivar_status`. Não há flag de histórico
  em `recuperar`: os três modos já respondem "o que era" e "o que sabíamos"
  (**confirmado pelo dono**).
- Licença: MIT (**confirmado pelo dono**).
- Idioma: português em tudo, termos em `docs/glossario.md` (**decidido pelo dono**
  em 2026-11-06, revertendo "tudo em inglês").

## Fora de escopo
- Extração por LLM, política, consolidação, grafos — Etapa 10; primeiro o ciclo de vida.
- Superfície assíncrona — nenhum consumidor assíncrono; ADR 0005.
- `como_em` + `sabido_em` numa consulta — três modos respondem às perguntas conhecidas.
- Corrigir uma versão histórica — só a vigente.
- Esquecer por contexto; metadados JSON; embedding em lote; limpar entidade/contexto
  ao substituir — cada um listado com a sua razão em `docs/architecture.md`.
- HTTP, MCP, CLI além de `migrar()` — biblioteca embutida.

## Perguntas abertas
- Nenhuma que bloqueie a Etapa 1. Ficam para a Etapa 2, sem decisão de produto:
  savepoints para operações de várias instruções dentro da transação do app
  (ADR 0004) e a mensagem exata do `ErroDeConfiguracao` de autocommit.

## Para a arquitetura
- Schema PostgreSQL próprio `memory_lifecycle`, uma linha por versão, índice parcial
  nas versões vigentes, versão vigente única por `memoria_id`, dimensão da coluna
  de vetor fixada na primeira migração — ADR 0007, ADR 0008,
  `.claude/rules/migrations.md`.
- A variável de ambiente `MEMORY_LIFECYCLE_PROVEDOR_CONEXAO` nomeia uma fábrica de
  provedor por caminho pontuado.
