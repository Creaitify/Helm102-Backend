"""Deterministic SEBI compliance verifier with citations and automated revision support.

Regulatory moat: Deterministic Python code evaluation, not fuzzy prompt guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

SEBI_RULES_VERSION = "2026-08-17.1"


class ComplianceStatus(StrEnum):
    PASS = "pass"
    FLAG = "flag"
    BLOCK = "block"


# Hard Block rules mapped to regulatory clauses
HARD_BLOCK_RULES: dict[str, str] = {
    "guaranteed return": "SEBI (Prohibition of Fraudulent and Unfair Trade Practices) Reg 4(1) - Prohibits guaranteed return claims on market-linked securities.",
    "assured return": "SEBI Circular SEBI/HO/IMD/DF2/CIR/P/2019/17 - Strict ban on assured returns in mutual funds.",
    "guaranteed profit": "SEBI Advertisement Code Clause 2(b) - False assurance of profitability.",
    "assured profit": "SEBI Advertisement Code Clause 2(b) - Prohibited assurance of capital growth.",
    "risk-free": "SEBI Reg 4(2) - Misleading representation of securities as risk-free.",
    "risk free": "SEBI Reg 4(2) - Misleading representation of securities as risk-free.",
    "no risk": "SEBI Reg 4(2) - Denial of market risk.",
    "zero risk": "SEBI Reg 4(2) - Denial of market risk.",
    "double your money": "SEBI Advertisement Code Clause 4(a) - Unrealistic multiplication promise.",
    "cannot lose": "SEBI (Investment Advisers) Reg 19(1) - Absolute loss-immunity claims strictly forbidden.",
}

# Warning / Flag rules requiring explicit human signoff
WARN_RULES: dict[str, str] = {
    "guaranteed": "SEBI Clause 3(a) - Unqualified guarantee terminology.",
    "assured": "SEBI Clause 3(a) - Unqualified assurance terminology.",
    "highest returns": "SEBI Advertising Code Clause 5 - Superlative performance claims without peer-group benchmark disclosure.",
    "best returns": "SEBI Advertising Code Clause 5 - Unsubstantiated superlative claim.",
    "safe investment": "SEBI Clause 6 - Safety claims on volatile assets require risk categorization.",
    "always profitable": "SEBI Clause 2(c) - Omission of downside volatility.",
}

# Standard mandatory disclaimer keywords
MANDATORY_DISCLAIMER_PHRASES: tuple[str, ...] = (
    "market risks",
    "scheme related documents",
    "subject to market risk",
)


@dataclass(frozen=True, slots=True)
class RuleViolation:
    """A single matched rule violation with citation."""

    phrase: str
    severity: ComplianceStatus
    citation: str
    location: str = "general"


@dataclass(frozen=True, slots=True)
class ComplianceVerdict:
    """Full compliance evaluation result for a creative piece or campaign."""

    status: ComplianceStatus
    passed: bool
    violations: list[RuleViolation] = field(default_factory=list)
    has_mandatory_disclaimer: bool = True
    rules_version: str = SEBI_RULES_VERSION
    feedback_for_revision: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "passed": self.passed,
            "violations": [
                {
                    "phrase": v.phrase,
                    "severity": v.severity.value,
                    "citation": v.citation,
                    "location": v.location,
                }
                for v in self.violations
            ],
            "has_mandatory_disclaimer": self.has_mandatory_disclaimer,
            "rules_version": self.rules_version,
            "feedback_for_revision": self.feedback_for_revision,
        }


class SEBIComplianceVerifier:
    """Deterministic compliance checker enforcing SEBI advertising guidelines."""

    def normalize_text(self, text: str) -> str:
        """Normalize delimiters, repeated spaces, and character-spaced evasions."""
        if not text:
            return ""
        t = str(text).lower()
        # 1. Convert all non-alphanumeric punctuation and delimiter characters to spaces
        t = re.sub(r"[^a-z0-9\s]", " ", t)

        # 2. Collapse single-letter runs (length >= 2 letters: e.g. 'n o' -> 'no', 'g u a r a n t e e d' -> 'guaranteed')
        def _merge_single_letters(match: re.Match[str]) -> str:
            return re.sub(r"\s+", "", match.group(0))

        t = re.sub(r"\b[a-z](?:\s+[a-z])+\b", _merge_single_letters, t)

        # 3. Collapse multiple whitespace
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _match_rule_phrase(
        self,
        phrase: str,
        lowered: str,
        normalized: str,
        norm_tokens: set[str],
    ) -> bool:
        """Check if a compliance rule phrase matches text via word boundary or spaceless tokens."""
        phrase_lower = phrase.lower()

        # 1. Word boundary on lowered raw string
        if re.search(r"\b" + re.escape(phrase_lower) + r"\b", lowered):
            return True

        # 2. Word boundary on normalized string
        phrase_norm = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", phrase_lower)).strip()
        if phrase_norm and re.search(r"\b" + re.escape(phrase_norm) + r"\b", normalized):
            return True

        # 3. Spaceless token match on normalized tokens (e.g. 'zerorisk', 'norisk', 'guaranteedreturn', 'doubleyourmoney')
        phrase_spaceless = re.sub(r"[^a-z0-9]", "", phrase_lower)
        if phrase_spaceless and phrase_spaceless in norm_tokens:
            return True

        return False

    def verify_text(self, text: str | Any, location: str = "body") -> ComplianceVerdict:
        """Evaluate a text string against deterministic regulatory rules."""
        if text is None:
            text = ""
        else:
            text = str(text)

        lowered = text.lower()
        normalized = self.normalize_text(text)
        norm_tokens = set(normalized.split())
        violations: list[RuleViolation] = []

        # Check Hard Blocks
        for phrase, citation in HARD_BLOCK_RULES.items():
            if self._match_rule_phrase(phrase, lowered, normalized, norm_tokens):
                if not any(v.phrase == phrase for v in violations):
                    violations.append(
                        RuleViolation(
                            phrase=phrase,
                            severity=ComplianceStatus.BLOCK,
                            citation=citation,
                            location=location,
                        )
                    )

        # Check Warnings
        for phrase, citation in WARN_RULES.items():
            if self._match_rule_phrase(phrase, lowered, normalized, norm_tokens):
                # Skip if already caught or covered by a hard block violation
                if not any(v.phrase == phrase for v in violations) and not any(phrase in v.phrase for v in violations):
                    violations.append(
                        RuleViolation(
                            phrase=phrase,
                            severity=ComplianceStatus.FLAG,
                            citation=citation,
                            location=location,
                        )
                    )

        # Check Disclaimer
        has_disclaimer = any(
            re.search(r"\b" + re.escape(p) + r"\b", lowered)
            or re.search(r"\b" + re.escape(re.sub(r"[^a-z0-9\s]", " ", p)), normalized)
            for p in MANDATORY_DISCLAIMER_PHRASES
        )

        # Determine overall status
        if any(v.severity == ComplianceStatus.BLOCK for v in violations):
            status = ComplianceStatus.BLOCK
            passed = False
        elif violations or not has_disclaimer:
            status = ComplianceStatus.FLAG
            passed = False
        else:
            status = ComplianceStatus.PASS
            passed = True

        # Generate actionable revision feedback if failed
        feedback = ""
        if not passed:
            feedback_lines = []
            for v in violations:
                feedback_lines.append(f"- Remove prohibited phrase '{v.phrase}' ({v.citation})")
            if not has_disclaimer:
                feedback_lines.append("- Add mandatory SEBI disclaimer: 'Mutual fund investments are subject to market risks, read all scheme related documents carefully.'")
            feedback = "\n".join(feedback_lines)

        return ComplianceVerdict(
            status=status,
            passed=passed,
            violations=violations,
            has_mandatory_disclaimer=has_disclaimer,
            rules_version=SEBI_RULES_VERSION,
            feedback_for_revision=feedback,
        )

    def verify_package(self, package_dict: dict[str, Any] | Any) -> ComplianceVerdict:
        """Verify an entire creative package (script, headline, body text, captions)."""
        if not isinstance(package_dict, dict):
            return ComplianceVerdict(
                status=ComplianceStatus.FLAG,
                passed=False,
                violations=[],
                has_mandatory_disclaimer=False,
                rules_version=SEBI_RULES_VERSION,
                feedback_for_revision="Invalid creative package payload: expected a dictionary.",
            )

        combined_violations: list[RuleViolation] = []
        all_text: list[str] = []

        # Extract texts safely handling None, missing dicts, or non-dict values
        creative = package_dict.get("creative") if isinstance(package_dict.get("creative"), dict) else {}
        script = package_dict.get("script") if isinstance(package_dict.get("script"), dict) else {}
        captions = package_dict.get("captions") if isinstance(package_dict.get("captions"), dict) else {}

        def _safe_str(val: Any) -> str:
            if val is None or isinstance(val, (dict, list, bool)):
                return ""
            return str(val)

        fields_to_check = [
            ("headline", _safe_str(creative.get("headline"))),
            ("primary_text", _safe_str(creative.get("primary_text"))),
            ("video_hook", _safe_str(script.get("hook_3s"))),
            ("video_body", _safe_str(script.get("problem_solution"))),
            ("meta_caption", _safe_str(captions.get("meta_caption"))),
            ("instagram_caption", _safe_str(captions.get("instagram_caption"))),
        ]

        has_disclaimer_anywhere = False

        for location, content in fields_to_check:
            if not content.strip():
                continue
            all_text.append(content)
            res = self.verify_text(content, location=location)
            combined_violations.extend(res.violations)
            if res.has_mandatory_disclaimer:
                has_disclaimer_anywhere = True

        # Check alternative headlines if present
        raw_alt_headlines = creative.get("alternative_headlines")
        alt_headlines = raw_alt_headlines if isinstance(raw_alt_headlines, list) else []
        for alt_h in alt_headlines:
            cleaned_alt = _safe_str(alt_h)
            if cleaned_alt.strip():
                res = self.verify_text(cleaned_alt, location="alternative_headline")
                combined_violations.extend(res.violations)

        if any(v.severity == ComplianceStatus.BLOCK for v in combined_violations):
            overall_status = ComplianceStatus.BLOCK
            passed = False
        elif combined_violations or not has_disclaimer_anywhere:
            overall_status = ComplianceStatus.FLAG
            passed = False
        else:
            overall_status = ComplianceStatus.PASS
            passed = True

        feedback_lines = []
        for v in combined_violations:
            feedback_lines.append(f"[{v.location}] Remove '{v.phrase}': {v.citation}")
        if not has_disclaimer_anywhere:
            feedback_lines.append("Add mandatory statutory disclaimer to primary copy.")

        return ComplianceVerdict(
            status=overall_status,
            passed=passed,
            violations=combined_violations,
            has_mandatory_disclaimer=has_disclaimer_anywhere,
            rules_version=SEBI_RULES_VERSION,
            feedback_for_revision="\n".join(feedback_lines),
        )
