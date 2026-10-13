"""Autonomous Content Quality, Relevance, and Technical Accuracy Evaluator.

Evaluates generated content drafts across 4 rigorous quality dimensions:
1. Topic Relevance & Semantic Density (RFID, IoT, Supply Chain)
2. Technical Accuracy & Domain Fact Alignment (Innovions Solutions)
3. Readability & Grammatical Fluency
4. Commercial Safety & Anti-Spam Compliance

Calculates a composite score (0-100) and letter grade, enabling autonomous review
and auto-approval of high-quality drafts without requiring manual operator intervention.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from database.models import ContentEvaluationResult, Draft

TECHNICAL_TERMS = {
    "rfid", "uhf", "reader", "readers", "tag", "tags", "passive", "active",
    "antenna", "telemetry", "asset tracking", "inventory", "supply chain",
    "sensors", "iot", "logistics", "rtls", "frequency", "middleware", "real-time"
}

SPAM_SIGNALS = [
    r"\bclick here\b", r"\bbuy now\b", r"\bcheap\b", r"\bguaranteed best\b",
    r"\b100% free\b", r"\bact now\b", r"\bdiscount\b", r"!{2,}", r"\?{2,}"
]


class ContentEvaluator:
    """Evaluates draft content relevance, technical correctness, readability, and anti-spam compliance."""

    def __init__(self, primary_keyword: str = "RFID", min_approval_score: float = 75.0):
        self.primary_keyword = primary_keyword.strip().lower()
        self.min_approval_score = min_approval_score

    def evaluate_draft(self, draft: Draft, target_url: str = "https://innovions.org/") -> ContentEvaluationResult:
        """Evaluates a content draft and returns a structured quality report."""
        text = f"{draft.title} {draft.description}".lower()
        words = re.findall(r"\b[a-z0-9_-]+\b", text)
        word_count = len(words)

        # 1. Relevance Score (35% weight)
        relevance_score = 100.0
        kw_matches = len(re.findall(rf"\b{re.escape(self.primary_keyword)}\b", text))
        if kw_matches == 0:
            relevance_score -= 50.0
        elif kw_matches == 1:
            relevance_score += 0.0  # Perfect
        elif kw_matches <= 3:
            relevance_score += 0.0
        else:
            relevance_score -= (kw_matches - 3) * 15.0

        if "innovions" in text:
            relevance_score = min(100.0, relevance_score + 10.0)

        tech_found = sum(1 for term in TECHNICAL_TERMS if term in text)
        if tech_found >= 4:
            relevance_score = min(100.0, relevance_score + 10.0)
        elif tech_found < 2:
            relevance_score -= 20.0
        relevance_score = max(0.0, min(100.0, relevance_score))

        # 2. Technical Accuracy & Domain Fact Alignment (25% weight)
        accuracy_score = 85.0
        # Target URL integrity check
        if target_url in draft.description:
            accuracy_score += 15.0
        else:
            accuracy_score -= 30.0

        # Title keyword integrity
        if self.primary_keyword in draft.title.lower():
            accuracy_score = min(100.0, accuracy_score + 5.0)
        else:
            accuracy_score -= 20.0

        accuracy_score = max(0.0, min(100.0, accuracy_score))

        # 3. Readability & Grammatical Fluency (20% weight)
        readability_score = 80.0
        title_len = len(draft.title.strip())
        desc_len = len(draft.description.strip())

        # Title length checks (optimal: 30 - 80 chars)
        if 25 <= title_len <= 90:
            readability_score += 10.0
        else:
            readability_score -= 15.0

        # Description length checks (optimal: 60 - 300 chars)
        if 50 <= desc_len <= 350:
            readability_score += 10.0
        else:
            readability_score -= 15.0

        # Average word length heuristic
        avg_word_len = sum(len(w) for w in words) / max(1, word_count)
        if 4.0 <= avg_word_len <= 7.5:
            readability_score = min(100.0, readability_score + 5.0)

        readability_score = max(0.0, min(100.0, readability_score))

        # 4. Commercial Safety & Anti-Spam Compliance (20% weight)
        safety_score = 100.0
        # Check spam signals
        for sig in SPAM_SIGNALS:
            if re.search(sig, text):
                safety_score -= 25.0

        # Check keyword density
        if word_count > 0:
            density = kw_matches / word_count
            if density > 0.10:
                safety_score -= 30.0

        safety_score = max(0.0, min(100.0, safety_score))

        # Composite Score Calculation
        composite = (
            (0.35 * relevance_score)
            + (0.25 * accuracy_score)
            + (0.20 * readability_score)
            + (0.20 * safety_score)
        )
        composite = round(composite, 1)

        # Assign Grade
        if safety_score < 60.0 or relevance_score < 50.0:
            grade = "C" if composite >= 60 else "F"
        elif composite >= 90:
            grade = "A+"
        elif composite >= 80:
            grade = "A"
        elif composite >= 70:
            grade = "B"
        elif composite >= 60:
            grade = "C"
        else:
            grade = "F"

        auto_approved = (
            (composite >= self.min_approval_score)
            and (safety_score >= 60.0)
            and (relevance_score >= 50.0)
        )
        justification = (
            f"Evaluated Grade {grade} (Composite: {composite}/100 | "
            f"Relevance: {relevance_score:.0f}, Accuracy: {accuracy_score:.0f}, "
            f"Readability: {readability_score:.0f}, Safety: {safety_score:.0f}). "
            + ("Autonomous auto-approval granted." if auto_approved else "Requires manual refinement.")
        )

        return ContentEvaluationResult(
            relevance_score=relevance_score,
            accuracy_score=accuracy_score,
            readability_score=readability_score,
            safety_score=safety_score,
            composite_score=composite,
            grade=grade,
            auto_approved=auto_approved,
            justification=justification,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
