"""
Audit Logger — Immutable Compliance Audit Trail for Regulated RAG Systems

This module provides structured, tamper-evident audit logging for every
interaction in a governed AI system: queries, retrievals, LLM calls,
HITL decisions, access control events, and content filter actions.

Why Audit Logging is Non-Negotiable in Regulated Environments:
─────────────────────────────────────────────────────────────
  - Regulators (DOI, OCC, FINRA) require "who did what, when, and why"
  - Risk committees need proof that governance controls actually fired
  - Legal hold: audit records must be immutable and tamper-evident
  - Incident response: reconstruct the exact chain of events after a failure
  - Model drift detection: compare behavior over time using audit data

Design Principles:
─────────────────
  1. IMMUTABLE   — Log entries are append-only; never updated or deleted
  2. STRUCTURED  — Every entry has a fixed schema (queryable, not free-text)
  3. CORRELATED  — All events for one request share a session_id + request_id
  4. COMPLETE    — The full lifecycle: query → filter → retrieve → LLM → HITL → response
  5. EXPORTABLE  — Emits JSON-L (one JSON object per line), ready for SIEM/Splunk/Azure Monitor

Production Note:
───────────────
  In production, replace InMemoryAuditStore with:
    - Azure Monitor / Log Analytics (recommended for Azure deployments)
    - Azure Blob Storage (append-only, immutable tier) for long-term retention
    - Azure Event Hub for real-time streaming to SIEM
  The AuditLogger interface stays identical — only the store changes.

Author: Sundar Nalli
License: MIT
"""

import json
import uuid
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class AuditEventType(Enum):
    # Lifecycle events
    SESSION_STARTED        = "session.started"
    SESSION_ENDED          = "session.ended"

    # Query pipeline events
    QUERY_RECEIVED         = "query.received"
    QUERY_FILTERED         = "query.filtered"       # Content filter ran
    QUERY_BLOCKED          = "query.blocked"         # Content filter blocked
    QUERY_PII_REDACTED     = "query.pii_redacted"

    # Retrieval events
    RETRIEVAL_STARTED      = "retrieval.started"
    RETRIEVAL_COMPLETED    = "retrieval.completed"
    RBAC_CHECK_PASSED      = "rbac.check_passed"
    RBAC_CHECK_FAILED      = "rbac.check_failed"    # Access violation — high priority

    # LLM events
    LLM_CALL_STARTED       = "llm.call_started"
    LLM_CALL_COMPLETED     = "llm.call_completed"
    LLM_CALL_FAILED        = "llm.call_failed"

    # Citation & hallucination events
    CITATION_VALIDATED     = "citation.validated"
    HALLUCINATION_FLAGGED  = "citation.hallucination_flagged"  # Critical

    # HITL events
    HITL_ESCALATED         = "hitl.escalated"       # Routed to human review
    HITL_APPROVED          = "hitl.approved"
    HITL_REJECTED          = "hitl.rejected"
    HITL_MODIFIED          = "hitl.modified"
    HITL_SLA_BREACHED      = "hitl.sla_breached"    # Critical

    # Output events
    OUTPUT_FILTERED        = "output.filtered"
    OUTPUT_BLOCKED         = "output.blocked"
    RESPONSE_DELIVERED     = "response.delivered"

    # Governance events
    RISK_SCORED            = "governance.risk_scored"
    COMPLIANCE_VIOLATION   = "governance.compliance_violation"  # Critical


class AuditSeverity(Enum):
    INFO     = "INFO"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"    # Always alerts compliance team


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT ENTRY — THE CORE DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    """
    A single immutable audit record.

    Every field has a defined purpose for compliance reporting:

      entry_id      — Globally unique ID; used to reference this exact record
      session_id    — Groups all events for one user session
      request_id    — Groups all events for one query/response cycle
      event_type    — What happened (from AuditEventType enum)
      severity      — INFO / WARNING / CRITICAL
      timestamp     — UTC ISO-8601; always UTC, never local time
      user_id       — Who triggered this event
      user_role     — Their role at the time (roles can change; log the actual role)
      details       — Structured payload (event-specific fields)
      entry_hash    — SHA-256 of all fields above; detects tampering
    """
    entry_id:    str
    session_id:  str
    request_id:  str
    event_type:  AuditEventType
    severity:    AuditSeverity
    timestamp:   str                      # UTC ISO-8601 string
    user_id:     str
    user_role:   str
    details:     Dict[str, Any]
    entry_hash:  str = field(init=False)  # Computed after all other fields are set

    def __post_init__(self):
        self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """
        SHA-256 hash of all fields (excluding entry_hash itself).
        Any modification to any field will invalidate the hash.
        This is the tamper-evidence mechanism.
        """
        payload = json.dumps({
            "entry_id"   : self.entry_id,
            "session_id" : self.session_id,
            "request_id" : self.request_id,
            "event_type" : self.event_type.value,
            "severity"   : self.severity.value,
            "timestamp"  : self.timestamp,
            "user_id"    : self.user_id,
            "user_role"  : self.user_role,
            "details"    : self.details,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Returns True if the entry has not been tampered with since creation."""
        return self.entry_hash == self._compute_hash()

    def to_dict(self) -> Dict:
        return {
            "entry_id"   : self.entry_id,
            "session_id" : self.session_id,
            "request_id" : self.request_id,
            "event_type" : self.event_type.value,
            "severity"   : self.severity.value,
            "timestamp"  : self.timestamp,
            "user_id"    : self.user_id,
            "user_role"  : self.user_role,
            "details"    : self.details,
            "entry_hash" : self.entry_hash,
        }

    def to_jsonl(self) -> str:
        """Single-line JSON (JSON-L format) for log ingestion pipelines."""
        return json.dumps(self.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT STORE — PLUGGABLE BACKEND
# ─────────────────────────────────────────────────────────────────────────────

class AuditStore(ABC):
    """
    Abstract backend for persisting audit entries.
    Swap implementations without changing AuditLogger.
    """

    @abstractmethod
    def append(self, entry: AuditEntry) -> None:
        """Append an entry. Must be append-only; never update/delete."""
        ...

    @abstractmethod
    def query(
        self,
        session_id:  Optional[str] = None,
        request_id:  Optional[str] = None,
        user_id:     Optional[str] = None,
        event_types: Optional[List[AuditEventType]] = None,
        severity:    Optional[AuditSeverity] = None,
    ) -> List[AuditEntry]:
        """Query entries by one or more filter criteria."""
        ...

    @abstractmethod
    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify all entries are untampered. Returns a summary report."""
        ...


class InMemoryAuditStore(AuditStore):
    """
    In-memory store for development and testing.

    Replace with AzureMonitorAuditStore or AzureBlobAuditStore
    before deploying to production.
    """

    def __init__(self):
        self._entries: List[AuditEntry] = []    # append-only

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def query(
        self,
        session_id:  Optional[str] = None,
        request_id:  Optional[str] = None,
        user_id:     Optional[str] = None,
        event_types: Optional[List[AuditEventType]] = None,
        severity:    Optional[AuditSeverity] = None,
    ) -> List[AuditEntry]:
        results = self._entries
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if request_id:
            results = [e for e in results if e.request_id == request_id]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if event_types:
            results = [e for e in results if e.event_type in event_types]
        if severity:
            results = [e for e in results if e.severity == severity]
        return results

    def verify_chain_integrity(self) -> Dict[str, Any]:
        total   = len(self._entries)
        tampered = [e.entry_id for e in self._entries if not e.verify_integrity()]
        return {
            "total_entries"   : total,
            "tampered_entries": tampered,
            "integrity_status": "PASS" if not tampered else "FAIL",
            "checked_at"      : datetime.now(timezone.utc).isoformat(),
        }

    def export_jsonl(self) -> str:
        """Export all entries as JSON-L (one JSON object per line)."""
        return "\n".join(e.to_jsonl() for e in self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGGER — THE MAIN INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogger:
    """
    Structured audit logger for the regulated RAG pipeline.

    Usage pattern — one AuditLogger per application, shared across components:

        logger = AuditLogger()

        # At query start
        logger.log_query_received(session_id, request_id, user, query_text)

        # After content filter
        logger.log_query_filtered(session_id, request_id, user, filter_result)

        # After retrieval
        logger.log_retrieval_completed(session_id, request_id, user, chunks)

        # After LLM call
        logger.log_llm_completed(session_id, request_id, user, response)

        # After HITL decision
        logger.log_hitl_decision(session_id, request_id, user, decision)

        # At response delivery
        logger.log_response_delivered(session_id, request_id, user, final_response)
    """

    def __init__(self, store: Optional[AuditStore] = None):
        self._store = store or InMemoryAuditStore()

    # ── Query Pipeline ────────────────────────────────────────────────────────

    def log_query_received(
        self,
        session_id:  str,
        request_id:  str,
        user_id:     str,
        user_role:   str,
        query_text:  str,
        query_length: int
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.QUERY_RECEIVED,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "query_preview" : query_text[:120],   # Never log full query in prod (PII risk)
                "query_length"  : query_length,
            }
        )

    def log_pii_redacted(
        self,
        session_id:   str,
        request_id:   str,
        user_id:      str,
        user_role:    str,
        pii_types:    List[str],
        redacted_text: str
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.QUERY_PII_REDACTED,
            severity    = AuditSeverity.WARNING,    # PII detected is always notable
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "pii_types_detected": pii_types,
                "pii_count"         : len(pii_types),
                "redacted_preview"  : redacted_text[:120],
            }
        )

    def log_query_blocked(
        self,
        session_id: str,
        request_id: str,
        user_id:    str,
        user_role:  str,
        reason:     str,
        block_type: str   # "prompt_injection" | "blocked_topic" | "compliance"
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.QUERY_BLOCKED,
            severity    = AuditSeverity.CRITICAL,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "block_type": block_type,
                "reason"    : reason,
            }
        )

    # ── RBAC & Retrieval ──────────────────────────────────────────────────────

    def log_rbac_passed(
        self,
        session_id:          str,
        request_id:          str,
        user_id:             str,
        user_role:           str,
        authorized_classifications: List[str]
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.RBAC_CHECK_PASSED,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "authorized_classifications": authorized_classifications,
            }
        )

    def log_rbac_failed(
        self,
        session_id:      str,
        request_id:      str,
        user_id:         str,
        user_role:       str,
        attempted_resource: str,
        reason:          str
    ) -> AuditEntry:
        """Access violation — always CRITICAL, always alerted."""
        logger.critical(
            f"[AuditLogger] ACCESS VIOLATION: user={user_id} role={user_role} "
            f"attempted={attempted_resource}"
        )
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.RBAC_CHECK_FAILED,
            severity    = AuditSeverity.CRITICAL,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "attempted_resource": attempted_resource,
                "reason"            : reason,
            }
        )

    def log_retrieval_completed(
        self,
        session_id:    str,
        request_id:    str,
        user_id:       str,
        user_role:     str,
        chunks_count:  int,
        doc_ids:       List[str],
        classifications: List[str],
        latency_ms:    int
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.RETRIEVAL_COMPLETED,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "chunks_retrieved"        : chunks_count,
                "document_ids"            : doc_ids,
                "document_classifications": classifications,
                "latency_ms"              : latency_ms,
            }
        )

    # ── LLM Call ─────────────────────────────────────────────────────────────

    def log_llm_call_started(
        self,
        session_id:    str,
        request_id:    str,
        user_id:       str,
        user_role:     str,
        model:         str,
        prompt_tokens: int
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.LLM_CALL_STARTED,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "model"        : model,
                "prompt_tokens": prompt_tokens,
            }
        )

    def log_llm_call_completed(
        self,
        session_id:        str,
        request_id:        str,
        user_id:           str,
        user_role:         str,
        model:             str,
        completion_tokens: int,
        latency_ms:        int,
        citation_count:    int
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.LLM_CALL_COMPLETED,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "model"            : model,
                "completion_tokens": completion_tokens,
                "latency_ms"       : latency_ms,
                "citation_count"   : citation_count,
            }
        )

    # ── Citation & Hallucination ──────────────────────────────────────────────

    def log_hallucination_flagged(
        self,
        session_id:         str,
        request_id:         str,
        user_id:            str,
        user_role:          str,
        citation_coverage:  float,
        uncited_count:      int,
        flagged_sentences:  List[str]
    ) -> AuditEntry:
        logger.warning(
            f"[AuditLogger] Hallucination risk in request {request_id}: "
            f"coverage={citation_coverage:.0%} uncited={uncited_count}"
        )
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.HALLUCINATION_FLAGGED,
            severity    = AuditSeverity.CRITICAL,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "citation_coverage"       : citation_coverage,
                "uncited_sentence_count"  : uncited_count,
                "flagged_sentence_previews": [s[:80] for s in flagged_sentences],
            }
        )

    # ── HITL Events ───────────────────────────────────────────────────────────

    def log_hitl_escalated(
        self,
        session_id:  str,
        request_id:  str,
        user_id:     str,
        user_role:   str,
        queue_id:    str,
        risk_score:  float,
        risk_reasons: List[str],
        sla_deadline: str
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.HITL_ESCALATED,
            severity    = AuditSeverity.WARNING,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "queue_id"    : queue_id,
                "risk_score"  : risk_score,
                "risk_reasons": risk_reasons,
                "sla_deadline": sla_deadline,
            }
        )

    def log_hitl_decision(
        self,
        session_id:   str,
        request_id:   str,
        reviewer_id:  str,
        reviewer_role: str,
        queue_id:     str,
        decision:     str,    # "approved" | "rejected" | "modified"
        reviewer_notes: str,
        response_was_modified: bool
    ) -> AuditEntry:
        event_map = {
            "approved": AuditEventType.HITL_APPROVED,
            "rejected": AuditEventType.HITL_REJECTED,
            "modified": AuditEventType.HITL_MODIFIED,
        }
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = event_map.get(decision, AuditEventType.HITL_APPROVED),
            severity    = AuditSeverity.INFO,
            user_id     = reviewer_id,
            user_role   = reviewer_role,
            details     = {
                "queue_id"            : queue_id,
                "decision"            : decision,
                "reviewer_notes"      : reviewer_notes,
                "response_was_modified": response_was_modified,
            }
        )

    def log_hitl_sla_breached(
        self,
        session_id:   str,
        request_id:   str,
        queue_id:     str,
        user_id:      str,
        user_role:    str,
        minutes_overdue: int
    ) -> AuditEntry:
        logger.critical(
            f"[AuditLogger] HITL SLA BREACHED: queue_id={queue_id} "
            f"overdue by {minutes_overdue} minutes"
        )
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.HITL_SLA_BREACHED,
            severity    = AuditSeverity.CRITICAL,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "queue_id"      : queue_id,
                "minutes_overdue": minutes_overdue,
            }
        )

    # ── Response Delivery ─────────────────────────────────────────────────────

    def log_response_delivered(
        self,
        session_id:           str,
        request_id:           str,
        user_id:              str,
        user_role:            str,
        risk_level:           str,
        required_human_review: bool,
        citation_count:       int,
        total_latency_ms:     int
    ) -> AuditEntry:
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.RESPONSE_DELIVERED,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "risk_level"           : risk_level,
                "required_human_review": required_human_review,
                "citation_count"       : citation_count,
                "total_latency_ms"     : total_latency_ms,
            }
        )

    def log_compliance_violation(
        self,
        session_id:  str,
        request_id:  str,
        user_id:     str,
        user_role:   str,
        violations:  List[str],
        layer:       str   # "input" | "output"
    ) -> AuditEntry:
        logger.critical(
            f"[AuditLogger] COMPLIANCE VIOLATION in {layer} layer: "
            f"{violations} | request={request_id}"
        )
        return self._write(
            session_id  = session_id,
            request_id  = request_id,
            event_type  = AuditEventType.COMPLIANCE_VIOLATION,
            severity    = AuditSeverity.CRITICAL,
            user_id     = user_id,
            user_role   = user_role,
            details     = {
                "violations" : violations,
                "filter_layer": layer,
            }
        )

    # ── Query Interface ───────────────────────────────────────────────────────

    def get_request_trail(self, request_id: str) -> List[AuditEntry]:
        """Full ordered event trail for one request — primary tool for incident response."""
        return self._store.query(request_id=request_id)

    def get_session_trail(self, session_id: str) -> List[AuditEntry]:
        """All events for a user session."""
        return self._store.query(session_id=session_id)

    def get_critical_events(self) -> List[AuditEntry]:
        """All CRITICAL severity events — used by compliance dashboards."""
        return self._store.query(severity=AuditSeverity.CRITICAL)

    def get_access_violations(self) -> List[AuditEntry]:
        """All RBAC failures — required for security reporting."""
        return self._store.query(event_types=[AuditEventType.RBAC_CHECK_FAILED])

    def get_hitl_events(self) -> List[AuditEntry]:
        """All HITL-related events — used to report human oversight activity."""
        return self._store.query(event_types=[
            AuditEventType.HITL_ESCALATED,
            AuditEventType.HITL_APPROVED,
            AuditEventType.HITL_REJECTED,
            AuditEventType.HITL_MODIFIED,
            AuditEventType.HITL_SLA_BREACHED,
        ])

    def verify_integrity(self) -> Dict[str, Any]:
        """Run tamper-detection check across all stored entries."""
        return self._store.verify_chain_integrity()

    def export_jsonl(self) -> str:
        """Export full audit log as JSON-L for SIEM ingestion."""
        if isinstance(self._store, InMemoryAuditStore):
            return self._store.export_jsonl()
        raise NotImplementedError("export_jsonl only supported on InMemoryAuditStore")

    # ── Private ───────────────────────────────────────────────────────────────

    def _write(
        self,
        session_id: str,
        request_id: str,
        event_type: AuditEventType,
        severity:   AuditSeverity,
        user_id:    str,
        user_role:  str,
        details:    Dict[str, Any]
    ) -> AuditEntry:
        entry = AuditEntry(
            entry_id   = str(uuid.uuid4()),
            session_id = session_id,
            request_id = request_id,
            event_type = event_type,
            severity   = severity,
            timestamp  = datetime.now(timezone.utc).isoformat(),
            user_id    = user_id,
            user_role  = user_role,
            details    = details,
        )
        self._store.append(entry)
        return entry


# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE REPORT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceReportGenerator:
    """
    Generates structured compliance summaries from audit logs.
    Used for: quarterly governance reviews, regulatory submissions,
    risk committee reports, and incident response briefings.
    """

    def __init__(self, audit_logger: AuditLogger):
        self._logger = audit_logger

    def generate_summary(self) -> Dict[str, Any]:
        """
        High-level governance summary — the report you'd show a risk committee.
        """
        store = self._logger._store
        all_entries = store.query() if hasattr(store, 'query') else []

        total     = len(all_entries)
        criticals = [e for e in all_entries if e.severity == AuditSeverity.CRITICAL]
        warnings  = [e for e in all_entries if e.severity == AuditSeverity.WARNING]

        event_counts: Dict[str, int] = {}
        for e in all_entries:
            event_counts[e.event_type.value] = event_counts.get(e.event_type.value, 0) + 1

        integrity = self._logger.verify_integrity()

        return {
            "report_generated_at"   : datetime.now(timezone.utc).isoformat(),
            "total_audit_events"    : total,
            "critical_events_count" : len(criticals),
            "warning_events_count"  : len(warnings),
            "event_type_breakdown"  : event_counts,
            "access_violations"     : len(self._logger.get_access_violations()),
            "hitl_escalations"      : event_counts.get("hitl.escalated", 0),
            "hitl_rejections"       : event_counts.get("hitl.rejected", 0),
            "hallucinations_flagged": event_counts.get("citation.hallucination_flagged", 0),
            "compliance_violations" : event_counts.get("governance.compliance_violation", 0),
            "audit_log_integrity"   : integrity["integrity_status"],
        }

    def print_request_timeline(self, request_id: str) -> None:
        """
        Print a human-readable timeline for one request.
        Useful for incident response: "show me exactly what happened to request X"
        """
        entries = self._logger.get_request_trail(request_id)
        if not entries:
            print(f"  No audit entries found for request_id={request_id}")
            return

        print(f"\n  ── Request Timeline: {request_id} ──")
        for e in entries:
            icon = {"INFO": "ℹ️ ", "WARNING": "⚠️ ", "CRITICAL": "🚨"}.get(e.severity.value, "  ")
            print(f"  {icon} {e.timestamp[11:19]}Z | {e.event_type.value:<35} | user={e.user_id}")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

def run_demo():
    audit_logger = AuditLogger()
    reporter     = ComplianceReportGenerator(audit_logger)

    print("\n" + "=" * 60)
    print("  Audit Logger — Demo")
    print("=" * 60)

    # ── Simulate Request 1: Clean, low-risk query ─────────────────────────────
    session_id  = str(uuid.uuid4())
    request_id_1 = str(uuid.uuid4())
    print(f"\n[Request 1] Clean query from junior underwriter")

    audit_logger.log_query_received(
        session_id, request_id_1,
        user_id="u001", user_role="junior_underwriter",
        query_text="What are the standard flood insurance guidelines?",
        query_length=49
    )
    audit_logger.log_rbac_passed(
        session_id, request_id_1,
        user_id="u001", user_role="junior_underwriter",
        authorized_classifications=["public", "internal"]
    )
    audit_logger.log_retrieval_completed(
        session_id, request_id_1,
        user_id="u001", user_role="junior_underwriter",
        chunks_count=3,
        doc_ids=["doc-001", "doc-002"],
        classifications=["internal", "public"],
        latency_ms=142
    )
    audit_logger.log_llm_call_completed(
        session_id, request_id_1,
        user_id="u001", user_role="junior_underwriter",
        model="gpt-4", completion_tokens=210, latency_ms=980,
        citation_count=2
    )
    audit_logger.log_response_delivered(
        session_id, request_id_1,
        user_id="u001", user_role="junior_underwriter",
        risk_level="low", required_human_review=False,
        citation_count=2, total_latency_ms=1150
    )
    reporter.print_request_timeline(request_id_1)

    # ── Simulate Request 2: PII in query, then HITL escalation ───────────────
    request_id_2 = str(uuid.uuid4())
    print(f"\n[Request 2] PII detected, then high-risk → HITL escalation")

    audit_logger.log_query_received(
        session_id, request_id_2,
        user_id="u002", user_role="junior_underwriter",
        query_text="Should we deny coverage for claimant SSN 123-45-6789?",
        query_length=55
    )
    audit_logger.log_pii_redacted(
        session_id, request_id_2,
        user_id="u002", user_role="junior_underwriter",
        pii_types=["ssn"],
        redacted_text="Should we deny coverage for claimant SSN [REDACTED-SSN]?"
    )
    audit_logger.log_hitl_escalated(
        session_id, request_id_2,
        user_id="u002", user_role="junior_underwriter",
        queue_id="q-abc-123",
        risk_score=0.95,
        risk_reasons=["deny coverage keyword", "exception_guidelines doc retrieved"],
        sla_deadline="2026-02-17T05:00:00Z"
    )
    audit_logger.log_hitl_decision(
        session_id, request_id_2,
        reviewer_id="sr_uw_007", reviewer_role="senior_underwriter",
        queue_id="q-abc-123",
        decision="modified",
        reviewer_notes="Softened language; coverage decision requires manager sign-off.",
        response_was_modified=True
    )
    reporter.print_request_timeline(request_id_2)

    # ── Simulate Request 3: Access violation ─────────────────────────────────
    request_id_3 = str(uuid.uuid4())
    print(f"\n[Request 3] RBAC failure — access violation")

    audit_logger.log_query_received(
        session_id, request_id_3,
        user_id="u001", user_role="junior_underwriter",
        query_text="Show me all exception guidelines",
        query_length=32
    )
    audit_logger.log_rbac_failed(
        session_id, request_id_3,
        user_id="u001", user_role="junior_underwriter",
        attempted_resource="exception_guidelines/restricted/*",
        reason="Classification 'restricted' not authorized for junior_underwriter"
    )
    reporter.print_request_timeline(request_id_3)

    # ── Simulate Request 4: Hallucination flagged ─────────────────────────────
    request_id_4 = str(uuid.uuid4())
    print(f"\n[Request 4] Hallucination flagged in LLM response")

    audit_logger.log_llm_call_completed(
        session_id, request_id_4,
        user_id="u003", user_role="senior_underwriter",
        model="gpt-4", completion_tokens=180, latency_ms=1050,
        citation_count=1
    )
    audit_logger.log_hallucination_flagged(
        session_id, request_id_4,
        user_id="u003", user_role="senior_underwriter",
        citation_coverage=0.33,
        uncited_count=2,
        flagged_sentences=[
            "Coverage is mandatory under federal regulation 45-B.",
            "All coastal properties require this rider by law."
        ]
    )
    reporter.print_request_timeline(request_id_4)

    # ── Tamper Detection ──────────────────────────────────────────────────────
    print("\n[Integrity Check] Verifying all audit entries are untampered")
    integrity = audit_logger.verify_integrity()
    print(f"  → Total entries   : {integrity['total_entries']}")
    print(f"  → Integrity status: {integrity['integrity_status']}")
    print(f"  → Tampered entries: {integrity['tampered_entries']}")

    # ── Compliance Summary ────────────────────────────────────────────────────
    print("\n[Compliance Report] Risk committee summary")
    summary = reporter.generate_summary()
    for key, val in summary.items():
        if key != "event_type_breakdown":
            print(f"  {key:<35} : {val}")

    # ── JSON-L Export Preview ─────────────────────────────────────────────────
    print("\n[JSON-L Export] First entry (ready for SIEM / Azure Monitor ingestion)")
    jsonl = audit_logger.export_jsonl()
    first_line = jsonl.split("\n")[0]
    parsed = json.loads(first_line)
    print(f"  entry_id   : {parsed['entry_id']}")
    print(f"  event_type : {parsed['event_type']}")
    print(f"  timestamp  : {parsed['timestamp']}")
    print(f"  entry_hash : {parsed['entry_hash'][:32]}...")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    run_demo()
