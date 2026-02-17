# Responsible AI Checklist
### Production GenAI Systems in Regulated Insurance Environments

> **Purpose:** A pre-launch and ongoing operational checklist for teams deploying
> GenAI in regulated environments. Each item is cross-referenced to the architecture
> components in this repository.
>
> **How to use:**
> - **Pre-Launch:** Complete the full checklist before any production deployment
> - **Quarterly Review:** Re-run Sections 3–6 as part of governance review cycle
> - **Post-Incident:** Re-run the relevant section after any AI-related incident
>
> **Scoring:** Mark each item ✅ Complete | ⚠️ Partial | ❌ Not Done | N/A
> Any ❌ on a mandatory item blocks production deployment.

---

## Section 1 — Transparency & Explainability

*Users and auditors must be able to understand how the AI reached its conclusions.*

### 1.1 Citation & Attribution
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 1.1.1 | Every AI response includes source document citations (title, section, version) | ✅ Yes | | See `examples/citation-tracker/` |
| 1.1.2 | Citations are verified against the actual retrieved documents (not LLM-fabricated) | ✅ Yes | | `CitationValidator.validate()` |
| 1.1.3 | Hallucination detection flags responses with uncited sentences | ✅ Yes | | `CitationTracker.analyze()` |
| 1.1.4 | Fabricated citations (not in retrieval set) trigger CRITICAL audit event | ✅ Yes | | `AuditLogger.log_hallucination_flagged()` |
| 1.1.5 | Users can click through to the source document from the UI | Recommended | | |
| 1.1.6 | Provenance chain (query → chunk → document → page) is logged for every response | ✅ Yes | | `CitationReport.provenance_chain` |

### 1.2 User-Facing Transparency
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 1.2.1 | UI clearly identifies responses as AI-generated | ✅ Yes | | |
| 1.2.2 | System limitations are disclosed to users during onboarding | ✅ Yes | | |
| 1.2.3 | Confidence/relevance scores are shown where meaningful | Recommended | | |
| 1.2.4 | Medium-risk responses display a disclaimer before being shown | ✅ Yes | | `HITLApprovalGate.MEDIUM_DISCLAIMER` |
| 1.2.5 | Users are told when their query has been escalated for human review | ✅ Yes | | `FinalResponse.queue_id` returned to user |
| 1.2.6 | A feedback mechanism ("flag this response") is available | ✅ Yes | | Feeds back into HITL queue |

---

## Section 2 — Fairness & Bias Prevention

*AI responses must not discriminate or treat protected classes differently.*

### 2.1 Output Controls
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 2.1.1 | Output compliance filter detects and blocks discriminatory language | ✅ Yes | | `OutputComplianceChecker.check()` |
| 2.1.2 | Filter covers protected characteristics: race, religion, gender, age, national origin, disability | ✅ Yes | | `OUTPUT_COMPLIANCE_PATTERNS` |
| 2.1.3 | Discriminatory output attempts trigger CRITICAL audit event | ✅ Yes | | `AuditLogger.log_compliance_violation()` |
| 2.1.4 | LLM system prompt explicitly prohibits discriminatory language | ✅ Yes | | `GovernedLLMGateway.SYSTEM_PROMPT` |

### 2.2 Knowledge Base Fairness
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 2.2.1 | Source documents reviewed for embedded historical biases before ingestion | ✅ Yes | | Pre-ingestion review process |
| 2.2.2 | Regulatory coverage is balanced across geographies (no state-level gaps) | ✅ Yes | | Knowledge base audit |
| 2.2.3 | Document classification metadata does not encode protected characteristics | ✅ Yes | | Schema review |

### 2.3 Ongoing Bias Testing
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 2.3.1 | Quarterly bias testing conducted with diverse underwriting scenarios | ✅ Yes | | See `RISK-ASSESSMENT-TEMPLATE.md §6.2` |
| 2.3.2 | Test cases include edge cases for all protected characteristics | ✅ Yes | | |
| 2.3.3 | Bias test results documented and reviewed by Compliance | ✅ Yes | | |
| 2.3.4 | Red team exercises conducted before each major model/data update | Recommended | | |

---

## Section 3 — Privacy & Data Protection

*PII must be protected at every stage of the AI pipeline.*

### 3.1 Input Sanitization
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 3.1.1 | PII detection and redaction active on all user queries before LLM call | ✅ Yes | | `PIIDetector.detect()` |
| 3.1.2 | PII patterns cover: SSN, DOB, credit card, email, phone, policy number, claim number | ✅ Yes | | `PII_PATTERNS` dictionary |
| 3.1.3 | PII redaction events are logged in audit trail | ✅ Yes | | `AuditLogger.log_pii_redacted()` |
| 3.1.4 | Full query text is never logged; only a character-limited preview is stored | ✅ Yes | | `log_query_received(query_preview=text[:120])` |

### 3.2 Output Sanitization
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 3.2.1 | Output filter checks LLM responses for PII before delivery | ✅ Yes | | `OutputComplianceChecker` re-runs PII check |
| 3.2.2 | PII in LLM output triggers CRITICAL audit event and blocks response | ✅ Yes | | `compliance_flags` includes `pii_in_output` |

### 3.3 Data Governance
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 3.3.1 | Vendor DPA (Data Processing Agreement) in place for all third-party AI services | ✅ Yes | | Azure OpenAI DPA on file |
| 3.3.2 | Data retention policy defined for audit logs | ✅ Yes | | See deployment guide |
| 3.3.3 | Data residency requirements met (e.g., US-only for GLBA) | ✅ Yes | | Azure region configuration |
| 3.3.4 | User data deletion process defined and tested (CCPA/GDPR right-to-erasure) | ✅ Yes | | |
| 3.3.5 | Knowledge base documents are versioned; stale versions are removed | ✅ Yes | | `document_version` field in vector index |

---

## Section 4 — Safety & Human Oversight

*Humans must remain accountable for high-stakes decisions.*

### 4.1 Human-in-the-Loop Controls
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 4.1.1 | Risk scoring defined for all query types (LOW / MEDIUM / HIGH) | ✅ Yes | | `RiskScorer.score()` |
| 4.1.2 | HIGH-risk queries are routed to human review before response is shown | ✅ Yes | | `HITLApprovalGate._queue_for_review()` |
| 4.1.3 | HITL SLA is defined and monitored | ✅ Yes | | `HITLQueue.SLA_MINUTES` |
| 4.1.4 | SLA breaches trigger CRITICAL audit event and alert | ✅ Yes | | `AuditLogger.log_hitl_sla_breached()` |
| 4.1.5 | Reviewers receive structured context, not raw LLM output | ✅ Yes | | `HITLQueueItem` structure |
| 4.1.6 | Reviewer decisions (approve / reject / modify) are fully logged | ✅ Yes | | `AuditLogger.log_hitl_decision()` |
| 4.1.7 | Modified responses record both original and revised text | ✅ Yes | | `HITLQueueItem.modified_response` |
| 4.1.8 | AI system is explicitly prohibited from making final coverage decisions autonomously | ✅ Yes | | Documented in system prompt + ADRs |

### 4.2 Fallback & Failure Safety
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 4.2.1 | Graceful degradation defined if AI system is unavailable | ✅ Yes | | Manual fallback to policy documents |
| 4.2.2 | Circuit breaker pattern implemented for LLM API failures | Recommended | | |
| 4.2.3 | Users are notified immediately if AI system is degraded | ✅ Yes | | |
| 4.2.4 | Rollback procedure documented and tested for model/data updates | ✅ Yes | | See deployment guide |

---

## Section 5 — Security

*Adversarial inputs must not compromise system integrity or data confidentiality.*

### 5.1 Access Control
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 5.1.1 | RBAC enforced at the retrieval layer (vector DB), not just the UI | ✅ Yes | | `RBACGateway.build_vector_search_filter()` |
| 5.1.2 | RBAC enforced at the API layer (authentication + authorization) | ✅ Yes | | Azure AD + JWT validation |
| 5.1.3 | RBAC enforced at the UI layer | ✅ Yes | | Role-based feature flags |
| 5.1.4 | Access violation attempts trigger CRITICAL audit event | ✅ Yes | | `AuditLogger.log_rbac_failed()` |
| 5.1.5 | Principle of least privilege applied to all user roles | ✅ Yes | | `ROLE_HIERARCHY` in `RBACGateway` |
| 5.1.6 | Service-to-service authentication uses managed identities (not API keys in code) | ✅ Yes | | Azure Managed Identity |

### 5.2 Prompt Injection
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 5.2.1 | Prompt injection detection active on all user inputs | ✅ Yes | | `PromptInjectionDetector.detect()` |
| 5.2.2 | Detected injection attempts are blocked and logged as CRITICAL | ✅ Yes | | `AuditLogger.log_query_blocked(block_type="prompt_injection")` |
| 5.2.3 | System prompt is not exposed to users under any circumstances | ✅ Yes | | Enforced at API layer |
| 5.2.4 | RBAC at retrieval layer provides defense-in-depth against injection (even if prompt is compromised, retrieval is still filtered) | ✅ Yes | | ADR-001 |

### 5.3 Secrets & Infrastructure
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 5.3.1 | No API keys or secrets in source code or configuration files | ✅ Yes | | All in Azure Key Vault |
| 5.3.2 | Key rotation schedule defined and followed | ✅ Yes | | 90-day rotation |
| 5.3.3 | Network access restricted (private endpoints, VNet integration) | Recommended | | |
| 5.3.4 | Penetration test completed before production launch | ✅ Yes | | |

---

## Section 6 — Audit & Compliance Readiness

*The system must be able to answer any question a regulator or auditor might ask.*

### 6.1 Audit Trail Completeness
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 6.1.1 | Every query, retrieval, LLM call, and response is logged | ✅ Yes | | `AuditLogger` full lifecycle |
| 6.1.2 | Every HITL escalation, decision, and modification is logged | ✅ Yes | | `AuditEventType.HITL_*` |
| 6.1.3 | Every access violation attempt is logged | ✅ Yes | | `AuditEventType.RBAC_CHECK_FAILED` |
| 6.1.4 | Audit entries are tamper-evident (hash chain) | ✅ Yes | | `AuditEntry.entry_hash` (SHA-256) |
| 6.1.5 | Audit entries are stored in an append-only data store | ✅ Yes | | Azure Blob Storage (immutable tier) in prod |
| 6.1.6 | Audit log retention meets regulatory requirements (minimum 7 years for insurance) | ✅ Yes | | |
| 6.1.7 | Audit log integrity can be verified on demand | ✅ Yes | | `AuditLogger.verify_integrity()` |

### 6.2 Governance Reporting
| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 6.2.1 | Compliance summary report can be generated on demand | ✅ Yes | | `ComplianceReportGenerator.generate_summary()` |
| 6.2.2 | Full request timeline can be reconstructed for any historical request | ✅ Yes | | `AuditLogger.get_request_trail(request_id)` |
| 6.2.3 | NIST AI RMF mapping documented | ✅ Yes | | `governance/NIST-AI-RMF-MAPPING.md` |
| 6.2.4 | Quarterly governance review is scheduled and has an owner | ✅ Yes | | |
| 6.2.5 | Risk committee receives monthly dashboard + quarterly deep-dive | ✅ Yes | | |
| 6.2.6 | All Architecture Decision Records (ADRs) are current and reviewed | ✅ Yes | | `docs/ADR-*` |

### 6.3 Regulatory Readiness Questions

_The system must be able to answer each of these questions on demand:_

| Question | How Answered |
|----------|-------------|
| "Can User X access Document Y?" | RBAC audit log + `get_access_violations()` |
| "What did the AI tell User X on Date D?" | `get_request_trail(request_id)` |
| "Was this response reviewed by a human?" | `required_human_review` field in audit entry |
| "Where did this specific claim in the response come from?" | `CitationReport.provenance_chain` |
| "Has any PII been exposed to the LLM?" | `QUERY_PII_REDACTED` audit events |
| "How many high-risk queries were escalated this quarter?" | `ComplianceReportGenerator.generate_summary()` |
| "Has any hallucinated content been delivered to users?" | `HALLUCINATION_FLAGGED` audit events + HITL logs |
| "Has the audit log been tampered with?" | `AuditLogger.verify_integrity()` |

---

## Section 7 — Model Lifecycle & LLMOps

*AI models degrade over time; governance must extend across the full lifecycle.*

| # | Check | Mandatory | Status | Notes |
|---|-------|-----------|--------|-------|
| 7.1 | Model versioning tracked in CI/CD pipeline | ✅ Yes | | Azure DevOps |
| 7.2 | Model update process includes re-run of bias testing | ✅ Yes | | |
| 7.3 | Knowledge base refresh cadence defined (how often policy documents are updated) | ✅ Yes | | |
| 7.4 | Stale document detection and removal process defined | ✅ Yes | | |
| 7.5 | Retrieval quality monitored for drift (relevance scores over time) | ✅ Yes | | Azure Monitor |
| 7.6 | Token usage and cost monitored (budget alerts configured) | Recommended | | |
| 7.7 | Model deprecation plan exists (what happens when GPT-4 is retired) | ✅ Yes | | |

---

## Pre-Launch Summary

| Section | Items | Complete | Partial | Not Done | Blocking? |
|---------|-------|----------|---------|----------|-----------|
| 1. Transparency | | | | | |
| 2. Fairness & Bias | | | | | |
| 3. Privacy | | | | | |
| 4. Safety & HITL | | | | | |
| 5. Security | | | | | |
| 6. Audit & Compliance | | | | | |
| 7. Model Lifecycle | | | | | |

**Overall readiness:**
- ☐ **Launch Ready** — All mandatory items complete, no blockers
- ☐ **Conditional** — Non-mandatory gaps acceptable with documented plan
- ☐ **Not Ready** — One or more mandatory items incomplete (list below)

**Blockers:**
```
[List any mandatory items that are ❌ Not Done and the remediation plan / owner / date]
```

**Sign-Off:**

| Name | Role | Date |
|------|------|------|
| | AI Architecture Lead | |
| | Risk Officer | |
| | Compliance Officer | |

---

> **Living Document:** This checklist should be updated whenever new controls are added
> to the architecture. Each item links to the relevant code example or governance document
> so that checklist compliance can be verified by reviewing artifacts, not just self-attestation.
