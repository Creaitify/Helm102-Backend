"""BYOD (Bring-Your-Own-Data) Excel/CSV Campaign Importer for HELM02.

Supports:
- Multi-sheet Excel workbooks (.xlsx) with platform auto-detection (e.g. Google_Ads, Meta_Ads, Summary).
- Standard CSV files (.csv) with dialect sniffing and encoding fallbacks.
- Column normalization and alias mapping.
- Validation of required metric columns (spend, roas, clicks, conversions).
- Automatic derivation of CTR and CPA if omitted.
- Sample Finnovate bundle generator for testing and demos.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import openpyxl

from modules.ads.contracts import CampaignSnapshot, MetricRow, Platform


class BYODImportError(ValueError):
    """Base exception for BYOD import failures."""


class MissingRequiredColumnsError(BYODImportError):
    """Raised when required metric columns are missing from the dataset."""


class InvalidDataFormatError(BYODImportError):
    """Raised when dataset formatting or content cannot be parsed."""


# Canonical column keys required for basic metric calculation
REQUIRED_METRIC_FIELDS: tuple[str, ...] = ("spend_inr", "roas", "clicks", "conversions")

# Human-friendly field display names for error messages
FIELD_DISPLAY_NAMES: dict[str, str] = {
    "spend_inr": "spend",
    "roas": "roas",
    "clicks": "clicks",
    "conversions": "conversions",
    "campaign_id": "campaign_id",
    "campaign_name": "campaign_name",
    "platform": "platform",
    "impressions": "impressions",
    "cpa_inr": "cpa",
    "ctr": "ctr",
    "status": "status",
    "account_id": "account_id",
}

# Alias dictionary mapping canonical names to acceptable column header variations
COLUMN_ALIASES: dict[str, set[str]] = {
    "campaign_id": {
        "campaign_id",
        "campaignid",
        "id",
        "campaign_idx",
        "ad_set_id",
        "adset_id",
        "ad_id",
        "adgroup_id",
        "ad_group_id",
        "campaign_code",
    },
    "campaign_name": {
        "campaign_name",
        "campaignname",
        "campaign",
        "name",
        "ad_set_name",
        "adset_name",
        "ad_name",
        "campaign_title",
        "adgroup_name",
        "ad_group_name",
    },
    "platform": {
        "platform",
        "platform_name",
        "network",
        "channel",
        "source",
        "publisher",
        "ad_network",
    },
    "spend_inr": {
        "spend_inr",
        "spend",
        "cost",
        "spend_rs",
        "spend_in_inr",
        "amount_spent",
        "amount_spent_inr",
        "total_spend",
        "cost_inr",
        "spend_amount",
        "daily_spend",
    },
    "impressions": {
        "impressions",
        "impr",
        "views",
        "impressions_count",
        "impr_count",
        "total_impressions",
    },
    "clicks": {
        "clicks",
        "link_clicks",
        "ad_clicks",
        "clicks_count",
        "total_clicks",
    },
    "conversions": {
        "conversions",
        "conv",
        "results",
        "leads",
        "actions",
        "purchases",
        "conversions_count",
        "total_conversions",
    },
    "roas": {
        "roas",
        "return_on_ad_spend",
        "conv_value_per_cost",
        "purchase_roas",
        "return_on_spend",
        "value_per_cost",
        "conv_value_cost",
    },
    "cpa_inr": {
        "cpa_inr",
        "cpa",
        "cost_per_conversion",
        "cost_per_action",
        "cost_per_result",
        "cost_per_lead",
        "cost_per_conv",
        "cost_conv",
        "cpa_rs",
    },
    "ctr": {
        "ctr",
        "click_through_rate",
        "ctr_pct",
        "ctr_percent",
        "click_thru_rate",
        "clickthrough_rate",
    },
    "status": {
        "status",
        "campaign_status",
        "state",
        "status_name",
        "ad_status",
    },
    "account_id": {
        "account_id",
        "accountid",
        "customer_id",
        "act_id",
        "account",
        "advertiser_id",
    },
}


def normalize_column_name(col: str) -> str:
    """Normalize a header string for case/format-insensitive matching."""
    if not isinstance(col, str):
        col = str(col) if col is not None else ""
    # Strip whitespace, lower-case
    norm = col.strip().lower()
    # Remove common punctuation / currency / unit annotations like (inr), (%), [inr], ₹, $
    norm = re.sub(r"[\(（\[].*?[\)）\]]", "", norm)
    norm = re.sub(r"[₹\$,%#@!]", "", norm)
    # Replace whitespace and punctuation with underscores
    norm = re.sub(r"[\s\-\./\\]+", "_", norm)
    norm = re.sub(r"_+", "_", norm).strip("_")
    return norm


def map_headers(raw_headers: Sequence[Any]) -> dict[str, int]:
    """Map canonical field names to column indices in raw_headers.

    Returns:
        dict[canonical_field_name, column_index]
    """
    mapping: dict[str, int] = {}
    normalized_headers = [normalize_column_name(str(h or "")) for h in raw_headers]

    for col_idx, norm_header in enumerate(normalized_headers):
        if not norm_header:
            continue
        for canonical, aliases in COLUMN_ALIASES.items():
            if canonical in mapping:
                continue
            if norm_header in aliases or norm_header == canonical:
                mapping[canonical] = col_idx
                break

    return mapping


def validate_headers(header_map: dict[str, int], raw_headers: Sequence[Any]) -> None:
    """Ensure all required metric columns are present in the header map."""
    missing = [
        FIELD_DISPLAY_NAMES.get(field, field)
        for field in REQUIRED_METRIC_FIELDS
        if field not in header_map
    ]
    if missing:
        raw_names = [str(h) for h in raw_headers if h is not None and str(h).strip()]
        raise MissingRequiredColumnsError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Found columns: {raw_names}"
        )


def _parse_float(val: Any, default: float = 0.0) -> float:
    """Parse string/numeric value into float, handling currency and percentage symbols."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s == "-" or s.lower() == "nan" or s.lower() == "none":
        return default
    # Remove currency symbols, commas, spaces, %
    cleaned = re.sub(r"[₹\$,\s]", "", s)
    is_percent = cleaned.endswith("%")
    if is_percent:
        cleaned = cleaned[:-1].strip()
    try:
        fval = float(cleaned)
        return fval
    except ValueError:
        return default


def _parse_int(val: Any, default: int = 0) -> int:
    """Parse string/numeric value into int."""
    f = _parse_float(val, default=float(default))
    return int(round(f))


def _parse_platform(val: Any, context_hint: str = "", default: Platform = Platform.BYOD) -> Platform:
    """Resolve Platform enum from string value or context hint (e.g. sheet name)."""
    text = f"{val or ''} {context_hint}".strip().lower()
    if "google" in text or "gads" in text or "adwords" in text:
        return Platform.GOOGLE_ADS
    if "meta" in text or "facebook" in text or "fb" in text or "instagram" in text:
        return Platform.META_ADS
    if "byod" in text or "manual" in text or "sheet" in text:
        return Platform.BYOD
    return default


def _is_summary_or_metadata_sheet(sheet_name: str) -> bool:
    """Check if sheet name implies non-tabular metadata or summary."""
    s = sheet_name.strip().lower()
    return s in {"summary", "metadata", "overview", "readme", "notes", "config", "settings"}


def parse_row(
    row_values: Sequence[Any],
    header_map: dict[str, int],
    row_index: int,
    default_platform: Platform = Platform.BYOD,
    context_hint: str = "",
) -> MetricRow | None:
    """Parse a single data row into a MetricRow instance."""
    # Check if row is completely empty
    if not any(v is not None and str(v).strip() != "" for v in row_values):
        return None

    def get_val(canonical: str) -> Any:
        idx = header_map.get(canonical)
        if idx is not None and idx < len(row_values):
            return row_values[idx]
        return None

    campaign_name_val = get_val("campaign_name")
    campaign_name = str(campaign_name_val).strip() if campaign_name_val is not None else f"Campaign_{row_index}"
    if not campaign_name:
        campaign_name = f"Campaign_{row_index}"

    campaign_id_val = get_val("campaign_id")
    if campaign_id_val is not None and str(campaign_id_val).strip():
        campaign_id = str(campaign_id_val).strip()
    else:
        # Create deterministic slug ID
        slug = re.sub(r"[^\w]+", "_", campaign_name.lower()).strip("_")
        campaign_id = f"cmp_{slug or 'row'}_{row_index}"

    platform_val = get_val("platform")
    if platform_val is not None and str(platform_val).strip():
        platform = _parse_platform(platform_val, context_hint=context_hint, default=default_platform)
    else:
        platform = _parse_platform("", context_hint=context_hint, default=default_platform)

    spend_inr = _parse_float(get_val("spend_inr"), 0.0)
    impressions = _parse_int(get_val("impressions"), 0)
    clicks = _parse_int(get_val("clicks"), 0)
    conversions = _parse_int(get_val("conversions"), 0)
    roas = _parse_float(get_val("roas"), 0.0)

    # Derived or explicit CPA
    cpa_raw = get_val("cpa_inr")
    if cpa_raw is not None and str(cpa_raw).strip() and str(cpa_raw).strip() != "-":
        cpa_inr = round(_parse_float(cpa_raw, 0.0), 2)
    else:
        cpa_inr = round(spend_inr / conversions, 2) if conversions > 0 else 0.0

    # Derived or explicit CTR
    ctr_raw = get_val("ctr")
    if ctr_raw is not None and str(ctr_raw).strip() and str(ctr_raw).strip() != "-":
        ctr = round(_parse_float(ctr_raw, 0.0), 2)
    else:
        ctr = round((clicks / impressions) * 100.0, 2) if impressions > 0 else 0.0

    status_val = get_val("status")
    status = str(status_val).strip().upper() if status_val is not None and str(status_val).strip() else "ENABLED"

    return MetricRow(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        platform=platform,
        spend_inr=spend_inr,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        roas=roas,
        cpa_inr=cpa_inr,
        ctr=ctr,
        status=status,
    )


def _build_snapshot(
    campaigns: list[MetricRow],
    account_ids: list[str] | None = None,
    platform: Platform | None = None,
    source: str = "byod",
) -> CampaignSnapshot:
    """Build aggregated CampaignSnapshot from a list of MetricRows."""
    total_spend = sum(c.spend_inr for c in campaigns)
    if total_spend > 0:
        blended_roas = sum(c.roas * c.spend_inr for c in campaigns) / total_spend
    else:
        blended_roas = 0.0

    # Determine dominant or combined platform
    if platform is not None:
        snap_platform = platform
    elif campaigns:
        platforms = {c.platform for c in campaigns}
        if len(platforms) == 1:
            snap_platform = next(iter(platforms))
        else:
            snap_platform = Platform.BYOD
    else:
        snap_platform = Platform.BYOD

    if not account_ids:
        account_ids = ["byod_account"]

    return CampaignSnapshot(
        account_ids=account_ids,
        platform=snap_platform,
        campaigns=campaigns,
        total_spend_inr=round(total_spend, 2),
        blended_roas=round(blended_roas, 2),
        source=source,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def parse_csv(
    source: str | bytes | Path | io.IOBase,
    platform: Platform | str | None = None,
    account_id: str = "byod_account",
    source_tag: str = "byod",
) -> CampaignSnapshot:
    """Parse CSV data into a CampaignSnapshot.

    Args:
        source: File path, string content, raw bytes, or file-like object.
        platform: Optional explicit Platform override.
        account_id: Account ID to associate with snapshot.
        source_tag: Source tag (default: 'byod').

    Returns:
        CampaignSnapshot containing parsed MetricRows.
    """
    if isinstance(source, Path) or (isinstance(source, str) and ("\n" not in source and Path(source).is_file() if len(source) < 500 else False)):
        path = Path(source)
        if not path.is_file():
            raise InvalidDataFormatError(f"CSV file not found: {source}")
        raw_bytes = path.read_bytes()
    elif isinstance(source, bytes):
        raw_bytes = source
    elif isinstance(source, str):
        raw_bytes = source.encode("utf-8")
    elif hasattr(source, "read"):
        content = source.read()
        raw_bytes = content if isinstance(content, bytes) else content.encode("utf-8")
    else:
        raise InvalidDataFormatError(f"Unsupported source type: {type(source)}")

    # Decode text handling UTF-8, UTF-8 BOM, and Latin-1 fallbacks
    text = ""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        text = raw_bytes.decode("utf-8", errors="replace")

    string_io = io.StringIO(text.strip())
    # Sniff dialect for delimiter
    try:
        sample = text[:2048]
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except Exception:
        dialect = csv.excel

    reader = csv.reader(string_io, dialect=dialect)
    rows = [r for r in reader if any(cell.strip() for cell in r)]

    if not rows:
        raise InvalidDataFormatError("CSV dataset is empty.")

    raw_headers = rows[0]
    header_map = map_headers(raw_headers)
    validate_headers(header_map, raw_headers)

    default_plat = (
        Platform(platform) if isinstance(platform, str)
        else platform if platform is not None
        else Platform.BYOD
    )

    campaigns: list[MetricRow] = []
    for idx, row in enumerate(rows[1:], start=1):
        metric_row = parse_row(
            row_values=row,
            header_map=header_map,
            row_index=idx,
            default_platform=default_plat,
            context_hint="",
        )
        if metric_row is not None:
            campaigns.append(metric_row)

    return _build_snapshot(
        campaigns=campaigns,
        account_ids=[account_id],
        platform=default_plat if platform is not None else None,
        source=source_tag,
    )


def parse_excel(
    source: str | bytes | Path | io.IOBase,
    sheets: Sequence[str] | None = None,
    default_platform: Platform | str | None = None,
    account_ids: list[str] | None = None,
    ignore_non_tabular: bool = True,
    source_tag: str = "byod",
) -> CampaignSnapshot:
    """Parse an Excel workbook (.xlsx) into a consolidated CampaignSnapshot.

    Supports reading multiple sheets (e.g. 'Google_Ads', 'Meta_Ads', 'Summary').
    Automatically maps sheets like 'Google_Ads' or 'Meta_Ads' to their platforms.
    Gracefully skips non-tabular or summary sheets when ignore_non_tabular=True.

    Args:
        source: File path, raw bytes, or file-like object.
        sheets: Optional list of sheet names to parse. If None, parses all valid sheets.
        default_platform: Fallback platform if not inferred from sheet/row.
        account_ids: List of account IDs.
        ignore_non_tabular: Whether to skip summary/metadata sheets without raising error.
        source_tag: Source tag (default: 'byod').

    Returns:
        CampaignSnapshot combining campaign metrics from all parsed sheets.
    """
    if isinstance(source, (str, Path)) and Path(source).is_file():
        wb = openpyxl.load_workbook(filename=str(source), data_only=True)
    elif isinstance(source, bytes):
        wb = openpyxl.load_workbook(filename=io.BytesIO(source), data_only=True)
    elif hasattr(source, "read"):
        content = source.read()
        byte_io = io.BytesIO(content if isinstance(content, bytes) else content.encode("utf-8"))
        wb = openpyxl.load_workbook(filename=byte_io, data_only=True)
    else:
        raise InvalidDataFormatError(f"Unsupported Excel source: {type(source)}")

    target_sheet_names = list(sheets) if sheets is not None else wb.sheetnames
    if not target_sheet_names:
        raise InvalidDataFormatError("Excel workbook contains no sheets.")

    fallback_platform = (
        Platform(default_platform) if isinstance(default_platform, str)
        else default_platform if default_platform is not None
        else Platform.BYOD
    )

    all_campaigns: list[MetricRow] = []
    parsed_sheet_count = 0
    errors: list[str] = []

    for sheet_name in target_sheet_names:
        if sheet_name not in wb.sheetnames:
            if sheets is not None:
                raise InvalidDataFormatError(f"Sheet '{sheet_name}' not found in workbook.")
            continue

        ws = wb[sheet_name]
        raw_rows = list(ws.iter_rows(values_only=True))
        # Filter non-empty rows
        valid_rows = [r for r in raw_rows if any(c is not None and str(c).strip() != "" for c in r)]

        if not valid_rows:
            if _is_summary_or_metadata_sheet(sheet_name) and ignore_non_tabular:
                continue
            if sheets is not None:
                raise InvalidDataFormatError(f"Sheet '{sheet_name}' is empty.")
            continue

        raw_headers = valid_rows[0]
        header_map = map_headers(raw_headers)

        # Check required columns
        try:
            validate_headers(header_map, raw_headers)
        except MissingRequiredColumnsError as err:
            if _is_summary_or_metadata_sheet(sheet_name) and ignore_non_tabular:
                continue
            if sheets is not None or len(target_sheet_names) == 1:
                raise err
            # When auto-scanning multi-sheet workbook, record note and continue
            errors.append(f"Sheet '{sheet_name}': {err}")
            continue

        sheet_platform = _parse_platform("", context_hint=sheet_name, default=fallback_platform)

        for idx, row in enumerate(valid_rows[1:], start=1):
            metric_row = parse_row(
                row_values=row,
                header_map=header_map,
                row_index=len(all_campaigns) + idx,
                default_platform=sheet_platform,
                context_hint=sheet_name,
            )
            if metric_row is not None:
                all_campaigns.append(metric_row)

        parsed_sheet_count += 1

    if parsed_sheet_count == 0 and not all_campaigns:
        if errors:
            raise MissingRequiredColumnsError(f"No valid campaign sheets found. {'; '.join(errors)}")
        raise InvalidDataFormatError("No tabular campaign data found in workbook.")

    return _build_snapshot(
        campaigns=all_campaigns,
        account_ids=account_ids,
        platform=default_platform if default_platform is not None else None,
        source=source_tag,
    )


def parse_excel_sheets(
    source: str | bytes | Path | io.IOBase,
    sheets: Sequence[str] | None = None,
    default_platform: Platform | str | None = None,
) -> dict[str, CampaignSnapshot]:
    """Parse each sheet of an Excel workbook into its own individual CampaignSnapshot."""
    if isinstance(source, (str, Path)) and Path(source).is_file():
        wb = openpyxl.load_workbook(filename=str(source), data_only=True)
    elif isinstance(source, bytes):
        wb = openpyxl.load_workbook(filename=io.BytesIO(source), data_only=True)
    elif hasattr(source, "read"):
        content = source.read()
        byte_io = io.BytesIO(content if isinstance(content, bytes) else content.encode("utf-8"))
        wb = openpyxl.load_workbook(filename=byte_io, data_only=True)
    else:
        raise InvalidDataFormatError(f"Unsupported Excel source: {type(source)}")

    target_sheet_names = list(sheets) if sheets is not None else wb.sheetnames
    result: dict[str, CampaignSnapshot] = {}

    for sheet_name in target_sheet_names:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        raw_rows = list(ws.iter_rows(values_only=True))
        valid_rows = [r for r in raw_rows if any(c is not None and str(c).strip() != "" for c in r)]
        if not valid_rows:
            continue

        raw_headers = valid_rows[0]
        header_map = map_headers(raw_headers)
        try:
            validate_headers(header_map, raw_headers)
        except MissingRequiredColumnsError:
            continue

        sheet_platform = _parse_platform("", context_hint=sheet_name, default=Platform.BYOD)
        campaigns: list[MetricRow] = []
        for idx, row in enumerate(valid_rows[1:], start=1):
            metric_row = parse_row(
                row_values=row,
                header_map=header_map,
                row_index=idx,
                default_platform=sheet_platform,
                context_hint=sheet_name,
            )
            if metric_row is not None:
                campaigns.append(metric_row)

        if campaigns:
            result[sheet_name] = _build_snapshot(
                campaigns=campaigns,
                account_ids=[f"account_{sheet_name.lower()}"],
                platform=sheet_platform,
                source="byod",
            )

    return result


def import_byod_file(
    source: str | bytes | Path | io.IOBase,
    filename: str | None = None,
    default_platform: Platform | str | None = None,
) -> CampaignSnapshot:
    """Unified importer that auto-detects CSV or Excel formats."""
    # Determine filename/format
    name = ""
    if filename:
        name = filename
    elif isinstance(source, (str, Path)):
        name = str(source)

    if name.lower().endswith(".xlsx") or name.lower().endswith(".xlsm") or name.lower().endswith(".xltx"):
        return parse_excel(source, default_platform=default_platform)
    elif name.lower().endswith(".csv") or name.lower().endswith(".tsv") or name.lower().endswith(".txt"):
        return parse_csv(source, platform=default_platform)

    # Check magic bytes for ZIP (XLSX)
    if isinstance(source, bytes) and source.startswith(b"PK\x03\x04"):
        return parse_excel(source, default_platform=default_platform)

    # Fallback to CSV
    try:
        return parse_csv(source, platform=default_platform)
    except Exception:
        return parse_excel(source, default_platform=default_platform)


# Aliases for convenience
import_csv = parse_csv
import_excel = parse_excel


# ---------------------------------------------------------------------------
# Sample Finnovate Bundle Generator
# ---------------------------------------------------------------------------

def get_finnovate_sample_data() -> dict[str, list[dict[str, Any]]]:
    """Structured mock campaigns for Finnovate ad accounts."""
    return {
        "Google_Ads": [
            {
                "campaign_id": "cmp_gads_search_01",
                "campaign_name": "Finnovate — Mutual Fund Search Intent",
                "platform": "google_ads",
                "spend_inr": 45000.0,
                "impressions": 125000,
                "clicks": 8400,
                "conversions": 420,
                "roas": 3.4,
                "cpa_inr": 107.14,
                "ctr": 6.72,
                "status": "ENABLED",
            },
            {
                "campaign_id": "cmp_gads_brand_02",
                "campaign_name": "Finnovate — Brand Search Core",
                "platform": "google_ads",
                "spend_inr": 25000.0,
                "impressions": 80000,
                "clicks": 7200,
                "conversions": 360,
                "roas": 4.2,
                "cpa_inr": 69.44,
                "ctr": 9.0,
                "status": "ENABLED",
            },
            {
                "campaign_id": "cmp_gads_pmax_03",
                "campaign_name": "Finnovate — Performance Max Direct SIP",
                "platform": "google_ads",
                "spend_inr": 50000.0,
                "impressions": 220000,
                "clicks": 9500,
                "conversions": 380,
                "roas": 2.8,
                "cpa_inr": 131.58,
                "ctr": 4.32,
                "status": "ENABLED",
            },
        ],
        "Meta_Ads": [
            {
                "campaign_id": "cmp_meta_retargeting_01",
                "campaign_name": "Finnovate — SIP Growth Retargeting",
                "platform": "meta_ads",
                "spend_inr": 65000.0,
                "impressions": 340000,
                "clicks": 14200,
                "conversions": 510,
                "roas": 2.1,
                "cpa_inr": 127.45,
                "ctr": 4.18,
                "status": "ENABLED",
            },
            {
                "campaign_id": "cmp_meta_gold_fatigue_02",
                "campaign_name": "Finnovate — Gold ETF Broad Audience",
                "platform": "meta_ads",
                "spend_inr": 30000.0,
                "impressions": 210000,
                "clicks": 3900,
                "conversions": 95,
                "roas": 1.1,
                "cpa_inr": 315.79,
                "ctr": 1.86,
                "status": "PAUSED",
            },
            {
                "campaign_id": "cmp_meta_hnw_lookalike_03",
                "campaign_name": "Finnovate — High Net Worth Lookalike 1%",
                "platform": "meta_ads",
                "spend_inr": 55000.0,
                "impressions": 190000,
                "clicks": 8100,
                "conversions": 310,
                "roas": 2.9,
                "cpa_inr": 177.42,
                "ctr": 4.26,
                "status": "ENABLED",
            },
        ],
        "Summary": [
            {
                "metric": "Total Accounts",
                "value": "2 (Google Ads & Meta Ads)",
            },
            {
                "metric": "Target Monthly Budget (INR)",
                "value": "270000.00",
            },
            {
                "metric": "Blended Target ROAS",
                "value": "2.80",
            },
            {
                "metric": "Primary Conversion Goal",
                "value": "SIP Registration Completed",
            },
        ],
    }


def create_finnovate_excel_bytes() -> bytes:
    """Generate in-memory multi-sheet Excel workbook bytes containing Finnovate sample data."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)  # type: ignore

    data = get_finnovate_sample_data()

    # Google Ads sheet
    ws_gads = wb.create_sheet(title="Google_Ads")
    gads_headers = [
        "Campaign ID", "Campaign Name", "Platform", "Spend (INR)",
        "Impressions", "Clicks", "Conversions", "ROAS", "CPA (INR)", "CTR (%)", "Status"
    ]
    ws_gads.append(gads_headers)
    for row in data["Google_Ads"]:
        ws_gads.append([
            row["campaign_id"], row["campaign_name"], row["platform"], row["spend_inr"],
            row["impressions"], row["clicks"], row["conversions"], row["roas"],
            row["cpa_inr"], row["ctr"], row["status"]
        ])

    # Meta Ads sheet
    ws_meta = wb.create_sheet(title="Meta_Ads")
    meta_headers = [
        "Campaign ID", "Campaign Name", "Platform", "Spend (INR)",
        "Impressions", "Clicks", "Conversions", "ROAS", "CPA (INR)", "CTR (%)", "Status"
    ]
    ws_meta.append(meta_headers)
    for row in data["Meta_Ads"]:
        ws_meta.append([
            row["campaign_id"], row["campaign_name"], row["platform"], row["spend_inr"],
            row["impressions"], row["clicks"], row["conversions"], row["roas"],
            row["cpa_inr"], row["ctr"], row["status"]
        ])

    # Summary sheet
    ws_summary = wb.create_sheet(title="Summary")
    ws_summary.append(["Metric", "Value"])
    for row in data["Summary"]:
        ws_summary.append([row["metric"], row["value"]])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def create_finnovate_csv_bytes(sheet_name: str = "Google_Ads") -> bytes:
    """Generate in-memory CSV bytes for Finnovate sample campaigns."""
    data = get_finnovate_sample_data()
    rows = data.get(sheet_name, data["Google_Ads"])

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "campaign_id", "campaign_name", "platform", "spend_inr",
            "impressions", "clicks", "conversions", "roas", "cpa_inr", "ctr", "status"
        ],
    )
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

    return buf.getvalue().encode("utf-8")


def generate_finnovate_sample_bundle(
    output_dir: str | Path | None = None,
) -> dict[str, Path | bytes]:
    """Generate complete Finnovate sample bundle for testing and demos.

    If output_dir is provided, writes files to disk and returns mapping of filename -> Path.
    If output_dir is None, returns mapping of filename -> bytes.
    """
    excel_bytes = create_finnovate_excel_bytes()
    gads_csv = create_finnovate_csv_bytes("Google_Ads")
    meta_csv = create_finnovate_csv_bytes("Meta_Ads")

    # Also generate blended CSV
    all_data = get_finnovate_sample_data()
    blended_rows = all_data["Google_Ads"] + all_data["Meta_Ads"]
    blended_buf = io.StringIO()
    writer = csv.DictWriter(
        blended_buf,
        fieldnames=[
            "campaign_id", "campaign_name", "platform", "spend_inr",
            "impressions", "clicks", "conversions", "roas", "cpa_inr", "ctr", "status"
        ],
    )
    writer.writeheader()
    for r in blended_rows:
        writer.writerow(r)
    blended_csv = blended_buf.getvalue().encode("utf-8")

    bundle: dict[str, bytes] = {
        "finnovate_campaigns.xlsx": excel_bytes,
        "finnovate_google_ads.csv": gads_csv,
        "finnovate_meta_ads.csv": meta_csv,
        "finnovate_blended.csv": blended_csv,
    }

    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        disk_bundle: dict[str, Path] = {}
        for fname, bdata in bundle.items():
            fpath = out_path / fname
            fpath.write_bytes(bdata)
            disk_bundle[fname] = fpath
        return disk_bundle  # type: ignore

    return bundle  # type: ignore
