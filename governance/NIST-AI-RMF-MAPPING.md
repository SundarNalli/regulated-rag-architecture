# NIST AI RMF Mapping for Regulated RAG Architecture

> **How this RAG system architecture aligns with the NIST AI Risk Management Framework**

---

## Overview

The [NIST AI Risk Management Framework (AI RMF)](https://www.nist.gov/itl/ai-risk-management-framework) provides a structured approach to managing AI risks. This document maps our RAG architecture components to the four core functions of the AI RMF:

1. **GOVERN** - Establish AI governance culture and processes
2. **MAP** - Understand AI system context and risks
3. **MEASURE** - Track AI system performance and impacts
4. **MANAGE** - Respond to and mitigate AI risks

---

## GOVERN Function

*"Cultivates a culture of risk management and establishes structures to enable other functions"*

### AI RMF Category: GOVERN 1.1 - Legal and Regulatory Requirements

**Our Implementation:**
- **Regulatory Compliance Tracking**: Documentation of state insurance regulations applicable to AI-assisted underwriting
- **Audit Readiness**: Architecture designed for SOC2, regulatory audits, and risk committee scrutiny
- **Policy Enforcement**: RBAC controls aligned with "need-to-know" principles for insurance data

**Evidence:**
- [`governance/REGULATORY-COMPLIANCE.md`](governance/REGULATORY-COMPLIANCE.md)
- Audit logs showing access controls and decision trails

---

### AI RMF Category: GOVERN 1.3 - Organizational Policies and Practices

**Our Implementation:**
- **Responsible AI Policy**: Embedded human oversight (HITL) for high-risk decisions
- **Governance Committee**: Risk committee oversight for GenAI deployments
- **Incident Response**: Playbooks for AI failures, bias incidents, and security breaches

**Evidence:**
- HITL approval workflows (see [`examples/hitl-queue/`](examples/hitl-queue/))
- Escalation procedures documented in `docs/INCIDENT-RESPONSE.md`

---

### AI RMF Category: GOVERN 1.5 - Organizational Risk Tolerances

**Our Implementation:**
- **Risk-Based Query Routing**: Low-risk queries auto-approved, high-risk queries require human review
- **Risk Thresholds**: Defined criteria for what constitutes "high-risk" in underwriting context

**Risk Classification Example:**

| Query Type | Risk Level | Governance Action |
|-----------|-----------|-------------------|
| "What is the definition of flood insurance?" | Low | Auto-respond |
| "Can I approve this exception to policy limits?" | Medium | Log + monitor |
| "Should we deny this claim?" | High | HITL required |

**Evidence:**
- Risk assessment matrix in [`governance/RISK-ASSESSMENT-TEMPLATE.md`](governance/RISK-ASSESSMENT-TEMPLATE.md)

---

## MAP Function

*"Establishes context to frame risks related to AI systems"*

### AI RMF Category: MAP 1.1 - Document AI System Purpose and Context

**Our Implementation:**
- **Use Case Documentation**: RAG system for insurance underwriting knowledge retrieval
- **User Roles Defined**: Junior underwriters, senior underwriters, managers, auditors
- **Business Impact**: 60% reduction in manual research time, improved policy consistency

**Evidence:**
- This README (system overview, use cases, impact metrics)
- Architecture Decision Records (ADRs) explaining design choices

---

### AI RMF Category: MAP 2.3 - AI System Dependencies and Interactions

**Our Implementation:**
- **Data Dependencies**: Policy documents, state regulations, historical decisions
- **External Integrations**: Azure OpenAI (LLM), Azure AI Search (vector DB)
- **Upstream/Downstream Systems**: Underwriting platforms, compliance dashboards

**Evidence:**
- Architecture diagram showing system dependencies
- Data lineage tracking in audit logs

---

### AI RMF Category: MAP 5.1 - AI System Risks Identified and Documented

**Our Implementation:**
- **Risk Inventory**:
  - Hallucination risk (LLM generates incorrect policy interpretations)
  - Unauthorized access risk (users accessing restricted underwriting data)
  - Bias risk (unequal treatment based on protected characteristics)
  - Prompt injection risk (malicious prompts bypassing safety controls)

**Mitigation Strategies:**

| Risk | Mitigation | Implementation |
|------|-----------|----------------|
| Hallucination | Citation requirement | Every response must cite source documents |
| Unauthorized access | RBAC at retrieval layer | Vector DB filters by user role |
| Bias | Monitoring and testing | Quarterly bias audits, diverse test cases |
| Prompt injection | Input validation | System prompts + content filtering |

**Evidence:**
- [`governance/RISK-ASSESSMENT-TEMPLATE.md`](governance/RISK-ASSESSMENT-TEMPLATE.md)

---

## MEASURE Function

*"Employs quantitative and qualitative tools to analyze and track AI risks"*

### AI RMF Category: MEASURE 1.1 - Appropriate Methods Selected for Evaluation

**Our Implementation:**
- **Retrieval Quality Metrics**: Precision, recall, relevance scores for vector search
- **Governance Compliance Metrics**: HITL approval rates, access violation attempts
- **User Feedback**: Satisfaction scores, "thumbs up/down" on AI responses

**Metrics Dashboard:**

```
Key Performance Indicators (KPIs):
- Retrieval Accuracy: 92% (target: >90%)
- Citation Coverage: 98% (target: 100%)
- HITL Approval Rate: 15% of queries (expected range: 10-20%)
- Access Violations: 0 in last 90 days
- User Satisfaction: 4.3/5.0
```

**Evidence:**
- Azure Monitor dashboards (see `docs/MONITORING-STRATEGY.md`)
- Quarterly governance reports

---

### AI RMF Category: MEASURE 2.3 - AI System Performance Monitored

**Our Implementation:**
- **Continuous Monitoring**: Real-time tracking of response latency, token usage, error rates
- **Drift Detection**: Monthly reviews of retrieval quality to detect model/data drift
- **Alert Thresholds**: Automated alerts for hallucination flags, access violations

**Observability Stack:**
- Azure Monitor for infrastructure metrics
- Application Insights for application performance
- Custom dashboards for AI-specific metrics (Grafana)

**Evidence:**
- Monitoring dashboards and alert configurations
- Monthly performance review reports

---

### AI RMF Category: MEASURE 4.1 - AI System Tested for Bias

**Our Implementation:**
- **Bias Testing Protocol**: Quarterly testing with diverse underwriting scenarios
- **Fairness Metrics**: Measure response consistency across demographic groups (where applicable)
- **Red Team Exercises**: Adversarial testing to find edge cases and failure modes

**Bias Mitigation:**
- Prompt engineering to reduce stereotyping
- Human review for high-stakes decisions
- Regular audits of AI outputs

**Evidence:**
- Bias testing reports (internal, sanitized versions available on request)
- Red team findings and remediation actions

---

## MANAGE Function

*"Allocates resources to manage AI risks on a regular basis"*

### AI RMF Category: MANAGE 1.1 - AI Risks Prioritized and Responded To

**Our Implementation:**
- **Incident Response Plan**: Playbooks for AI failures, security breaches, bias incidents
- **Risk Prioritization Matrix**: Critical/High/Medium/Low based on impact and likelihood
- **Remediation Tracking**: Issues logged, assigned, and tracked to closure

**Example Incident Response:**

```
Scenario: User reports AI system provided incorrect policy interpretation

Response Flow:
1. User flags response (thumbs down + comment)
2. Alert sent to governance team
3. Human expert reviews flagged content
4. If confirmed incorrect:
   - Response removed from system
   - Source document reviewed for accuracy
   - Root cause analysis (retrieval failure? hallucination?)
5. System updated with corrective action
6. User notified of resolution
```

**Evidence:**
- Incident response playbook (`docs/INCIDENT-RESPONSE.md`)
- Incident log (anonymized)

---

### AI RMF Category: MANAGE 2.1 - AI System Risks Communicated to Stakeholders

**Our Implementation:**
- **Transparency Reports**: Quarterly governance reports shared with risk committee
- **User Notifications**: System limitations clearly communicated in UI
- **Audit Access**: Auditors have read-only access to all system logs and decisions

**Stakeholder Communication:**
- **Underwriters**: Training on system limitations, when to escalate to human expert
- **Risk Committee**: Monthly risk dashboards, quarterly deep dives
- **Auditors**: On-demand access to audit logs and architecture documentation

**Evidence:**
- Quarterly governance reports (template in `governance/TRANSPARENCY-REPORT-TEMPLATE.md`)
- User training materials

---

### AI RMF Category: MANAGE 4.1 - AI System Documentation Maintained

**Our Implementation:**
- **Living Documentation**: Architecture Decision Records (ADRs) updated as system evolves
- **Version Control**: All documentation in Git, changes tracked and reviewed
- **Stakeholder Access**: Documentation accessible to engineering, risk, compliance teams

**Documentation Inventory:**
- Architecture diagrams (this repo)
- ADRs (design decisions with rationale)
- Risk assessments (governance folder)
- Monitoring dashboards (observability stack)
- Incident logs (internal)

**Evidence:**
- This GitHub repository (public documentation)
- Internal confluence/wiki (detailed operational docs)

---

## Continuous Improvement

This NIST AI RMF mapping is a **living document** that evolves as:
- New risks are identified
- Regulatory requirements change
- System architecture is updated
- NIST AI RMF guidance is refined

**Review Schedule:**
- **Quarterly**: Performance metrics, bias testing results
- **Annually**: Full architecture review, risk reassessment
- **Ad Hoc**: Following incidents, regulatory changes, or significant system updates

---

## References

- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST AI RMF Playbook](https://airc.nist.gov/AI_RMF_Knowledge_Base/Playbook)
- [ISO/IEC 42001 - AI Management Systems](https://www.iso.org/standard/81230.html)
- [EU AI Act - High-Risk AI Systems](https://artificialintelligenceact.eu/)

---

## Contact

For questions about this NIST AI RMF mapping or governance approach:

**Sundar Nalli**  
Enterprise AI Governance & GenAI Transformation Architect  
📧 sundarnalli@gmail.com  
🔗 [LinkedIn](https://linkedin.com/in/sundarnalli)

---

**Note:** This mapping demonstrates how governance principles translate into system architecture. It is based on production systems deployed in regulated insurance environments and reflects real-world governance challenges and solutions.
