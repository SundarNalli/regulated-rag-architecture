"""
Citation Tracker — Source Attribution for Regulated RAG Systems

This module demonstrates how to track, validate, and display citations
for every AI-generated response in a regulated environment.

Key Design Decisions:
- Citations are extracted from LLM output AND verified against retrieved docs
- Every sentence in the response is mapped to its source chunk
- Uncited sentences are flagged as potential hallucinations
- Full provenance chain: User Query → Chunk → Source Document → Page

Why citations matter in regulated environments:
- Auditors need to verify "where did this answer come from?"
- Underwriters need to validate recommendations before acting
- Hallucination detection: if the LLM cited something it didn't retrieve, flag it
- Explainability: users can click through to the exact source passage

Author: Sundar Nalli
License: MIT
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DocumentChunk:
    """
    A chunk of text retrieved from the vector database.
    Represents one passage from a source document.
    """
    chunk_id:       str
    document_id:    str
    document_title: str
    document_version: str
    section:        str        # e.g., "Section 4.2"
    page_number:    int
    text:           str
    classification: str        # e.g., "internal", "confidential"
    retrieved_at:   datetime = field(default_factory=datetime.utcnow)


@dataclass
class ParsedCitation:
    """
    A citation extracted from LLM-generated text.
    Format in LLM output: [Source: Policy Manual v2.3, Section 4.2]
    """
    raw_text:         str      # Full citation string as it appeared
    document_title:   str
    document_version: str
    section:          str
    page_number:      Optional[int] = None


@dataclass
class CitationValidationResult:
    """Result of verifying a parsed citation against retrieved chunks"""
    citation:          ParsedCitation
    is_valid:          bool           # Was this citation actually retrieved?
    matched_chunk_id:  Optional[str]  # Which chunk it matched (if valid)
    confidence:        float          # 0.0–1.0 match confidence
    validation_note:   str


@dataclass
class SentenceCitation:
    """Maps a single sentence in the response to its source chunk"""
    sentence:         str
    citation:         Optional[ParsedCitation]
    is_cited:         bool
    is_hallucination_risk: bool   # True if cited something not in retrieval set


@dataclass
class CitationReport:
    """Complete citation analysis for one AI response"""
    response_id:          str
    original_response:    str
    sentence_citations:   List[SentenceCitation]
    validation_results:   List[CitationValidationResult]
    citation_coverage:    float     # % of sentences that have valid citations
    hallucination_flags:  List[str] # Sentences with uncited or invalid claims
    provenance_chain:     List[Dict]
    generated_at:         datetime = field(default_factory=datetime.utcnow)

    @property
    def is_fully_cited(self) -> bool:
        return self.citation_coverage == 1.0

    @property
    def has_hallucination_risk(self) -> bool:
        return len(self.hallucination_flags) > 0


# ─────────────────────────────────────────────────────────────────────────────
# CITATION PARSER
# ─────────────────────────────────────────────────────────────────────────────

class CitationParser:
    """
    Extracts structured citations from LLM-generated text.

    Expected citation format in LLM output:
        [Source: Policy Manual v2.3, Section 4.2]
        [Source: Underwriting Guidelines v1.0, Section 2.1, Page 14]

    The system prompt instructs the LLM to use this format (see SYSTEM_PROMPT
    in the LLM Gateway). This parser extracts and validates those citations.
    """

    # Matches: [Source: <title> v<version>, Section <section>, Page <page>]
    # Page number is optional
    CITATION_PATTERN = re.compile(
        r'\[Source:\s*'
        r'(?P<title>[^,\[\]]+?)\s+'
        r'v(?P<version>[\d.]+)'
        r'(?:,\s*Section\s*(?P<section>[^\],]+?))?'
        r'(?:,\s*Page\s*(?P<page>\d+))?'
        r'\s*\]',
        re.IGNORECASE
    )

    def parse(self, text: str) -> List[ParsedCitation]:
        """Extract all citations from a block of text"""
        citations = []
        for match in self.CITATION_PATTERN.finditer(text):
            citations.append(ParsedCitation(
                raw_text         = match.group(0),
                document_title   = match.group("title").strip(),
                document_version = match.group("version").strip(),
                section          = (match.group("section") or "").strip(),
                page_number      = int(match.group("page")) if match.group("page") else None
            ))
        return citations

    def sentence_split(self, text: str) -> List[str]:
        """
        Split text into sentences, keeping citation markers attached
        to the preceding sentence.
        """
        # Split on ". " or ".\n" but NOT inside brackets
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s+', text)
        return [s.strip() for s in sentences if s.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# CITATION VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

class CitationValidator:
    """
    Verifies parsed citations against the actual retrieved document chunks.

    This is the critical governance check:
    - If the LLM cited a document that was NOT in the retrieval set → hallucination risk
    - If the LLM cited a real document correctly → citation is valid
    - If a sentence has no citation → potential hallucination
    """

    def validate(
        self,
        citation: ParsedCitation,
        retrieved_chunks: List[DocumentChunk]
    ) -> CitationValidationResult:
        """
        Check if a citation refers to an actually retrieved chunk.
        Uses fuzzy title matching (LLMs occasionally paraphrase titles).
        """
        best_match = None
        best_confidence = 0.0

        for chunk in retrieved_chunks:
            confidence = self._match_confidence(citation, chunk)
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = chunk

        if best_confidence >= 0.80:
            return CitationValidationResult(
                citation         = citation,
                is_valid         = True,
                matched_chunk_id = best_match.chunk_id,
                confidence       = best_confidence,
                validation_note  = f"Matched chunk {best_match.chunk_id} with {best_confidence:.0%} confidence"
            )
        elif best_confidence >= 0.50:
            return CitationValidationResult(
                citation         = citation,
                is_valid         = True,
                matched_chunk_id = best_match.chunk_id if best_match else None,
                confidence       = best_confidence,
                validation_note  = f"Partial match with {best_confidence:.0%} confidence — verify manually"
            )
        else:
            return CitationValidationResult(
                citation         = citation,
                is_valid         = False,
                matched_chunk_id = None,
                confidence       = best_confidence,
                validation_note  = "⚠️ Citation not found in retrieval set — possible hallucination"
            )

    def _match_confidence(
        self,
        citation: ParsedCitation,
        chunk: DocumentChunk
    ) -> float:
        """Score how well a citation matches a retrieved chunk (0.0–1.0)"""
        score = 0.0

        # Title similarity (normalized)
        citation_title = citation.document_title.lower()
        chunk_title    = chunk.document_title.lower()

        if citation_title == chunk_title:
            score += 0.50
        elif citation_title in chunk_title or chunk_title in citation_title:
            score += 0.35
        else:
            # Check for significant word overlap
            c_words = set(citation_title.split())
            t_words = set(chunk_title.split())
            overlap = len(c_words & t_words) / max(len(c_words | t_words), 1)
            score += 0.25 * overlap

        # Version match
        if citation.document_version == chunk.document_version:
            score += 0.30

        # Section match
        if citation.section and chunk.section:
            if citation.section.lower() == chunk.section.lower():
                score += 0.20

        # Page match
        if citation.page_number and citation.page_number == chunk.page_number:
            score += 0.10

        return min(score, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# CITATION TRACKER — THE MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

class CitationTracker:
    """
    Orchestrates citation extraction, sentence-level mapping, and validation.

    Produces a CitationReport that:
    1. Shows citation coverage (% of sentences with valid sources)
    2. Flags potential hallucinations (uncited or invalid citations)
    3. Builds a provenance chain: query → chunk → source → page
    """

    def __init__(self):
        self.parser    = CitationParser()
        self.validator = CitationValidator()

    def analyze(
        self,
        response_id: str,
        response_text: str,
        retrieved_chunks: List[DocumentChunk]
    ) -> CitationReport:
        """Full citation analysis for one AI response"""

        # Step 1: Extract all citations from response
        all_citations = self.parser.parse(response_text)
        logger.info(f"[CitationTracker] Found {len(all_citations)} citations in response {response_id}")

        # Step 2: Validate each citation against retrieved chunks
        validation_results = [
            self.validator.validate(c, retrieved_chunks)
            for c in all_citations
        ]

        # Step 3: Map each sentence to its citations
        sentences = self.parser.sentence_split(response_text)
        sentence_citations = self._map_sentences_to_citations(
            sentences, all_citations, validation_results
        )

        # Step 4: Calculate coverage and flag issues
        cited_sentences = sum(1 for sc in sentence_citations if sc.is_cited)
        citation_coverage = cited_sentences / len(sentences) if sentences else 0.0

        hallucination_flags = [
            sc.sentence
            for sc in sentence_citations
            if sc.is_hallucination_risk
        ]

        # Step 5: Build provenance chain
        provenance_chain = self._build_provenance_chain(
            response_id, retrieved_chunks, validation_results
        )

        report = CitationReport(
            response_id         = response_id,
            original_response   = response_text,
            sentence_citations  = sentence_citations,
            validation_results  = validation_results,
            citation_coverage   = round(citation_coverage, 3),
            hallucination_flags = hallucination_flags,
            provenance_chain    = provenance_chain
        )

        if report.has_hallucination_risk:
            logger.warning(
                f"[CitationTracker] ⚠️ {len(hallucination_flags)} hallucination risk(s) "
                f"detected in response {response_id}"
            )

        return report

    # ── Private helpers ───────────────────────────────────────────────────────

    def _map_sentences_to_citations(
        self,
        sentences: List[str],
        citations: List[ParsedCitation],
        validation_results: List[CitationValidationResult]
    ) -> List[SentenceCitation]:
        """
        Map each sentence to the citation it contains (if any).
        A sentence "owns" a citation if the citation appears within it.
        """
        # Build a lookup: raw citation text → validation result
        validation_map = {
            vr.citation.raw_text: vr for vr in validation_results
        }

        sentence_citations = []
        for sentence in sentences:
            # Find citations embedded in this sentence
            found_citations = [
                c for c in citations if c.raw_text in sentence
            ]

            if found_citations:
                citation = found_citations[0]  # primary citation for this sentence
                validation = validation_map.get(citation.raw_text)
                is_hallucination = validation and not validation.is_valid

                sentence_citations.append(SentenceCitation(
                    sentence              = sentence,
                    citation              = citation,
                    is_cited              = True,
                    is_hallucination_risk = is_hallucination
                ))
            else:
                # Sentence has no citation — flag it
                sentence_citations.append(SentenceCitation(
                    sentence              = sentence,
                    citation              = None,
                    is_cited              = False,
                    is_hallucination_risk = True  # No citation = potential hallucination
                ))

        return sentence_citations

    def _build_provenance_chain(
        self,
        response_id: str,
        chunks: List[DocumentChunk],
        validations: List[CitationValidationResult]
    ) -> List[Dict]:
        """
        Build the full provenance chain for audit purposes.
        Each link: User Query → Chunk ID → Source Document → Page → Classification
        """
        chain = []
        matched_ids = {vr.matched_chunk_id for vr in validations if vr.matched_chunk_id}

        for chunk in chunks:
            chain.append({
                "response_id"      : response_id,
                "chunk_id"         : chunk.chunk_id,
                "document_id"      : chunk.document_id,
                "document_title"   : chunk.document_title,
                "document_version" : chunk.document_version,
                "section"          : chunk.section,
                "page_number"      : chunk.page_number,
                "classification"   : chunk.classification,
                "cited_in_response": chunk.chunk_id in matched_ids,
                "retrieved_at"     : chunk.retrieved_at.isoformat()
            })

        return chain


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

def run_demo():
    tracker = CitationTracker()

    print("\n" + "=" * 60)
    print("  Citation Tracker — Demo")
    print("=" * 60)

    # Simulate retrieved chunks from vector DB
    retrieved_chunks = [
        DocumentChunk(
            chunk_id         = "chunk-001",
            document_id      = "doc-pm-23",
            document_title   = "Policy Manual",
            document_version = "2.3",
            section          = "Section 1.1",
            page_number      = 5,
            text             = "Flood insurance covers property damage caused by flooding...",
            classification   = "internal"
        ),
        DocumentChunk(
            chunk_id         = "chunk-002",
            document_id      = "doc-ug-41",
            document_title   = "Underwriting Guidelines",
            document_version = "4.1",
            section          = "Section 3.2",
            page_number      = 22,
            text             = "Coverage limits for commercial properties vary by endorsement type...",
            classification   = "confidential"
        )
    ]

    # ── Scenario 1: Well-cited response ──────────────────────────────────────
    print("\n[Scenario 1] Well-cited, compliant response")
    good_response = (
        "Flood insurance covers property damage caused by flooding. "
        "[Source: Policy Manual v2.3, Section 1.1] "
        "Coverage limits for commercial properties depend on the endorsement applied. "
        "[Source: Underwriting Guidelines v4.1, Section 3.2, Page 22]"
    )
    report1 = tracker.analyze("resp-001", good_response, retrieved_chunks)
    print(f"  → Citation Coverage   : {report1.citation_coverage:.0%}")
    print(f"  → Hallucination Risk  : {report1.has_hallucination_risk}")
    print(f"  → Fully Cited         : {report1.is_fully_cited}")
    print(f"  → Provenance entries  : {len(report1.provenance_chain)}")

    # ── Scenario 2: Partially-cited response (hallucination risk) ─────────────
    print("\n[Scenario 2] Partially cited — hallucination risk detected")
    partial_response = (
        "Flood insurance is mandatory for properties in high-risk flood zones. "
        "Coverage limits are set by FEMA regulations and vary by state. "
        "[Source: Policy Manual v2.3, Section 1.1] "
        "Always consult your state guidelines before issuing a policy."
    )
    report2 = tracker.analyze("resp-002", partial_response, retrieved_chunks)
    print(f"  → Citation Coverage   : {report2.citation_coverage:.0%}")
    print(f"  → Hallucination Risk  : {report2.has_hallucination_risk}")
    print(f"  → Uncited sentences:")
    for flag in report2.hallucination_flags:
        print(f"    ⚠️  '{flag[:70]}...'")

    # ── Scenario 3: Fabricated citation (hallucination) ───────────────────────
    print("\n[Scenario 3] Fabricated citation — not in retrieval set")
    hallucinated_response = (
        "Coverage is denied based on Section 9 of the Risk Assessment Model. "
        "[Source: Internal Risk Model v9.0, Section 9.1]"
    )
    report3 = tracker.analyze("resp-003", hallucinated_response, retrieved_chunks)
    print(f"  → Citation Coverage   : {report3.citation_coverage:.0%}")
    print(f"  → Hallucination Risk  : {report3.has_hallucination_risk}")
    for vr in report3.validation_results:
        print(f"  → Validation: '{vr.citation.document_title}' — "
              f"valid={vr.is_valid} | {vr.validation_note}")

    # ── Provenance chain ──────────────────────────────────────────────────────
    print("\n[Provenance Chain] Audit trail for Scenario 1")
    for link in report1.provenance_chain:
        print(f"  chunk={link['chunk_id']} | "
              f"{link['document_title']} v{link['document_version']} | "
              f"p.{link['page_number']} | "
              f"cited={link['cited_in_response']}")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    run_demo()
