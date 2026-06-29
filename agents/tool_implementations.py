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
import re
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
    import os
    from registry.tool_registry import register_tool_implementation

    # Demo mode: deterministic, hardcoded responses to avoid external LLM calls
    DEMO = os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")
    if DEMO:
        logger.info("DEMO_MODE active: registering deterministic tool implementations.")

        def _demo_search_customers(query: str = "", segment: str = "", min_churn_risk: float = 0.0, limit: int = 20) -> str:
            # Simple deterministic mapping for demo/testing
            demo_customers = [
                {"id": 1, "customer_id": "CUST-001", "company_name": "Acme Corp", "name": "Sarah Mitchell", "registered_email": "sarah@acme.com", "segment": "Premium", "churn_risk_score": 0.15},
                {"id": 2, "customer_id": "CUST-002", "company_name": "Globex Inc", "name": "James Thornton", "registered_email": "james@globex.com", "segment": "Premium", "churn_risk_score": 0.78},
            ]
            results = [c for c in demo_customers if (not query or query.lower() in (c['company_name']+c['name']+c['registered_email']).lower())]
            results = [c for c in results if c['churn_risk_score'] >= min_churn_risk]
            return json.dumps({"total_found": len(results), "customers": results[:limit]}, default=str)

        register_tool_implementation("search_customers", _demo_search_customers)

        def _demo_get_customer_detail(customer_id: str | int) -> str:
            if str(customer_id).upper() in ("CUST-002", "2"):
                return json.dumps({
                    "customer": {"full_name": "James Thornton", "company_name": "Globex Inc", "customer_id": "CUST-002", "registered_email": "james@globex.com", "churn_risk_score": 0.78, "contract_end_date": "2026-09-30"},
                    "customer_id": 2,
                    "display_name": "James Thornton",
                    "risk_level": "HIGH",
                    "negative_interactions": 2,
                    "account_health": "At risk",
                    "renewal_urgent": True,
                }, default=str)
            return json.dumps({"error": f"Customer '{customer_id}' not found."})

        register_tool_implementation("get_customer_detail", _demo_get_customer_detail)

        def _demo_analyze_churn_risk(customer_id: str | int) -> str:
            if str(customer_id).upper() in ("CUST-002", "2"):
                return json.dumps({
                    "customer_id": 2,
                    "customer_name": "James Thornton",
                    "churn_risk_score": 0.78,
                    "risk_label": "HIGH",
                    "urgency": "Contact within 48 hours",
                    "recommendation": "Immediate retention outreach with senior account management.",
                    "analysis": "Multiple recent negative interactions and high churn signal. Prioritise immediate outreach."
                }, default=str)
            return json.dumps({"error": f"Customer {customer_id} not found."})

        register_tool_implementation("analyze_churn_risk", _demo_analyze_churn_risk)

        def _demo_semantic_search_knowledge(query: str, top_k: int = 5) -> str:
            # Return canned policy excerpt for billing disputes
            snippets = [
                {"content": "Billing dispute policy: investigate within 3 business days and escalate to finance if unresolved.", "similarity": 0.95},
            ]
            return json.dumps({"results": snippets[:top_k]}, default=str)

        register_tool_implementation("semantic_search_knowledge", _demo_semantic_search_knowledge)

        def _demo_get_interaction_history(customer_id: str | int, limit: int = 10) -> str:
            # Provide canned interactions including sentiment and timestamps for demo customers
            cid = str(customer_id).upper()
            if cid in ("CUST-003", "3"):
                interactions = [
                    {"id": 101, "channel": "email", "subject": "Onboarding feedback", "sentiment": "positive", "created_at": "2026-03-01T10:15:00Z", "content": "Great onboarding experience."},
                    {"id": 102, "channel": "chat", "subject": "Feature request", "sentiment": "neutral", "created_at": "2026-04-12T09:30:00Z", "content": "Can you add export to CSV?"},
                    {"id": 103, "channel": "ticket", "subject": "Support delay", "sentiment": "negative", "created_at": "2026-05-20T14:05:00Z", "content": "Support response took too long."},
                ]
                return json.dumps({
                    "customer_id": 3,
                    "total_interactions": len(interactions),
                    "interactions": interactions[:limit],
                }, default=str)

            # Default: empty
            return json.dumps({"customer_id": customer_id, "total_interactions": 0, "interactions": []})

        register_tool_implementation("get_interaction_history", _demo_get_interaction_history)

        def _demo_generate_decision_recommendation(customer_id: str | int, context: str = "") -> str:
            if str(customer_id).upper() in ("CUST-002", "2"):
                return json.dumps({
                    "action": "Initiate retention call with senior account manager and offer targeted incentive.",
                    "confidence_score": 0.85,
                    "rationale": "High churn score (0.78), multiple negative interactions, contract ending soon.",
                    "time_sensitivity": "immediate",
                }, default=str)
            return json.dumps({"error": f"Customer {customer_id} not found."})

        register_tool_implementation("generate_decision_recommendation", _demo_generate_decision_recommendation)

    def _normalize_entity_id(value: str | int) -> str | int:
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return value

    # --- search_customers ---
    def search_customers(
        query: str = "",
        segment: str = "",
        min_churn_risk: float = 0.0,
        limit: int = 20,
    ) -> str:
        """
        Search customers by identifier, name, email, company name, notes, segment,
        and minimum churn risk score.

        Args:
            query:          Text to search across customer identifier, name, company,
                            email, or notes. Leave blank to list all customers.
            segment:        Filter by exact segment — "Premium", "Standard", or "Trial".
            min_churn_risk: Only return customers with churn_risk_score >= this value (0.0–1.0).
                            Use 0.7 for HIGH risk, 0.4 for MEDIUM+ risk.
            limit:          Maximum number of results to return (default 20).
        """
        fetch_limit = min(limit * 5, 100)
        filters = {"segment": segment} if segment else None
        query_text = (query or "").strip()

        if query_text:
            if re.fullmatch(r"(?i)CUST[- ]?\d{1,5}", query_text):
                filters = {"customer_id": query_text.upper(), **(filters or {})}
                query_text = ""
            elif re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", query_text):
                filters = {"registered_email": query_text.lower(), **(filters or {})}
                query_text = ""

        result = connector.search("Customer", query=query_text, filters=filters, limit=fetch_limit)

        records = []
        for r in result.records:
            churn_score = float(r.get_field("churn_risk_score") or 0.0)
            if churn_score < min_churn_risk:
                continue
            records.append({
                "id": r.entity_id,
                "customer_id": r.get_field("customer_id"),
                "company_name": r.get_field("company_name"),
                "name": r.display_name,
                "registered_email": r.get_field("registered_email"),
                "segment": r.get_field("segment"),
                "churn_risk_score": churn_score,
                "risk_level": "HIGH" if churn_score >= 0.70 else "MEDIUM" if churn_score >= 0.40 else "LOW",
                "sentiment_score": r.get_field("sentiment_score"),
                "lifetime_value": r.get_field("lifetime_value"),
                "last_interaction_date": r.get_field("last_interaction_date"),
            })
            if len(records) >= limit:
                break

        # Sort by churn_risk_score descending (highest risk first)
        records.sort(key=lambda x: x["churn_risk_score"], reverse=True)

        return json.dumps({
            "total_found": len(records),
            "filters_applied": {
                "segment": segment or "any",
                "min_churn_risk": min_churn_risk,
                "query": query,
            },
            "customers": records,
        }, default=str)

    register_tool_implementation("search_customers", search_customers)

    # --- get_customer_detail ---
    def get_customer_detail(customer_id: str | int) -> str:
        record = None
        if isinstance(customer_id, int):
            record = connector.get_by_id("Customer", customer_id)
        else:
            lookup_value = str(customer_id).strip()
            if re.fullmatch(r"(?i)CUST[- ]?\d{1,5}", lookup_value):
                search_results = connector.search(
                    "Customer",
                    query=lookup_value.upper(),
                    filters={"customer_id": lookup_value.upper()},
                    limit=1,
                )
                record = search_results.records[0] if search_results.records else None
            elif re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", lookup_value):
                search_results = connector.search(
                    "Customer",
                    query=lookup_value.lower(),
                    filters={"registered_email": lookup_value.lower()},
                    limit=1,
                )
                record = search_results.records[0] if search_results.records else None
            else:
                search_results = connector.search(
                    "Customer",
                    query=lookup_value,
                    limit=1,
                )
                record = search_results.records[0] if search_results.records else None

        if record is None:
            return json.dumps({"error": f"Customer '{customer_id}' not found."})

        interactions = connector.filter_by(
            "Interaction",
            filters={"customer_id": record.entity_id},
            limit=20,
            order_by="created_at",
            descending=True,
        )
        negative_count = sum(
            1 for r in interactions.records if r.get_field("sentiment") == "negative"
        )
        health = "Healthy" if float(record.get_field("churn_risk_score") or 0.0) < 0.4 else "At risk"
        renewal_urgent = False
        contract_end = record.get_field("contract_end_date")
        if contract_end:
            from datetime import datetime
            try:
                end_date = datetime.fromisoformat(contract_end)
                renewal_urgent = (end_date - datetime.now()).days <= 90
            except ValueError:
                renewal_urgent = False

        return json.dumps({
            "customer": record.data,
            "customer_id": record.entity_id,
            "display_name": record.display_name,
            "registered_email": record.get_field("registered_email"),
            "company_name": record.get_field("company_name"),
            "customer_identifier": record.get_field("customer_id"),
            "risk_level": (
                "HIGH" if float(record.get_field("churn_risk_score") or 0.0) >= 0.7
                else "MEDIUM" if float(record.get_field("churn_risk_score") or 0.0) >= 0.4
                else "LOW"
            ),
            "negative_interactions": negative_count,
            "account_health": health,
            "renewal_urgent": renewal_urgent,
            "contract_end_date": contract_end,
            "recent_interaction_date": record.get_field("last_interaction_date"),
        }, default=str)

    register_tool_implementation("get_customer_detail", get_customer_detail)

    # --- get_interaction_history ---
    def get_interaction_history(customer_id: str | int, limit: int = 10) -> str:
        lookup_id = customer_id
        if isinstance(customer_id, str) and not customer_id.isdigit():
            detail = get_customer_detail(customer_id)
            detail_payload = json.loads(detail)
            if detail_payload.get("error"):
                return json.dumps({"error": detail_payload["error"]})
            lookup_id = detail_payload["customer_id"]

        result = connector.filter_by(
            "Interaction",
            filters={"customer_id": lookup_id},
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
            "customer_id": lookup_id,
            "total_interactions": result.total_found,
            "interactions": interactions,
        }, default=str)

    register_tool_implementation("get_interaction_history", get_interaction_history)

    # --- analyze_churn_risk ---
    def analyze_churn_risk(customer_id: str | int) -> str:
        lookup_id = customer_id
        if isinstance(customer_id, str) and not customer_id.isdigit():
            detail = get_customer_detail(customer_id)
            detail_payload = json.loads(detail)
            if detail_payload.get("error"):
                return json.dumps({"error": detail_payload["error"]})
            lookup_id = detail_payload["customer_id"]

        record = connector.get_by_id("Customer", lookup_id)
        if record is None:
            return json.dumps({"error": f"Customer {customer_id} not found."})

        score = float(record.get_field("churn_risk_score") or 0.0)
        sentiment = float(record.get_field("sentiment_score") or 0.0)
        interactions = connector.filter_by(
            "Interaction", filters={"customer_id": lookup_id}, limit=20
        )
        neg_count = sum(
            1 for r in interactions.records if r.get_field("sentiment") == "negative"
        )
        total_interactions = interactions.total_found

        if score >= 0.70:
            risk_label = "HIGH"
            urgency = "Contact within 48 hours"
            recommendation = "Immediate retention outreach with senior account management."
        elif score >= 0.40:
            risk_label = "MEDIUM"
            urgency = "Schedule outreach within 2 weeks"
            recommendation = "Proactive customer check-in and issue resolution planning."
        else:
            risk_label = "LOW"
            urgency = "Continue standard cadence"
            recommendation = "Maintain existing engagement rhythm and monitor sentiment."

        contract_end_date = record.get_field("contract_end_date")
        renewal_note = ""
        if contract_end_date:
            from datetime import datetime
            try:
                end_date = datetime.fromisoformat(contract_end_date)
                days_to_renewal = (end_date - datetime.now()).days
                if days_to_renewal <= 60:
                    renewal_note = f" Renewal planning required within {days_to_renewal} days."
            except ValueError:
                renewal_note = ""

        context_insight_parts = []
        if neg_count >= 1:
            context_insight_parts.append(
                "This customer has multiple recent negative interactions and is evaluating competitors."
            )
        else:
            context_insight_parts.append("This customer has stable sentiment and standard account health.")
        if renewal_note:
            context_insight_parts.append(renewal_note.strip())

        context_insight = " ".join(context_insight_parts)

        policy_checks = []
        if score >= 0.7:
            policy_checks.append("High risk policy: contact within 48 hours and prepare retention incentive.")
        if contract_end_date and renewal_note:
            policy_checks.append("Renewal policy: prepare ROI-based renewal proposal ahead of contract end.")

        return json.dumps({
            "customer_id": lookup_id,
            "customer_name": record.display_name,
            "churn_risk_score": score,
            "risk_label": risk_label,
            "urgency": urgency,
            "sentiment_score": sentiment,
            "total_interactions": total_interactions,
            "negative_interactions": neg_count,
            "renewal_note": renewal_note,
            "policy_checks": policy_checks,
            "recommendation": recommendation,
            "analysis": (
                f"{record.display_name} has a {risk_label} churn risk (score: {score:.2f}). "
                f"Sentiment: {sentiment:.2f}. {neg_count}/{total_interactions} interactions were negative. "
                f"{context_insight} Action: {urgency}."
            ),
        }, default=str)

    register_tool_implementation("analyze_churn_risk", analyze_churn_risk)

    # --- semantic_search_knowledge ---
    def semantic_search_knowledge(query: str, top_k: int = 5) -> str:
        if retrieval_service is None:
            return json.dumps({
                "query": query,
                "chunks_found": 0,
                "results": [],
            }, default=str)

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
        customer_id: str | int, context: str = ""
    ) -> str:
        if isinstance(customer_id, str) and not customer_id.isdigit():
            detail = get_customer_detail(customer_id)
            payload = json.loads(detail)
            if payload.get("error"):
                return json.dumps({"error": payload["error"]})
            lookup_id = payload["customer_id"]
        else:
            lookup_id = customer_id
        record = connector.get_by_id("Customer", lookup_id)
        if record is None:
            return json.dumps({"error": f"Customer {customer_id} not found."})

        score = float(record.get_field("churn_risk_score") or 0.0)
        segment = record.get_field("segment") or "Unknown"
        company = record.get_field("company_name") or "this customer"
        contract_end_date = record.get_field("contract_end_date") or "unknown"
        interactions = connector.filter_by(
            "Interaction",
            filters={"customer_id": lookup_id},
            limit=10,
            order_by="created_at",
            descending=True,
        )
        interaction_text = " ".join(
            str(r.get_field("subject") or "") + ". " + str(r.get_field("content") or "")
            for r in interactions.records[:3]
        )

        issues = []
        if re.search(r"billing|invoice|dispute|overcharge", interaction_text, re.IGNORECASE):
            issues.append("billing dispute")
        if re.search(r"sla|outage|downtime|incident|complaint", interaction_text, re.IGNORECASE):
            issues.append("SLA breach")
        if re.search(r"competitor|salesforce|monday.com|hubspot", interaction_text, re.IGNORECASE):
            issues.append("competitive pressure")
        if re.search(r"trial|onboarding|conversion", interaction_text, re.IGNORECASE):
            issues.append("trial conversion risk")
        if contract_end_date != "unknown":
            from datetime import datetime
            try:
                days_to_renewal = (datetime.fromisoformat(contract_end_date) - datetime.now()).days
                if days_to_renewal <= 60:
                    issues.append("renewal risk")
            except ValueError:
                pass

        if score >= 0.70:
            action = (
                f"Immediate retention outreach for {company}: schedule a senior account call within 48 hours, "
                f"resolve outstanding issues, and offer an incentive aligned with policy."
            )
            confidence = 0.92
        elif score >= 0.40:
            action = (
                f"Schedule a proactive customer review for {company} within 7 days, "
                f"surface key adoption and contract health metrics, and prepare a renewal/retention package."
            )
            confidence = 0.80
        else:
            action = (
                f"Maintain standard engagement cadence for {company}. "
                f"Monitor adoption, confirm contract milestones, and keep the customer informed."
            )
            confidence = 0.82

        alternative_options = []
        if "billing dispute" in issues:
            alternative_options.append(
                "Validate the disputed invoice line items and offer a partial credit if the service issues are confirmed."
            )
        if "SLA breach" in issues:
            alternative_options.append(
                "Provide a formal SLA remediation plan and compensation estimate to the customer."
            )
        if "renewal risk" in issues:
            alternative_options.append(
                "Deliver an ROI-based renewal proposal and align executives on the renewal path."
            )
        if not alternative_options:
            alternative_options.append(
                "Review the customer success plan and identify one upsell or advocacy opportunity."
            )

        risk_label = (
            "HIGH" if score >= 0.70 else "MEDIUM" if score >= 0.40 else "LOW"
        )
        rationale_parts = [
            f"Churn risk is {score:.2f} for a {segment} customer.",
        ]
        if issues:
            rationale_parts.append(f"Observed issues: {', '.join(sorted(set(issues)))}.")
        if contract_end_date != "unknown":
            rationale_parts.append(f"Contract ends {contract_end_date}.")
        if context:
            rationale_parts.append(context)

        return json.dumps({
            "customer_id": lookup_id,
            "customer_name": record.display_name,
            "recommended_action": action,
            "confidence": confidence,
            "rationale": " ".join(rationale_parts),
            "risk_level": risk_label,
            "alternative_options": alternative_options,
            "policy_references": [
                "Churn prevention policy",
                "Billing and escalation policy",
                "Renewal policy",
            ],
        }, default=str)

    register_tool_implementation(
        "generate_decision_recommendation", generate_decision_recommendation
    )

    logger.info(
        "Registered %d concrete tool implementations for customer_management domain.",
        6,
    )
