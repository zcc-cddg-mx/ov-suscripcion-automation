# 🧠 Secure End-to-End Agent Orchestration Architecture (Final Version)

## 1. High-Level Overview

This architecture defines a **secure, container-based, event-driven automation pipeline**, where a Jira ticket is transformed into a **code change, validated and deployed automatically**.

### 🔑 Key Principles

* **Separation of concerns**
  * Code Agent → code generation only
  * n8n → orchestration + DevOps control
* **Containerized execution**
* **Network isolation (public vs internal)**
* **PR-driven validation and deployment**
* **n8n as central control plane**

***

## 2. Network Architecture

### 🌐 Public Network

Components exposed externally:

* Jira
* n8n Robot
* Code Agent (container endpoint)
* QA Agent (container endpoint)

**Purpose:**

* Event ingestion
* Orchestration
* Controlled agent triggering (via HTTP APIs)

***

### 🔒 Internal Network

* Application servers (DEV environment)
* Docker runtime services
* Azure DevOps deployment targets

**Purpose:**

* Secure execution
* Deployment
* Runtime validation

***

## 3. Core Components

### 3.1 Jira

* Entry point for requests
* Uses predefined templates
* Emits **webhook on ticket creation**

***

### 3.2 n8n Robot (Central Orchestrator)

Runs in public network.

#### Responsibilities:

* Normalize Jira tickets
* Execute orchestration logic
* Call agent APIs
* Handle responses
* Execute Azure CLI commands
* Manage workflow state
* Update Jira

***

### 3.3 Enricher Agent (within n8n)

* Runs as part of n8n workflow
* Uses LLM (Claude)

#### Responsibilities:

* Interpret ticket
* Generate structured technical requirement

#### Output example:

```json
{
  "type": "request",
  "technical_requirement": {
    "summary": "...",
    "steps": [...],
    "files_expected": [...],
    "constraints": [...]
  }
}
```

***

## 4. Code Agent (Containerized Service) 🚧

### 📦 Deployment

* Containerized service
* Hosted in SERVICIOSIAS (UAT farm)
* Exposed via **controlled public endpoint**

***

### ⚙️ Responsibilities

The Code Agent is a **pure execution engine**:

#### 1. Listener (API)

* Receives request from n8n
* Implemented in Python

***

#### 2. Git Operations

* Create feature branch → `git + shell`

***

#### 3. Code Generation

* Modify / generate:
  * Java code
  * Python scripts
  * Excel files

***

#### 4. Build Step

* Compile project → `Java`

***

#### 5. Push Changes

* Push branch to Azure Repos → `git + shell`

***

#### 6. ✅ Notify n8n (NEW CRITICAL STEP)

The Code Agent **DOES NOT create PRs anymore**

Instead, it sends a response:

```json
{
  "status": "success",
  "branch": "feature/auto-change-123",
  "commit_id": "abc123",
  "repo": "project-repo",
  "build_status": "success",
  "summary": "Code generated and pushed successfully"
}
```

***

## 5. n8n as DevOps Controller (NEW ROLE)

After receiving Code Agent response:

### Responsibilities:

#### 1. Create Pull Request

* Uses:
  * Azure CLI OR Azure DevOps API
* Inputs:
  * Branch name
  * Target branch

***

#### 2. Monitor PR & Pipeline

Tracks:

* Build status
* Deployment status

***

#### 3. Control Flow Decisions

* If success → trigger QA
* If failure → log + update Jira

***

## 6. Azure DevOps Pipeline

Triggered after PR creation.

### Responsibilities:

* Build
* Deploy to DEV server

***

### Environment:

* Internal network
* Docker-based services

***

## 7. QA Agent (Containerized Service)

### 📦 Deployment

* Container in SERVICIOSIAS
* Public endpoint (controlled access)

***

### ⚙️ Responsibilities

#### 1. Listener (API)

* Receives validation request from n8n

***

#### 2. Endpoint Validation

* Uses:
  * Shell scripts
  * Python
* Validates:
  * APIs
  * Services availability

***

#### 3. Data Validation

* Validates correctness of outputs

***

### Output:

```json
{
  "status": "approved | rejected",
  "observations": [...]
}
```

***

## 8. Full End-to-End Flow

```text
1. Jira
   → New ticket created (webhook)

2. n8n
   → Normalize ticket
   → Generate context

3. Enricher Agent (n8n)
   → Build structured technical requirement

4. Code Agent (container)
   → Receive request
   → Create branch
   → Modify code (Python / Java / Excel)
   → Compile
   → Push changes (Azure Repos)
   → Send response to n8n

5. n8n
   → Create PR (Azure CLI / API)
   → Monitor PR and pipeline

6. Azure DevOps
   → Execute pipeline
   → Deploy to DEV environment (internal network)

7. n8n
   → Trigger validation

8. QA Agent (container)
   → Validate endpoints and data
   → Return result

9. n8n
   → Update Jira:
       - PR link
       - QA result
   → Close ticket (if approved)
```

***

## 9. Key Architectural Advantages

### ✅ 1. Strong Separation of Responsibilities

* Code Agent = execution engine
* n8n = orchestration + DevOps brain

***

### ✅ 2. Security Improvements

* Code Agent does NOT manage PRs
* Reduced permissions surface
* Clear boundaries between services

***

### ✅ 3. Centralized Control Plane

* n8n controls:
  * PR lifecycle
  * Pipeline monitoring
  * QA triggering

***

### ✅ 4. Scalability

* Agents = stateless containers
* Can scale independently

***

### ✅ 5. Extensibility

Future additions become easy:

* Security scans
* Approval gates
* Multi-env deployments
* Additional agents

***

## 10. Critical Design Contracts (Implicit but Key)

This architecture **depends heavily on contracts**:

### Between n8n ↔ Code Agent

* Structured requirement JSON
* Deterministic response schema

### Between n8n ↔ QA Agent

* PR + endpoint context
* Validation schema

***

## 🔥 Suggested Next Step (High Impact)

Ahora que la arquitectura está sólida, el siguiente paso más valioso sería:

👉 Definir formalmente:

### 1. API Contract del Code Agent (request/response + errores)

### 2. Error handling strategy (retry, fallback, idempotency)

### 3. Execution model (sync vs async con callbacks/webhooks)