"""Tests for deterministic SEBI compliance rules."""

from modules.compliance.verifier import ComplianceStatus, SEBIComplianceVerifier


def test_sebi_hard_block_guaranteed_return():
    verifier = SEBIComplianceVerifier()
    res = verifier.verify_text("Get a guaranteed return of 18% with our high growth portfolio.")
    assert res.status == ComplianceStatus.BLOCK
    assert not res.passed
    assert any("guaranteed return" in v.phrase for v in res.violations)
    assert any("SEBI" in v.citation for v in res.violations)


def test_sebi_hard_block_risk_free():
    verifier = SEBIComplianceVerifier()
    res = verifier.verify_text("Our fund strategy is completely risk-free and secure.")
    assert res.status == ComplianceStatus.BLOCK
    assert not res.passed
    assert any("risk-free" in v.phrase for v in res.violations)


def test_sebi_flag_warn_words():
    verifier = SEBIComplianceVerifier()
    # Contains warning word "best returns"
    res = verifier.verify_text("Invest for best returns in top funds. Mutual fund investments are subject to market risks.")
    assert res.status == ComplianceStatus.FLAG
    assert not res.passed
    assert any("best returns" in v.phrase for v in res.violations)


def test_sebi_clean_copy_with_disclaimer_passes():
    verifier = SEBIComplianceVerifier()
    copy = "Build long-term wealth with disciplined monthly SIPs. Mutual fund investments are subject to market risks, read all scheme related documents carefully."
    res = verifier.verify_text(copy)
    assert res.status == ComplianceStatus.PASS
    assert res.passed
    assert len(res.violations) == 0
