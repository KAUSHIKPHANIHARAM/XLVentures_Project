# Team Members

* Phaniharam venkata ram kaushik
* Kakumanu chaitanya
* Akula rithwik

---

# GitHub Repository

Repository:

https://github.com/Chintu-0511/SentinalAI

---

# Reusable Agentic Decision Intelligence Platform

## XLVentures Hackathon Submission

---

## Project Overview

The **Reusable Agentic Decision Intelligence Platform** is an enterprise AI platform designed to help organizations make intelligent, explainable, and governed business decisions by integrating information from multiple enterprise systems.

Unlike traditional AI assistants that focus on answering questions, our platform focuses on **Decision Intelligence**—collecting enterprise context, retrieving organizational knowledge, reasoning over business information, validating recommendations against organizational policies, and executing approved actions through enterprise integrations.

The platform has been intentionally designed as a **domain-agnostic reusable architecture**.

While the demonstration focuses on **Customer Success Management**, the same architecture can support Sales, Staffing, HR, Healthcare, Procurement, Finance, and other enterprise domains through configuration rather than code changes.

---

# Problem Statement

Enterprise organizations store business information across multiple disconnected systems such as:

* CRM Systems
* Email Platforms
* Meeting Platforms
* Support Ticketing Systems
* Internal Knowledge Bases
* SQL Databases
* Collaboration Platforms

Business users spend significant time gathering information before making decisions.

This results in:

* Fragmented context
* Manual reasoning
* Slow decision making
* Inconsistent recommendations
* Poor knowledge reuse

---

# Our Solution

The platform provides a reusable decision intelligence layer that:

* Understands business intent
* Retrieves enterprise context
* Retrieves organizational knowledge
* Retrieves historical organizational memory
* Creates a Unified Business Context
* Recommends the Next Best Action
* Validates recommendations
* Explains AI reasoning
* Supports Human-in-the-Loop approval
* Executes approved business actions
* Learns from previous interactions

---

# Key Features

* Reusable capability-based architecture
* Configuration-driven workflows
* Enterprise connector framework
* Retrieval-Augmented Generation (RAG)
* Unified Business Context
* Explainable AI recommendations
* Confidence scoring
* Validation against business rules
* Human approval before execution
* Organizational memory
* Extensible connector ecosystem

---

# Technology Stack

## Frontend

* Streamlit

## Backend

* Python

## Agent Orchestration

* LangGraph

## Language Model

* OpenAI GPT

## Embeddings

* OpenAI Embeddings

## Vector Database

* ChromaDB

## Database

* SQLite

## Configuration

* YAML

## Validation

* Pydantic

---

# Architecture Overview

The platform follows a modular architecture consisting of:

* Planner Agent
* Workflow Manager
* Capability Registry
* Context Intelligence Agent
* Knowledge Agent
* Memory Agent
* Connector Manager
* Enterprise Connectors
* Unified Business Context
* Decision Intelligence Engine
* Validation Layer
* Confidence Scorer
* Explanation Agent
* Human Approval
* Tool Executor
* Memory Update

Each component has a single responsibility and can evolve independently.

---

# Demo Use Case

Customer Success Management

Scenario:

> Identify customers at risk of churn and recommend the most appropriate business action.

The platform:

1. Retrieves CRM information
2. Retrieves customer emails
3. Retrieves meeting history
4. Retrieves company retention policies
5. Builds unified business context
6. Performs AI reasoning
7. Validates recommendations
8. Explains reasoning
9. Waits for manager approval
10. Executes approved actions
11. Stores organizational memory

---

# Project Structure

```
app/
agents/
planner/
workflow/
registry/
connectors/
knowledge/
memory/
decision/
frontend/
config/
schemas/
models/
utils/
```

---

# Installation

```bash
git clone <repository_url>

cd project

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

---

# Running the Platform

```bash
streamlit run app.py
```

---

# Future Extensibility

The platform supports new business domains by adding:

* New workflow configuration
* New connectors
* New prompt templates
* New knowledge base
* Domain-specific policies

No architectural changes are required.

---



