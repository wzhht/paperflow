"""One-click publisher acquisition acceptance test, using PaperFlow's source clients."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import zipfile
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from lxml import etree
from pypdf import PdfReader

from paperflow.config import load_settings
from paperflow.documents import normalize_document
from paperflow.parsers.elsevier_xml import inspect_elsevier_xml
from paperflow.qa.pdf import (
    PdfExpectation,
    extract_elsevier_pdf_expectation,
    inspect_pdf_page_sequence,
    validate_pdf_bytes,
)
from paperflow.qa.structured import inspect_jats_xml
from paperflow.sources.building_simulation_pdf import BuildingSimulationPdfClient
from paperflow.sources.elsevier import ElsevierClient
from paperflow.sources.ieee import describe_ieee_error
from paperflow.sources.native import fetch_wiley_pdf, native_candidates
from paperflow.sources.nature_pdf import NaturePdfClient, NaturePdfContentError
from paperflow.sources.public_pdf import discover_pdf
from paperflow.sources.springer_nature import SpringerNatureClient

PROJECT = Path(__file__).resolve().parents[1]
ACCESS = {"gold": "出版社 OA", "hybrid": "混合期刊中的 OA 文章",
          "bronze": "出版社免费可读（许可待核）", "green": "出版社非 OA，有开放存档",
          "closed": "非 OA / 订阅文章", "unknown": "未确认"}


def safe_error(exc):
    # Store only exception type and HTTP status, never provider bodies or URLs with keys.
    if isinstance(exc, NaturePdfContentError):
        labels = {
            "access_restricted": "Nature 返回购买/机构访问网页，未取得 PDF",
            "institution_login_required": "Nature 需要机构登录，未取得 PDF",
            "user_verification_required": "Nature 要求人工验证，请在浏览器完成；未尝试绕过",
            "non_pdf_response": "Nature 返回非 PDF 内容，原因待核验",
        }
        if exc.reason in labels:
            return labels[exc.reason]
    match = re.search(r"HTTP\s+(\d{3})", str(exc))
    return type(exc).__name__ + (" HTTP " + match[1] if match else "")


def check_pdf(content, expectation, directory, stage, *, doi=None):
    stats = validate_pdf_bytes(content, expectation)
    good = stats.is_valid
    evidence = None
    if not good and stats.parseable and doi:
        verification_path = PROJECT / "workspace/pdf_verifications.json"
        try:
            verified = json.loads(verification_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            verified = []
        digest = hashlib.sha256(content).hexdigest()
        for record in verified if isinstance(verified, list) else []:
            if isinstance(record, dict) and record.get('doi') == doi and record.get('sha256') == digest:
                evidence = {"verified": True, "method": "reviewed_version_sha256",
                            "version": record.get('version'), "sha256": digest,
                            "version_kind": record.get('version_kind', 'preprint'),
                            "basis": record.get('basis')}
                break
        if evidence is None:
            evidence = inspect_pdf_page_sequence(content, doi, expectation)
        good = evidence.get('verified', False)
    name = "paper.pdf" if good else "unverified_" + hashlib.sha256(content).hexdigest()[:12] + ".pdf"
    if stats.signature_ok:
        (directory / name).write_bytes(content)
    row = {"stage": stage, "format": "PDF", "full_text_verified": good,
            "status": ("全文页数通过" if good else
                       "已取得 PDF；缺少可靠页数依据，完整性待核验" if stats.parseable and stats.expected_pages is None else
                       "已取得 PDF；页数不符，需核对版本或是否缺页" if stats.parseable else
                       "未取得可解析 PDF"),
            "pdf": asdict(stats), "file": name if stats.signature_ok else None}
    if good and evidence:
        row['verification'] = evidence
        if evidence['method'] == 'reviewed_version_sha256':
            row['status'] = ("与已核验的同版本出版文件指纹一致" if evidence.get('version_kind') == 'published'
                             else "与已人工复核的同版本预印本逐字节一致（非出版版内容核验）")
        elif evidence['method'] == 'publisher_range_with_front_sheets':
            row['status'] = f"全文正文页码连续齐全；另含 {evidence['front_pages']} 页封面"
        else:
            row['status'] = "全文内逐页页码及总页数一致，DOI匹配"
    if not good and stats.parseable and stats.pages_match_expected is False:
        first_page = PdfReader(BytesIO(content)).pages[0].extract_text() or ""
        markers = [marker for marker in ("a submission to ieee", "accepted manuscript", "arxiv:")
                   if marker in first_page[:3000].lower()]
        if markers:
            row.update(status="疑似作者稿/预印本与出版版页数不同，完整性待人工核验",
                       version_hint="author_manuscript_or_preprint", version_markers=markers)
    return row


def result_label(row):
    if row["full_text_verified"]:
        return "全文检查通过"
    if any(stage.get("pdf", {}).get("parseable") for stage in row["stages"]):
        return "已取得 PDF，完整性待核验（不计成功）"
    return "未取得可验证全文"


def page_expectation(doi, settings):
    try:
        with httpx.Client(timeout=settings.http_timeout) as client:
            response = client.get("https://api.crossref.org/works/" + doi)
            response.raise_for_status()
            work = response.json()["message"]
        if str(work.get("DOI", "")).lower() != doi:
            return None
        match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", str(work.get("page", "")))
        if match and int(match[2]) >= int(match[1]):
            return PdfExpectation(None, None, int(match[2]) - int(match[1]) + 1, None,
                                  first_page=int(match[1]), last_page=int(match[2]))
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return None


def probe_ieee_api(doi, settings):
    """Test this user's IEEE metadata key; a metadata response is never a full text."""
    if not settings.ieee_api_enabled:
        return {"stage": "IEEE API", "status": "已停用 IEEE API；继续检查合法开放全文",
                "full_text_verified": False, "api_enabled": False}
    if not settings.ieee_api_key:
        return {"stage": "IEEE API", "status": "未配置 IEEE_API_KEY", "full_text_verified": False}
    with httpx.Client(timeout=settings.http_timeout, follow_redirects=False) as client:
        response = client.get("https://ieeexploreapi.ieee.org/api/v1/search/articles",
                              params={"doi": doi, "apikey": settings.ieee_api_key, "format": "json"})
        row = {"stage": "IEEE API", "http_status": response.status_code,
               "full_text_verified": False, "status": f"HTTP {response.status_code}，元数据请求未成功"}
        if response.status_code >= 400:
            row.update(describe_ieee_error(response))
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            matched = next((a for a in articles if str(a.get("doi", "")).lower() == doi), None)
            if matched:
                row.update(status="元数据成功（不等于全文权限）",
                           publisher_access_type=matched.get("accessType", "unknown"),
                           article_number=matched.get("article_number"))
        return row


def acquire(case, settings, directory):
    doi, publisher = case["doi"], case["publisher"]
    directory.mkdir(parents=True, exist_ok=False)
    stages = []
    expectation = page_expectation(doi, settings)

    def attempt(label, operation):
        try:
            row = operation()
        except (RuntimeError, OSError, ValueError, httpx.HTTPError, etree.XMLSyntaxError) as exc:
            row = {"stage": label, "status": safe_error(exc), "full_text_verified": False}
        stages.append(row)
        print(f"    {label}：{row['status']}", flush=True)
        return row.get("full_text_verified", False)

    def elsevier_xml():
        nonlocal expectation
        with ElsevierClient(settings.elsevier_api_key or "", timeout=settings.http_timeout,
                            insttoken=settings.elsevier_insttoken) as client:
            content = client.fetch_xml(doi)
        tree = etree.fromstring(content, etree.XMLParser(resolve_entities=False, no_network=True))
        identifiers = tree.xpath("//*[local-name()='coredata']/*[local-name()='doi']/text()")
        if not identifiers or str(identifiers[0]).lower().strip() != doi:
            raise ValueError("DOI mismatch")
        stats = inspect_elsevier_xml(content)
        candidate = extract_elsevier_pdf_expectation(content)
        if candidate.expected_pages:
            expectation = candidate
        (directory / "paper.xml").write_bytes(content)
        return {"stage": "Elsevier XML", "format": "XML", "full_text_verified": stats.is_full_text,
                "status": "XML全文正文通过" if stats.is_full_text else "只有元数据/摘要或正文不足",
                "xml": asdict(stats)}

    def elsevier_pdf():
        with ElsevierClient(settings.elsevier_api_key or "", timeout=settings.http_timeout,
                            insttoken=settings.elsevier_insttoken) as client:
            content = client.fetch_pdf(doi)
        return check_pdf(content, expectation, directory, "Elsevier PDF", doi=doi)

    def jats():
        with SpringerNatureClient(settings.springer_oa_api_key or "", settings.http_timeout) as client:
            payload = client.fetch_jats(doi)
        path = directory / "jats.xml"
        path.write_bytes(payload.article_xml)
        stats = inspect_jats_xml(path)
        return {"stage": "Springer OA JATS", "format": "XML",
                "full_text_verified": stats.candidate_full_text and stats.doi == doi,
                "status": "JATS全文通过" if stats.candidate_full_text and stats.doi == doi else "JATS不足/DOI不匹配",
                "xml": asdict(stats)}

    def publisher_pdf():
        cls = NaturePdfClient if publisher == "Nature" else BuildingSimulationPdfClient
        with cls(settings.http_timeout) as client:
            payload = client.fetch_pdf(doi)
        return check_pdf(payload.content, expectation, directory, "出版商 PDF", doi=doi)

    def public_pdf():
        metadata, content, source, _url, warnings = discover_pdf(doi, settings)
        (directory / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        if content is None:
            status = "未取得 PDF，元数据不是全文"
            if any(w.startswith('browser_verification_required:') for w in warnings):
                status = "出版社要求浏览器验证；请在浏览器完成并下载 PDF，程序未取得全文"
            elif any(w.startswith('publisher_http_403:') for w in warnings):
                status = "出版社拒绝程序请求（HTTP 403）；不能据此判定文章收费"
            elif any(w.startswith('publisher_http_429:') for w in warnings):
                status = "出版社请求限流（HTTP 429）；稍后再试"
            if any(w.startswith('openalex_content_http_') for w in warnings):
                status += "；OpenAlex 全文存档接口未授权、额度不足或限流，未取得缓存 PDF"
            return {"stage": "官方/合法开放 PDF", "status": status,
                    "full_text_verified": False, "warnings": warnings}
        return {**check_pdf(content, expectation, directory, source, doi=doi), "warnings": warnings}

    def wiley_pdf():
        content = fetch_wiley_pdf(doi, settings)
        if content is None:
            return {"stage": "Wiley TDM", "status": "没有读到 Wiley_API_KEY / WILEY_API_KEY",
                    "full_text_verified": False}
        return check_pdf(content, expectation, directory, "Wiley TDM", doi=doi)

    def native_document():
        diagnostics = []
        for content, kind, source, _url in native_candidates(doi, settings, diagnostics=diagnostics):
            if kind == "pdf":
                row = check_pdf(content, expectation, directory, source, doi=doi)
                if row["full_text_verified"]:
                    return row
                stages.append(row)
                print(f"    {source}：{row['status']}", flush=True)
                continue
            try:
                normalized = normalize_document(content, kind, doi=doi)
                path = directory / "native_jats.xml"
                path.write_bytes(normalized)
                stats = inspect_jats_xml(path)
                if stats.candidate_full_text and stats.reference_count:
                    return {"stage": source, "format": "XML", "full_text_verified": True,
                            "status": "原生结构化全文通过", "xml": asdict(stats)}
                stages.append({"stage": source, "status": "结构化正文或 References 不足",
                               "full_text_verified": False})
            except (ValueError, TypeError, RuntimeError, OSError, etree.XMLSyntaxError,
                    KeyError, zipfile.BadZipFile) as exc:
                stages.append({"stage": source, "status": "原生格式未通过转换检查：" + safe_error(exc),
                               "full_text_verified": False})
                continue
        return {"stage": "原生全文", "status": "未取得可验证原生全文", "full_text_verified": False,
                "requests": diagnostics}

    if publisher == "Elsevier":
        if not attempt("Elsevier XML", elsevier_xml):
            attempt("Elsevier PDF", elsevier_pdf)
    elif publisher in {"Nature", "Springer"}:
        if not attempt("Springer OA JATS", jats):
            attempt("出版商 PDF" if publisher == "Nature" else "官方/合法开放 PDF",
                    publisher_pdf if publisher == "Nature" else public_pdf)
    elif publisher == "Building Simulation":
        attempt("出版商 PDF", publisher_pdf)
    elif publisher == "IEEE":
        attempt("IEEE API", lambda: probe_ieee_api(doi, settings))
        attempt("官方/合法开放 PDF", public_pdf)
    elif publisher == "Wiley":
        if not attempt("Wiley TDM", wiley_pdf):
            attempt("官方/合法开放 PDF", public_pdf)
    else:
        if not attempt("原生全文", native_document):
            attempt("官方/合法开放 PDF", public_pdf)
    return {**case, "stages": stages, "full_text_verified": any(s["full_text_verified"] for s in stages)}


def compare_previous(report, previous):
    old = {row["doi"]: row for row in previous.get("papers", [])}
    return [{"doi": row["doi"], "previous_network": previous.get("network_label", "未标记"),
             "current_network": report["network_label"],
             "previous_full_text": old[row["doi"]]["full_text_verified"],
             "current_full_text": row["full_text_verified"]}
            for row in report["papers"] if row["doi"] in old]


def choose_previous(report, paths):
    current_dois = {row["doi"] for row in report["papers"]}
    candidates = []
    for path in paths:
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous.get("completed") is False:
                continue
            overlap = len(current_dois & {row["doi"] for row in previous.get("papers", [])})
            if overlap:
                candidates.append((overlap, previous.get("network_label") != report["network_label"],
                                   path.stat().st_mtime, previous))
        except (OSError, ValueError, KeyError):
            continue
    return max(candidates, key=lambda item: item[:3])[3] if candidates else None


def main():
    parser = argparse.ArgumentParser(description="整批检测出版社获取能力，不调用GPU/MinerU")
    parser.add_argument("--network", choices=["campus", "vpn", "other"])
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--cases", type=Path, default=PROJECT / "scripts/publisher_test_cases.json")
    parser.add_argument("--choose-journal", action="store_true",
                        help="Choose one journal/venue group, or run the complete sample list")
    options = parser.parse_args()
    if options.timeout <= 0:
        parser.error("timeout must be positive")
    cases = json.loads(options.cases.read_text(encoding="utf-8"))
    if options.choose_journal:
        groups = list(dict.fromkeys(c.get("test_group", c.get("journal", c["publisher"]))
                                    for c in cases))
        print("选择期刊（每组 2–3 篇；会议、预印本另列，不混称期刊）：")
        print(f"  0. 全部样本（{len(cases)} 篇，可能需要较长时间）")
        for number, group in enumerate(groups, 1):
            count = sum(c.get("test_group", c.get("journal", c["publisher"])) == group
                        for c in cases)
            print(f"  {number}. {group}（{count} 篇）")
        choice = input("输入编号（回车选全部）：").strip() or "0"
        if not choice.isdigit() or not 0 <= int(choice) <= len(groups):
            parser.error("期刊编号不在列表中；没有开始下载")
        if int(choice):
            selected = groups[int(choice) - 1]
            cases = [c for c in cases
                     if c.get("test_group", c.get("journal", c["publisher"])) == selected]
    if options.network:
        label = options.network
    else:
        choice = input("当前网络：1 校园网 / 2 VPN / 3 其他（回车选3）：").strip()
        label = {"1": "campus", "2": "vpn"}.get(choice, "other")
    load_dotenv(PROJECT / ".env", override=False)
    settings = replace(load_settings(), http_timeout=options.timeout)
    root = PROJECT / "workspace/publisher_checks"
    root.mkdir(parents=True, exist_ok=True)
    previous_files = sorted(root.glob("*/report.json"), key=lambda p: p.stat().st_mtime)
    now = datetime.now(timezone(timedelta(hours=8)))
    output = root / (now.strftime("%Y%m%d_%H%M%S") + "_" + label + "_" + uuid4().hex[:6])
    output.mkdir()
    report = {"network_label": label, "checked_at": now.isoformat(),
              "sample_count": len(cases), "completed": False,
              "proxy_env_present": any(os.getenv(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")),
              "papers": []}
    print("使用 .env / 系统环境中的自己的 key；网络标记由你选择，不推断当前是否校园网。")
    print("不自动切换网络，不更改代理设置，不调用 MinerU。只取得完整全文才通过。", flush=True)
    for number, case in enumerate(cases, 1):
        print(f"\n[{number}/{len(cases)}] {case.get('test_group', case.get('journal', case['publisher']))} | {ACCESS.get(case.get('oa_status'), '未确认')}")
        print(f"  {case['title']}\n  DOI：{case['doi']}")
        print(f"  类型来源：{case.get('metadata_source', '未知')}，核验日期：{case.get('classification_checked_at', '未知')}", flush=True)
        row = acquire(case, settings, output / f"{number:02d}")
        report["papers"].append(row)
        print("  结果：" + result_label(row), flush=True)
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    comparisons = []
    previous = choose_previous(report, previous_files)
    if previous:
        comparisons = compare_previous(report, previous)
    report["comparison"] = comparisons
    report["completed"] = True
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "检测汇总.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["出版社", "期刊/会议", "文章类型", "标题", "DOI", "全文检查通过", "检测结论"])
        for row in report["papers"]:
            writer.writerow([row["publisher"], row.get("journal", ""), ACCESS.get(row.get("oa_status"), "未确认"), row["title"],
                             row["doi"], row["full_text_verified"], result_label(row)])
    passed = sum(row["full_text_verified"] for row in report["papers"])
    pending = sum("已取得 PDF" in result_label(row) for row in report["papers"])
    lines = ["出版社整批获取检测", f"网络标记：{label}", f"检测时间：{now.isoformat()}",
             f"全文通过 {passed}/{len(cases)}；PDF 待核验 {pending}；未取得可验证全文 {len(cases) - passed - pending}",
             "本次只测试获取与完整性，不代表 Markdown 转换或 GPU 验证通过。", ""]
    for row in report["papers"]:
        lines.append(f"{row.get('test_group', row.get('journal', row['publisher']))} | {ACCESS.get(row.get('oa_status'), '未确认')} | {row['doi']}："
                     + result_label(row))
        for stage in row["stages"]:
            lines.append(f"  {stage['stage']}：{stage['status']}")
            if "pdf" in stage:
                expected = stage['pdf']['expected_pages']
                lines.append(f"    实际 {stage['pdf']['actual_pages']} 页 / 应有页数：{str(expected) + ' 页' if expected is not None else '未查到可靠记录'}")
    if comparisons:
        lines += ["", "与上一次检测比较（网络标记由用户选择；不能单独证明差异原因）："]
        lines += [f"{c['doi']}：{c['previous_network']}={c['previous_full_text']} → "
                  f"{c['current_network']}={c['current_full_text']}" for c in comparisons]
    (output / "检测结论.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n全文通过 {passed}/{len(cases)}；PDF 待核验 {pending}；未取得可验证全文 {len(cases) - passed - pending}。结果：{output}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已停止，已完成的检测保留在本次结果目录。")
        raise SystemExit(130) from None
    except (OSError, ValueError, KeyError) as exc:
        print("检测程序未完成：" + safe_error(exc) + "。请检查目录权限和样本配置；未输出凭据。")
        raise SystemExit(2) from None
