"""Analysis reports — a full account read-out, persisted and exportable.

A report is a point-in-time snapshot: account KPIs, channel split, a ranked
campaign table, decay signals, budget recommendations, and the compliance
posture, all assembled from the same workers the chat agents use. Reports are
stored so a finance or compliance reader can open the exact document that was
generated on a given date, and exported as Markdown for circulation.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from modules.ads.analyst import AdOpsAnalyst
from modules.ads.contracts import CampaignSnapshot
from modules.budget.optimizer import BudgetOptimizer
from services.api.report_html import render_html as _render_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

DB_PATH = os.environ.get("HELM_REPORTS_DB", "helm_reports.sqlite")

_lock = threading.Lock()
_deps: dict[str, Any] = {}


def configure(gateway: Any, connector: Any) -> None:
    """Inject the app-level singletons reports are generated from."""
    _deps["gateway"] = gateway
    _deps["connector"] = connector


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id           TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                period_days  INTEGER NOT NULL,
                data_source  TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                document_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);
            """
        )


class GenerateReportRequest(BaseModel):
    title: str = Field(default="", json_schema_extra={"example": "Q3 Executive Summary"})
    period_days: int = Field(default=30, ge=7, le=90)
    objective: str = Field(
        default="Full account performance review",
        json_schema_extra={"example": "Reduce CPA and scale winning SIP campaigns"},
    )


# ----------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------


@router.post("/generate")
async def generate_report(req: GenerateReportRequest) -> dict[str, Any]:
    """Build a full analysis report from current campaign data and store it."""
    connector = _deps.get("connector")
    if connector is None:
        raise HTTPException(status_code=503, detail="Connector is not configured")

    try:
        snapshot: CampaignSnapshot = connector.fetch_campaigns()
        history = connector.fetch_history(lookback_days=req.period_days)
        findings = await AdOpsAnalyst().generate_ai_analysis(
            snapshot, history, gateway=_deps.get("gateway"), objective=req.objective
        )
        budget = BudgetOptimizer().optimize(snapshot).to_dict()
    except Exception as exc:
        logger.exception("Report generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}") from exc

    report_id = f"rpt_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc)
    title = req.title.strip() or f"Account Performance Report — {created_at:%d %b %Y}"

    kpis = findings["account_kpis"]
    names = {c.campaign_id: c.campaign_name for c in snapshot.campaigns}

    document: dict[str, Any] = {
        "id": report_id,
        "title": title,
        "objective": req.objective,
        "period_days": req.period_days,
        "generated_at": created_at.isoformat(),
        "data_source": snapshot.source,
        "data_source_label": _source_label(snapshot.source),
        "account_kpis": kpis,
        "executive_summary": findings.get("executive_summary", ""),
        "key_takeaways": findings.get("key_takeaways", []),
        "strategic_advice": findings.get("strategic_advice", ""),
        "channel_breakdown": findings.get("channel_breakdown", {}),
        "campaigns": findings.get("per_campaign", []),
        "what_works": findings.get("what_works", []),
        "decay_signals": findings.get("decay_signals", []),
        "trends": findings.get("trends", []),
        "top_angles": findings.get("top_angles", []),
        "recommendations": findings.get("recommendations", []),
        "budget_plan": {
            "total_current_inr": budget["total_current_inr"],
            "total_proposed_inr": budget["total_proposed_inr"],
            "is_conserved": budget["is_conserved"],
            "notes": budget["notes"],
            "shifts": [
                {**s, "campaign_name": names.get(s["campaign_id"], s["campaign_id"])}
                for s in budget["shifts"]
            ],
        },
        "campaign_drafts": findings.get("campaign_drafts", []),
    }

    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO reports (id, title, period_days, data_source, created_at, document_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                report_id,
                title,
                req.period_days,
                snapshot.source,
                created_at.isoformat(),
                json.dumps(document, ensure_ascii=False),
            ),
        )

    return document


@router.get("")
def list_reports(limit: int = 50) -> list[dict[str, Any]]:
    """Report index for the Reports screen."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, period_days, data_source, created_at FROM reports "
            "ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "period_days": r["period_days"],
            "data_source": r["data_source"],
            "data_source_label": _source_label(r["data_source"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.get("/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    document = _load(report_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return document


@router.delete("/{report_id}")
def delete_report(report_id: str) -> dict[str, Any]:
    with _lock, _connect() as conn:
        cursor = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return {"status": "deleted", "id": report_id}


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
def export_markdown(report_id: str, download: bool = False) -> Response:
    """Markdown export, for pasting into a deck, doc, or email."""
    document = _load(report_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    body = render_markdown(document)
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{_filename(document)}.md"'
    return PlainTextResponse(body, headers=headers, media_type="text/markdown; charset=utf-8")


@router.get("/{report_id}/html", response_class=HTMLResponse)
def export_html(report_id: str, download: bool = True) -> Response:
    """Self-contained HTML export — the shareable deliverable.

    Everything is inlined, so the saved file opens correctly on any machine
    with no network access and no dependency on this server still running.
    """
    document = _load(report_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{_filename(document)}.html"'
    return HTMLResponse(render_html(document), headers=headers)


def render_html(doc: dict[str, Any]) -> str:
    """Render a stored report as a standalone, shareable HTML document."""
    return _render_html(doc, inr=_inr, platform_label=_platform_label)


def _filename(doc: dict[str, Any]) -> str:
    """Filesystem-safe basename derived from the report title and date."""
    import re

    stem = re.sub(r"[^A-Za-z0-9]+", "-", str(doc.get("title", "helm-report"))).strip("-")
    return f"{stem or 'helm-report'}-{str(doc.get('generated_at', ''))[:10]}"


def _load(report_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT document_json FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["document_json"])


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def render_markdown(doc: dict[str, Any]) -> str:
    """Render a stored report document as Markdown."""
    kpis = doc.get("account_kpis", {})
    lines: list[str] = [
        f"# {doc['title']}",
        "",
        f"**Generated:** {doc['generated_at'][:19].replace('T', ' ')} UTC  ",
        f"**Period:** last {doc['period_days']} days  ",
        f"**Data source:** {doc.get('data_source_label', doc.get('data_source', ''))}  ",
        f"**Objective:** {doc.get('objective', '')}",
        "",
        "## Account performance",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Total spend | {_inr(kpis.get('total_spend_inr', 0))} |",
        f"| Blended ROAS | {kpis.get('blended_roas', 0)}x |",
        f"| Blended CPA | {_inr(kpis.get('blended_cpa_inr', 0))} |",
        f"| Conversions | {kpis.get('total_conversions', 0):,} |",
        f"| Clicks | {kpis.get('total_clicks', 0):,} |",
        f"| Impressions | {kpis.get('total_impressions', 0):,} |",
        "",
    ]

    if doc.get("executive_summary"):
        lines += ["## Executive summary", "", doc["executive_summary"], ""]

    if doc.get("key_takeaways"):
        lines += ["## Key takeaways", ""] + [f"- {t}" for t in doc["key_takeaways"]] + [""]

    channels = doc.get("channel_breakdown") or {}
    if channels:
        lines += [
            "## Channel breakdown",
            "",
            "| Channel | Campaigns | Spend | ROAS | CPA |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for channel, stats in channels.items():
            lines.append(
                f"| {_platform_label(channel)} | {stats.get('campaign_count', 0)} | "
                f"{_inr(stats.get('spend_inr', 0))} | {stats.get('blended_roas', 0)}x | "
                f"{_inr(stats.get('blended_cpa_inr', 0))} |"
            )
        lines.append("")

    if doc.get("campaigns"):
        lines += [
            "## Campaign performance",
            "",
            "| Campaign | Platform | Spend | ROAS | CPA | CTR | Score | Verdict |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for c in doc["campaigns"]:
            lines.append(
                f"| {c.get('campaign_name', '')} | {_platform_label(c.get('platform', ''))} | "
                f"{_inr(c.get('spend_inr', 0))} | {c.get('roas', 0)}x | {_inr(c.get('cpa_inr', 0))} | "
                f"{c.get('ctr', 0)}% | {c.get('score', '')} | {c.get('status_tag', '')} |"
            )
        lines.append("")

    for heading, key in (("What's working", "what_works"), ("Decay signals", "decay_signals")):
        if doc.get(key):
            lines += [f"## {heading}", ""] + [f"- {item}" for item in doc[key]] + [""]

    if doc.get("recommendations"):
        lines += [
            "## Recommended actions",
            "",
            "| Action | Campaign | Rationale |",
            "| --- | --- | --- |",
        ]
        for rec in doc["recommendations"]:
            lines.append(
                f"| {rec.get('action', '')} | {rec.get('campaign_name', '')} | {rec.get('reason', '')} |"
            )
        lines.append("")

    plan = doc.get("budget_plan") or {}
    if plan.get("shifts"):
        lines += [
            "## Budget reallocation plan",
            "",
            "| Campaign | Current | Proposed | Change | Rationale |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
        for s in plan["shifts"]:
            lines.append(
                f"| {s.get('campaign_name', s.get('campaign_id', ''))} | "
                f"{_inr(s.get('current_daily_budget_inr', 0))} | "
                f"{_inr(s.get('proposed_daily_budget_inr', 0))} | "
                f"{s.get('shift_percentage', 0):+}% | {s.get('rationale', '')} |"
            )
        lines += [
            "",
            f"**Total:** {_inr(plan.get('total_current_inr', 0))} -> "
            f"{_inr(plan.get('total_proposed_inr', 0))}  ",
            f"**Conservation check:** {'passed' if plan.get('is_conserved') else 'FAILED'}",
            "",
        ]

    if doc.get("strategic_advice"):
        lines += ["## Strategic advice", "", doc["strategic_advice"], ""]

    lines += [
        "---",
        "",
        "_Generated by HELM. Every budget change requires human approval before dispatch._",
    ]
    return "\n".join(lines)


def _source_label(source: str) -> str:
    return {
        "live": "Live platform API",
        "synthetic": "Synthetic dataset",
        "byod": "Imported dataset (BYOD)",
        "degraded": "Degraded — platform fetch failed",
    }.get(source, source)


def _platform_label(platform: Any) -> str:
    value = getattr(platform, "value", platform)
    return {"google_ads": "Google Ads", "meta_ads": "Meta", "byod": "Imported"}.get(str(value), str(value))


def _inr(amount: Any) -> str:
    """Format a number as Indian-grouped rupees (₹12,45,000)."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return str(amount)

    sign = "-" if value < 0 else ""
    whole = f"{abs(value):.0f}"
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return f"{sign}₹{whole}"
