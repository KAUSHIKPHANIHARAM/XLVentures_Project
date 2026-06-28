# Enterprise Reusable Agentic Decision Intelligence Platform

## Overview

A domain-agnostic, configuration-driven, agentic decision intelligence platform built for enterprise hackathon demonstration. The platform uses LangGraph for orchestration, OpenAI GPT for reasoning, ChromaDB for semantic memory, and Streamlit for visualization. It is designed so the **entire workflow, domain knowledge, agents, and business logic are driven by YAML configuration** — swapping domains requires only a config change, not code changes.

---

## Architecture Principles Applied

| Principle | How It's Applied |
|---|---|
| Clean Architecture | Domain → Application → Infrastructure layering |
| SOLID | Each class has one reason to change; interfaces everywhere |
| Separation of Concerns | Agents, memory, decisions, connectors all isolated |
| Interface-Driven Dev | Abstract base classes define all contracts |
| Configuration-Driven | YAML controls agents, workflows, schemas, prompts |
| Dependency Injection | All services injected at runtime via registries |
| Composition over Inheritance | Capabilities composed from mixins/providers |

---

## Full Module Dependency Map

```
config/          ← YAML schemas + loaders (no deps)
schemas/         ← Pydantic models (depends on config)
models/          ← Domain entity models (depends on schemas)
connectors/      ← Abstract data source interfaces (depends on models)
memory/          ← ChromaDB vector memory (depends on connectors, models)
knowledge/       ← Domain knowledge ingestion (depends on memory)
registry/        ← Agent + tool registry (depends on schemas)
agents/          ← LangGraph agents (depends on registry, memory, decision)
planner/         ← Intent parser + task decomposer (depends on agents)
workflow/        ← LangGraph graph orchestrator (depends on planner, agents)
decision/        ← Decision engine + explainability (depends on agents, memory)
data/            ← SQLite + seed data (depends on connectors)
utils/           ← Logging, helpers (no deps)
frontend/        ← Streamlit UI (depends on workflow, decision)
app/             ← Entry point (wires everything)
```

---

## Build Order (Module by Module)

Each module is built independently and in dependency order. No module is skipped.

| # | Module | Description | Status |
|---|---|---|---|
| 1 | `config/` | YAML config loader, environment resolver, config schema | 🔲 |
| 2 | `schemas/` | Pydantic base models for agents, tools, decisions, domains | 🔲 |
| 3 | `models/` | Domain entity models (generic, not customer-specific) | 🔲 |
| 4 | `utils/` | Logging factory, common helpers | 🔲 |
| 5 | `connectors/` | Abstract connector interface + SQLite implementation | 🔲 |
| 6 | `data/` | SQLite setup, seed loader, migration utils | 🔲 |
| 7 | `memory/` | ChromaDB vector memory interface + implementation | 🔲 |
| 8 | `knowledge/` | Domain knowledge ingestion + retrieval | 🔲 |
| 9 | `registry/` | Agent registry, tool registry, domain registry | 🔲 |
| 10 | `agents/` | Base agent, tool-calling agent, LangGraph nodes | 🔲 |
| 11 | `planner/` | Intent classifier, task planner, query decomposer | 🔲 |
| 12 | `decision/` | Decision engine, scoring, explainability | 🔲 |
| 13 | `workflow/` | LangGraph graph builder, state machine, orchestrator | 🔲 |
| 14 | `frontend/` | Streamlit UI, domain switcher, decision viewer | 🔲 |
| 15 | `app/` | Bootstrap, wiring, entry point | 🔲 |

---

## Module 1: `config/` — Detailed Design

### Responsibility
Load, validate, and expose all platform configuration from YAML files. This module is the **single source of truth** for all runtime behavior.

### Files to Create

#### [NEW] `config/__init__.py`
#### [NEW] `config/settings.py`
Main `PlatformConfig` dataclass — loaded once at startup.

#### [NEW] `config/loader.py`
- `ConfigLoader` class — reads YAML, resolves env vars, merges configs.
- Supports multiple YAML files (base + domain override).

#### [NEW] `config/resolver.py`
- `EnvResolver` — replaces `${ENV_VAR}` patterns in YAML with actual env values.

#### [NEW] `config/validator.py`
- `ConfigValidator` — validates loaded config against Pydantic schemas.

#### [NEW] `config/schemas.py`
- Pydantic models for `LLMConfig`, `VectorDBConfig`, `DatabaseConfig`, `AgentConfig`, `WorkflowConfig`, `DomainConfig`.

#### [NEW] `config/platform.yaml`
Base platform configuration (LLM, DB, vector store settings).

#### [NEW] `config/domains/customer_management.yaml`
First domain configuration (agents, tools, workflows, prompts, schema).

---

## Open Questions

> [!IMPORTANT]
> **Q1**: Should I start with **Module 1: `config/`** as the foundation? This is the recommended starting point since every other module depends on it.

> [!IMPORTANT]
> **Q2**: For the OpenAI API key — should it be loaded from a `.env` file using `python-dotenv`, or from environment variables only?

> [!IMPORTANT]
> **Q3**: Should the `customer_management.yaml` domain config define agent prompts inline in YAML, or reference external `.txt`/`.jinja2` prompt template files?

> [!IMPORTANT]
> **Q4**: What is the workspace root path? I'll set up the project under `c:\Users\chait\on pc\XL ventures\` — confirm this is correct.

---

## Verification Plan

### Per Module
- Each module will include a `__init__.py` that exports its public API.
- Each module will include a `tests/` stub or inline smoke test where applicable.
- Pydantic validation ensures correctness at load time.

### Integration
- After all modules are complete, a full integration walkthrough with the Customer Management demo will be run via Streamlit.
