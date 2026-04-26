from __future__ import annotations

# Per-kind imports below trigger each module's `register_provider_type(...)` call,
# populating PROVIDER_TYPES before the kernel reads it.
from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import PROVIDER_TYPES, register_provider_type
from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.kinds.audit import Audit, AuditReport, BaseAudit, Finding
from kvault_mcp.kinds.embedding import BaseEmbeddingProvider, EmbeddingProvider
from kvault_mcp.kinds.manifest_builder import BaseManifestBuilder, ManifestBuilder
from kvault_mcp.kinds.retriever import BaseRetriever, Retriever
from kvault_mcp.kinds.rule_injector import BaseRuleInjector, RuleInjector
from kvault_mcp.kinds.rule_store import BaseRuleStore, Rule, RuleStore
from kvault_mcp.kinds.text_index import BaseTextIndex, TextIndex
from kvault_mcp.kinds.vector_store import BaseVectorStore, VectorStore

__all__ = [
    "Audit",
    "AuditReport",
    "BaseAudit",
    "BaseEmbeddingProvider",
    "BaseManifestBuilder",
    "BasePlugin",
    "BaseRetriever",
    "BaseRuleInjector",
    "BaseRuleStore",
    "BaseTextIndex",
    "BaseVectorStore",
    "EmbeddingProvider",
    "Finding",
    "ManifestBuilder",
    "PROVIDER_TYPES",
    "RetrievalResult",
    "Retriever",
    "Rule",
    "RuleInjector",
    "RuleStore",
    "TextIndex",
    "VectorStore",
    "register_provider_type",
]
