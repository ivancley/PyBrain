# Integração

Como ligar a memory-lifecycle à sua aplicação: instalação, a conexão com o banco
(por provedor), o provedor de embeddings e o que usar nas suas próprias suítes.
Os conceitos estão em `docs/conceitos.md`; os exemplos completos, em `exemplos/`,
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
padrão; mude com `Memoria(schema=...)`). `migrar()` cria o schema, instala o
pgvector se o usuário tiver privilégio, aplica as migrações pendentes e é
idempotente: chame no deploy, ou dentro das migrações do seu framework (veja
Django abaixo). A dimensão do vetor fica fixa na primeira migração, pela
dimensão do seu provedor de embeddings.

## Escolhendo o provedor de conexão

A biblioteca nunca abre um segundo pool: ela pede uma conexão a um provedor, por
operação, e devolve no fim.

| provedor | extra | modo | quando usar |
|---|---|---|---|
| `ProvedorDSN(dsn)` | `psycopg` | própria | scripts, jobs, testes |
| `ProvedorPoolPsycopg(pool)` | `psycopg` | própria | serviço com pool do psycopg |
| `ProvedorDjango(alias)` | `django` | participar | dentro de um request Django |
| `ProvedorSQLAlchemy(engine)` | `sqlalchemy` | própria | app SQLAlchemy, fora de uma sessão |
| `ProvedorSQLAlchemy.de_sessao(sessao)` | `sqlalchemy` | participar | dentro da unidade de trabalho da sessão |

- **Própria:** a biblioteca faz commit no fim de cada operação e rollback se ela
  falhar.
- **Participar:** a biblioteca nunca faz commit nem rollback. A escrita entra na
  transação do app e só vale se o app fizer commit; se o request falhar, a memória
  some junto.

Uma conexão em autocommit é recusada nos dois modos com `ErroDeConfiguracao`:
sem transação, uma operação de várias instruções ficaria pela metade.

## Scripts e jobs: `ProvedorDSN`

```python
from memory_lifecycle import Memoria
from memory_lifecycle.connection.dsn import ProvedorDSN

memoria = Memoria(
    conexao=ProvedorDSN("postgresql://usuario:senha@host:5432/banco"),
    embeddings=meu_provedor_de_embeddings,
    tenant_id="org-1",
)
memoria.migrar()
```

Cada operação abre e fecha uma conexão (8 a 13 ms a mais). Para um serviço com
muitas chamadas, prefira o pool.

## Pool do psycopg

```python
from psycopg_pool import ConnectionPool

from memory_lifecycle.connection.psycopg_pool import ProvedorPoolPsycopg

pool = ConnectionPool("postgresql://...", min_size=2, max_size=10, open=True)
memoria = Memoria(conexao=ProvedorPoolPsycopg(pool), embeddings=..., tenant_id="org-1")
```

## Django, do começo ao fim

O exemplo completo está em `exemplos/django_app/` e roda na suíte
(`tests/integration/test_exemplos.py`). As peças:

**1. Configuração.** O banco do Django é o da memória; nada além de um
`DATABASES` com o backend `django.db.backends.postgresql`. Opcional:

```python
MEMORIA_SCHEMA = "memory_lifecycle"
ATOMIC_REQUESTS = True  # dentro de DATABASES["default"]: cada request numa transação
```

**2. Uma `Memoria` por tenant, criada uma vez por processo** (`exemplos/django_app/memoria.py`):

```python
from functools import cache

from memory_lifecycle import Memoria
from memory_lifecycle.connection.django import ProvedorDjango


@cache
def memoria_do_tenant(tenant_id: str) -> Memoria:
    return Memoria(conexao=ProvedorDjango(), embeddings=..., tenant_id=tenant_id)
```

**3. O schema junto com o `manage.py migrate`**, numa migração do seu app:

```python
from django.db import migrations

from exemplos.django_app.memoria import migrar_memoria


class Migration(migrations.Migration):
    dependencies = [("seu_app", "0001_initial")]
    operations = [migrations.RunPython(migrar_memoria, migrations.RunPython.noop)]
```

**4. A view** (`exemplos/django_app/views.py`) recupera, monta o contexto, chama o
agente e grava o que ele propôs, tudo na transação do request. Tenant e dono vêm
da autenticação, nunca do corpo do request.

O `ProvedorDjango` roda cada operação dentro de `transaction.atomic()`:

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

from memory_lifecycle.connection.sqlalchemy import ProvedorSQLAlchemy

engine = create_engine("postgresql+psycopg://...")
memoria = Memoria(conexao=ProvedorSQLAlchemy(engine), embeddings=..., tenant_id="org-1")

with Session(engine) as sessao:  # ou: a memória entra na unidade de trabalho da sessão
    memoria_da_sessao = Memoria(
        conexao=ProvedorSQLAlchemy.de_sessao(sessao), embeddings=..., tenant_id="org-1"
    )
    memoria_da_sessao.lembrar("usuario-7", "prefere tabelas", categoria="preferencia")
    sessao.commit()  # só aqui a memória fica gravada
```

Com a sessão, cada operação roda num savepoint (`begin_nested`), como no Django.

## Configurar pelo ambiente

Quando o app prefere decidir o provedor por configuração, aponte a variável
`MEMORY_LIFECYCLE_PROVEDOR_CONEXAO` para uma função sem argumentos que devolve o
provedor (`pacote.modulo:funcao`). Só o caminho viaja pelo ambiente; o pool
continua sendo construído pelo seu código.

```python
from memory_lifecycle.connection import carregar_provedor

memoria = Memoria(conexao=carregar_provedor(), embeddings=..., tenant_id="org-1")
```

## O seu provedor de embeddings

A biblioteca não fala com nenhum provedor de embeddings: você passa um objeto com
três membros (o protocolo `ProvedorDeEmbeddings`).

```python
from collections.abc import Sequence


class MeuProvedorDeEmbeddings:
    dimensao = 1024                    # fixa: o schema é criado com ela
    nome_do_modelo = "meu-modelo-v1"   # gravado em cada versão

    def __init__(self, cliente) -> None:
        self._cliente = cliente

    def gerar(self, textos: Sequence[str]) -> list[list[float]]:
        return self._cliente.embed(list(textos))  # um vetor por texto, na mesma ordem
```

- **Quando é chamado:** sempre **antes** de a biblioteca pegar uma conexão. Um
  provedor lento não segura uma conexão do pool.
- **Falha do provedor:** vira `ErroDeEmbedding`, com o erro original encadeado e
  sem o texto na mensagem. Um erro de programação (`TypeError`, `KeyError`) sobe
  intacto.
- **Dimensão diferente da do schema:** é `ErroDeDimensaoDeEmbedding`. Trocar de
  modelo pede um schema novo.

## Desempenho

- **Busca vetorial exata (ADR 0009):** com `consulta`, a distância é calculada
  sobre toda versão que passa nos filtros. Medido com vetores de 1536 dimensões:
  - 2 mil versões por dono e cache quente: até 11 ms.
  - 24 mil versões vigentes: 82 ms.
- **O escopo é a alavanca:** com `contextos` ou `entidades`, a mesma consulta cai
  para menos de 1 ms de SQL. Passe o escopo da conversa.
- **Sem `consulta`:** a listagem lê só as linhas pedidas pelo `limite`.

## Nas suas suítes de teste

- **`ProvedorDeEmbeddingsFalso`:** é determinístico e não usa rede. Textos
  iguais dão vetores iguais.
- **`Memoria(relogio=...)`:** coloca as escritas em instantes escolhidos, sem
  `sleep`. É assim que se testa `como_em` e `sabido_em`.
- **Um schema por teste:** passe `Memoria(schema=...)` e apague o schema no fim.
  Foi o que funcionou neste repositório; um rollback por teste não serve no modo
  própria nem para concorrência (`tests/conftest.py`).
