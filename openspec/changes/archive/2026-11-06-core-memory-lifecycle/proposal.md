# Proposal

## Why

Uma aplicação que dá memória a um agente de IA hoje guarda linhas planas: uma
preferência é sobrescrita quando muda, um fato que deixou de valer é apagado, e um
fato registrado errado é editado no lugar. Depois ninguém responde "o que o agente
sabia quando respondeu no mês passado?", e uma memória sobre uma entidade que saiu
de um contexto é apagada (perdendo o passado) ou mantida (poluindo o presente). O
desenvolvedor escreve as regras temporais à mão, uma vez por app, e erra nelas de
forma sutil.

O sucesso é observável: os sete cenários de aceitação da Etapa 7 do plano (troca
de período de um contexto, entidade sai do escopo, preferência muda, correção,
isolamento, esquecer, substituição concorrente) passam contra um PostgreSQL real
usando só a API pública, com toda instrução filtrada por tenant e dono.

## What Changes

`memory-lifecycle` 0.1.0 dá a uma aplicação Python memória persistente, contextual
e bitemporal para os seus agentes, embutida no processo sobre o PostgreSQL da
própria aplicação. Você constrói uma `Memoria` por tenant com o seu provedor de
conexão e o seu provedor de embeddings, então `lembrar` fatos sobre um dono,
`recuperar` por escopo, filtros, similaridade e momento (agora, como em uma data,
ou sabido em uma data), e cuida do ciclo de vida com `substituir`, `corrigir`,
`encerrar` e `invalidar_contexto`. O escopo é da aplicação e é estrito: uma
memória sem contexto só volta quando os contextos passados incluem `None`. Toda
mudança é uma versão nova e imutável, então o histórico está sempre lá;
`esquecer` é o único delete físico, para pedidos de privacidade. O núcleo não tem
dependência obrigatória; drivers, adaptadores de framework e provedores de
embeddings são extras opcionais.

## Capabilities

### New Capabilities
- `memory-versions`: registrar uma memória, suas versões imutáveis, o registro de versão e o status derivado, o histórico de uma memória
- `temporal-operations`: encerrar, corrigir, substituir e invalidar contexto, com o seu efeito nos dois eixos e o conflito no fechamento concorrente
- `recall`: escopo estrito passado pelo app, filtros estruturados, similaridade, os três modos de consulta, limite e ordenação
- `isolation`: tenant e dono em toda operação; nada atravessa
- `forget`: delete físico de toda versão de um alvo
- `connection-and-embedding`: o contrato do provedor de conexão com dois modos de transação, o contrato do provedor de embeddings, embedding antes da conexão, dimensão divergente
- `schema-migrations`: inicialização do schema da biblioteca, idempotente e só de acréscimo

### Modified Capabilities
(nenhuma — primeira mudança)

## Impact

- Superfície pública nova: `Memoria` com `migrar`, `lembrar`, `substituir`,
  `corrigir`, `encerrar`, `invalidar_contexto`, `esquecer`, `recuperar`,
  `historico`; os registros `VersaoDeMemoria`, `ResultadoDeRecuperacao`, `Status`
  e `derivar_status`; os protocolos `ProvedorDeConexao` e `ProvedorDeEmbeddings`;
  `ProvedorDeEmbeddingsFalso`; as exceções tipadas.
- Nenhum comportamento existente muda (primeira versão). Nenhuma dependência
  obrigatória é adicionada.
- A aplicação deve fornecer um provedor de conexão e um provedor de embeddings, e
  calcular o escopo de toda recuperação.
