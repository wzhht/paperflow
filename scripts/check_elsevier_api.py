"""Standalone official Elsevier API diagnostic. No MinerU, GPU or corpus changes."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from lxml import etree

from paperflow.config import redact_error
from paperflow.parsers.elsevier_xml import inspect_elsevier_xml
from paperflow.qa.pdf import extract_elsevier_pdf_expectation, validate_pdf_bytes
from paperflow.utils.doi import normalize_doi

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_DOI = "10.1016/j.apenergy.2011.11.048"
PROBES = [
    ("XML 默认", "text/xml", None, "xml_default"),
    ("XML FULL", "text/xml", "FULL", "xml_full"),
    ("PDF FULL", "application/pdf", "FULL", "pdf_full"),
    ("PDF 默认", "application/pdf", None, "pdf_default"),
    ("权限查询", "application/json", "ENTITLED", "entitled"),
]


def safe(text, secrets):
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return redact_error(text)


def safe_fields(value, secrets):
    if isinstance(value, str):
        return safe(value, secrets)
    if isinstance(value, dict):
        return {key: safe_fields(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_fields(item, secrets) for item in value]
    return value


def read_doi(value=None):
    while True:
        supplied = value if value is not None else input(
            f"测试文章 DOI（直接回车用默认 {DEFAULT_DOI}；这里不要填 API key）："
        ).strip()
        try:
            doi = normalize_doi(supplied or DEFAULT_DOI)
            if not doi.startswith("10.1016/"):
                raise ValueError("Not an Elsevier DOI")
            return doi
        except (ValueError, TypeError):
            # Never echo the input: users may accidentally paste their key here.
            print("DOI 格式不正确：请填 10.1016/... 或直接回车，下一步才输入 API key。")
            value = None


def clean_credential(value):
    value = value.strip()
    for prefix in ("ELSEVIER_API_KEY=", "ELSEVIER_INSTTOKEN=", "ELSEVIER_INST_TOKEN="):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    value = value.strip("\"'")
    if value and (not value.isascii() or any(ord(char) < 33 or ord(char) == 127 for char in value)):
        raise ValueError("Credential input contains whitespace or non-ASCII characters")
    return value


def analyze(response, *, expectation=None):
    """HTTP success and PDF signature alone never imply complete full text."""
    row = {"http_status": response.status_code, "bytes": len(response.content),
           "full_text_verified": False}
    if response.status_code != 200:
        row["result"] = "接口未返回可验证全文"
        try:
            payload = response.json()
            status = payload.get("service-error", {}).get("status", {})
            row["api_code"] = status.get("statusCode")
            row["api_message"] = status.get("statusText")
        except (ValueError, AttributeError):
            try:
                tree = etree.fromstring(response.content,
                                        etree.XMLParser(resolve_entities=False, no_network=True))
                for name, target in [("statusCode", "api_code"), ("statusText", "api_message")]:
                    values = tree.xpath(f"//*[local-name()='{name}']/text()")
                    if values:
                        row[target] = str(values[0])
            except etree.XMLSyntaxError:
                pass
        return row
    if response.content.startswith(b"%PDF-"):
        result = validate_pdf_bytes(response.content, expectation)
        row["pdf"] = asdict(result)
        row["full_text_verified"] = result.is_valid
        row["result"] = (
            "PDF 页数检查通过"
            if result.is_valid else "PDF 不完整/疑似预览"
            if result.pages_match_expected is False else "取得 PDF，但无法确认全文完整性"
        )
        return row
    try:
        tree = etree.fromstring(response.content,
                                etree.XMLParser(resolve_entities=False, no_network=True))
        identifiers = tree.xpath("//*[local-name()='coredata']/*[local-name()='doi']/text()")
        if identifiers:
            row["returned_doi"] = str(identifiers[0]).strip().lower()
        stats = inspect_elsevier_xml(response.content)
        row["xml"] = asdict(stats)
        row["full_text_verified"] = stats.is_full_text
        row["result"] = "XML 正文检查通过" if stats.is_full_text else "XML 仅元数据/摘要或正文不完整"
    except (ValueError, RuntimeError, etree.XMLSyntaxError):
        row["result"] = "非 PDF/XML 全文（JSON 权限结果不算全文）"
    return row


def compare_keys(options):
    doi = read_doi(options.doi)
    print("API key 只在本次进程内使用，不写入 .env、不保存、不显示输入字符。")
    results = []
    while True:
        print(f"\n===== API {len(results) + 1:02d} =====")
        try:
            key = clean_credential(getpass.getpass("粘贴 API key 后按回车（输入不显示）："))
            token = clean_credential(getpass.getpass(
                "机构 token（没有就直接回车；输入不显示）："
            )) or None
        except ValueError:
            print("密钥输入含空格、换行或中文符号。请重新粘贴纯 key/token；没有发送请求。")
            continue
        if not key:
            print("没有输入 key，未发送请求。")
            continue
        try:
            code = main(
                [doi, "--timeout", str(options.timeout), "--output-root", str(options.output_root)],
                api_key=key, institution_token=token,
            )
        except OSError as exc:
            print(f"无法读写检测文件：{type(exc).__name__}，系统错误号 {exc.errno}。")
            print("请确认 workspace 文件夹可写；密钥未保存。")
            code = 2
        except ValueError as exc:
            print(f"请求或响应格式异常：{type(exc).__name__}；密钥未显示。")
            code = 2
        results.append(code)
        del key, token
        if input("回车测试下一个 API；输入 q 结束：").strip().lower() == "q":
            break
    print("\n本次比较结果（只适用于本次 DOI 和网络/授权上下文）：")
    for number, code in enumerate(results, 1):
        result = "取得可验证全文" if code == 0 else "程序未完成检测" if code == 2 else "未取得可验证全文"
        print(f"API {number:02d}：{result}")
    print("未取得全文不代表 key 一定无效；请查看各次 HTTP/API 错误及页数。")
    return 0 if 0 in results else 1


def main(argv=None, *, api_key=None, institution_token=None):
    parser = argparse.ArgumentParser(description="Elsevier API 全文专项检查，不调用 MinerU")
    parser.add_argument("doi", nargs="?")
    parser.add_argument("--compare-keys", action="store_true", help="安全输入多个 key 连续比较，不改 .env")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--output-root", type=Path,
                        default=PROJECT / "workspace/elsevier_api_tests")
    options = parser.parse_args(argv)
    if options.timeout <= 0:
        parser.error("timeout 必须大于 0")
    if options.compare_keys:
        return compare_keys(options)
    if api_key is None:
        load_dotenv(PROJECT / ".env", override=False)
        key = os.getenv("ELSEVIER_API_KEY")
        institution = os.getenv("ELSEVIER_INSTTOKEN") or os.getenv("ELSEVIER_INST_TOKEN")
    else:
        key, institution = api_key, institution_token
    if not key:
        print("未配置 ELSEVIER_API_KEY。请在 PaperFlow 项目 .env 中设置，不要粘贴到聊天。")
        return 2
    try:
        doi = normalize_doi(options.doi or input("输入一篇 Elsevier DOI：").strip())
        if not doi.startswith("10.1016/"):
            raise ValueError("本工具只检查 10.1016/ 开头的 Elsevier DOI。")
    except ValueError as exc:
        print(safe(str(exc), [key, institution]))
        return 2
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
    destination = options.output_root.resolve() / (
        stamp + "_" + hashlib.sha256(doi.encode()).hexdigest()[:8] + "_" + uuid4().hex[:6]
    )
    destination.mkdir(parents=True, exist_ok=False)
    report = {"doi": doi, "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "institution_token_configured": bool(institution), "probes": []}
    headers = {"X-ELS-APIKey": key, "User-Agent": "PaperFlow-Elsevier-Diagnostic/1.0"}
    if institution:
        headers["X-ELS-Insttoken"] = institution
    expectation = None
    key_source = "本次手动输入，不读取 .env 的 key" if api_key is not None else "环境配置"
    print(f"DOI：{doi}\nAPI key：{key_source}（不显示）\n机构 token：{'已配置' if institution else '未配置'}")
    print("分别检查 5 种官方请求。只有完整正文/匹配页数的 PDF 才通过。", flush=True)
    with httpx.Client(timeout=options.timeout, headers=headers, follow_redirects=False) as client:
        for number, (label, accept, view, filename) in enumerate(PROBES, 1):
            print(f"[{number}/5] {label} …", flush=True)
            row = {"name": label, "accept": accept, "view": view}
            try:
                response = client.get(
                    "https://api.elsevier.com/content/article/doi/" + quote(doi, safe="/"),
                    headers={"Accept": accept}, params={"view": view} if view else None,
                )
                row.update(analyze(response, expectation=expectation))
                if row.get("returned_doi") and row["returned_doi"] != doi:
                    row.update(full_text_verified=False, result="返回 DOI 不一致，拒绝作为全文")
                elif "xml" in row:
                    candidate = extract_elsevier_pdf_expectation(response.content)
                    if candidate.expected_pages:
                        expectation = candidate
                    content = response.content
                    for secret in [key, institution]:
                        if secret:
                            content = content.replace(secret.encode(), b"[REDACTED]")
                    (destination / (filename + ".xml")).write_bytes(content)
                elif "pdf" in row:
                    suffix = ".pdf" if row["full_text_verified"] else "_UNVERIFIED.pdf"
                    (destination / (filename + suffix)).write_bytes(response.content)
                elif label == "权限查询" and response.status_code == 200:
                    # Keep only this diagnostic's verdict, never arbitrary credential-bearing payloads.
                    row["result"] = "权限查询返回 200；这不证明全文已获取"
            except httpx.HTTPError as exc:
                row.update(full_text_verified=False, result="网络请求失败", error=type(exc).__name__)
            except (ValueError, TypeError, etree.XMLSyntaxError) as exc:
                row.update(full_text_verified=False, result="响应格式无法解析", error=type(exc).__name__)
            row = safe_fields(row, [key, institution])
            report["probes"].append(row)
            print(f"  HTTP={row.get('http_status', '无响应')}；{row['result']}")
            if "pdf" in row:
                print(f"  实际页数={row['pdf']['actual_pages']}；应有页数={row['pdf']['expected_pages']}")
            if row.get("api_code"):
                print(f"  API：{row['api_code']}；{str(row.get('api_message', ''))[:200]}")
    verified = any(row["full_text_verified"] for row in report["probes"])
    report["full_text_verified"] = verified
    verdict = "通过：取得通过正文结构/页数检查的全文。" if verified else "未通过：没有取得可验证的完整全文。"
    lines = [f"DOI：{doi}", verdict, ""]
    for row in report["probes"]:
        lines.append(f"{row['name']}：HTTP {row.get('http_status', '无响应')}；{row['result']}")
        if "pdf" in row:
            lines.append(f"  实际页数 {row['pdf']['actual_pages']} / 应有页数 {row['pdf']['expected_pages']}")
        if row.get("api_code"):
            lines.append(f"  {row['api_code']}：{str(row.get('api_message', ''))[:200]}")
    (destination / "检测报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (destination / "检测结论.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{verdict}\n结果文件夹：{destination}\n未调用 MinerU；未修改原文献库。")
    return 0 if verified else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已停止检测。")
        raise SystemExit(130) from None
    except (OSError, ValueError):
        print("检测未完成：文件路径、响应格式或参数异常。请检查配置；未输出响应或凭据。")
        raise SystemExit(2) from None
