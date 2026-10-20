"""Optional official MinerU cloud adapters; no local GPU imports."""

from __future__ import annotations

import io
import json
import re
import time
import zipfile
from pathlib import Path

import httpx

from paperflow.parsers.mineru_pdf import (
    MinerUArtifactError,
    MinerUExecutionError,
    MinerUParseResult,
)

BASE = "https://mineru.net"


def content_list_to_structured(items: list) -> dict:
    pages = {}
    for item in items:
        if not isinstance(item, dict):
            raise MinerUArtifactError("Invalid MinerU content list entry.")
        kind = item.get("type", "text")
        block = {"type": kind}
        if kind == "text":
            block["content"] = item.get("text", "")
            if item.get("text_level"):
                block["type"] = (
                    "doc_title" if not pages and item.get("page_idx", 0) == 0 else "paragraph_title"
                )
            if re.fullmatch(r"\s*(references|bibliography)\s*", block["content"], re.IGNORECASE):
                block["type"] = "paragraph_title"
        elif kind == "table":
            block.update(
                content=item.get("table_body", ""),
                captions=[{"content": x} for x in item.get("table_caption", [])],
                footnotes=[{"content": x} for x in item.get("table_footnote", [])],
            )
        elif kind in {"image", "chart"}:
            block["captions"] = [{"content": x} for x in item.get("img_caption", [])]
        elif kind in {"equation", "interline_equation"}:
            block["content"] = item.get("text", "")
        elif kind == "ref_text":
            block.update(
                type="list", sub_type="ref_text", content=item.get("text", item.get("content", ""))
            )
        elif kind == "list":
            block["content"] = "\n".join(item.get("list_items", []))
            block["sub_type"] = item.get("sub_type", "")
        else:
            block["content"] = item.get("text", item.get("content", ""))
        page = int(item.get("page_idx", 0))
        pages.setdefault(page, []).append(block)
    if not pages:
        raise MinerUArtifactError("MinerU returned an empty content list.")
    return {
        "pages": [{"page_idx": n, "blocks": blocks} for n, blocks in sorted(pages.items())],
        "is_full_document": True,
        "metadata": {"producer": {"name": "mineru-api"}},
    }


def markdown_to_structured(text: str) -> dict:
    # Lightweight API exposes no layout or original table JSON: never claim table QA.
    text = re.sub(r"!\[[^\]]*\]\([^\n]*?\)", "", text)
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.IGNORECASE)
    blocks = []
    for part in re.split(r"\n\s*\n", text):
        part = part.strip()
        if not part:
            continue
        for line in part.splitlines() if part.startswith("#") else [part]:
            heading = re.match(r"^#{1,6}\s+(.+)$", line)
            is_ref = re.fullmatch(r"references|bibliography", line, re.IGNORECASE)
            blocks.append(
                {
                    "type": ("doc_title" if heading and not blocks else "paragraph_title")
                    if heading or is_ref
                    else "text",
                    "content": heading[1] if heading else line,
                }
            )
    return {
        "pages": [{"page_idx": 0, "blocks": blocks}],
        "is_full_document": False,
        "metadata": {"producer": {"name": "mineru-api-light"}},
        "warnings": ["lightweight_api_no_structured_table_or_page_validation"],
    }


def normalize_structured(data):
    """Cloud v4 may use ref_text blocks; map them without changing bibliography text."""
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise MinerUArtifactError("Cloud structured content has no pages list.")
    for page in data["pages"]:
        for block in page.get("blocks", []):
            if block.get("type") == "ref_text":
                block["type"] = "list"
                block["sub_type"] = "ref_text"
    return data


def normalize_archive(content: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            native = [n for n in names if Path(n).name == "structured_content.json"]
            if len(native) == 1:
                return normalize_structured(json.loads(archive.read(native[0])))
            lists = [
                n
                for n in names
                if n.endswith("_content_list.json") or Path(n).name == "content_list.json"
            ]
            if len(lists) != 1:
                raise MinerUArtifactError(
                    "Cloud ZIP must contain one structured content or content list JSON."
                )
            return content_list_to_structured(json.loads(archive.read(lists[0])))
    except (zipfile.BadZipFile, ValueError, KeyError, TypeError) as exc:
        raise MinerUArtifactError(
            "MinerU cloud artifact is invalid or has an unsupported schema."
        ) from exc


def parse_pdf_with_mineru_api(
    pdf_path,
    output_zip,
    *,
    token=None,
    model="vlm",
    timeout=600.0,
    poll_interval=3.0,
    lightweight=False,
    transport=None,
    progress=None,
):
    pdf_path, output_zip = Path(pdf_path), Path(output_zip)
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if not lightweight and not token:
        raise MinerUExecutionError(
            "MINERU_API_TOKEN is required for the precision API; configure it in .env."
        )
    if model not in {"pipeline", "vlm"} or timeout <= 0 or poll_interval <= 0:
        raise ValueError("Invalid MinerU model or timing options.")
    if pdf_path.stat().st_size > (10 if lightweight else 200) * 1024 * 1024:
        raise MinerUExecutionError("PDF exceeds selected MinerU API size limit.")
    from pypdf import PdfReader

    if len(PdfReader(pdf_path).pages) > (20 if lightweight else 200):
        raise MinerUExecutionError(
            "PDF exceeds selected MinerU API page limit; no automatic truncation."
        )
    auth = {"Authorization": f"Bearer {token}"} if not lightweight else {}
    deadline = time.monotonic() + timeout
    try:
        # Auth is passed only to the fixed official API, never signed upload/CDN URLs.
        with httpx.Client(
            timeout=min(timeout, 120), transport=transport, follow_redirects=False
        ) as client:

            def request(method, url, **kwargs):
                response = client.request(method, url, **kwargs)
                if not 200 <= response.status_code < 300:
                    raise MinerUExecutionError(
                        f"MinerU request failed (HTTP {response.status_code}); check access/quota."
                    )
                return response

            def data(response):
                payload = response.json()
                if payload.get("code") != 0:
                    raise MinerUExecutionError(
                        f"MinerU API rejected request (code {payload.get('code')}); check token/quota/file limits."
                    )
                return payload["data"]

            if lightweight:
                started = data(
                    request(
                        "POST",
                        BASE + "/api/v1/agent/parse/file",
                        json={
                            "file_name": pdf_path.name,
                            "language": "en",
                            "enable_table": True,
                            "enable_formula": True,
                        },
                    )
                )
                upload = started["file_url"]
                poll = BASE + "/api/v1/agent/parse/" + started["task_id"]
            else:
                started = data(
                    request(
                        "POST",
                        BASE + "/api/v4/file-urls/batch",
                        headers=auth,
                        json={
                            "files": [{"name": pdf_path.name}],
                            "model_version": model,
                            "enable_table": True,
                            "enable_formula": True,
                            "language": "en",
                        },
                    )
                )
                upload = started["file_urls"][0]
                poll = BASE + "/api/v4/extract-results/batch/" + started["batch_id"]
            if not str(upload).startswith("https://"):
                raise MinerUExecutionError("MinerU returned an insecure upload URL.")
            with pdf_path.open("rb") as handle:
                request("PUT", upload, content=handle)
            previous = None
            while time.monotonic() < deadline:
                state = data(request("GET", poll, headers=auth))
                state = state if lightweight else (state.get("extract_result") or [{}])[0]
                if progress and state.get("state") != previous:
                    progress("MinerU API: " + str(state.get("state", "pending")))
                previous = state.get("state")
                if previous == "failed":
                    raise MinerUExecutionError(
                        "MinerU cloud parsing failed; check file limits or provider status."
                    )
                if previous == "done":
                    url = state.get("markdown_url" if lightweight else "full_zip_url")
                    if not str(url).startswith("https://"):
                        raise MinerUExecutionError("MinerU returned an insecure artifact URL.")
                    response = request("GET", url)
                    structured = (
                        markdown_to_structured(response.text)
                        if lightweight
                        else normalize_archive(response.content)
                    )
                    output_zip.parent.mkdir(parents=True, exist_ok=True)
                    temp = output_zip.with_suffix(".tmp.zip")
                    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
                        archive.writestr(
                            "structured_content.json", json.dumps(structured, ensure_ascii=False)
                        )
                    temp.replace(output_zip)
                    return MinerUParseResult(pdf_path, output_zip, ("structured_content.json",))
                time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
            raise MinerUExecutionError("MinerU API timed out; no automatic paid resubmission.")
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        # Never include HTTP request/response dumps or provider messages (may contain secrets).
        raise MinerUExecutionError(
            "MinerU API communication/schema error; check connectivity and provider configuration."
        ) from exc
