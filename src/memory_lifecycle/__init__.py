"""memory-lifecycle: memória persistente, contextual e bitemporal para agentes de IA.

Construa uma ``Memoria`` por tenant com um provedor de conexão e um de embeddings
e então ``lembrar``, ``recuperar``, ``substituir``, ``corrigir``, ``encerrar`` e
``esquecer``. Os adaptadores de conexão ficam em ``memory_lifecycle.connection``
e são extras opcionais.

Importar este pacote não puxa nenhuma dependência de terceiros (CLAUDE.md, regra 4).
"""

from memory_lifecycle.api import LIMITE_PADRAO_RECUPERACAO, SCHEMA_PADRAO, Memoria
from memory_lifecycle.connection import ModoDeTransacao, ProvedorDeConexao
from memory_lifecycle.embeddings import ProvedorDeEmbeddings, ProvedorDeEmbeddingsFalso
from memory_lifecycle.exceptions import (
    ErroDeArgumentoInvalido,
    ErroDeConfiguracao,
    ErroDeConflito,
    ErroDeDimensaoDeEmbedding,
    ErroDeEmbedding,
    ErroDeMigracao,
    ErroExtraNaoInstalado,
    ErroMemoryLifecycle,
    ErroNaoEncontrado,
)
from memory_lifecycle.model import (
    ResultadoDeRecuperacao,
    Status,
    VersaoDeMemoria,
    derivar_status,
)

__all__ = [
    "LIMITE_PADRAO_RECUPERACAO",
    "SCHEMA_PADRAO",
    "ErroDeArgumentoInvalido",
    "ErroDeConfiguracao",
    "ErroDeConflito",
    "ErroDeDimensaoDeEmbedding",
    "ErroDeEmbedding",
    "ErroDeMigracao",
    "ErroExtraNaoInstalado",
    "ErroMemoryLifecycle",
    "ErroNaoEncontrado",
    "Memoria",
    "ModoDeTransacao",
    "ProvedorDeConexao",
    "ProvedorDeEmbeddings",
    "ProvedorDeEmbeddingsFalso",
    "ResultadoDeRecuperacao",
    "Status",
    "VersaoDeMemoria",
    "derivar_status",
]
