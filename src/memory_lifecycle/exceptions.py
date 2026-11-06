"""Os erros tipados da biblioteca, todos num único módulo.

Quem chama captura ``ErroMemoryLifecycle`` para tratar qualquer coisa que a
biblioteca levante, ou uma subclasse para tratar uma situação. O tipo diz o que
aconteceu e se repetir ajuda; a mensagem diz onde. Nenhum caminho de código
levanta um ``Exception`` puro (CLAUDE.md § Convenções).
"""

from __future__ import annotations


class ErroMemoryLifecycle(Exception):
    """Base de todo erro levantado pela biblioteca."""


class ErroDeArgumentoInvalido(ErroMemoryLifecycle, ValueError):
    """Quem chamou passou algo que o contrato proíbe.

    Exemplos: um ``datetime`` sem fuso, ``como_em`` e ``sabido_em`` juntos, um
    ``esquecer`` sem alvo, um ``conteudo`` vazio. Também é ``ValueError`` para que
    uma validação genérica de entrada continue capturando.
    """


class ErroNaoEncontrado(ErroMemoryLifecycle):
    """Não existe versão vigente da memória para este tenant e dono.

    Levantado por ``substituir``, ``corrigir``, ``encerrar`` e ``historico`` quando
    o ``memoria_id`` é desconhecido, pertence a outro, ou foi esquecido. A mensagem
    nunca diz qual dos três, para que uma sondagem entre tenants não aprenda nada.
    """


class ErroDeConflito(ErroMemoryLifecycle):
    """A versão a fechar foi fechada antes por outro escritor.

    Fechar um limite de tempo é condicional ao limite ainda estar aberto; zero
    linhas afetadas significa que outro escritor venceu. Também levantado quando
    ``versao_esperada_id`` já não nomeia a versão vigente. Quem chamou relê e
    decide; a biblioteca nunca tenta de novo por conta própria.
    """


class ErroDeEmbedding(ErroMemoryLifecycle):
    """O provedor de embeddings não conseguiu produzir um vetor (em geral, transitório)."""


class ErroDeDimensaoDeEmbedding(ErroDeEmbedding):
    """A dimensão do provedor difere da registrada no schema (permanente).

    Um modelo diferente, ou o mesmo modelo reconfigurado, não pode compartilhar a
    coluna de vetores. A solução é um schema novo ou reprocessar os embeddings,
    nunca um cast silencioso.
    """


class ErroDeConfiguracao(ErroMemoryLifecycle):
    """A biblioteca não consegue rodar como foi configurada.

    Exemplos: o schema nunca foi migrado, o provedor de conexão nomeado pelo
    ambiente não carrega, o provedor não honra o protocolo.
    """


class ErroExtraNaoInstalado(ErroDeConfiguracao, ImportError):
    """Falta uma dependência opcional; a mensagem nomeia o extra a instalar."""


class ErroDeMigracao(ErroMemoryLifecycle):
    """O conjunto de migrações é inconsistente: arquivo aplicado alterado ou número duplicado."""
