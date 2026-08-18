"""Empirical Adversarial Stress Suite for SEBI Compliance Verifier.
Authored by Challenger 3.

Covers:
- Comprehensive evasion matrix (dots, hyphens, underscores, spaces, newlines, colons, punctuation)
- Single-letter spaced words and 2-letter evasion words ('n o   r i s k')
- Malformed dictionary null safety and type safety
- Substring boundary false positive immunity
"""

import pytest
from modules.compliance.verifier import (
    SEBIComplianceVerifier,
    ComplianceStatus,
    HARD_BLOCK_RULES,
    WARN_RULES,
    MANDATORY_DISCLAIMER_PHRASES,
)

DISCLAIMER = " Mutual fund investments are subject to market risks, read all scheme related documents carefully."


class TestSEBIComplianceChallenger3:
    """Adversarial challenge test suite for SEBI Compliance Verifier."""

    @pytest.mark.parametrize(
        "evasion_phrase,expected_status",
        [
            # Delimiters
            ("g.u.a.r.a.n.t.e.e.d   r.e.t.u.r.n", ComplianceStatus.BLOCK),
            ("a.s.s.u.r.e.d   p.r.o.f.i.t", ComplianceStatus.BLOCK),
            ("r.i.s.k. .f.r.e.e", ComplianceStatus.BLOCK),
            ("c.a.n.n.o.t   l.o.s.e", ComplianceStatus.BLOCK),
            ("z.e.r.o   r.i.s.k", ComplianceStatus.BLOCK),
            ("d.o.u.b.l.e   y.o.u.r   m.o.n.e.y", ComplianceStatus.BLOCK),
            ("guaranteed-return", ComplianceStatus.BLOCK),
            ("assured-return", ComplianceStatus.BLOCK),
            ("guaranteed_return", ComplianceStatus.BLOCK),
            ("assured_profit", ComplianceStatus.BLOCK),
            ("risk-free", ComplianceStatus.BLOCK),
            ("risk_free", ComplianceStatus.BLOCK),
            ("zero-risk", ComplianceStatus.BLOCK),
            ("zero_risk", ComplianceStatus.BLOCK),
            ("no-risk", ComplianceStatus.BLOCK),
            ("no_risk", ComplianceStatus.BLOCK),
            ("cannot-lose", ComplianceStatus.BLOCK),
            ("cannot_lose", ComplianceStatus.BLOCK),
            ("double-your-money", ComplianceStatus.BLOCK),
            ("double_your_money", ComplianceStatus.BLOCK),
            ("guaranteed\nreturn", ComplianceStatus.BLOCK),
            ("assured\nprofit", ComplianceStatus.BLOCK),
            ("guaranteed\t\treturn", ComplianceStatus.BLOCK),
            ("safe-investment", ComplianceStatus.FLAG),
            ("safe_investment", ComplianceStatus.FLAG),
            ("best-returns", ComplianceStatus.FLAG),
            ("highest-returns", ComplianceStatus.FLAG),
            ("always-profitable", ComplianceStatus.FLAG),
            ("always_profitable", ComplianceStatus.FLAG),
            ("g:u:a:r:a:n:t:e:e:d", ComplianceStatus.FLAG),
            ("g!u!a!r!a!n!t!e!e!d", ComplianceStatus.FLAG),
            ("g@u@a@r@a@n@t@e@e@d", ComplianceStatus.FLAG),
            ("g#u#a#r#a#n#t#e#e#d", ComplianceStatus.FLAG),
            ("n o   r i s k", ComplianceStatus.BLOCK),
            ("z e r o   r i s k", ComplianceStatus.BLOCK),
            ("z e r o r i s k", ComplianceStatus.BLOCK),
            ("d o u b l e   y o u r   m o n e y", ComplianceStatus.BLOCK),
        ],
    )
    def test_evasion_matrix_delimiters_and_spacing(self, evasion_phrase: str, expected_status: ComplianceStatus):
        verifier = SEBIComplianceVerifier()
        text = f"Invest now with our {evasion_phrase} plan!{DISCLAIMER}"
        res = verifier.verify_text(text)
        assert res.status == expected_status
        assert not res.passed

    def test_false_positive_immunity(self):
        """Ensure legitimate financial phrases with common substrings are not incorrectly blocked."""
        verifier = SEBIComplianceVerifier()
        legit_phrases = [
            f"Analyze your risk profile before making investment decisions.{DISCLAIMER}",
            f"Understand equity market returns and volatility.{DISCLAIMER}",
            f"Evaluate credit risk and interest rate duration.{DISCLAIMER}",
            f"Understand casino risk metrics before gaming.{DISCLAIMER}",
            f"Domino risk in interconnected debt markets.{DISCLAIMER}",
        ]
        for phrase in legit_phrases:
            res = verifier.verify_text(phrase)
            assert res.passed is True
            assert res.status == ComplianceStatus.PASS
            assert len(res.violations) == 0

    def test_malformed_dictionary_null_safety(self):
        """Test extreme malformed packages for null safety and graceful handling."""
        verifier = SEBIComplianceVerifier()

        # Valid empty package
        res_empty = verifier.verify_package({})
        assert res_empty.status == ComplianceStatus.FLAG
        assert not res_empty.passed

        # None values inside fields
        res_none = verifier.verify_package({
            "creative": {"headline": None, "primary_text": f"SIP investing.{DISCLAIMER}"},
            "script": {"hook_3s": None, "problem_solution": None},
            "captions": None,
        })
        assert res_none.status == ComplianceStatus.PASS
        assert res_none.passed

        # Non-dict package payloads
        for bad_pkg in [None, "string_payload", 12345, [1, 2, 3], True, False]:
            res_bad = verifier.verify_package(bad_pkg)
            assert res_bad.status == ComplianceStatus.FLAG
            assert not res_bad.passed

        # Malformed subkeys (strings, ints, lists in unexpected places)
        res_bad_subkeys = verifier.verify_package({
            "creative": "not_a_dict",
            "script": 12345,
            "captions": ["not", "a", "dict"],
        })
        assert res_bad_subkeys.status == ComplianceStatus.FLAG
        assert not res_bad_subkeys.passed

        # Malformed alternative_headlines
        res_bad_alt = verifier.verify_package({
            "creative": {
                "headline": f"Smart SIP Investing{DISCLAIMER}",
                "primary_text": f"Wealth building strategy.{DISCLAIMER}",
                "alternative_headlines": 9999,
            }
        })
        assert res_bad_alt.status == ComplianceStatus.PASS
        assert res_bad_alt.passed
