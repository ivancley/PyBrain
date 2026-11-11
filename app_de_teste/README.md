# App de teste — chat com o Brainiac

Um chat Django de uma tela só, para testar a `memory-lifecycle` de verdade antes
de publicar. O Brainiac responde perguntas básicas sempre de bom humor e lembra o que
você conta sobre você. O LLM e os embeddings vêm do [OpenRouter](https://openrouter.ai);
os modelos são trocados pelo `.env`.

Não faz parte do pacote publicado (o wheel só leva `src/memory_lifecycle`).

## Rodando

```bash
make install                              # uma vez: .venv com Django e psycopg
make db-up                                # Postgres + pgvector na porta 5433
cp app_de_teste/.env.example app_de_teste/.env   # e preencha OPENROUTER_API_KEY
make chat                                 # http://127.0.0.1:8010 (PORTA_CHAT=... muda)
```

Não há `manage.py migrate`: a app não tem models. O schema da memória
(`MEMORIA_SCHEMA`, padrão `chat_teste`) é criado pelo `Memory.migrate()` na
primeira requisição.

## Configuração (`app_de_teste/.env`)

| variável | padrão | para quê |
|---|---|---|
| `OPENROUTER_API_KEY` | — | obrigatória |
| `OPENROUTER_MODELO` | `openai/gpt-4o-mini` | o modelo que conversa |
| `OPENROUTER_MODELO_EXTRATOR` | o mesmo de cima | o modelo que decide o que lembrar |
| `EMBEDDINGS` | `openrouter` | `falso` usa o `FakeEmbeddingProvider` (sem rede, sem semântica) |
| `OPENROUTER_MODELO_EMBEDDING` | `openai/text-embedding-3-small` | o modelo de embedding |
| `OPENROUTER_DIMENSAO_EMBEDDING` | `1536` | tem que bater com o modelo de embedding |
| `CHAT_DATABASE_URL` | o banco do `make db-up` | o Postgres |
| `MEMORIA_SCHEMA` / `MEMORIA_TENANT` | `chat_teste` / `app-de-teste` | onde a memória mora |

A dimensão do vetor fica gravada no schema. Trocou para um modelo de embedding
de outra dimensão? Mude `MEMORIA_SCHEMA` também, senão a primeira escrita levanta
`ErroDeDimensaoDeEmbedding` (que é o comportamento certo da biblioteca).

## Como um turno funciona

A app testa a memória de longo prazo, não o LLM: o modelo **não recebe o
histórico da conversa**, só a mensagem atual e as memórias do banco. Tudo o que o
Brainiac sabe sobre a pessoa veio da `memory-lifecycle`; "memórias usadas",
embaixo de cada resposta, mostra o que ele recebeu.

1. `recall(query=<mensagem>)` traz até 12 memórias da pessoa, as mais parecidas.
2. Duas chamadas ao LLM, em paralelo, com essas memórias e a mensagem atual: a **resposta** (a
   persona do Brainiac) e a **extração**, que devolve operações em JSON.
3. As operações viram `lembrar`, `substituir`, `corrigir` ou `encerrar`, cada uma
   numa transação curta pelo `DjangoProvider`. A tela mostra cada uma como uma
   etiqueta embaixo da resposta; uma falha da extração aparece como etiqueta de
   erro sem derrubar a resposta.

## Roteiro de teste

| converse | e confira no painel |
|---|---|
| "Meu nome é Ana e moro em Recife" | duas memórias novas (`lembrar`) |
| "Me mudei para São Paulo" | `substituir`; o histórico mostra a cópia limitada |
| "Errei, não gosto de café, gosto de chá" (depois de dizer que gostava de café) | `corrigir`; `como_em` antes não devolve mais café, `sabido_em` antes devolve |
| "Parei de jogar futebol" | `encerrar` |
| "Qual a capital da França?" | resposta engraçada e nenhuma operação |
| modo `como_em` / `sabido_em` com um instante anterior | a viagem no tempo dos dois eixos |
| troque para **Bruno** no seletor | painel vazio: isolamento entre donos |
| **Esquecer tudo** | delete físico; nem `sabido_em` devolve mais |

## Pessoas

Três pessoas fixas, em `PESSOAS` no `config/settings.py`: **Ana**, **Bruno** e
**Carla**, cada uma com um `dono_id` (uuid) fixo. O seletor no topo da tela troca
de pessoa; a escolha fica num cookie assinado, e a conversa de cada uma fica no
navegador (localStorage). A memória de cada pessoa fica no banco e nunca aparece
para as outras: trocar no seletor é o teste de isolamento entre donos.
