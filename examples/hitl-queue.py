"""
HITL Approval Gate - Human-in-the-Loop for Regulated AI Systems

This module demonstrates how to implement a Human-in-the-Loop (HITL)
approval gate for high-risk AI-generated responses in regulated environments.

Key Design Decisions:
- Risk scoring is deterministic (auditable, not another LLM call)
- High-risk responses are queued, not blocked — preserving UX
- Every escalation creates an immutable audit record
- Approvers receive structured context, not raw LLM output

Author: Sundar Nalli
License: MIT
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS & CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

class RiskLevel(Enum):
    LOW    = "low"       # Auto-approve, respond immediately
    MEDIUM = "medium"    # Log + monitor, respond with disclaimer
    HIGH   = "high"      # Queue for human review before responding


class ReviewDecision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


# Keywords that elevate risk in insurance/underwriting context
RISK_KEYWORDS = {
    RiskLevel.HIGH: [
        "deny coverage", "deny claim", "reject policy", "coverage exclusion",
        "policy cancellation", "exception to policy", "override underwriting",
        "fraud indicator", "claim dispute", "litigation"
    ],
    RiskLevel.MEDIUM: [
        "coverage limit", "deductible", "exclusion", "endorsement",
        "premium increase", "rate change", "non-renewal"
    ]
}

# If response references high-sensitivity document types, elevate risk
SENSITIVE_DOC_TYPES = ["exception_guidelines", "risk_assessment", "claims_history"]


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AIResponse:
    """Represents a generated AI response pending risk evaluation"""
    response_id: str
    user_id: str
    user_role: str
    original_query: str
    generated_text: str
    citations: List[str]
    retrieved_doc_types: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RiskAssessment:
    """Structured risk evaluation of an AI response"""
    risk_level: RiskLevel
    risk_score: float                    # 0.0 – 1.0
    triggered_keywords: List[str]
    triggered_doc_types: List[str]
    rationale: str


@dataclass
class HITLQueueItem:
    """An item waiting for human review"""
    queue_id: str
    ai_response: AIResponse
    risk_assessment: RiskAssessment
    enqueued_at: datetime
    sla_deadline: datetime               # Must be reviewed by this time
    assigned_reviewer: Optional[str] = None
    review_decision: Optional[ReviewDecision] = None
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    modified_response: Optional[str] = None

    @property
    def is_overdue(self) -> bool:
        return datetime.utcnow() > self.sla_deadline

    @property
    def is_resolved(self) -> bool:
        return self.review_decision is not None


@dataclass
class FinalResponse:
    """What the user ultimately receives"""
    response_id: str
    text: str
    citations: List[str]
    risk_level: str
    required_human_review: bool
    disclaimer: Optional[str] = None
    queue_id: Optional[str] = None     # If pending, user can poll this


# ─────────────────────────────────────────────────────────────────────────────
# RISK SCORER
# ─────────────────────────────────────────────────────────────────────────────

class RiskScorer:
    """
    Deterministic risk scorer for AI-generated responses.

    Why deterministic, not another LLM?
    - Auditable: every scoring decision is explainable by rule
    - Fast: no additional API latency
    - Consistent: same input always produces same risk score
    - Compliant: regulators can verify risk logic without model access
    """

    HIGH_THRESHOLD   = 0.65
    MEDIUM_THRESHOLD = 0.35

    def score(self, response: AIResponse) -> RiskAssessment:
        score = 0.0
        triggered_keywords   = []
        triggered_doc_types  = []

        text_lower = response.generated_text.lower()

        # Rule 1: High-risk keyword match (+0.4 per match, capped at 0.6)
        for keyword in RISK_KEYWORDS[RiskLevel.HIGH]:
            if keyword in text_lower:
                score += 0.40
                triggered_keywords.append(keyword)
        score = min(score, 0.60)

        # Rule 2: Medium-risk keyword match (+0.15 per match, capped at 0.30)
        medium_score = 0.0
        for keyword in RISK_KEYWORDS[RiskLevel.MEDIUM]:
            if keyword in text_lower:
                medium_score += 0.15
                triggered_keywords.append(keyword)
        score += min(medium_score, 0.30)

        # Rule 3: Sensitive document type in retrieval set (+0.25 per type)
        for doc_type in response.retrieved_doc_types:
            if doc_type in SENSITIVE_DOC_TYPES:
                score += 0.25
                triggered_doc_types.append(doc_type)
        score = min(score, 1.0)

        # Rule 4: Non-senior role making a coverage-impacting query (+0.10)
        if response.user_role == "junior_underwriter" and triggered_keywords:
            score += 0.10
            score = min(score, 1.0)

        # Classify
        if score >= self.HIGH_THRESHOLD:
            level = RiskLevel.HIGH
        elif score >= self.MEDIUM_THRESHOLD:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        rationale = self._build_rationale(score, triggered_keywords, triggered_doc_types)

        return RiskAssessment(
            risk_level=level,
            risk_score=round(score, 3),
            triggered_keywords=triggered_keywords,
            triggered_doc_types=triggered_doc_types,
            rationale=rationale
        )

    def _build_rationale(
        self,
        score: float,
        keywords: List[str],
        doc_types: List[str]
    ) -> str:
        parts = [f"Risk score: {score:.2f}."]
        if keywords:
            parts.append(f"High-risk phrases detected: {', '.join(keywords)}.")
        if doc_types:
            parts.append(f"Sensitive document types in retrieval: {', '.join(doc_types)}.")
        return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# HITL QUEUE (in-memory; swap for Azure Service Bus in production)
# ─────────────────────────────────────────────────────────────────────────────

class HITLQueue:
    """
    Human-in-the-loop approval queue.

    Production note: Replace self._queue with Azure Service Bus or
    a database-backed queue for durability, dead-letter handling,
    and multi-reviewer support.
    """

    SLA_MINUTES = 30  # Reviewers must act within 30 minutes

    def __init__(self):
        self._queue: Dict[str, HITLQueueItem] = {}
        self._audit_log: List[Dict] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def enqueue(self, response: AIResponse, risk: RiskAssessment) -> HITLQueueItem:
        """Place a response into the human review queue"""
        item = HITLQueueItem(
            queue_id=str(uuid.uuid4()),
            ai_response=response,
            risk_assessment=risk,
            enqueued_at=datetime.utcnow(),
            sla_deadline=datetime.utcnow() + timedelta(minutes=self.SLA_MINUTES)
        )
        self._queue[item.queue_id] = item
        self._audit("ENQUEUED", item)
        logger.warning(
            f"[HITL] Queued response {response.response_id} "
            f"(risk={risk.risk_score:.2f}) — SLA: {item.sla_deadline.isoformat()}"
        )
        return item

    def review(
        self,
        queue_id: str,
        reviewer_id: str,
        decision: ReviewDecision,
        notes: str = "",
        modified_text: Optional[str] = None
    ) -> HITLQueueItem:
        """Submit a reviewer's decision on a queued item"""
        item = self._queue.get(queue_id)
        if not item:
            raise ValueError(f"Queue item {queue_id} not found")
        if item.is_resolved:
            raise ValueError(f"Queue item {queue_id} already resolved")

        item.assigned_reviewer = reviewer_id
        item.review_decision   = decision
        item.reviewer_notes    = notes
        item.reviewed_at       = datetime.utcnow()
        item.modified_response = modified_text

        self._audit("REVIEWED", item)
        logger.info(
            f"[HITL] {decision.value.upper()} by {reviewer_id} "
            f"for queue_id={queue_id}"
        )
        return item

    def get_pending(self) -> List[HITLQueueItem]:
        """Return all unresolved queue items, oldest first"""
        return sorted(
            [i for i in self._queue.values() if not i.is_resolved],
            key=lambda x: x.enqueued_at
        )

    def get_overdue(self) -> List[HITLQueueItem]:
        """Return unresolved items past their SLA deadline"""
        return [i for i in self.get_pending() if i.is_overdue]

    def get_audit_log(self) -> List[Dict]:
        return self._audit_log.copy()

    # ── Private ───────────────────────────────────────────────────────────────

    def _audit(self, event: str, item: HITLQueueItem):
        self._audit_log.append({
            "timestamp"       : datetime.utcnow().isoformat(),
            "event"           : event,
            "queue_id"        : item.queue_id,
            "response_id"     : item.ai_response.response_id,
            "user_id"         : item.ai_response.user_id,
            "risk_score"      : item.risk_assessment.risk_score,
            "risk_level"      : item.risk_assessment.risk_level.value,
            "reviewer_id"     : item.assigned_reviewer,
            "review_decision" : item.review_decision.value if item.review_decision else None,
        })


# ─────────────────────────────────────────────────────────────────────────────
# HITL GATE — THE MAIN ORCHESTRATION POINT
# ─────────────────────────────────────────────────────────────────────────────

class HITLApprovalGate:
    """
    The primary entry point for HITL governance.

    Workflow:
        AI generates response
              ↓
        RiskScorer assigns LOW / MEDIUM / HIGH
              ↓
        LOW    → respond immediately
        MEDIUM → respond with disclaimer, log for review
        HIGH   → queue for human approval, return pending status
    """

    MEDIUM_DISCLAIMER = (
        "⚠️ This response involves coverage-sensitive information. "
        "Please verify with your team's policy guidelines before acting."
    )

    def __init__(self):
        self.risk_scorer = RiskScorer()
        self.hitl_queue  = HITLQueue()

    def process(self, response: AIResponse) -> FinalResponse:
        """Evaluate an AI response and route appropriately"""
        risk = self.risk_scorer.score(response)

        logger.info(
            f"[HITL Gate] response_id={response.response_id} "
            f"risk={risk.risk_level.value} score={risk.risk_score}"
        )

        if risk.risk_level == RiskLevel.LOW:
            return self._auto_approve(response, risk)

        elif risk.risk_level == RiskLevel.MEDIUM:
            return self._approve_with_disclaimer(response, risk)

        else:  # HIGH
            return self._queue_for_review(response, risk)

    def complete_review(
        self,
        queue_id: str,
        reviewer_id: str,
        decision: ReviewDecision,
        notes: str = "",
        modified_text: Optional[str] = None
    ) -> Optional[FinalResponse]:
        """
        Called by the reviewer UI / webhook after a human makes a decision.
        Returns the final response to send to the user, or None if rejected.
        """
        item = self.hitl_queue.review(queue_id, reviewer_id, decision, notes, modified_text)

        if decision == ReviewDecision.REJECTED:
            logger.info(f"[HITL Gate] Response rejected by {reviewer_id}: {notes}")
            return None

        final_text = (
            item.modified_response
            if decision == ReviewDecision.MODIFIED and item.modified_response
            else item.ai_response.generated_text
        )

        return FinalResponse(
            response_id       = item.ai_response.response_id,
            text              = final_text,
            citations         = item.ai_response.citations,
            risk_level        = item.risk_assessment.risk_level.value,
            required_human_review = True,
            queue_id          = queue_id
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _auto_approve(self, response: AIResponse, risk: RiskAssessment) -> FinalResponse:
        logger.info(f"[HITL Gate] Auto-approved response_id={response.response_id}")
        return FinalResponse(
            response_id           = response.response_id,
            text                  = response.generated_text,
            citations             = response.citations,
            risk_level            = risk.risk_level.value,
            required_human_review = False
        )

    def _approve_with_disclaimer(self, response: AIResponse, risk: RiskAssessment) -> FinalResponse:
        logger.info(f"[HITL Gate] Medium-risk response approved with disclaimer: {response.response_id}")
        return FinalResponse(
            response_id           = response.response_id,
            text                  = response.generated_text,
            citations             = response.citations,
            risk_level            = risk.risk_level.value,
            required_human_review = False,
            disclaimer            = self.MEDIUM_DISCLAIMER
        )

    def _queue_for_review(self, response: AIResponse, risk: RiskAssessment) -> FinalResponse:
        item = self.hitl_queue.enqueue(response, risk)
        return FinalResponse(
            response_id           = response.response_id,
            text                  = "Your query requires review by a senior underwriter. You will be notified when approved.",
            citations             = [],
            risk_level            = risk.risk_level.value,
            required_human_review = True,
            queue_id              = item.queue_id
        )


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

def run_demo():
    gate = HITLApprovalGate()

    print("\n" + "=" * 60)
    print("  HITL Approval Gate — Demo")
    print("=" * 60)

    # ── Scenario 1: Low-risk query ────────────────────────────────────────────
    print("\n[Scenario 1] Low-risk query — definition lookup")
    low_risk = AIResponse(
        response_id        = str(uuid.uuid4()),
        user_id            = "u001",
        user_role          = "junior_underwriter",
        original_query     = "What is flood insurance?",
        generated_text     = "Flood insurance covers property damage caused by flooding. [Source: Policy Manual v2.3, Section 1.1]",
        citations          = ["Policy Manual v2.3, Section 1.1"],
        retrieved_doc_types= ["policy"]
    )
    result = gate.process(low_risk)
    print(f"  → Risk Level       : {result.risk_level}")
    print(f"  → Human Review     : {result.required_human_review}")
    print(f"  → Response Preview : {result.text[:80]}...")

    # ── Scenario 2: Medium-risk query ────────────────────────────────────────
    print("\n[Scenario 2] Medium-risk — coverage limit inquiry")
    medium_risk = AIResponse(
        response_id        = str(uuid.uuid4()),
        user_id            = "u002",
        user_role          = "senior_underwriter",
        original_query     = "What is the coverage limit for a commercial property?",
        generated_text     = "The coverage limit for commercial properties depends on the endorsement applied. [Source: Underwriting Guidelines v4.1]",
        citations          = ["Underwriting Guidelines v4.1, Section 3.2"],
        retrieved_doc_types= ["policy"]
    )
    result = gate.process(medium_risk)
    print(f"  → Risk Level       : {result.risk_level}")
    print(f"  → Human Review     : {result.required_human_review}")
    print(f"  → Disclaimer       : {result.disclaimer}")

    # ── Scenario 3: High-risk query ───────────────────────────────────────────
    print("\n[Scenario 3] High-risk — coverage denial query")
    high_risk = AIResponse(
        response_id        = str(uuid.uuid4()),
        user_id            = "u003",
        user_role          = "junior_underwriter",
        original_query     = "Should we deny coverage for this flood claim?",
        generated_text     = "Based on the policy terms, we should deny coverage for this claim due to the coverage exclusion for pre-existing conditions. [Source: Exception Guidelines v1.2]",
        citations          = ["Exception Guidelines v1.2"],
        retrieved_doc_types= ["exception_guidelines"]
    )
    result = gate.process(high_risk)
    print(f"  → Risk Level       : {result.risk_level}")
    print(f"  → Human Review     : {result.required_human_review}")
    print(f"  → Queue ID         : {result.queue_id}")
    print(f"  → User sees        : {result.text}")

    # ── Reviewer approves the high-risk item ─────────────────────────────────
    print("\n[Reviewer Action] Senior underwriter reviews the queued item")
    pending = gate.hitl_queue.get_pending()
    if pending:
        queue_id = pending[0].queue_id
        final = gate.complete_review(
            queue_id      = queue_id,
            reviewer_id   = "sr_underwriter_007",
            decision      = ReviewDecision.MODIFIED,
            notes         = "Softened language; escalated to manager for final decision.",
            modified_text = "Based on preliminary review, this claim may have coverage exclusions. A manager must make the final coverage decision. [Source: Exception Guidelines v1.2]"
        )
        print(f"  → Final response text : {final.text}")
        print(f"  → Required human review confirmed : {final.required_human_review}")

    # ── Audit log ─────────────────────────────────────────────────────────────
    print("\n[Audit Log] (all events recorded for compliance)")
    for entry in gate.hitl_queue.get_audit_log():
        print(f"  {entry['timestamp']} | {entry['event']:10} | "
              f"risk={entry['risk_score']:.2f} | "
              f"decision={entry['review_decision']}")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    run_demo()
