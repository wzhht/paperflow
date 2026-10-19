import importlib.util
from pathlib import Path

import httpx
import pytest

from paperflow.sources.ieee import describe_ieee_error
from paperflow.sources.nature_pdf import NaturePdfClient, NaturePdfContentError

spec = importlib.util.spec_from_file_location(
    "publisher_access_checks", Path(__file__).resolve().parents[1] / "scripts/check_publishers.py"
)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def test_ieee_gateway_reason_is_specific_and_does_not_echo_credentials():
    response = httpx.Response(403, text="<h1>Developer Inactive</h1> private-ieee-key",
                              headers={"X-Mashery-Error-Code": "ERR_403_DEVELOPER_INACTIVE"})
    diagnosis = describe_ieee_error(response)
    assert diagnosis["api_error_code"] == "developer_inactive"
    assert "private-ieee-key" not in str(diagnosis)
    assert "不能只凭此判定key无效" in diagnosis["status"]


@pytest.mark.parametrize("status,body,code", [
    (403, "Invalid API key: private-key", "invalid_api_key"),
    (429, "too many requests", "rate_limited"),
    (403, "unknown upstream response", "http_403"),
])
def test_ieee_gateway_error_types(status, body, code):
    diagnosis = describe_ieee_error(httpx.Response(status, text=body))
    assert diagnosis["api_error_code"] == code
    assert "private-key" not in str(diagnosis)


def test_nature_purchase_html_is_not_pdf_or_full_text():
    def handler(request):
        return httpx.Response(200, text="<html><p>Buy this article</p>Access through your institution</html>")

    with (
        NaturePdfClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(NaturePdfContentError) as raised,
    ):
        client.fetch_pdf("10.1038/nclimate2841")
    assert raised.value.reason == "access_restricted"
    assert "购买/机构访问网页" in checks.safe_error(raised.value)


def test_nature_challenge_does_not_trigger_more_download_attempts():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text="<h1>Verify you are human</h1>")

    with (
        NaturePdfClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(NaturePdfContentError) as raised,
    ):
        client.fetch_pdf("10.1038/nclimate2841")
    assert raised.value.reason == "user_verification_required"
    assert len(requests) == 1
