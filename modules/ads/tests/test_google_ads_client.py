"""Tests for the direct Google Ads REST client.

The live path is the one that turns synthetic demos into real insight, so the
query builder, the response aggregation, and the failure modes are all pinned
down here rather than discovered against a production account.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from modules.ads.contracts import Platform
from modules.ads.google_ads_client import (
    GOOGLE_ADS_BASE,
    GOOGLE_TOKEN_URI,
    GoogleAdsClient,
    GoogleAdsError,
    build_campaign_query,
    normalize_customer_id,
    rows_to_metrics,
)

CREDS = {
    "client_id": "cid.apps.googleusercontent.com",
    "client_secret": "secret",
    "refresh_token": "refresh",
    "developer_token": "devtoken",
    "customer_id": "123-456-7890",
}


def make_client(**overrides) -> GoogleAdsClient:
    return GoogleAdsClient.from_credentials({**CREDS, **overrides})


# ----------------------------------------------------------------------
# Construction & credentials
# ----------------------------------------------------------------------


def test_customer_id_is_normalized():
    assert normalize_customer_id("123-456-7890") == "1234567890"
    assert normalize_customer_id("123 456 7890") == "1234567890"
    assert normalize_customer_id("1234567890") == "1234567890"


def test_incomplete_credentials_name_the_missing_fields():
    with pytest.raises(GoogleAdsError) as excinfo:
        GoogleAdsClient.from_credentials({"client_id": "x"})

    message = str(excinfo.value)
    for field in ("client_secret", "refresh_token", "developer_token", "customer_id"):
        assert field in message


def test_login_customer_id_is_only_sent_when_configured():
    plain = make_client()
    mcc = make_client(login_customer_id="999-888-7777")

    plain._access_token = "token"
    plain._access_token_expiry = 1e12
    mcc._access_token = "token"
    mcc._access_token_expiry = 1e12

    assert "login-customer-id" not in plain._headers()
    assert mcc._headers()["login-customer-id"] == "9998887777"


# ----------------------------------------------------------------------
# GAQL construction
# ----------------------------------------------------------------------


def test_query_requests_conversion_value_so_roas_is_real():
    query = build_campaign_query()
    assert "metrics.conversions_value" in query
    assert "metrics.cost_micros" in query
    assert "segments.date DURING LAST_30_DAYS" in query


def test_explicit_date_range_becomes_a_between_clause():
    query = build_campaign_query(date_range="2026-07-01,2026-07-31")
    assert "segments.date BETWEEN '2026-07-01' AND '2026-07-31'" in query


def test_status_filter_is_sanitized_against_injection():
    query = build_campaign_query(status_filter="ENABLED'; DROP TABLE campaign; --")
    assert "DROP" not in query.upper().replace("DROPTABLECAMPAIGN", "")
    # Only A-Z and underscores survive the scrub.
    assert "campaign.status = 'ENABLEDDROPTABLECAMPAIGN'" in query


def test_garbage_date_range_falls_back_to_a_safe_default():
    query = build_campaign_query(date_range="'; DELETE FROM campaign WHERE '1'='1")
    assert "segments.date DURING LAST_30_DAYS" in query
    assert "DELETE" not in query


def test_status_filter_can_be_omitted():
    """Status stays in the SELECT list; only the WHERE predicate disappears."""
    query = build_campaign_query(status_filter=None)
    assert "campaign.status" in query.split("WHERE")[0]
    assert "campaign.status =" not in query


# ----------------------------------------------------------------------
# Response normalization
# ----------------------------------------------------------------------


def test_daily_rows_are_aggregated_per_campaign():
    """A date-segmented query returns one row per campaign per day."""
    rows = [
        {
            "campaign": {"id": "1", "name": "Search Intent", "status": "ENABLED"},
            "metrics": {
                "costMicros": "10000000",  # ₹10
                "impressions": "1000",
                "clicks": "100",
                "conversions": 5,
                "conversionsValue": 40,
            },
        },
        {
            "campaign": {"id": "1", "name": "Search Intent", "status": "ENABLED"},
            "metrics": {
                "costMicros": "30000000",  # ₹30
                "impressions": "3000",
                "clicks": "100",
                "conversions": 5,
                "conversionsValue": 60,
            },
        },
    ]

    metrics = rows_to_metrics(rows)
    assert len(metrics) == 1

    row = metrics[0]
    assert row.spend_inr == 40.0
    assert row.impressions == 4000
    assert row.clicks == 200
    assert row.conversions == 10
    # Ratios are recomputed from totals, never averaged.
    assert row.roas == 2.5  # 100 value / 40 spend
    assert row.cpa_inr == 4.0  # 40 spend / 10 conversions
    assert row.ctr == 5.0  # 200 clicks / 4000 impressions
    assert row.platform == Platform.GOOGLE_ADS


def test_rows_are_ordered_by_spend_descending():
    rows = [
        {"campaign": {"id": "1", "name": "Small"}, "metrics": {"costMicros": "1000000"}},
        {"campaign": {"id": "2", "name": "Large"}, "metrics": {"costMicros": "9000000"}},
    ]
    assert [r.campaign_name for r in rows_to_metrics(rows)] == ["Large", "Small"]


def test_zero_spend_and_zero_conversions_do_not_divide_by_zero():
    rows = [{"campaign": {"id": "1", "name": "Paused"}, "metrics": {}}]
    row = rows_to_metrics(rows)[0]
    assert (row.spend_inr, row.roas, row.cpa_inr, row.ctr) == (0.0, 0.0, 0.0, 0.0)


def test_rows_without_a_campaign_id_are_skipped():
    assert rows_to_metrics([{"metrics": {"costMicros": "5000000"}}]) == []


# ----------------------------------------------------------------------
# Network behaviour
# ----------------------------------------------------------------------


@respx.mock
def test_search_stream_flattens_chunked_results():
    respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
    )
    respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/googleAds:searchStream").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"results": [{"campaign": {"id": "1", "name": "A"}, "metrics": {"costMicros": "1000000"}}]},
                {"results": [{"campaign": {"id": "2", "name": "B"}, "metrics": {"costMicros": "2000000"}}]},
            ],
        )
    )

    snapshot = make_client().fetch_snapshot()
    assert snapshot.source == "live"
    assert len(snapshot.campaigns) == 2
    assert snapshot.total_spend_inr == 3.0
    assert snapshot.account_ids == ["1234567890"]


@respx.mock
def test_access_token_is_cached_across_calls():
    token_route = respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
    )
    respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/googleAds:searchStream").mock(
        return_value=httpx.Response(200, json=[{"results": []}])
    )

    client = make_client()
    client.search("SELECT campaign.id FROM campaign")
    client.search("SELECT campaign.id FROM campaign")

    assert token_route.call_count == 1


@respx.mock
def test_expired_token_triggers_a_refresh():
    token_route = respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
    )
    respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/googleAds:searchStream").mock(
        return_value=httpx.Response(200, json=[{"results": []}])
    )

    client = make_client()
    client.search("SELECT campaign.id FROM campaign")
    client._access_token_expiry = 0  # simulate expiry
    client.search("SELECT campaign.id FROM campaign")

    assert token_route.call_count == 2


@respx.mock
def test_failed_token_refresh_raises_rather_than_returning_empty_data():
    respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(400, json={"error": "invalid_grant"})
    )

    with pytest.raises(GoogleAdsError, match="token refresh failed"):
        make_client().fetch_snapshot()


@respx.mock
def test_api_error_surfaces_the_google_message():
    respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
    )
    respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/googleAds:searchStream").mock(
        return_value=httpx.Response(
            403,
            json=[
                {
                    "error": {
                        "message": "The caller does not have permission",
                        "details": [
                            {"errors": [{"message": "Developer token is not approved"}]}
                        ],
                    }
                }
            ],
        )
    )

    with pytest.raises(GoogleAdsError) as excinfo:
        make_client().fetch_snapshot()

    message = str(excinfo.value)
    assert "does not have permission" in message
    assert "Developer token is not approved" in message


@respx.mock
def test_budget_update_resolves_the_real_budget_resource():
    respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
    )
    respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/googleAds:searchStream").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "results": [
                        {
                            "campaign": {"id": "555"},
                            "campaignBudget": {
                                "resourceName": "customers/1234567890/campaignBudgets/777",
                                "amountMicros": "50000000",
                            },
                        }
                    ]
                }
            ],
        )
    )
    mutate = respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/campaignBudgets:mutate").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"resourceName": "customers/1234567890/campaignBudgets/777"}]},
        )
    )

    result = make_client().update_campaign_budget("555", 62.5)

    assert result["results"][0]["resourceName"].endswith("campaignBudgets/777")
    sent = mutate.calls[0].request
    body = sent.read().decode()
    # Micros conversion and the update mask must both be right.
    assert '"amountMicros": "62500000"' in body or '"amountMicros":"62500000"' in body
    assert "amount_micros" in body


@respx.mock
def test_budget_update_refuses_a_campaign_with_no_budget_resource():
    respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
    )
    respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/googleAds:searchStream").mock(
        return_value=httpx.Response(200, json=[{"results": []}])
    )

    with pytest.raises(GoogleAdsError, match="not found"):
        make_client().update_campaign_budget("555", 100.0)


@respx.mock
def test_verify_returns_account_identity():
    respx.post(GOOGLE_TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
    )
    respx.post(f"{GOOGLE_ADS_BASE}/customers/1234567890/googleAds:searchStream").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "results": [
                        {
                            "customer": {
                                "id": "1234567890",
                                "descriptiveName": "Finnovate India",
                                "currencyCode": "INR",
                                "timeZone": "Asia/Kolkata",
                            }
                        }
                    ]
                }
            ],
        )
    )

    result = make_client().verify()
    assert result["connected"] is True
    assert result["descriptive_name"] == "Finnovate India"
    assert result["currency_code"] == "INR"
