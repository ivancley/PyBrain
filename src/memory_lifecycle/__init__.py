"""memory-lifecycle: persistent, contextual and bitemporal memory for AI agents.

Build one ``Memory`` per tenant with a connection provider and an embedding provider,
then ``remember``, ``recall``, ``supersede``, ``correct``, ``expire`` and ``forget``.
The connection adapters live in ``memory_lifecycle.connection`` and are optional
extras.

Importing this package pulls in no third-party dependency (CLAUDE.md, regra 4).

PT: memory-lifecycle: memória persistente, contextual e bitemporal para agentes de IA.

Construa uma ``Memory`` por tenant com um provedor de conexão e um de embeddings
e então ``remember``, ``recall``, ``supersede``, ``correct``, ``expire`` e
``forget``. Os adaptadores de conexão ficam em ``memory_lifecycle.connection``
e são extras opcionais.

Importar este pacote não puxa nenhuma dependência de terceiros (CLAUDE.md, regra 4).
"""

from memory_lifecycle.api import DEFAULT_RECALL_LIMIT, DEFAULT_SCHEMA, Memory
from memory_lifecycle.connection import ConnectionProvider, TransactionMode
from memory_lifecycle.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from memory_lifecycle.exceptions import (
    ConfigurationError,
    ConflictError,
    EmbeddingDimensionError,
    EmbeddingError,
    ExtraNotInstalledError,
    InvalidArgumentError,
    MemoryLifecycleError,
    MigrationError,
    NotFoundError,
)
from memory_lifecycle.model import (
    MemoryVersion,
    RecallResult,
    Status,
    derive_status,
)

__all__ = [
    "DEFAULT_RECALL_LIMIT",
    "DEFAULT_SCHEMA",
    "ConfigurationError",
    "ConflictError",
    "ConnectionProvider",
    "EmbeddingDimensionError",
    "EmbeddingError",
    "EmbeddingProvider",
    "ExtraNotInstalledError",
    "FakeEmbeddingProvider",
    "InvalidArgumentError",
    "Memory",
    "MemoryLifecycleError",
    "MemoryVersion",
    "MigrationError",
    "NotFoundError",
    "RecallResult",
    "Status",
    "TransactionMode",
    "derive_status",
]
