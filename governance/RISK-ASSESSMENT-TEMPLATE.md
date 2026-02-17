# AI Use Case Risk Assessment Template
### Regulated Insurance & Financial Services Environments

> **Purpose:** Evaluate a proposed GenAI use case before committing to architecture,
> development, or deployment. This template gates progression from Concept → Pilot → Production.
>
> **When to use:** Complete one assessment per distinct AI use case. Reassess when scope,
> data sources, user population, or regulatory environment changes materially.
>
> **Who completes it:** AI/Architecture lead (Sections 1–3), Risk & Compliance (Sections 4–5),
> Legal (Section 6), joint sign-off (Section 7).

---

## Section 1 — Use Case Definition

| Field | Response |
|-------|----------|
| **Use Case Name** | _(e.g., "Underwriting Knowledge Companion")_ |
| **Use Case ID** | _(e.g., AI-UC-2024-001)_ |
| **Business Owner** | |
| **Technical Lead** | |
| **Assessment Date** | |
| **Assessment Version** | v1.0 |
| **Current Stage** | ☐ Concept  ☐ Pilot  ☐ Production  ☐ Reassessment |

### 1.1 Problem Statement
_What business problem does this AI use case solve? What is the cost of not solving it?_

```
[Describe the problem in 2–4 sentences. Be specific about current pain points,
manual effort, error rates, or compliance gaps this use case addresses.]
```

### 1.2 Proposed AI Capability
_What exactly will the AI do? What will it NOT do?_

| In Scope | Out of Scope |
|----------|-------------|
| _(e.g., Retrieve and summarize underwriting policy content)_ | _(e.g., Make final coverage decisions)_ |
| | |
| | |

### 1.3 User Population

| Role | Count (approx.) | Primary Use |
|------|----------------|-------------|
| _(e.g., Junior Underwriters)_ | | |
| _(e.g., Senior Underwriters)_ | | |
| _(e.g., Managers)_ | | |

### 1.4 AI System Type
_Select all that apply:_

- ☐ **RAG System** — Retrieval-augmented generation over internal knowledge
- ☐ **Decision Support** — AI surfaces recommendations; human decides
- ☐ **Autonomous Decision** — AI makes decisions without per-instance human review
- ☐ **Document Processing** — Extraction, summarization, classification
- ☐ **Conversational Agent** — Multi-turn dialogue with users
- ☐ **Agentic Workflow** — AI orchestrates multi-step tasks with tool use

> ⚠️ **Autonomous Decision** systems require additional sign-off from Legal and a dedicated
> explainability review before proceeding to pilot.

---

## Section 2 — Data & Model Inventory

### 2.1 Data Sources

| Data Source | Classification | Contains PII? | Regulatory Constraints | Owner |
|-------------|---------------|---------------|----------------------|-------|
| _(e.g., Policy manuals)_ | Internal | No | None | Underwriting Ops |
| _(e.g., Claims history)_ | Confidential | Yes | GLBA, CCPA | Claims |
| _(e.g., State regulations)_ | Public | No | None | Compliance |
| | | | | |

### 2.2 PII & Sensitive Data Inventory

_List all personal data elements that may be processed by this AI system:_

- ☐ Policyholder name / address
- ☐ Social Security Number (SSN)
- ☐ Date of birth
- ☐ Financial account information
- ☐ Claims history (medical, property)
- ☐ Credit score / financial profile
- ☐ Protected characteristics (race, religion, gender, national origin)
- ☐ None — this system processes no PII

**Data minimization plan:**
```
[Describe how PII will be minimized, anonymized, or excluded from LLM prompts.
Reference content_filter.py PII redaction controls if applicable.]
```

### 2.3 AI Model & Infrastructure

| Component | Technology | Version / Deployment |
|-----------|-----------|---------------------|
| LLM | _(e.g., Azure OpenAI GPT-4)_ | |
| Embedding Model | _(e.g., text-embedding-ada-002)_ | |
| Vector Database | _(e.g., Azure AI Search)_ | |
| Orchestration | _(e.g., LangChain, custom Python)_ | |
| Hosting | _(e.g., Azure AKS)_ | |

### 2.4 Third-Party AI Dependencies
_Any external AI services, APIs, or models used?_

| Vendor | Service | Data Sent to Vendor | Data Retention Policy |
|--------|---------|--------------------|-----------------------|
| _(e.g., Microsoft Azure)_ | OpenAI API | Sanitized query text | 30-day rolling |
| | | | |

> ⚠️ Verify vendor DPA (Data Processing Agreement) covers your data classification
> before sending any data to third-party AI services.

---

## Section 3 — Risk Identification

### 3.1 Risk Scoring Matrix

Rate each risk dimension on likelihood (1–3) and impact (1–3).
**Risk Score = Likelihood × Impact** (1–9 scale).

| Risk Category | Risk Description | Likelihood (1–3) | Impact (1–3) | Score | Mitigation |
|--------------|-----------------|-----------------|-------------|-------|-----------|
| **Hallucination** | AI generates factually incorrect policy interpretations | | | | Citation tracking, HITL for high-risk |
| **Unauthorized Access** | Users retrieve documents above their clearance level | | | | RBAC at retrieval layer |
| **PII Leakage (Input)** | User submits PII in query; sent to LLM API | | | | Input content filter / PII redaction |
| **PII Leakage (Output)** | LLM generates response containing PII | | | | Output content filter |
| **Prompt Injection** | User embeds instructions to override system behavior | | | | Prompt injection detection |
| **Discriminatory Output** | AI produces responses that treat protected classes unfairly | | | | Output compliance filter, quarterly bias audit |
| **Model Drift** | AI behavior degrades as underlying knowledge base ages | | | | Monitoring, refresh cadence |
| **Over-Reliance** | Users stop verifying AI outputs; errors propagate | | | | UI disclaimers, HITL, training |
| **Regulatory Non-Compliance** | AI output conflicts with state insurance regulations | | | | Regulatory doc ingestion, legal review |
| **Data Poisoning** | Malicious content injected into knowledge base | | | | Document ingestion controls, versioning |
| **SLA / Availability** | AI system unavailability disrupts regulated workflows | | | | SRE practices, fallback to manual process |

**Scoring Guide:**
- **1–3**: Low risk — standard controls sufficient
- **4–6**: Medium risk — enhanced controls + monitoring required
- **7–9**: High risk — HITL mandatory + compliance sign-off required before pilot

### 3.2 Composite Risk Level

_Based on highest individual scores and overall profile:_

- ☐ **Low** (all scores 1–3) — Standard controls, proceed to pilot with documentation
- ☐ **Medium** (any score 4–6) — Enhanced controls required, quarterly review
- ☐ **High** (any score 7–9) — HITL mandatory, Compliance + Legal sign-off required
- ☐ **Critical** (score 9 or autonomous decision-making) — Executive sponsorship required

### 3.3 Residual Risk After Controls

_After applying all planned mitigations, what risk remains?_

```
[Describe residual risks that cannot be fully mitigated by technical controls.
These are risks the business is accepting by proceeding with this use case.]
```

**Risk acceptance sign-off required from:** _(name / role)_

---

## Section 4 — Governance Controls Required

### 4.1 Mandatory Controls Checklist

_Based on risk assessment — mark each as Implemented / Planned / Not Applicable:_

**Access Control:**
- ☐ Role-based access control (RBAC) at retrieval layer — see `examples/rbac-gateway/`
- ☐ Authentication via Azure Active Directory
- ☐ Session-level audit logging
- ☐ Principle of least privilege enforced for all roles

**Human Oversight:**
- ☐ Human-in-the-loop (HITL) for high-risk query types — see `examples/hitl-approval-gate/`
- ☐ HITL SLA defined: ______ minutes
- ☐ Escalation path for SLA breaches defined
- ☐ Reviewer training completed

**Explainability & Attribution:**
- ☐ Citation tracking on all AI responses — see `examples/citation-tracker/`
- ☐ Source document links surfaced in UI
- ☐ Confidence/relevance scores visible to users
- ☐ "How was this answer generated?" user-facing explanation available

**Content Safety:**
- ☐ PII redaction on inputs — see `examples/content-filter/`
- ☐ Prompt injection detection active
- ☐ Output compliance filter active (discriminatory language, legal conclusions)
- ☐ Blocked topic list reviewed and approved by Legal

**Audit & Monitoring:**
- ☐ Immutable audit log for all pipeline events — see `examples/audit-logger/`
- ☐ Tamper-detection (hash chain) implemented
- ☐ Audit retention policy defined: ______ years
- ☐ Real-time alerting on CRITICAL audit events
- ☐ SIEM / Azure Monitor integration configured

**Incident Response:**
- ☐ AI incident response playbook exists
- ☐ Rollback procedure for model/data updates documented
- ☐ User feedback mechanism ("flag this response") implemented
- ☐ On-call escalation path for AI failures defined

### 4.2 HITL Risk Thresholds

_Define the specific criteria that trigger human review for this use case:_

| Trigger Condition | Action |
|------------------|--------|
| _(e.g., Response contains "deny coverage")_ | Route to HITL queue |
| _(e.g., Response references exception_guidelines docs)_ | Route to HITL queue |
| _(e.g., Query from junior role about policy limits)_ | Add disclaimer |
| _(e.g., Citation coverage < 50%)_ | Block response, log for review |

---

## Section 5 — Regulatory & Compliance Mapping

### 5.1 Applicable Regulations

_Check all that apply to this use case:_

**Insurance-Specific:**
- ☐ State Department of Insurance (DOI) regulations — specify states: ____________
- ☐ NAIC Model Laws and Guidelines
- ☐ Fair Credit Reporting Act (FCRA) — if using credit data in underwriting
- ☐ Americans with Disabilities Act (ADA) — if AI makes coverage decisions

**Financial / Data Privacy:**
- ☐ Gramm-Leach-Bliley Act (GLBA) — financial data protection
- ☐ California Consumer Privacy Act (CCPA)
- ☐ GDPR — if any EU data subjects
- ☐ SOC 2 Type II — organizational controls

**AI-Specific:**
- ☐ NIST AI Risk Management Framework (AI RMF) — see `governance/NIST-AI-RMF-MAPPING.md`
- ☐ ISO/IEC 42001 — AI Management Systems
- ☐ EU AI Act — High Risk AI System classification (if applicable)
- ☐ Colorado SB 21-169 — Algorithmic insurance decisions

### 5.2 Regulatory Risk Summary

```
[Describe specific regulatory requirements this use case must satisfy.
Include any regulatory guidance received from Legal or external counsel.]
```

### 5.3 Compliance Team Review

| Reviewer | Role | Review Date | Finding | Sign-Off |
|----------|------|-------------|---------|---------|
| | Compliance Officer | | ☐ No findings  ☐ Findings (see below) | ☐ |
| | Legal Counsel | | ☐ No findings  ☐ Findings (see below) | ☐ |
| | Data Privacy Officer | | ☐ No findings  ☐ Findings (see below) | ☐ |

**Compliance findings (if any):**
```
[List any compliance requirements or restrictions that must be addressed
before this use case can proceed to the next stage.]
```

---

## Section 6 — Bias & Fairness Assessment

### 6.1 Potential Bias Vectors

_For each, describe the risk and planned mitigation:_

**Training Data Bias:**
```
[Does the knowledge base reflect current, accurate, and representative
information? Are there gaps or historical biases embedded in source documents?]
```

**Retrieval Bias:**
```
[Could the vector search favor certain document types, vintages, or perspectives
over others? How will retrieval quality be monitored for consistency?]
```

**Protected Characteristics:**
```
[List any protected characteristics (race, gender, age, religion, national origin,
disability) that could be implicitly or explicitly referenced in retrieved documents
or AI outputs. Describe controls.]
```

### 6.2 Bias Testing Plan

| Test Type | Frequency | Responsible Party | Pass Criteria |
|-----------|-----------|------------------|---------------|
| Demographic parity testing | Quarterly | AI/ML Lead | ≤5% response variation across groups |
| Adversarial prompt testing | Pre-launch + quarterly | Security + Compliance | Zero discriminatory outputs |
| Document coverage audit | Semi-annually | Knowledge Management | No systematic gaps by geography/type |

---

## Section 7 — Stage Gate Sign-Off

### 7.1 Concept → Pilot Gate

_Required before beginning any pilot or proof-of-concept:_

| Condition | Status |
|-----------|--------|
| Risk assessment completed (Sections 1–6) | ☐ Complete |
| Risk level determined | ☐ Low  ☐ Medium  ☐ High  ☐ Critical |
| All High/Critical risks have mitigation plans | ☐ Yes  ☐ No (block) |
| Data inventory completed | ☐ Complete |
| Applicable regulations identified | ☐ Complete |
| Compliance team notified | ☐ Yes |

**Pilot Gate Decision:**
- ☐ **Approved** — Proceed to pilot with controls documented above
- ☐ **Approved with conditions** — Conditions: ____________
- ☐ **Deferred** — Reason: ____________
- ☐ **Rejected** — Reason: ____________

| Approver | Role | Date | Signature |
|----------|------|------|-----------|
| | AI Architecture Lead | | |
| | Risk Officer | | |

---

### 7.2 Pilot → Production Gate

_Required before production deployment. All mandatory controls must be Implemented:_

| Condition | Status |
|-----------|--------|
| All Section 4.1 mandatory controls implemented | ☐ Complete |
| Pilot results reviewed (accuracy, HITL rates, user feedback) | ☐ Complete |
| Incident response playbook tested | ☐ Complete |
| Legal sign-off obtained | ☐ Yes |
| Compliance sign-off obtained | ☐ Yes |
| Security review completed | ☐ Yes |
| User training completed | ☐ Yes |
| Rollback plan documented and tested | ☐ Yes |
| Monitoring dashboards live | ☐ Yes |

**Production Gate Decision:**
- ☐ **Approved** — Proceed to production
- ☐ **Approved with conditions** — Conditions: ____________
- ☐ **Deferred** — Reason: ____________
- ☐ **Rejected** — Reason: ____________

| Approver | Role | Date | Signature |
|----------|------|------|-----------|
| | AI Architecture Lead | | |
| | Risk Officer | | |
| | Compliance Officer | | |
| | Legal Counsel | | |
| | CISO / Security Lead | | |

---

## Section 8 — Ongoing Review Schedule

| Review Type | Frequency | Trigger Events |
|-------------|-----------|----------------|
| Governance controls audit | Quarterly | — |
| Bias & fairness testing | Quarterly | New user populations |
| Risk reassessment | Annually | Regulatory changes, model updates, scope changes |
| Full re-assessment | When triggered | Significant scope change, security incident, adverse regulatory finding |

**Next scheduled review date:** ____________

**Review owner:** ____________

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0 | | | Initial assessment |
| | | | |

---

> **Note:** This template is based on production governance practices for GenAI systems
> in regulated insurance environments. It reflects controls aligned with NIST AI RMF,
> ISO/IEC 42001, and standard insurance regulatory expectations. Adapt to your
> organization's specific regulatory obligations and risk appetite.
