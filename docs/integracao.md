# Integração

Como ligar a memory-lifecycle à sua aplicação: instalação, a conexão com o banco
(por provedor), o provedor de embeddings e o que usar nas suas próprias suítes.
Os conceitos estão em `docs/conceitos.md`; os exemplos completos, em `examples/`,
rodam na suíte deste repositório.

## Instalação

A biblioteca ainda não está publicada no PyPI. Instale a partir do repositório,
com o extra do seu provedor de conexão:

```bash
pip install "memory-lifecycle[psycopg] @ git+<url-do-repositório>"   # DSN e pool do psycopg
pip install "memory-lifecycle[django] @ git+<url-do-repositório>"    # Django
pip install "memory-lifecycle[sqlalchemy] @ git+<url-do-repositório>" # SQLAlchemy
```

O núcleo não tem dependência obrigatória: cada adaptador importa a sua só quando
é construído, e diz qual extra falta se ela não estiver instalada. O banco
precisa ser PostgreSQL 13 ou mais novo, com a extensão pgvector disponível no
servidor.

## O schema da memória

A memória vive num schema próprio dentro do seu banco (`memory_lifecycle`, por
padrão; mude com `Memory(schema=...)`). `migrate()` cria o schema, instala o
pgvector se o usuário tiver privilégio, aplica as migrações pendentes e é
idempotente: chame no deploy, ou dentro das migrações do seu framework (veja
Django abaixo). A dimensão do vetor fica fixa na primeira migração, pela
dimensão do seu provedor de embeddings.

## Escolhendo o provedor de conexão

A biblioteca nunca abre um segundo pool: ela pede uma conexão a um provedor, por
operação, e devolve no fim.

| provedor | extra | modo | quando usar |
|---|---|---|---|
| `DSNProvider(dsn)` | `psycopg` | própria (`OWN`) | scripts, jobs, testes |
| `PsycopgPoolProvider(pool)` | `psycopg` | própria (`OWN`) | serviço com pool do psycopg |
| `DjangoProvider(alias)` | `django` | participar (`PARTICIPATE`) | dentro de um request Django |
| `SQLAlchemyProvider(engine)` | `sqlalchemy` | própria (`OWN`) | app SQLAlchemy, fora de uma sessão |
| `SQLAlchemyProvider.from_session(session)` | `sqlalchemy` | participar (`PARTICIPATE`) | dentro da unidade de trabalho da sessão |

- **Própria (`TransactionMode.OWN`):** a biblioteca faz commit no fim de cada operação e rollback se ela
  falhar.
- **Participar (`TransactionMode.PARTICIPATE`):** a biblioteca nunca faz commit nem rollback. A escrita entra na
  transação do app e só vale se o app fizer commit; se o request falhar, a memória
  some junto.

Uma conexão em autocommit é recusada nos dois modos com `ConfigurationError`:
sem transação, uma operação de várias instruções ficaria pela metade.

## Scripts e jobs: `DSNProvider`

```python
from memory_lifecycle import Memory
from memory_lifecycle.connection.dsn import DSNProvider

memory = Memory(
    connection=DSNProvider("postgresql://user:password@host:5432/database"),
    embeddings=my_embedding_provider,
    tenant_id="org-1",
)
memory.migrate()
```

Cada operação abre e fecha uma conexão (8 a 13 ms a mais). Para um serviço com
muitas chamadas, prefira o pool.

## Pool do psycopg

```python
from psycopg_pool import ConnectionPool

from memory_lifecycle.connection.psycopg_pool import PsycopgPoolProvider

pool = ConnectionPool("postgresql://...", min_size=2, max_size=10, open=True)
memory = Memory(connection=PsycopgPoolProvider(pool), embeddings=..., tenant_id="org-1")
```

## Django, do começo ao fim

O exemplo completo está em `examples/django_app/` e roda na suíte
(`tests/integration/test_examples.py`). As peças:

**1. Configuração.** O banco do Django é o da memória; nada além de um
`DATABASES` com o backend `django.db.backends.postgresql`. Opcional:

```python
MEMORY_SCHEMA = "memory_lifecycle"
ATOMIC_REQUESTS = True  # dentro de DATABASES["default"]: cada request numa transação
```

**2. Uma `Memory` por tenant, criada uma vez por processo** (`examples/django_app/memory.py`):

```python
from functools import cache

from memory_lifecycle import Memory
from memory_lifecycle.connection.django import DjangoProvider


@cache
def tenant_memory(tenant_id: str) -> Memory:
    return Memory(connection=DjangoProvider(), embeddings=..., tenant_id=tenant_id)
```

**3. O schema junto com o `manage.py migrate`**, numa migração do seu app:

```python
from django.db import migrations

from examples.django_app.memory import migrate_memory


class Migration(migrations.Migration):
    dependencies = [("seu_app", "0001_initial")]
    operations = [migrations.RunPython(migrate_memory, migrations.RunPython.noop)]
```

**4. A view** (`examples/django_app/views.py`) recupera, monta o contexto, chama o
agente e grava o que ele propôs, tudo na transação do request. Tenant e dono vêm
da autenticação, nunca do corpo do request.

O `DjangoProvider` roda cada operação dentro de `transaction.atomic()`:

- **Dentro de uma transação do request:** a operação vira um savepoint, e a
  memória só fica gravada se o request fizer commit.
- **Fora de uma transação:** a operação é uma transação curta, com commit
  sozinha.
- **Num erro da biblioteca:** só o savepoint é desfeito, e o resto do request
  segue.

## SQLAlchemy

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from memory_lifecycle.connection.sqlalchemy import SQLAlchemyProvider

engine = create_engine("postgresql+psycopg://...")
memory = Memory(connection=SQLAlchemyProvider(engine), embeddings=..., tenant_id="org-1")

with Session(engine) as session:  # ou: a memória entra na unidade de trabalho da sessão
    session_memory = Memory(
        connection=SQLAlchemyProvider.from_session(session), embeddings=..., tenant_id="org-1"
    )
    session_memory.remember("user-7", "prefere tabelas", kind="preference")
    session.commit()  # só aqui a memória fica gravada
```

Com a sessão, cada operação roda num savepoint (`begin_nested`), como no Django.

## Configurar pelo ambiente

Quando o app prefere decidir o provedor por configuração, aponte a variável
`MEMORY_LIFECYCLE_CONNECTION_PROVIDER` para uma função sem argumentos que devolve o
provedor (`pacote.modulo:funcao`). Só o caminho viaja pelo ambiente; o pool
continua sendo construído pelo seu código.

```python
from memory_lifecycle.connection import load_provider

memory = Memory(connection=load_provider(), embeddings=..., tenant_id="org-1")
```

## O seu provedor de embeddings

A biblioteca não fala com nenhum provedor de embeddings: você passa um objeto com
três membros (o protocolo `EmbeddingProvider`).

```python
from collections.abc import Sequence


class MyEmbeddingProvider:
    dimension = 1024                 # fixa: o schema é criado com ela
    model_name = "my-model-v1"       # gravado em cada versão

    def __init__(self, client) -> None:
        self._client = client

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return self._client.embed(list(texts))  # um vetor por texto, na mesma ordem
```

- **Quando é chamado:** sempre **antes** de a biblioteca pegar uma conexão. Um
  provedor lento não segura uma conexão do pool.
- **Falha do provedor:** vira `EmbeddingError`, com o erro original encadeado e
  sem o texto na mensagem. Um erro de programação (`TypeError`, `KeyError`) sobe
  intacto.
- **Dimensão diferente da do schema:** é `EmbeddingDimensionError`. Trocar de
  modelo pede um schema novo.

## Desempenho

- **Busca vetorial exata (ADR 0009):** com `query`, a distância é calculada
  sobre toda versão que passa nos filtros. Medido com vetores de 1536 dimensões:
  - 2 mil versões por dono e cache quente: até 11 ms.
  - 24 mil versões vigentes: 82 ms.
- **O escopo é a alavanca:** com `contexts` ou `entities`, a mesma consulta cai
  para menos de 1 ms de SQL. Passe o escopo da conversa.
- **Sem `query`:** a listagem lê só as linhas pedidas pelo `limit`.

## Nas suas suítes de teste

- **`FakeEmbeddingProvider`:** é determinístico e não usa rede. Textos
  iguais dão vetores iguais.
- **`Memory(clock=...)`:** coloca as escritas em instantes escolhidos, sem
  `sleep`. É assim que se testa `as_of` e `known_at`.
- **Um schema por teste:** passe `Memory(schema=...)` e apague o schema no fim.
  Foi o que funcionou neste repositório; um rollback por teste não serve no modo
  `OWN` nem para concorrência (`tests/conftest.py`).
