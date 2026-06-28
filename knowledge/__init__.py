"""
knowledge/__init__.py

Public API for the knowledge module.

Usage:
    from knowledge import bootstrap_knowledge_layer, get_retrieval_service
    from knowledge import KnowledgeIngestionService, KnowledgeRetrievalService
"""

from knowledge.bootstrap import (
    bootstrap_knowledge_layer,
    get_retrieval_service,
    reset_knowledge_services,
)
from knowledge.ingestion import KnowledgeIngestionService
from knowledge.retrieval import KnowledgeRetrievalService

__all__ = [
    "bootstrap_knowledge_layer",
    "get_retrieval_service",
    "reset_knowledge_services",
    "KnowledgeIngestionService",
    "KnowledgeRetrievalService",
]
