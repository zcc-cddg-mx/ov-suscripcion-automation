A continuación tienes una **traducción estructurada y explicada del diagrama**, lista para dársela a Claude como contexto de arquitectura. La redacté en inglés técnico (más adecuado para modelos como Claude) e incorporé explícitamente el rol actual del **Agente Código** que mencionaste.

***

# 🧠 End-to-End Agent Orchestration Architecture (Jira → Code → Deployment)

## 1. High-Level Overview

This architecture defines an **end-to-end automated workflow** that starts when a user creates a new Jira ticket and finishes with a **code change and deployment-ready artifact**.

The orchestration is based on a sequence of specialized agents, each responsible for a specific stage of the lifecycle:

1. Ticket ingestion and normalization
2. Ticket classification
3. Technical requirement enrichment
4. QA validation
5. Code generation and repository update

***

## 2. Actors / Components

* **Jira**: Source of incoming requests (issues, changes, incidents)
* **n8n Robot (Orchestrator)**: Workflow engine that coordinates the agents
* **Classifier Agent**
* **Enricher Agent**
* **QA Agent**
* **Code Agent (currently under development)**
* **Azure Repos**: Code repository for version control

***

## 3. End-to-End Flow Description

### Step 1 — Ticket Creation (Trigger)

* A new Jira ticket is created.
* Jira emits a **webhook event**.
* The webhook triggers the **n8n Robot**.

### Step 2 — Ticket Normalization (n8n)

* The orchestration layer:
  * Extracts ticket data (title, description, metadata)
  * Normalizes the structure into a consistent format
* It then sends the **clean ticket context** to the next agent.

***

### Step 3 — Classification (Classifier Agent)

* The Classifier Agent:
  * Analyzes the ticket using **Claude (ReAct pattern)**
  * Determines the **type of request**, e.g.:
    * Incident
    * Infra
    * Requirement
    * Support

**Output:**

* Ticket enriched with a **classification label**
* Structured semantic understanding of the request

***

### Step 4 — Technical Enrichment (Enricher Agent)

* Takes the classified ticket and:
  * Expands it into a **structured technical requirement**
  * Adds:
    * Functional expectations
    * Technical details
    * Possible constraints
    * Implementation hints (if applicable)

**Output:**

* Fully **structured technical requirement**
* Better suited for downstream automation (especially code generation)

***

### Step 5 — QA Validation (QA Agent)

* The QA Agent evaluates:
  * Completeness of the requirement
  * Consistency and clarity
  * Testability
* Produces one of two outcomes:
  * ✅ **Validated**
  * ❌ **Rejected with reason**

**Output:**

* Validated requirement OR rejection feedback

***

### Step 6 — Code Generation (Code Agent) 🚧 *Current Focus*

> You are currently working on this agent.

The Code Agent is responsible for:

* Receiving a **validated technical requirement**
* Generating code using **Claude Code capabilities**

### Current Scope (based on your note):

* Python-based agent capable of:
  * Reading and writing **Excel files**
  * Reading and modifying **Java code**
* Automates low-complexity change requests

### Responsibilities:

* Generate source code changes
* Ensure consistency with requirement
* Prepare changes for version control

***

### Step 7 — Repository Integration (Azure Repos)

* The Code Agent:
  * Creates a **new branch**
  * Commits generated changes
  * Opens a **Pull Request (PR)**

***

### Step 8 — Jira Update (Feedback Loop)

* The orchestrator (n8n Robot):
  * Updates the Jira ticket with:
    * PR link
  * Changes status to:
    * **"En revisión" (In Review)**

***

## 4. Sequence Summary

```text
Jira (Webhook)
  ↓
n8n (Normalize + Orchestrate)
  ↓
Classifier Agent (Claude - ReAct)
  ↓
Enricher Agent (Structured Requirement)
  ↓
QA Agent (Validation)
  ↓
Code Agent (Generate Code, Python + Java + Excel)
  ↓
Azure Repos (Branch + PR)
  ↓
n8n (Update Jira Ticket)
```

***

## 5. Key Design Principles

* ✅ **Agent specialization**: Each agent solves one problem well
* ✅ **LLM-driven reasoning (Claude)** for classification and generation
* ✅ **Orchestration-first design (n8n)**
* ✅ **Structured outputs between agents** (critical for automation)
* ✅ **Incremental automation** (starting with low complexity tickets)

***

## 6. Notes for Claude (Important Context)

* The system is **already orchestrated by n8n**
* The pipeline is **sequential and deterministic**
* The **Code Agent is under active development**, focused on:
  * Python scripting
  * Excel manipulation
  * Java code modification
* Current use cases are intentionally **low complexity**
* The goal is **progressive automation maturity**

***