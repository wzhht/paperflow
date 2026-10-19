"""Small real-source acceptance suite; downloads only unless --parse-pdf is explicit."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_publishers import acquire, result_label, safe_error

from paperflow.config import load_settings
from paperflow.pipeline import process_document, process_pdf
from paperflow.sources.academic_platforms import fetch_platform_paper

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='公开全文入口验收；默认不调用MinerU')
    parser.add_argument('--group', help='只测指定分组；不指定则测全部小样本')
    parser.add_argument('--parse-pdf', action='store_true', help='显式使用已配置的MinerU转换PDF，可能消耗额度')
    parser.add_argument('--timeout', type=float, default=20)
    options = parser.parse_args()
    cases = json.loads((PROJECT / 'scripts/public_extension_cases.json').read_text(encoding='utf-8'))
    if options.group:
        cases = [c for c in cases if c['test_group'].casefold() == options.group.casefold()]
        if not cases:
            parser.error('没有这个分组；请查看 public_extension_cases.json')
    load_dotenv(PROJECT / '.env', override=False)
    settings = replace(load_settings(), http_timeout=options.timeout)
    folder = PROJECT / 'workspace/public_extensions' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8])
    folder.mkdir(parents=True)
    report = {'completed': False, 'pdf_conversion_requested': options.parse_pdf, 'papers': []}
    print('只用公开全文来源；不推断当前是否校园网。报告：' + str(folder), flush=True)
    for number, case in enumerate(cases, 1):
        print(f"[{number}/{len(cases)}] {case['test_group']} {case.get('doi') or case['url']}", flush=True)
        target = folder / f'{number:02d}'
        try:
            if case.get('url'):
                pdf, metadata = fetch_platform_paper(case['url'], output_root=target,
                                                      timeout=settings.http_timeout)
                row = {**case, 'acquired_pdf': True, 'full_text_verified': metadata['completeness_verified'],
                       'acquisition': metadata, 'pdf': str(pdf)}
                if options.parse_pdf:
                    if metadata['expected_pages'] and not metadata['completeness_verified']:
                        row.update(markdown_status='not_run', markdown_error='Page count differs; MinerU not run')
                    else:
                        try:
                            result = process_pdf(pdf, output_root=target / 'converted', title=metadata['title'],
                                                 settings=replace(settings, mineru_backend='api'))
                            row.update(markdown_status=result.status, markdown=str(result.llm_markdown_path))
                        except (ValueError, RuntimeError, OSError) as exc:
                            row.update(markdown_status='failed', markdown_error=safe_error(exc))
            else:
                row = acquire(case, settings, target)
                # Structured acquisition and actual renderer/QA acceptance are separate.
                native = target / 'native_jats.xml'
                if row['full_text_verified'] and native.exists():
                    try:
                        result = process_document(native, doi=case['doi'], output_root=target / 'converted')
                        row.update(markdown_status=result.status, markdown=str(result.llm_markdown_path))
                    except (ValueError, RuntimeError, OSError) as exc:
                        row.update(markdown_status='failed', markdown_error=safe_error(exc))
                print('  ' + result_label(row), flush=True)
            print('  全文核验：' + str(row['full_text_verified']) + '; Markdown：' + row.get('markdown_status', '未执行'), flush=True)
        except (ValueError, RuntimeError, OSError, httpx.HTTPError) as exc:
            row = {**case, 'full_text_verified': False, 'error_type': type(exc).__name__}
            print('  未通过：' + safe_error(exc), flush=True)
        report['papers'].append(row)
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['completed'] = True
    (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['公开全文入口验收', '来源下载、完整性核验、Markdown转换分开报告。', '']
    for row in report['papers']:
        lines.append(f"{row['test_group']} | {row.get('doi') or row['url']} | 全文核验={row['full_text_verified']} | Markdown={row.get('markdown_status', '未执行')}")
    (folder / '检测结论.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('结果：' + str(folder), flush=True)
    return 0 if all(p['full_text_verified'] and p.get('markdown_status') != 'failed' for p in report['papers']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
