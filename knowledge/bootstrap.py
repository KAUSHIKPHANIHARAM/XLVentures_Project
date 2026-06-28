"""
knowledge/bootstrap.py

Knowledge layer bootstrap — initialises and ingests domain knowledge.

Called at application startup after the memory store is ready.
Provides both the ingestion trigger and the retrieval service factory.

Usage:
    from knowledge.bootstrap import bootstrap_knowledge_layer, get_retrieval_service
    bootstrap_knowledge_layer(cfg, store)
    retriever = get_retrieval_service(cfg.active_domain)
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from knowledge.ingestion import KnowledgeIngestionService
from knowledge.retrieval import KnowledgeRetrievalService
from memory.base import AbstractMemoryStore
from utils.logging import get_logger

if TYPE_CHECKING:
    from config.schemas import PlatformConfig

logger = get_logger(__name__)

_retrieval_services: dict[str, KnowledgeRetrievalService] = {}
_services_lock = threading.Lock()


def bootstrap_knowledge_layer(
    platform_config: "PlatformConfig",
    store: AbstractMemoryStore,
    force_reingest: bool = False,
) -> KnowledgeRetrievalService:
    """
    Ingest domain knowledge and return the retrieval service.

    Args:
        platform_config: Full platform configuration.
        store:           Initialised memory store.
        force_reingest:  If True, re-ingests even if knowledge already exists.

    Returns:
        KnowledgeRetrievalService ready for use by agents.
    """
    domain_config = platform_config.current_domain
    domain = domain_config.name

    with _services_lock:
        if domain in _retrieval_services and not force_reingest:
            logger.debug(
                "Knowledge retrieval service for domain '%s' already ready.", domain
            )
            return _retrieval_services[domain]

        # Ingest knowledge
        ingestion_svc = KnowledgeIngestionService(store, domain_config)
        results = ingestion_svc.ingest_all(force=force_reingest)

        if results:
            logger.info("Knowledge ingestion results: %s", results)

        # Create and cache retrieval service
        retrieval_svc = KnowledgeRetrievalService(
            store=store,
            domain=domain,
            top_k=platform_config.vector_db.top_k,
        )
        _retrieval_services[domain] = retrieval_svc

        count = retrieval_svc.knowledge_count()
        logger.info(
            "Knowledge layer ready for domain '%s'. Total chunks: %d.",
            domain,
            count,
        )
        return retrieval_svc


def get_retrieval_service(domain: str) -> KnowledgeRetrievalService:
    """
    Retrieve the cached KnowledgeRetrievalService for a domain.

    Args:
        domain: Domain name.

    Returns:
        KnowledgeRetrievalService.

    Raises:
        RuntimeError: If bootstrap_knowledge_layer() wasn't called first.
    """
    service = _retrieval_services.get(domain)
    if service is None:
        raise RuntimeError(
            f"Knowledge retrieval service for domain '{domain}' is not initialized. "
            f"Call bootstrap_knowledge_layer() at startup."
        )
    return service


def reset_knowledge_services() -> None:
    """Clear cached services (for tests only)."""
    global _retrieval_services  # noqa: PLW0603
    with _services_lock:
        _retrieval_services = {}
    logger.debug("Knowledge services reset.")
