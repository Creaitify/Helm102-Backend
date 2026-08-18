"""Unit tests for Qualitative Citation Verifier and Brand Voice Grounding Engine."""

from __future__ import annotations

import pytest
from services.api.knowledge.citations import (
    BrandCorpus,
    CitationSpan,
    CitationVerifier,
    CorpusDocument,
    CorpusDocumentType,
    DocumentSection,
    GroundingVerdict,
)


@pytest.fixture
def corpus() -> BrandCorpus:
    """Fixture providing the default reference corpus."""
    return BrandCorpus.default_corpus()


@pytest.fixture
def verifier(corpus: BrandCorpus) -> CitationVerifier:
    """Fixture providing a CitationVerifier initialized with the default corpus."""
    return CitationVerifier(corpus=corpus)


# -----------------------------------------------------------------------------
# 1. BrandCorpus Tests
# -----------------------------------------------------------------------------


def test_brand_corpus_default_initialization(corpus: BrandCorpus) -> None:
    """Verify that default corpus loads SEBI, Brand Voice, Product Specs, and Personas."""
    docs = corpus.list_documents()
    assert len(docs) >= 4

    # Check SEBI doc
    sebi_doc = corpus.get_document("sebi_ad_code")
    assert sebi_doc is not None
    assert sebi_doc.doc_type == CorpusDocumentType.REGULATORY
    assert len(sebi_doc.sections) >= 3

    # Check Brand Voice doc
    brand_doc = corpus.get_document("brand_voice_guide")
    assert brand_doc is not None
    assert brand_doc.doc_type == CorpusDocumentType.BRAND_VOICE

    # Check Product Specs doc
    prod_doc = corpus.get_document("product_specs_doc")
    assert prod_doc is not None
    assert prod_doc.doc_type == CorpusDocumentType.PRODUCT_SPEC

    # Check Personas doc
    persona_doc = corpus.get_document("personas_doc")
    assert persona_doc is not None
    assert persona_doc.doc_type == CorpusDocumentType.PERSONA


def test_brand_corpus_filter_by_type(corpus: BrandCorpus) -> None:
    """Test filtering documents by type."""
    reg_docs = corpus.list_documents(CorpusDocumentType.REGULATORY)
    assert len(reg_docs) == 1
    assert reg_docs[0].id == "sebi_ad_code"

    voice_docs = corpus.list_documents(CorpusDocumentType.BRAND_VOICE)
    assert len(voice_docs) == 1
    assert voice_docs[0].id == "brand_voice_guide"


def test_brand_corpus_custom_document_and_search() -> None:
    """Test adding custom documents and searching sections."""
    corpus = BrandCorpus()
    custom_sec = DocumentSection(
        section_id="tax_80c",
        doc_id="tax_guide",
        title="Section 80C ELSS Benefits",
        content="Invest in ELSS funds to claim tax deduction up to ₹1.5 lakh under Section 80C with a 3-year lock-in.",
        keywords=["tax", "80c", "elss", "deduction"],
    )
    custom_doc = CorpusDocument(
        id="tax_guide",
        title="Income Tax Guidelines for Mutual Funds",
        doc_type=CorpusDocumentType.REGULATORY,
        content="Overview of Section 80C and capital gains tax rules.",
        sections=[custom_sec],
    )
    corpus.add_document(custom_doc)

    assert corpus.get_document("tax_guide") is not None
    results = corpus.search_sections("tax 80c elss")
    assert len(results) >= 1
    assert results[0].section_id == "tax_80c"
    assert "₹1.5 lakh" in results[0].content


def test_brand_corpus_product_specs(corpus: BrandCorpus) -> None:
    """Test registering and retrieving product specs."""
    specs = corpus.get_product_specs()
    assert "finnovate_dynamic_sip" in specs
    assert specs["finnovate_dynamic_sip"]["min_sip_amount"] == 500

    assert "finnovate_liquid_reserve" in specs
    assert specs["finnovate_liquid_reserve"]["instant_withdrawal_max_inr"] == 50000


# -----------------------------------------------------------------------------
# 2. Compliant vs Ungrounded Claim Verification Tests
# -----------------------------------------------------------------------------


def test_compliant_claim_verification(verifier: CitationVerifier) -> None:
    """Test that compliant claims with approved pillars and disclaimers pass with high score."""
    text = (
        "Build long-term wealth through disciplined investing and systematic investment plans. "
        "Start your SIP with ₹500/month with zero commission direct mutual funds. "
        "Mutual fund investments are subject to market risks, read all scheme related documents carefully."
    )
    verdict = verifier.verify_text(text, location="body")

    assert verdict.is_fully_grounded is True
    assert verdict.overall_grounding_score >= 0.85
    assert verdict.regulatory_score >= 0.95
    assert verdict.brand_voice_score >= 0.85
    assert verdict.product_accuracy_score >= 0.85
    assert len(verdict.violations) == 0

    # Ensure citations are extracted
    assert len(verdict.spans) >= 3
    grounded_types = {s.grounding_type for s in verdict.spans}
    assert "brand_voice_aligned" in grounded_types
    assert "product_spec_verified" in grounded_types
    assert "sebi_compliant" in grounded_types


def test_sebi_hard_block_claim(verifier: CitationVerifier) -> None:
    """Test that guaranteed return or zero risk triggers hard regulatory block."""
    text = "Invest in our fund for guaranteed return of 18% with zero risk!"
    verdict = verifier.verify_claim(text)

    assert verdict.is_fully_grounded is False
    assert verdict.regulatory_score == 0.0
    assert verdict.overall_grounding_score <= 0.15
    assert len(verdict.violations) >= 2

    # Check violations contains citations
    violation_str = " ".join(verdict.violations)
    assert "guaranteed return" in violation_str
    assert "zero risk" in violation_str

    # Check spans
    block_spans = [s for s in verdict.spans if s.grounding_type == "regulatory_violation"]
    assert len(block_spans) >= 2
    assert any(s.source_section == "Reg 4(1)" for s in block_spans)
    assert any(s.source_section == "Reg 4(2)" for s in block_spans)


def test_sebi_superlative_warning_flag(verifier: CitationVerifier) -> None:
    """Test that superlative claims without benchmark trigger warning flags."""
    text = "We provide the highest returns in the market. Mutual fund investments are subject to market risks."
    verdict = verifier.verify_text(text)

    assert verdict.is_fully_grounded is False
    assert verdict.regulatory_score < 0.90
    assert any("highest returns" in v for v in verdict.violations)
    assert any("Clause 5" in s.source_section for s in verdict.spans if "highest returns" in s.claim_text)


def test_brand_voice_violations(verifier: CitationVerifier) -> None:
    """Test that hype and FOMO terminology trigger brand voice violations."""
    text = "Use this secret hack to get rich quick and watch your portfolio skyrocket!"
    verdict = verifier.verify_text(text)

    assert verdict.is_fully_grounded is False
    assert verdict.brand_voice_score < 0.50
    assert len(verdict.violations) >= 3

    violation_str = " ".join(verdict.violations)
    assert "get rich quick" in violation_str
    assert "secret hack" in violation_str
    assert "skyrocket" in violation_str

    # Check recommendations
    assert any("sensationalist" in r.lower() for r in verdict.recommendations)


def test_product_spec_mismatch(verifier: CitationVerifier) -> None:
    """Test that claiming instant withdrawal above limits triggers product spec mismatch."""
    text = "Finnovate Liquid Reserve allows you to instantly withdraw up to ₹10 Lakhs within 30 seconds."
    verdict = verifier.verify_text(text)

    assert verdict.is_fully_grounded is False
    assert verdict.product_accuracy_score < 0.30
    assert any("spec mismatch" in v.lower() or "PRODUCT_SPEC_MISMATCH" in v for v in verdict.violations)

    mismatch_spans = [s for s in verdict.spans if s.grounding_type == "product_spec_mismatch"]
    assert len(mismatch_spans) == 1
    assert "₹50,000" in mismatch_spans[0].source_quote


# -----------------------------------------------------------------------------
# 3. Citation Span Extraction & Offsets Tests
# -----------------------------------------------------------------------------


def test_citation_span_exact_character_offsets(verifier: CitationVerifier) -> None:
    """Verify that start_char and end_char exactly match substrings in input text."""
    text = "Start disciplined investing with ₹500 SIP. Avoid get rich quick traps."
    spans = verifier.extract_citation_spans(text)

    assert len(spans) >= 3
    for s in spans:
        extracted = text[s.start_char:s.end_char]
        assert extracted == s.claim_text
        assert 0.0 <= s.confidence_score <= 1.0


def test_confidence_score_ranges(verifier: CitationVerifier) -> None:
    """Verify confidence score ranges for different grounding types."""
    text = "Disciplined investing gives guaranteed profit. Start SIP with ₹500."
    spans = verifier.extract_citation_spans(text)

    for s in spans:
        if s.grounding_type in ("brand_voice_aligned", "product_spec_verified", "sebi_compliant"):
            assert s.confidence_score >= 0.85
            assert s.is_grounded is True
        elif s.grounding_type in ("regulatory_violation", "brand_voice_violation", "product_spec_mismatch"):
            assert s.confidence_score <= 0.50
            assert s.is_grounded is False


# -----------------------------------------------------------------------------
# 4. Creative Package Verification & Serialization Tests
# -----------------------------------------------------------------------------


def test_creative_package_verification_compliant(verifier: CitationVerifier) -> None:
    """Test full creative package verification when all components are grounded."""
    package = {
        "brief": {
            "value_proposition": "Disciplined monthly SIP investing with rupee cost averaging and 0% commission.",
        },
        "script": {
            "hook_3s": "Want to build long-term compounding without timing the market?",
            "problem_solution": "Start a systematic investment plan with just ₹500 monthly.",
        },
        "creative": {
            "headline": "Start Systematic SIP with ₹500/month",
            "primary_text": "Zero commission direct mutual funds. Subject to market risks, read all scheme related documents carefully.",
            "alternative_headlines": ["Disciplined Investing Made Simple"],
        },
        "captions": {
            "meta_caption": "Grow your wealth systematically. Mutual fund investments are subject to market risks.",
            "instagram_caption": "Start with ₹500/mo. Read all scheme related documents carefully.",
        },
    }

    verdict = verifier.verify_package(package)
    assert verdict.is_fully_grounded is True
    assert verdict.overall_grounding_score >= 0.85
    assert verdict.regulatory_score >= 0.90
    assert len(verdict.violations) == 0


def test_creative_package_verification_non_compliant(verifier: CitationVerifier) -> None:
    """Test full creative package verification when ungrounded claims are present."""
    package = {
        "brief": {
            "value_proposition": "Get rich quick with guaranteed returns",
        },
        "script": {
            "hook_3s": "Cannot lose your money with this foolproof hack!",
            "problem_solution": "Double your money with zero risk.",
        },
        "creative": {
            "headline": "Guaranteed Profit Every Month",
            "primary_text": "Highest returns guaranteed.",
            "alternative_headlines": ["100% Safe Investment"],
        },
        "captions": {
            "meta_caption": "Moonshot gains await!",
            "instagram_caption": "Secret hack for insane gains.",
        },
    }

    verdict = verifier.verify_package(package)
    assert verdict.is_fully_grounded is False
    assert verdict.overall_grounding_score <= 0.20
    assert len(verdict.violations) >= 5
    assert len(verdict.recommendations) >= 3


def test_suggest_grounded_revisions(verifier: CitationVerifier) -> None:
    """Test revision suggestions for ungrounded/violating text."""
    text = "We promise guaranteed return with zero risk. Use this secret hack to get rich quick!"
    suggestions = verifier.suggest_grounded_revisions(text)

    assert len(suggestions) >= 3
    sugg_str = " ".join(suggestions)
    assert "disciplined long-term" in sugg_str.lower()
    assert "diversification" in sugg_str.lower()
    assert "disclaimer" in sugg_str.lower()


def test_dict_serialization(verifier: CitationVerifier) -> None:
    """Test to_dict serialization on all data structures."""
    doc = verifier.corpus.get_document("sebi_ad_code")
    assert doc is not None
    doc_dict = doc.to_dict()
    assert doc_dict["id"] == "sebi_ad_code"
    assert len(doc_dict["sections"]) > 0

    verdict = verifier.verify_text("Disciplined investing with ₹500 SIP. Subject to market risks.")
    v_dict = verdict.to_dict()
    assert "overall_grounding_score" in v_dict
    assert "regulatory_score" in v_dict
    assert "brand_voice_score" in v_dict
    assert "product_accuracy_score" in v_dict
    assert "spans" in v_dict
    assert len(v_dict["spans"]) >= 2
