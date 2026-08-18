"""Qualitative Citation Verifier and Brand Voice Grounding Engine.

Verifies creative claims, copy, disclaimers, and scripts against:
- SEBI Advertising Codes & Regulatory Clauses
- Brand Voice & Persona Guidelines
- Product Specifications & Numerical Limits
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CorpusDocumentType(StrEnum):
    """Types of grounding documents in the BrandCorpus."""

    REGULATORY = "regulatory"
    BRAND_VOICE = "brand_voice"
    PRODUCT_SPEC = "product_spec"
    PERSONA = "persona"


@dataclass(frozen=True, slots=True)
class DocumentSection:
    """A granular section or clause within a corpus document."""

    section_id: str
    doc_id: str
    title: str
    content: str
    keywords: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    specs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "keywords": self.keywords,
            "rules": self.rules,
            "specs": self.specs,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    """A top-level reference document in the BrandCorpus."""

    id: str
    title: str
    doc_type: CorpusDocumentType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[DocumentSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "doc_type": self.doc_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "sections": [s.to_dict() for s in self.sections],
        }


@dataclass(frozen=True, slots=True)
class CitationSpan:
    """A verified citation span extracted from candidate text."""

    claim_text: str
    start_char: int
    end_char: int
    is_grounded: bool
    grounding_type: str  # "sebi_compliant", "regulatory_violation", "brand_voice_aligned", "brand_voice_violation", "product_spec_verified", "product_spec_mismatch", "ungrounded_claim"
    source_doc_id: str
    source_section: str
    source_quote: str
    confidence_score: float  # 0.0 to 1.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_text": self.claim_text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "is_grounded": self.is_grounded,
            "grounding_type": self.grounding_type,
            "source_doc_id": self.source_doc_id,
            "source_section": self.source_section,
            "source_quote": self.source_quote,
            "confidence_score": round(self.confidence_score, 4),
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class GroundingVerdict:
    """Aggregated grounding verdict across all qualitative dimensions."""

    text: str
    is_fully_grounded: bool
    overall_grounding_score: float  # 0.0 to 1.0
    regulatory_score: float  # 0.0 to 1.0
    brand_voice_score: float  # 0.0 to 1.0
    product_accuracy_score: float  # 0.0 to 1.0
    spans: list[CitationSpan] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "is_fully_grounded": self.is_fully_grounded,
            "overall_grounding_score": round(self.overall_grounding_score, 4),
            "regulatory_score": round(self.regulatory_score, 4),
            "brand_voice_score": round(self.brand_voice_score, 4),
            "product_accuracy_score": round(self.product_accuracy_score, 4),
            "spans": [s.to_dict() for s in self.spans],
            "violations": self.violations,
            "recommendations": self.recommendations,
        }


# Standard SEBI Rules and Disclaimers
SEBI_HARD_BLOCKS: dict[str, tuple[str, str, str]] = {
    # phrase -> (doc_id, clause_name, rule_quote)
    "guaranteed return": (
        "sebi_ad_code",
        "Reg 4(1)",
        "SEBI (Prohibition of Fraudulent and Unfair Trade Practices) Reg 4(1) - Prohibits guaranteed return claims on market-linked securities.",
    ),
    "assured return": (
        "sebi_ad_code",
        "Circular 2019/17",
        "SEBI Circular SEBI/HO/IMD/DF2/CIR/P/2019/17 - Strict ban on assured returns in mutual funds.",
    ),
    "guaranteed profit": (
        "sebi_ad_code",
        "Clause 2(b)",
        "SEBI Advertisement Code Clause 2(b) - False assurance of profitability.",
    ),
    "assured profit": (
        "sebi_ad_code",
        "Clause 2(b)",
        "SEBI Advertisement Code Clause 2(b) - Prohibited assurance of capital growth.",
    ),
    "risk-free": (
        "sebi_ad_code",
        "Reg 4(2)",
        "SEBI Reg 4(2) - Misleading representation of market-linked securities as risk-free.",
    ),
    "risk free": (
        "sebi_ad_code",
        "Reg 4(2)",
        "SEBI Reg 4(2) - Misleading representation of market-linked securities as risk-free.",
    ),
    "zero risk": (
        "sebi_ad_code",
        "Reg 4(2)",
        "SEBI Reg 4(2) - Denial of market risk is prohibited.",
    ),
    "no risk": (
        "sebi_ad_code",
        "Reg 4(2)",
        "SEBI Reg 4(2) - Absolute denial of market risk.",
    ),
    "double your money": (
        "sebi_ad_code",
        "Clause 4(a)",
        "SEBI Advertisement Code Clause 4(a) - Unrealistic multiplication promise.",
    ),
    "cannot lose": (
        "sebi_ad_code",
        "Reg 19(1)",
        "SEBI (Investment Advisers) Reg 19(1) - Absolute loss-immunity claims strictly forbidden.",
    ),
    "100% safe": (
        "sebi_ad_code",
        "Clause 6",
        "SEBI Clause 6 - 100% safety claims on volatile or market-linked assets are prohibited.",
    ),
}

SEBI_WARNING_FLAGS: dict[str, tuple[str, str, str]] = {
    "highest returns": (
        "sebi_ad_code",
        "Clause 5",
        "SEBI Advertising Code Clause 5 - Superlative performance claims require benchmark and peer disclosures.",
    ),
    "best returns": (
        "sebi_ad_code",
        "Clause 5",
        "SEBI Advertising Code Clause 5 - Unsubstantiated superlative claim.",
    ),
    "safe investment": (
        "sebi_ad_code",
        "Clause 6",
        "SEBI Clause 6 - Safety claims on volatile assets require prominent risk categorisation.",
    ),
    "always profitable": (
        "sebi_ad_code",
        "Clause 2(c)",
        "SEBI Clause 2(c) - Omission of downside market volatility.",
    ),
    "guaranteed": (
        "sebi_ad_code",
        "Clause 3(a)",
        "SEBI Clause 3(a) - Unqualified guarantee terminology.",
    ),
    "assured": (
        "sebi_ad_code",
        "Clause 3(a)",
        "SEBI Clause 3(a) - Unqualified assurance terminology.",
    ),
}

MANDATORY_DISCLAIMER_PATTERNS: tuple[str, ...] = (
    "market risks",
    "subject to market risk",
    "scheme related documents",
    "read all scheme related documents carefully",
)

BRAND_FORBIDDEN_WORDS: dict[str, tuple[str, str, str]] = {
    # phrase -> (doc_id, section, rationale)
    "get rich quick": (
        "brand_voice_guide",
        "Tone & Ethos",
        "Violates Finnovate brand integrity. Promote disciplined compounding, not get-rich-quick schemes.",
    ),
    "secret hack": (
        "brand_voice_guide",
        "Pillar: Transparency",
        "Deceptive jargon. We use transparent, data-backed systematic investing principles.",
    ),
    "foolproof": (
        "brand_voice_guide",
        "Pillar: Honesty",
        "Unrealistic certainty. All financial strategies involve trade-offs and market realities.",
    ),
    "skyrocket": (
        "brand_voice_guide",
        "Pillar: No Hyperbole",
        "Sensationalist hype prohibited. Use grounded metrics like CAGR, XIRR, or historical index performance.",
    ),
    "moonshot": (
        "brand_voice_guide",
        "Pillar: No Hyperbole",
        "Cryptocurrency/gambling slang prohibited. Maintain institutional-grade advisory tone.",
    ),
    "insane gains": (
        "brand_voice_guide",
        "Pillar: No Hyperbole",
        "Hyperbolic language violates brand voice.",
    ),
    "can't miss": (
        "brand_voice_guide",
        "Pillar: No FOMO",
        "High-pressure FOMO tactics violate brand values.",
    ),
    "100x": (
        "brand_voice_guide",
        "Pillar: No Hyperbole",
        "Unsubstantiated multi-bagger hype.",
    ),
}

BRAND_APPROVED_PILLARS: list[tuple[str, str, str]] = [
    (
        "disciplined investing",
        "brand_voice_guide",
        "Pillars of Wealth Creation: Consistent, rule-based monthly contributions outpace emotional timing.",
    ),
    (
        "systematic investment",
        "brand_voice_guide",
        "Pillars of Wealth Creation: SIP methodology enables automated rupee-cost averaging.",
    ),
    (
        "rupee cost averaging",
        "brand_voice_guide",
        "Core Concepts: Buying more units during dips lowers average unit cost over time.",
    ),
    (
        "long-term compounding",
        "brand_voice_guide",
        "Core Concepts: Harnessing compound interest over 5+ year horizons.",
    ),
    (
        "portfolio diversification",
        "brand_voice_guide",
        "Risk Mitigation: Allocating across large, mid, and multi-cap assets reduces idiosyncratic risk.",
    ),
    (
        "transparency",
        "brand_voice_guide",
        "Brand Values: 100% direct mutual funds with zero distributor commission fees.",
    ),
]


class BrandCorpus:
    """Repository of brand voice guidelines, regulatory rules, product specs, and personas."""

    def __init__(self) -> None:
        self._documents: dict[str, CorpusDocument] = {}
        self._product_specs: dict[str, dict[str, Any]] = {}

    def add_document(self, doc: CorpusDocument) -> None:
        """Register a corpus document."""
        self._documents[doc.id] = doc

    def get_document(self, doc_id: str) -> CorpusDocument | None:
        """Retrieve a corpus document by ID."""
        return self._documents.get(doc_id)

    def list_documents(
        self, doc_type: CorpusDocumentType | str | None = None
    ) -> list[CorpusDocument]:
        """List all documents, optionally filtered by type."""
        if doc_type is None:
            return list(self._documents.values())
        target_type = doc_type if isinstance(doc_type, str) else doc_type.value
        return [
            doc for doc in self._documents.values() if doc.doc_type.value == target_type
        ]

    def add_product_spec(self, product_id: str, specs: dict[str, Any]) -> None:
        """Register or update a product specification."""
        self._product_specs[product_id] = specs

    def get_product_specs(self) -> dict[str, dict[str, Any]]:
        """Get all registered product specifications."""
        return dict(self._product_specs)

    def search_sections(
        self,
        query: str,
        doc_type: CorpusDocumentType | str | None = None,
        top_k: int = 5,
    ) -> list[DocumentSection]:
        """Search sections across documents matching query tokens."""
        tokens = set(re.findall(r"\w+", query.lower()))
        if not tokens:
            return []

        scored_sections: list[tuple[float, DocumentSection]] = []
        for doc in self.list_documents(doc_type):
            for sec in doc.sections:
                sec_text = (sec.title + " " + sec.content + " " + " ".join(sec.keywords)).lower()
                matches = sum(1 for t in tokens if t in sec_text)
                if matches > 0:
                    score = matches / max(len(tokens), 1)
                    scored_sections.append((score, sec))

        scored_sections.sort(key=lambda x: x[0], reverse=True)
        return [sec for _, sec in scored_sections[:top_k]]

    @classmethod
    def default_corpus(cls) -> BrandCorpus:
        """Initialize standard HELM02 Finnovate & SEBI reference corpus."""
        corpus = cls()

        # 1. SEBI Regulatory Document
        sebi_sections = [
            DocumentSection(
                section_id="sebi_prohibitions",
                doc_id="sebi_ad_code",
                title="Prohibited Statements & Guarantees",
                content="SEBI Reg 4(1) & Circular 2019/17 strictly prohibit promising guaranteed or assured returns on market-linked securities. Claiming zero risk or 100% safety is illegal.",
                keywords=["guaranteed", "assured", "risk-free", "zero risk", "profit"],
                rules=list(SEBI_HARD_BLOCKS.keys()),
            ),
            DocumentSection(
                section_id="sebi_superlatives",
                doc_id="sebi_ad_code",
                title="Superlatives & Benchmark Disclosures",
                content="SEBI Advertising Code Clause 5 requires that any claim of 'best returns' or 'highest performance' must cite verifiable benchmark and peer data.",
                keywords=["best returns", "highest returns", "benchmark", "superlatives"],
                rules=list(SEBI_WARNING_FLAGS.keys()),
            ),
            DocumentSection(
                section_id="sebi_mandatory_disclaimers",
                doc_id="sebi_ad_code",
                title="Mandatory Statutory Disclaimers",
                content="All mutual fund advertisements must clearly carry: 'Mutual fund investments are subject to market risks, read all scheme related documents carefully.'",
                keywords=["market risks", "scheme related documents", "statutory disclaimer"],
                rules=["market risks", "scheme related documents"],
            ),
        ]
        corpus.add_document(
            CorpusDocument(
                id="sebi_ad_code",
                title="SEBI Mutual Fund Advertising Code & Compliance Guidelines",
                doc_type=CorpusDocumentType.REGULATORY,
                content="Comprehensive SEBI code regulating financial promotions, risk disclosures, and prohibited guarantees.",
                metadata={"version": "2026-08-17", "jurisdiction": "IN"},
                sections=sebi_sections,
            )
        )

        # 2. Brand Voice Guide
        brand_sections = [
            DocumentSection(
                section_id="brand_ethos",
                doc_id="brand_voice_guide",
                title="Finnovate Brand Persona & Tone of Voice",
                content="Finnovate represents transparent, disciplined, data-driven wealth creation. We empower retail investors through mathematical clarity without hype, fear-mongering, or aggressive sales tactics.",
                keywords=["transparency", "disciplined", "empowerment", "data-driven", "no hype"],
            ),
            DocumentSection(
                section_id="brand_forbidden_terms",
                doc_id="brand_voice_guide",
                title="Forbidden Hype & FOMO Jargon",
                content="Never use sensationalist phrases such as 'get rich quick', 'secret hack', 'foolproof', 'skyrocket', 'moonshot', 'insane gains', or 'can't miss'.",
                keywords=["get rich quick", "secret hack", "foolproof", "skyrocket", "moonshot"],
                rules=list(BRAND_FORBIDDEN_WORDS.keys()),
            ),
            DocumentSection(
                section_id="brand_approved_pillars",
                doc_id="brand_voice_guide",
                title="Approved Messaging Pillars",
                content="Highlight disciplined monthly SIP investing, rupee-cost averaging during market cycles, zero commission on direct plans, and long-term portfolio diversification.",
                keywords=["sip", "disciplined investing", "rupee cost averaging", "diversification", "zero commission"],
            ),
        ]
        corpus.add_document(
            CorpusDocument(
                id="brand_voice_guide",
                title="Finnovate Brand Voice, Tone, and Editorial Guidelines",
                doc_type=CorpusDocumentType.BRAND_VOICE,
                content="Official voice guidelines defining brand personality, forbidden phrases, and approved value pillars.",
                metadata={"tone": "Empathetic, Transparent, Mathematically Rigorous"},
                sections=brand_sections,
            )
        )

        # 3. Product Specifications
        sip_specs = {
            "product_name": "Finnovate Dynamic SIP",
            "min_sip_amount": 500,
            "commission_rate": "0% (Direct Plan)",
            "exit_load": "0% after 365 days (1% if redeemed within 1 year)",
            "tax_saving_lock_in_years": 3,  # ELSS
            "portfolio_type": "Multi-Cap & Flexi-Cap Direct Equity Funds",
            "frequency": ["monthly", "weekly", "quarterly"],
        }
        corpus.add_product_spec("finnovate_dynamic_sip", sip_specs)

        liquid_specs = {
            "product_name": "Finnovate Liquid Reserve",
            "min_investment": 1000,
            "instant_withdrawal_max_inr": 50000,
            "instant_withdrawal_sla": "Under 30 seconds",
            "redemption_timeline_standard": "T+1 business day",
            "underlying_assets": "Overnight & Liquid Instruments with sovereign and AAA debt",
        }
        corpus.add_product_spec("finnovate_liquid_reserve", liquid_specs)

        prod_sections = [
            DocumentSection(
                section_id="spec_dynamic_sip",
                doc_id="product_specs_doc",
                title="Finnovate Dynamic SIP Specifications",
                content="Minimum monthly SIP is ₹500. 0% distributor commission via direct plans. Zero exit load after 365 days. 3-year statutory lock-in applies only to ELSS tax-saving funds.",
                keywords=["sip", "500", "commission", "exit load", "elss", "lock-in"],
                specs=sip_specs,
            ),
            DocumentSection(
                section_id="spec_liquid_reserve",
                doc_id="product_specs_doc",
                title="Finnovate Liquid Reserve Specifications",
                content="Minimum investment is ₹1,000. Instant 24x7 redemption up to ₹50,000 within seconds; amounts above ₹50k settle on T+1 working day.",
                keywords=["liquid", "1000", "instant withdrawal", "50000", "t+1"],
                specs=liquid_specs,
            ),
        ]
        corpus.add_document(
            CorpusDocument(
                id="product_specs_doc",
                title="Finnovate Verified Product Catalog & Specification Limits",
                doc_type=CorpusDocumentType.PRODUCT_SPEC,
                content="Authoritative product parameters, minimums, fee structures, liquidity limits, and lock-in periods.",
                sections=prod_sections,
            )
        )

        # 4. Investor Persona Documents
        persona_sections = [
            DocumentSection(
                section_id="persona_millennial",
                doc_id="personas_doc",
                title="Persona: Salaried Tech Millennial (Age 24-35)",
                content="Goals: Automated long-term wealth compounding and Section 80C tax optimization. Values seamless mobile UX, zero commission, and data transparency over sales hype.",
                keywords=["millennial", "tech", "salaried", "tax saving", "automation", "mobile"],
            ),
            DocumentSection(
                section_id="persona_conservative",
                doc_id="personas_doc",
                title="Persona: Conservative Wealth Builder (Age 45-58)",
                content="Goals: Beating inflation while safeguarding capital. Values steady liquid reserves, low volatility, debt allocation, and transparent institutional credibility.",
                keywords=["conservative", "capital protection", "liquid", "inflation beat", "pre-retiree"],
            ),
        ]
        corpus.add_document(
            CorpusDocument(
                id="personas_doc",
                title="Target Investor Personas & Psychological Profiles",
                doc_type=CorpusDocumentType.PERSONA,
                content="Behavioral guidelines and value propositions tailored by investor demographic segment.",
                sections=persona_sections,
            )
        )

        return corpus


class CitationVerifier:
    """Verifies grounding of creative claims and disclaimers against BrandCorpus."""

    def __init__(self, corpus: BrandCorpus | None = None) -> None:
        self.corpus = corpus or BrandCorpus.default_corpus()

    def extract_citation_spans(self, text: str) -> list[CitationSpan]:
        """Identify all citation spans (regulatory, brand voice, product spec, and ungrounded claims)."""
        spans: list[CitationSpan] = []
        lowered = text.lower()

        # 1. Regulatory Hard Blocks
        for phrase, (doc_id, clause, quote) in SEBI_HARD_BLOCKS.items():
            for match in re.finditer(re.escape(phrase), lowered):
                start, end = match.span()
                spans.append(
                    CitationSpan(
                        claim_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        is_grounded=False,
                        grounding_type="regulatory_violation",
                        source_doc_id=doc_id,
                        source_section=clause,
                        source_quote=quote,
                        confidence_score=0.05,
                        notes=f"Hard regulatory block: '{phrase}' is prohibited by {clause}.",
                    )
                )

        # 2. Regulatory Warning Flags
        for phrase, (doc_id, clause, quote) in SEBI_WARNING_FLAGS.items():
            for match in re.finditer(re.escape(phrase), lowered):
                start, end = match.span()
                # If already covered by a hard block span, skip
                if any(s.start_char <= start and end <= s.end_char for s in spans):
                    continue
                spans.append(
                    CitationSpan(
                        claim_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        is_grounded=False,
                        grounding_type="regulatory_violation",
                        source_doc_id=doc_id,
                        source_section=clause,
                        source_quote=quote,
                        confidence_score=0.45,
                        notes=f"Regulatory flag: '{phrase}' requires explicit benchmark disclosure or risk qualification.",
                    )
                )

        # 3. Brand Voice Forbidden Terms
        for phrase, (doc_id, section, rationale) in BRAND_FORBIDDEN_WORDS.items():
            for match in re.finditer(r"\b" + re.escape(phrase) + r"\b", lowered):
                start, end = match.span()
                if any(s.start_char <= start and end <= s.end_char for s in spans):
                    continue
                spans.append(
                    CitationSpan(
                        claim_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        is_grounded=False,
                        grounding_type="brand_voice_violation",
                        source_doc_id=doc_id,
                        source_section=section,
                        source_quote=rationale,
                        confidence_score=0.15,
                        notes=f"Brand voice violation: '{phrase}' contradicts brand tone guidelines.",
                    )
                )

        # 4. Mandatory Statutory Disclaimer Grounding
        for phrase in MANDATORY_DISCLAIMER_PATTERNS:
            for match in re.finditer(re.escape(phrase), lowered):
                start, end = match.span()
                spans.append(
                    CitationSpan(
                        claim_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        is_grounded=True,
                        grounding_type="sebi_compliant",
                        source_doc_id="sebi_ad_code",
                        source_section="Mandatory Disclaimers",
                        source_quote="Mutual fund investments are subject to market risks, read all scheme related documents carefully.",
                        confidence_score=0.98,
                        notes="Mandatory statutory disclaimer grounded in SEBI advertising code.",
                    )
                )

        # 5. Brand Approved Value Pillars Grounding
        for pillar_phrase, doc_id, quote in BRAND_APPROVED_PILLARS:
            for match in re.finditer(r"\b" + re.escape(pillar_phrase) + r"\b", lowered):
                start, end = match.span()
                spans.append(
                    CitationSpan(
                        claim_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        is_grounded=True,
                        grounding_type="brand_voice_aligned",
                        source_doc_id=doc_id,
                        source_section="Approved Pillars",
                        source_quote=quote,
                        confidence_score=0.95,
                        notes=f"Approved brand voice pillar: '{pillar_phrase}'.",
                    )
                )

        # 6. Product Spec Verification
        specs = self.corpus.get_product_specs()
        # Check SIP ₹500 spec
        sip_match = re.search(r"(?:₹|rs\.?|inr)?\s*500\s*(?:/\s*(?:month|mo)|monthly|sip)?", lowered)
        if sip_match and "500" in sip_match.group(0):
            start, end = sip_match.span()
            spans.append(
                CitationSpan(
                    claim_text=text[start:end],
                    start_char=start,
                    end_char=end,
                    is_grounded=True,
                    grounding_type="product_spec_verified",
                    source_doc_id="product_specs_doc",
                    source_section="spec_dynamic_sip",
                    source_quote="Finnovate Dynamic SIP: Minimum monthly SIP is ₹500.",
                    confidence_score=0.96,
                    notes="Verified product spec: ₹500 minimum SIP threshold.",
                )
            )

        # Check 0% commission spec
        commission_match = re.search(r"0%?\s*commission|zero\s*commission|direct\s*mutual\s*funds?", lowered)
        if commission_match:
            start, end = commission_match.span()
            spans.append(
                CitationSpan(
                    claim_text=text[start:end],
                    start_char=start,
                    end_char=end,
                    is_grounded=True,
                    grounding_type="product_spec_verified",
                    source_doc_id="product_specs_doc",
                    source_section="spec_dynamic_sip",
                    source_quote="Finnovate Dynamic SIP: 0% distributor commission via direct plans.",
                    confidence_score=0.97,
                    notes="Verified product spec: 0% commission direct fund structure.",
                )
            )

        # Check Instant Withdrawal limits
        liquid_instant_match = re.search(
            r"instant(?:ly)?\s*withdraw(?:al)?(?:\s*up\s*to)?\s*(?:₹|rs\.?|inr)?\s*([0-9,]+(?:\s*lakhs?|\s*k)?)",
            lowered,
        )
        if liquid_instant_match:
            start, end = liquid_instant_match.span()
            amount_str = liquid_instant_match.group(1).replace(",", "").strip()
            # If claiming instant withdrawal > 50,000 INR
            is_mismatch = (
                "lakh" in amount_str
                or (amount_str.isdigit() and int(amount_str) > 50000)
                or (amount_str.endswith("k") and int(amount_str[:-1]) > 50)
            )
            if is_mismatch:
                spans.append(
                    CitationSpan(
                        claim_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        is_grounded=False,
                        grounding_type="product_spec_mismatch",
                        source_doc_id="product_specs_doc",
                        source_section="spec_liquid_reserve",
                        source_quote="Finnovate Liquid Reserve: Instant 24x7 redemption up to ₹50,000 within seconds.",
                        confidence_score=0.10,
                        notes=f"Product spec mismatch: Claimed instant withdrawal ({amount_str}) exceeds approved ₹50,000 ceiling.",
                    )
                )
            else:
                spans.append(
                    CitationSpan(
                        claim_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        is_grounded=True,
                        grounding_type="product_spec_verified",
                        source_doc_id="product_specs_doc",
                        source_section="spec_liquid_reserve",
                        source_quote="Finnovate Liquid Reserve: Instant 24x7 redemption up to ₹50,000 within seconds.",
                        confidence_score=0.94,
                        notes="Verified product spec: Instant withdrawal within ₹50,000 limit.",
                    )
                )

        # Sort spans by character offset
        spans.sort(key=lambda s: (s.start_char, s.end_char))
        return spans

    def calculate_grounding_score(
        self, spans: list[CitationSpan], has_disclaimer: bool = True
    ) -> tuple[float, float, float, float]:
        """Calculate overall, regulatory, brand voice, and product accuracy confidence scores (0.0 to 1.0)."""
        reg_violations = [s for s in spans if s.grounding_type == "regulatory_violation"]
        reg_grounded = [s for s in spans if s.grounding_type == "sebi_compliant"]
        brand_violations = [s for s in spans if s.grounding_type == "brand_voice_violation"]
        brand_grounded = [s for s in spans if s.grounding_type == "brand_voice_aligned"]
        spec_mismatches = [s for s in spans if s.grounding_type == "product_spec_mismatch"]
        spec_grounded = [s for s in spans if s.grounding_type == "product_spec_verified"]

        # Regulatory score calculation
        has_hard_block = any(s.confidence_score <= 0.1 for s in reg_violations)
        if has_hard_block:
            regulatory_score = 0.0
        elif reg_violations:
            regulatory_score = max(0.2, 0.6 - (0.2 * len(reg_violations)))
        elif has_disclaimer:
            regulatory_score = 1.0
        else:
            regulatory_score = 0.70  # Clean of violations but missing mandatory statutory disclaimer

        # Brand voice score calculation
        if brand_violations:
            penalty = sum(1.0 - s.confidence_score for s in brand_violations)
            brand_voice_score = max(0.1, 0.7 - (0.25 * penalty))
        elif brand_grounded:
            brand_voice_score = min(1.0, 0.85 + (0.05 * len(brand_grounded)))
        else:
            brand_voice_score = 0.80  # Neutral tone without violations

        # Product accuracy score calculation
        if spec_mismatches:
            product_accuracy_score = 0.15
        elif spec_grounded:
            product_accuracy_score = min(1.0, 0.90 + (0.05 * len(spec_grounded)))
        else:
            product_accuracy_score = 0.85  # No specific numerical spec claims violated

        # Overall composite grounding score (0.40 reg, 0.35 product, 0.25 brand voice)
        if has_hard_block:
            overall_score = min(0.15, 0.40 * regulatory_score + 0.35 * product_accuracy_score + 0.25 * brand_voice_score)
        else:
            overall_score = (
                0.40 * regulatory_score
                + 0.35 * product_accuracy_score
                + 0.25 * brand_voice_score
            )

        return (
            round(overall_score, 4),
            round(regulatory_score, 4),
            round(brand_voice_score, 4),
            round(product_accuracy_score, 4),
        )

    def verify_claim(self, claim: str, location: str = "claim") -> GroundingVerdict:
        """Verify a single claim or short statement."""
        return self.verify_text(claim, location=location)

    def verify_text(self, text: str, location: str = "body") -> GroundingVerdict:
        """Verify candidate ad copy, headline, or script text."""
        spans = self.extract_citation_spans(text)
        lowered = text.lower()

        # Check for statutory disclaimer
        has_disclaimer = any(p in lowered for p in MANDATORY_DISCLAIMER_PATTERNS)

        overall, reg_score, brand_score, prod_score = self.calculate_grounding_score(
            spans, has_disclaimer=has_disclaimer
        )

        violations: list[str] = []
        recommendations: list[str] = []

        for s in spans:
            if not s.is_grounded:
                violations.append(f"[{s.grounding_type.upper()}] '{s.claim_text}': {s.notes}")
                if s.grounding_type == "regulatory_violation":
                    recommendations.append(f"Remove prohibited term '{s.claim_text}' cited to {s.source_section}.")
                elif s.grounding_type == "brand_voice_violation":
                    recommendations.append(f"Replace sensationalist term '{s.claim_text}' with grounded educational tone.")
                elif s.grounding_type == "product_spec_mismatch":
                    recommendations.append(f"Correct product spec claim '{s.claim_text}' to match registered specs ({s.source_quote}).")

        if not has_disclaimer and location in ("body", "primary_text", "caption"):
            violations.append("[REGULATORY] Missing statutory SEBI disclaimer.")
            recommendations.append("Append statutory disclaimer: 'Mutual fund investments are subject to market risks, read all scheme related documents carefully.'")

        is_fully_grounded = (
            len(violations) == 0
            and overall >= 0.85
            and reg_score >= 0.90
            and prod_score >= 0.80
        )

        return GroundingVerdict(
            text=text,
            is_fully_grounded=is_fully_grounded,
            overall_grounding_score=overall,
            regulatory_score=reg_score,
            brand_voice_score=brand_score,
            product_accuracy_score=prod_score,
            spans=spans,
            violations=violations,
            recommendations=recommendations,
        )

    def verify_package(self, package_dict: dict[str, Any]) -> GroundingVerdict:
        """Verify an entire creative package (brief, script, creative variants, and captions)."""
        combined_spans: list[CitationSpan] = []
        combined_violations: list[str] = []
        combined_recommendations: list[str] = []

        # Extract text components
        creative = package_dict.get("creative", {})
        script = package_dict.get("script", {})
        captions = package_dict.get("captions", {})
        brief = package_dict.get("brief", {})

        fields_to_check = [
            ("headline", creative.get("headline", "")),
            ("primary_text", creative.get("primary_text", "")),
            ("video_hook", script.get("hook_3s", "")),
            ("video_body", script.get("problem_solution", "")),
            ("meta_caption", captions.get("meta_caption", "")),
            ("instagram_caption", captions.get("instagram_caption", "")),
            ("value_prop", brief.get("value_proposition", "")),
        ]

        has_disclaimer_anywhere = False

        for location, text_content in fields_to_check:
            if not text_content:
                continue
            verdict = self.verify_text(text_content, location=location)
            combined_spans.extend(verdict.spans)
            combined_violations.extend(verdict.violations)
            combined_recommendations.extend(verdict.recommendations)
            if any(p in text_content.lower() for p in MANDATORY_DISCLAIMER_PATTERNS):
                has_disclaimer_anywhere = True

        # Check alternative headlines if present
        for alt_h in creative.get("alternative_headlines", []):
            if alt_h:
                verdict = self.verify_text(alt_h, location="alternative_headline")
                combined_spans.extend(verdict.spans)
                combined_violations.extend(verdict.violations)
                combined_recommendations.extend(verdict.recommendations)

        overall, reg_score, brand_score, prod_score = self.calculate_grounding_score(
            combined_spans, has_disclaimer=has_disclaimer_anywhere
        )

        is_fully_grounded = (
            len(combined_violations) == 0
            and overall >= 0.85
            and reg_score >= 0.90
            and prod_score >= 0.80
        )

        return GroundingVerdict(
            text="[CreativePackage Evaluation]",
            is_fully_grounded=is_fully_grounded,
            overall_grounding_score=overall,
            regulatory_score=reg_score,
            brand_voice_score=brand_score,
            product_accuracy_score=prod_score,
            spans=combined_spans,
            violations=combined_violations,
            recommendations=list(dict.fromkeys(combined_recommendations)),  # Deduplicate
        )

    def suggest_grounded_revisions(self, text: str) -> list[str]:
        """Suggest compliant, grounded replacement formulations for problematic phrasing."""
        suggestions: list[str] = []
        lowered = text.lower()

        # Suggest alternatives for guaranteed returns
        if "guaranteed return" in lowered or "assured return" in lowered:
            suggestions.append("Replace 'guaranteed return' with 'disciplined long-term wealth compounding'.")

        if "zero risk" in lowered or "risk-free" in lowered or "no risk" in lowered:
            suggestions.append("Replace 'risk-free' with 'risk-managed diversification across asset classes'.")

        if "get rich quick" in lowered or "skyrocket" in lowered or "secret hack" in lowered:
            suggestions.append("Replace hype wording with 'systematic rupee-cost averaging and automated SIP investing'.")

        if not any(p in lowered for p in MANDATORY_DISCLAIMER_PATTERNS):
            suggestions.append("Add SEBI statutory disclaimer: 'Mutual fund investments are subject to market risks, read all scheme related documents carefully.'")

        return suggestions
