"""
agents/tool_implementations.py

Concrete tool implementations for the Customer Management domain.

These are the real functions registered with the ToolRegistry. Each function
is injected into the registry at startup via register_tool_implementation()
so the agents get live data from SQLite and ChromaDB — not stubs.

Design:
    - Each function is a closure over the connector and retrieval service.
    - register_all_tools() is called once during platform bootstrap.
    - Functions follow the same parameter names as the YAML tool parameter schemas.
"""

from __future__ import annotations

import json
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


def register_all_tools(
    connector: Any,
    retrieval_service: Any,
) -> None:
    """
    Register concrete implementations for all Customer Management tools.

    Args:
        connector:         SQLiteConnector for the active domain.
        retrieval_service: KnowledgeRetrievalService for the active domain.
    """
    from registry.tool_registry import register_tool_implementation

    # --- search_customers ---
    def search_customers(query: str, segment: str = "", limit: int = 10) -> str:
        filters = {"segment": segment} if segment else None
        result = connector.search("Customer", query=query, filters=filters, limit=limit)
        records = [
            {
                "id": r.entity_id,
                "name": r.display_name,
                "email": r.get_field("email"),
                "segment": r.get_field("segment"),
                "churn_risk_score": r.get_field("churn_risk_score"),
                "sentiment_score": r.get_field("sentiment_score"),
                "lifetime_value": r.get_field("lifetime_value"),
                "last_interaction_date": r.get_field("last_interaction_date"),
            }
            for r in result.records
        ]
        return json.dumps({
            "total_found": result.total_found,
            "customers": records,
        }, default=str)

    register_tool_implementation("search_customers", search_customers)

    # --- get_customer_detail ---
    def get_customer_detail(customer_id: int) -> str:
        record = connector.get_by_id("Customer", customer_id)
        if record is None:
            return json.dumps({"error": f"Customer {customer_id} not found."})
        return json.dumps({
            "customer": record.data,
            "customer_id": record.entity_id,
            "display_name": record.display_name,
        }, default=str)

    register_tool_implementation("get_customer_detail", get_customer_detail)

    # --- get_interaction_history ---
    def get_interaction_history(customer_id: int, limit: int = 10) -> str:
        result = connector.filter_by(
            "Interaction",
            filters={"customer_id": customer_id},
            limit=limit,
            order_by="created_at",
            descending=True,
        )
        interactions = [
            {
                "id": r.entity_id,
                "channel": r.get_field("channel"),
                "subject": r.get_field("subject"),
                "sentiment": r.get_field("sentiment"),
                "created_at": r.get_field("created_at"),
                "content_preview": str(r.get_field("content") or "")[:200],
            }
            for r in result.records
        ]
        return json.dumps({
            "customer_id": customer_id,
            "total_interactions": result.total_found,
            "interactions": interactions,
        }, default=str)

    register_tool_implementation("get_interaction_history", get_interaction_history)

    # --- analyze_churn_risk ---
    def analyze_churn_risk(customer_id: int) -> str:
        record = connector.get_by_id("Customer", customer_id)
        if record is None:
            return json.dumps({"error": f"Customer {customer_id} not found."})

        score = float(record.get_field("churn_risk_score") or 0.0)
        sentiment = float(record.get_field("sentiment_score") or 0.0)
        interactions = connector.filter_by(
            "Interaction", filters={"customer_id": customer_id}, limit=20
        )
        neg_count = sum(
            1 for r in interactions.records if r.get_field("sentiment") == "negative"
        )
        total_interactions = interactions.total_found

        if score >= 0.70:
            risk_label = "HIGH"
            urgency = "Contact within 48 hours"
        elif score >= 0.40:
            risk_label = "MEDIUM"
            urgency = "Schedule outreach within 2 weeks"
        else:
            risk_label = "LOW"
            urgency = "Continue standard cadence"

        return json.dumps({
            "customer_id": customer_id,
            "customer_name": record.display_name,
            "churn_risk_score": score,
            "risk_label": risk_label,
            "urgency": urgency,
            "sentiment_score": sentiment,
            "total_interactions": total_interactions,
            "negative_interactions": neg_count,
            "analysis": (
                f"{record.display_name} has a {risk_label} churn risk "
                f"(score: {score:.2f}). Sentiment: {sentiment:.2f}. "
                f"{neg_count}/{total_interactions} interactions were negative. "
                f"Action: {urgency}."
            ),
        }, default=str)

    register_tool_implementation("analyze_churn_risk", analyze_churn_risk)

    # --- semantic_search_knowledge ---
    def semantic_search_knowledge(query: str, top_k: int = 5) -> str:
        result = retrieval_service.retrieve(query=query, top_k=top_k)
        chunks = [
            {
                "content": r.content,
                "similarity": round(r.similarity_score, 3),
                "source": r.metadata.get("meta_source_name", "unknown"),
            }
            for r in result.results
        ]
        return json.dumps({
            "query": query,
            "chunks_found": result.total_found,
            "results": chunks,
        }, default=str)

    register_tool_implementation("semantic_search_knowledge", semantic_search_knowledge)

    # --- generate_decision_recommendation ---
    def generate_decision_recommendation(
        customer_id: int, context: str = ""
    ) -> str:
        record = connector.get_by_id("Customer", customer_id)
        if record is None:
            return json.dumps({"error": f"Customer {customer_id} not found."})

        score = float(record.get_field("churn_risk_score") or 0.0)
        segment = record.get_field("segment") or "Unknown"

        if score >= 0.70:
            action = "Immediate retention outreach — call within 48 hours"
            confidence = 0.90
        elif score >= 0.40:
            action = "Schedule proactive check-in within 2 weeks"
            confidence = 0.75
        else:
            action = "Maintain standard engagement cadence"
            confidence = 0.85

        return json.dumps({
            "customer_id": customer_id,
            "customer_name": record.display_name,
            "recommended_action": action,
            "confidence": confidence,
            "rationale": (
                f"Churn risk score {score:.2f} for {segment} customer. "
                f"{context}"
            ),
            "risk_level": "HIGH" if score >= 0.70 else "MEDIUM" if score >= 0.40 else "LOW",
        }, default=str)

    register_tool_implementation(
        "generate_decision_recommendation", generate_decision_recommendation
    )

    logger.info(
        "Registered %d concrete tool implementations for customer_management domain.",
        6,
    )
