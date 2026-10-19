"""Safe IEEE gateway diagnostics; never export provider bodies or credentials."""

from __future__ import annotations

import httpx


def describe_ieee_error(response: httpx.Response) -> dict:
    text = (response.text[:4096] + " " + response.headers.get("X-Mashery-Error-Code", "")).lower()
    if "developer inactive" in text or "developer_inactive" in text:
        code = "developer_inactive"
        message = "IEEE 网关返回 Developer Inactive；请核对开发者账户、应用和API授权，不能只凭此判定key无效"
    elif "invalid api key" in text or "invalidapikey" in text or "invalid_api_key" in text:
        code = "invalid_api_key"
        message = "IEEE 网关明确报告 API key 无效"
    elif response.status_code == 429 or "quota exceeded" in text or "rate limit exceeded" in text:
        code = "rate_limited"
        message = "IEEE API 限流或额度不足"
    else:
        code = "http_" + str(response.status_code)
        message = f"IEEE API HTTP {response.status_code}；原因尚未确认"
    return {"http_status": response.status_code, "api_error_code": code, "status": message}
