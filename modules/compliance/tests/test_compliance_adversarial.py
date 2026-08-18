"""Empirical Adversarial Stress Tests for SEBI Compliance Verifier.

Tests evasive phrases, character spacing, punctuation manipulation,
delimiters, leetspeak/casing, missing disclaimers, and loopback revision.
"""

import pytest
from modules.compliance.verifier import (
    ComplianceStatus,
    HARD_BLOCK_RULES,
    MANDATORY_DISCLAIMER_PHRASES,
    SEBIComplianceVerifier,
    WARN_RULES,
)
from modules.creative.schema import (
    AdCreative,
    CreativeBrief,
    CreativePackage,
    PlatformCaptions,
    SceneCue,
    VideoScript,
)


class TestSEBIComplianceAdversarial:
    """Stress testing SEBI Compliance Verifier with adversarial evasion vectors."""

    def test_evasive_mixed_case_variations(self):
        """Verify mixed-case prohibited phrases are caught."""
        verifier = SEBIComplianceVerifier()
        test_cases = [
            ("GuArAnTeEd ReTuRn", ComplianceStatus.BLOCK),
            ("100% Risk Free!", ComplianceStatus.BLOCK),
            ("AsSuReD PrOfIt", ComplianceStatus.BLOCK),
            ("ZeRo RiSk", ComplianceStatus.BLOCK),
            ("CaNnOt LoSe", ComplianceStatus.BLOCK),
            ("DoUbLe YoUr MoNeY", ComplianceStatus.BLOCK),
            ("HiGhEsT rEtUrNs", ComplianceStatus.FLAG),
            ("BeSt ReTuRnS", ComplianceStatus.FLAG),
        ]
        for phrase, expected_status in test_cases:
            text = f"Invest now for {phrase}. Mutual fund investments are subject to market risks."
            res = verifier.verify_text(text)
            assert res.status == expected_status, f"Failed on '{phrase}': got {res.status}, expected {expected_status}"
            assert not res.passed

    def test_evasive_character_spaced_tricks(self):
        """Adversarial test: dot-separated and space-separated characters.
        e.g. 'g.u.a.r.a.n.t.e.e.d   r.e.t.u.r.n', 'g u a r a n t e e d   r e t u r n'
        """
        verifier = SEBIComplianceVerifier()
        
        # Test dots between characters
        text_dots = "Get g.u.a.r.a.n.t.e.e.d   r.e.t.u.r.n with our scheme. Mutual fund investments are subject to market risks."
        res_dots = verifier.verify_text(text_dots)
        assert res_dots.status == ComplianceStatus.BLOCK
        assert not res_dots.passed
        assert any("guaranteed return" in v.phrase for v in res_dots.violations)
        
        # Test spaced out characters
        text_spaces = "Get g u a r a n t e e d   r e t u r n on SIPs. Mutual fund investments are subject to market risks."
        res_spaces = verifier.verify_text(text_spaces)
        assert res_spaces.status == ComplianceStatus.BLOCK
        assert not res_spaces.passed
        assert any("guaranteed return" in v.phrase for v in res_spaces.violations)

    def test_evasive_punctuation_and_delimiters(self):
        """Adversarial test: Hyphens, underscores, multiple spaces, newlines."""
        verifier = SEBIComplianceVerifier()
        disclaimer = " Mutual fund investments are subject to market risks, read all scheme related documents carefully."
        
        evasions = [
            ("guaranteed-return", "Hyphenated guaranteed return"),
            ("guaranteed_return", "Underscored guaranteed return"),
            ("guaranteed   return", "Multi-space guaranteed return"),
            ("guaranteed\nreturn", "Newline guaranteed return"),
            ("guaranteed\t\treturn", "Tab separated guaranteed return"),
            ("risk_free", "Underscore risk free"),
            ("risk--free", "Double hyphen risk free"),
            ("zero-risk", "Hyphenated zero risk"),
            ("zero_risk", "Underscored zero risk"),
            ("no-risk", "Hyphenated no risk"),
            ("cannot-lose", "Hyphenated cannot lose"),
            ("double-your-money", "Hyphenated double your money"),
        ]
        
        for evasion, desc in evasions:
            text = f"Our fund offers {evasion} for all retail investors.{disclaimer}"
            res = verifier.verify_text(text)
            assert res.status == ComplianceStatus.BLOCK, f"Failed on {desc} ({evasion}): got {res.status}"
            assert not res.passed
            assert len(res.violations) > 0

    def test_missing_disclaimers_variations(self):
        """Test copy with missing or modified statutory disclaimers."""
        verifier = SEBIComplianceVerifier()
        
        # 1. Completely missing disclaimer
        res_none = verifier.verify_text("Invest ₹500 monthly in top index funds to grow wealth over 10 years.")
        assert res_none.status == ComplianceStatus.FLAG
        assert not res_none.passed
        assert not res_none.has_mandatory_disclaimer
        assert "Add mandatory SEBI disclaimer" in res_none.feedback_for_revision

        # 2. Valid disclaimer phrase 1: "market risks"
        res_p1 = verifier.verify_text("Invest ₹500 monthly. Mutual funds are subject to market risks.")
        assert res_p1.status == ComplianceStatus.PASS
        assert res_p1.passed
        assert res_p1.has_mandatory_disclaimer

        # 3. Valid disclaimer phrase 2: "scheme related documents"
        res_p2 = verifier.verify_text("Invest ₹500 monthly. Please read all scheme related documents carefully before investing.")
        assert res_p2.status == ComplianceStatus.PASS
        assert res_p2.passed
        assert res_p2.has_mandatory_disclaimer

        # 4. Valid disclaimer phrase 3: "subject to market risk"
        res_p3 = verifier.verify_text("Invest ₹500 monthly. Investments are subject to market risk.")
        assert res_p3.status == ComplianceStatus.PASS
        assert res_p3.passed
        assert res_p3.has_mandatory_disclaimer

    def test_package_verification_and_location_tracking(self):
        """Test creative package verification across all constituent fields."""
        verifier = SEBIComplianceVerifier()
        
        # Package where headline is non-compliant, but primary text has disclaimer
        pkg = {
            "creative": {
                "headline": "Guaranteed Return Investment Plan",
                "primary_text": "Invest systematically. Mutual fund investments are subject to market risks.",
                "call_to_action": "Invest Now",
                "alternative_headlines": ["Safe Investment Plan"],
            },
            "script": {
                "hook_3s": "Want 100% risk-free returns?",
                "problem_solution": "Beat market volatility.",
            },
            "captions": {
                "meta_caption": "Double your money in 3 years!",
                "instagram_caption": "Best returns guaranteed.",
            },
        }
        
        res = verifier.verify_package(pkg)
        assert res.status == ComplianceStatus.BLOCK
        assert not res.passed
        
        locations = {v.location for v in res.violations}
        assert "headline" in locations
        assert "video_hook" in locations
        assert "meta_caption" in locations
        assert len(res.violations) >= 3

    def test_package_verification_null_safety(self):
        """Test null safety and partial structures in package verification."""
        verifier = SEBIComplianceVerifier()

        # 1. Sub-keys explicitly None
        pkg_null_subkeys = {
            "creative": None,
            "script": None,
            "captions": None,
        }
        res1 = verifier.verify_package(pkg_null_subkeys)
        assert res1.status == ComplianceStatus.FLAG  # missing disclaimer
        assert not res1.passed
        assert not res1.has_mandatory_disclaimer

        # 2. None inside nested fields
        pkg_none_fields = {
            "creative": {
                "headline": None,
                "primary_text": "Invest in SIPs. Mutual fund investments are subject to market risks.",
                "alternative_headlines": None,
            },
            "script": {
                "hook_3s": None,
                "problem_solution": None,
            },
            "captions": None,
        }
        res2 = verifier.verify_package(pkg_none_fields)
        assert res2.status == ComplianceStatus.PASS
        assert res2.passed
        assert res2.has_mandatory_disclaimer

        # 3. Completely empty dictionary
        res3 = verifier.verify_package({})
        assert res3.status == ComplianceStatus.FLAG
        assert not res3.passed

