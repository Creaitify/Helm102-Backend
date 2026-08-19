"""Self-contained HTML rendering for analysis reports.

This is the file a marketing lead actually forwards. Everything is inlined —
no stylesheet, no font, no script fetched at open time — so the saved document
renders identically on a machine that has never heard of this server, and
still prints cleanly.

Color follows the data-viz rules used across the console: categorical hues in
fixed slot order, status carried by a labelled pill rather than color alone.
"""

from __future__ import annotations

import html
from typing import Any

# Validated categorical slots (blue, orange) + status palette.
_CSS = """
:root{
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781; --rule:#e1e0d9;
  --surface:#ffffff; --plane:#f9f9f7; --brand:#0058be;
  --series-1:#2a78d6; --series-2:#eb6834;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font:400 15px/1.62 system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.page{max-width:980px;margin:0 auto;padding:56px 32px 96px}
header{border-bottom:2px solid var(--ink);padding-bottom:26px;margin-bottom:34px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:.04em;
  font-size:12px;text-transform:uppercase;color:var(--brand);margin-bottom:20px}
.brand i{width:24px;height:24px;border-radius:7px;background:var(--brand);color:#fff;
  display:inline-grid;place-items:center;font-size:13px;font-style:normal}
h1{font-size:33px;line-height:1.18;letter-spacing:-.022em;margin:0 0 12px}
h2{font-size:19px;letter-spacing:-.012em;margin:42px 0 14px;padding-bottom:8px;
  border-bottom:1px solid var(--rule)}
.meta{color:var(--ink-2);font-size:13px;display:flex;flex-wrap:wrap;gap:6px 22px}
.meta b{color:var(--ink);font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:12px;margin:26px 0}
.kpi{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:16px 18px}
.kpi .l{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:7px}
.kpi .v{font-size:25px;font-weight:600;letter-spacing:-.02em}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--surface);
  border:1px solid var(--rule);border-radius:12px;overflow:hidden;margin:14px 0}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  padding:11px 13px;background:var(--plane);border-bottom:1px solid var(--rule);font-weight:600}
td{padding:11px 13px;border-bottom:1px solid var(--rule);color:var(--ink-2);vertical-align:top}
tr:last-child td{border-bottom:0}
td.k{color:var(--ink);font-weight:500}
.num{text-align:right;font-variant-numeric:tabular-nums}
tfoot td{background:var(--plane);font-weight:600;color:var(--ink)}
ul{padding-left:20px;margin:10px 0}
li{margin:7px 0;color:var(--ink-2)}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600;
  letter-spacing:.03em;border:1px solid;white-space:nowrap}
.c-good{color:#0a6b0a;background:#eaf7ea;border-color:#bde3bd}
.c-warn{color:#8a6100;background:#fdf4e0;border-color:#f2ddab}
.c-crit{color:#8f2020;background:#fbeaea;border-color:#eec2c2}
.c-neu{color:var(--ink-2);background:var(--plane);border-color:var(--rule)}
.callout{background:var(--surface);border:1px solid var(--rule);border-left:3px solid var(--brand);
  border-radius:0 10px 10px 0;padding:16px 18px;margin:14px 0;color:var(--ink-2)}
.bars{margin:16px 0}
.bar-row{display:flex;align-items:center;gap:12px;margin:9px 0;font-size:13px}
.bar-row .nm{width:120px;color:var(--ink);font-weight:500}
.bar-track{flex:1;height:22px;background:var(--plane);border-radius:5px;overflow:hidden;
  border:1px solid var(--rule)}
.bar-fill{height:100%;border-radius:4px}
.bar-row .vl{width:132px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink-2)}
footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--rule);
  color:var(--muted);font-size:12px;line-height:1.7}
@media print{
  body{background:#fff}
  .page{padding:0;max-width:none}
  h2{break-after:avoid}
  table,.kpi,.callout{break-inside:avoid}
}
"""

_GOOD = {"WINNER", "SCALE", "PASS", "CONSERVED", "VALID", "HEALTHY"}
_WARN = {"FATIGUED", "FLAG", "REVIEW", "REDUCE OR REFRESH", "STABLE", "WARNING"}
_CRIT = {"BLOCK", "FAILED", "CRITICAL", "REJECTED"}


def render_html(doc: dict[str, Any], inr: Any, platform_label: Any) -> str:
    """Render a stored report document as a standalone HTML page."""
    kpis = doc.get("account_kpis", {})
    plan = doc.get("budget_plan") or {}
    out: list[str] = []
    add = out.append

    add("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    add("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    add(f"<title>{_e(doc.get('title', 'HELM Report'))}</title>")
    add(f"<style>{_CSS}</style></head><body><div class='page'>")

    add("<header><div class='brand'><i>H</i>HELM &middot; Marketing Intelligence</div>")
    add(f"<h1>{_e(doc.get('title', ''))}</h1>")
    add(
        "<div class='meta'>"
        f"<div><b>Generated</b> {_e(str(doc.get('generated_at', ''))[:19].replace('T', ' '))} UTC</div>"
        f"<div><b>Period</b> Last {_e(doc.get('period_days', 30))} days</div>"
        f"<div><b>Data source</b> {_e(doc.get('data_source_label', ''))}</div>"
        f"<div><b>Objective</b> {_e(doc.get('objective', ''))}</div>"
        "</div></header>"
    )

    add("<div class='kpis'>")
    for label, value in (
        ("Total spend", inr(kpis.get("total_spend_inr", 0))),
        ("Blended ROAS", f"{kpis.get('blended_roas', 0)}x"),
        ("Blended CPA", inr(kpis.get("blended_cpa_inr", 0))),
        ("Conversions", f"{kpis.get('total_conversions', 0):,}"),
    ):
        add(f"<div class='kpi'><div class='l'>{label}</div><div class='v'>{_e(value)}</div></div>")
    add("</div>")

    if doc.get("executive_summary"):
        add("<h2>Executive summary</h2>")
        add(f"<div class='callout'>{_e(doc['executive_summary'])}</div>")

    if doc.get("key_takeaways"):
        add("<h2>Key takeaways</h2><ul>")
        out += [f"<li>{_e(item)}</li>" for item in doc["key_takeaways"]]
        add("</ul>")

    channels = doc.get("channel_breakdown") or {}
    if channels:
        total = sum(float(v.get("spend_inr", 0)) for v in channels.values()) or 1.0
        slots = ["var(--series-1)", "var(--series-2)"]
        add("<h2>Channel split</h2><div class='bars'>")
        for idx, (channel, stats) in enumerate(channels.items()):
            spend = float(stats.get("spend_inr", 0))
            share = spend / total * 100
            # Every bar is directly labelled, so the fill color is redundant encoding.
            add(
                f"<div class='bar-row'><div class='nm'>{_e(platform_label(channel))}</div>"
                f"<div class='bar-track'><div class='bar-fill' style='width:{share:.1f}%;"
                f"background:{slots[idx % len(slots)]}'></div></div>"
                f"<div class='vl'>{_e(inr(spend))} &middot; {share:.0f}%</div></div>"
            )
        add("</div>")
        add(
            "<table><thead><tr><th>Channel</th><th class='num'>Campaigns</th>"
            "<th class='num'>Spend</th><th class='num'>ROAS</th>"
            "<th class='num'>CPA</th></tr></thead><tbody>"
        )
        for channel, stats in channels.items():
            add(
                f"<tr><td class='k'>{_e(platform_label(channel))}</td>"
                f"<td class='num'>{_e(stats.get('campaign_count', 0))}</td>"
                f"<td class='num'>{_e(inr(stats.get('spend_inr', 0)))}</td>"
                f"<td class='num'>{_e(stats.get('blended_roas', 0))}x</td>"
                f"<td class='num'>{_e(inr(stats.get('blended_cpa_inr', 0)))}</td></tr>"
            )
        add("</tbody></table>")

    if doc.get("campaigns"):
        add("<h2>Campaign performance</h2>")
        add(
            "<table><thead><tr><th>Campaign</th><th>Platform</th><th class='num'>Spend</th>"
            "<th class='num'>ROAS</th><th class='num'>CPA</th><th class='num'>CTR</th>"
            "<th class='num'>Score</th><th>Verdict</th></tr></thead><tbody>"
        )
        for c in doc["campaigns"]:
            add(
                f"<tr><td class='k'>{_e(c.get('campaign_name', ''))}</td>"
                f"<td>{_e(platform_label(c.get('platform', '')))}</td>"
                f"<td class='num'>{_e(inr(c.get('spend_inr', 0)))}</td>"
                f"<td class='num'>{_e(c.get('roas', 0))}x</td>"
                f"<td class='num'>{_e(inr(c.get('cpa_inr', 0)))}</td>"
                f"<td class='num'>{_e(c.get('ctr', 0))}%</td>"
                f"<td class='num'>{_e(c.get('score', ''))}</td>"
                f"<td>{_chip(c.get('status_tag', ''))}</td></tr>"
            )
        add("</tbody></table>")

    for heading, key in (("What is working", "what_works"), ("Decay signals", "decay_signals")):
        if doc.get(key):
            add(f"<h2>{heading}</h2><ul>")
            out += [f"<li>{_e(item)}</li>" for item in doc[key]]
            add("</ul>")

    if doc.get("recommendations"):
        add("<h2>Recommended actions</h2>")
        add("<table><thead><tr><th>Action</th><th>Campaign</th><th>Rationale</th></tr></thead><tbody>")
        for rec in doc["recommendations"]:
            add(
                f"<tr><td>{_chip(rec.get('action', ''))}</td>"
                f"<td class='k'>{_e(rec.get('campaign_name', ''))}</td>"
                f"<td>{_e(rec.get('reason', ''))}</td></tr>"
            )
        add("</tbody></table>")

    if plan.get("shifts"):
        add("<h2>Budget reallocation plan</h2>")
        add(
            "<table><thead><tr><th>Campaign</th><th class='num'>Current</th>"
            "<th class='num'>Proposed</th><th class='num'>Change</th>"
            "<th>Rationale</th></tr></thead><tbody>"
        )
        for shift in plan["shifts"]:
            pct = shift.get("shift_percentage", 0)
            add(
                f"<tr><td class='k'>{_e(shift.get('campaign_name', shift.get('campaign_id', '')))}</td>"
                f"<td class='num'>{_e(inr(shift.get('current_daily_budget_inr', 0)))}</td>"
                f"<td class='num'>{_e(inr(shift.get('proposed_daily_budget_inr', 0)))}</td>"
                f"<td class='num'>{'+' if pct >= 0 else ''}{_e(pct)}%</td>"
                f"<td>{_e(shift.get('rationale', ''))}</td></tr>"
            )
        add(
            "</tbody><tfoot><tr><td>Total</td>"
            f"<td class='num'>{_e(inr(plan.get('total_current_inr', 0)))}</td>"
            f"<td class='num'>{_e(inr(plan.get('total_proposed_inr', 0)))}</td>"
            f"<td class='num' colspan='2'>{_chip('Conserved' if plan.get('is_conserved') else 'Review')}"
            "</td></tr></tfoot></table>"
        )

    if doc.get("strategic_advice"):
        add("<h2>Strategic advice</h2>")
        add(f"<div class='callout'>{_e(doc['strategic_advice'])}</div>")

    add(
        "<footer>Generated by HELM &mdash; governed marketing operations. "
        "Figures are computed from the stated data source; every budget change "
        "requires human approval before it reaches an ad platform.<br>"
        f"Report ID {_e(doc.get('id', ''))}</footer>"
    )
    add("</div></body></html>")
    return "".join(out)


def _chip(label: Any) -> str:
    """Status pill that carries its own text — color is never the only signal."""
    text = str(label or "").strip()
    if not text:
        return ""
    key = text.upper().replace("_", " ")
    if key in _GOOD:
        cls = "c-good"
    elif key in _WARN:
        cls = "c-warn"
    elif key in _CRIT:
        cls = "c-crit"
    else:
        cls = "c-neu"
    return f"<span class='chip {cls}'>{_e(key)}</span>"


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)
