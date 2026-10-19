import hashlib
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pypdf import PdfWriter

from paperflow.config import Settings
from paperflow.qa.pdf import PdfExpectation
from paperflow.sources.elsevier import ElsevierClient
from paperflow.sources.public_pdf import discover_pdf

spec = importlib.util.spec_from_file_location(
    "publisher_checks", Path(__file__).resolve().parents[1] / "scripts/check_publishers.py"
)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def test_campus_cases_are_grouped_verified_and_unique():
    path = Path(__file__).resolve().parents[1] / "scripts/campus_journal_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len({c["doi"] for c in cases}) == len(cases)
    groups = {c["test_group"] for c in cases}
    assert all(2 <= sum(c["test_group"] == group for c in cases) <= 3 for group in groups)
    assert all(c["title"] and c["journal"] and c["metadata_source"] for c in cases)
    assert all(c["oa_status"] in checks.ACCESS for c in cases)
    assert not any("correction:" in c["title"].lower() or "masthead" in c["title"].lower()
                   for c in cases)


def test_invalid_journal_selection_stops_before_acquisition(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["check_publishers.py", "--choose-journal"])
    monkeypatch.setattr("builtins.input", lambda _: "9999")
    monkeypatch.setattr(checks, "acquire", lambda *a: pytest.fail("Must not download"))
    with pytest.raises(SystemExit) as exc:
        checks.main()
    assert exc.value.code == 2
    assert "期刊编号" in capsys.readouterr().err


def pdf_bytes(pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def test_preview_and_unknown_page_count_never_pass(tmp_path):
    expected = PdfExpectation(None, None, 9, None)
    assert not checks.check_pdf(pdf_bytes(1), expected, tmp_path, "publisher")["full_text_verified"]
    assert not checks.check_pdf(pdf_bytes(9), None, tmp_path, "publisher")["full_text_verified"]
    assert checks.check_pdf(pdf_bytes(9), expected, tmp_path, "publisher")["full_text_verified"]


def test_pending_pdf_status_and_distinct_candidate_files(tmp_path):
    a = checks.check_pdf(pdf_bytes(3), None, tmp_path, 'publisher')
    b = checks.check_pdf(pdf_bytes(4), None, tmp_path, 'repository')
    assert a['file'] != b['file']
    assert (tmp_path / a['file']).is_file() and (tmp_path / b['file']).is_file()
    assert '待核验' in checks.result_label({'full_text_verified': False, 'stages': [a, b]})
    assert '待核验' not in checks.result_label({'full_text_verified': False, 'stages': []})


def test_reviewed_version_requires_exact_hash_and_same_doi(tmp_path, monkeypatch):
    monkeypatch.setattr(checks, 'PROJECT', tmp_path)
    data = pdf_bytes(3)
    (tmp_path / 'workspace').mkdir()
    (tmp_path / 'workspace/pdf_verifications.json').write_text(json.dumps([{
        'doi': '10.1109/example', 'sha256': hashlib.sha256(data).hexdigest(),
        'version': 'arxiv-v6', 'basis': 'User-supplied version reference',
    }]), encoding='utf-8')
    expected = PdfExpectation(None, None, 4, None)
    correct = checks.check_pdf(data, expected, tmp_path, 'repository', doi='10.1109/example')
    assert correct['full_text_verified'] and correct['verification']['version'] == 'arxiv-v6'
    assert not correct['pdf']['pages_match_expected']
    assert not checks.check_pdf(pdf_bytes(2), expected, tmp_path, 'repository', doi='10.1109/example')['full_text_verified']
    assert not checks.check_pdf(data, expected, tmp_path, 'repository', doi='10.1109/other')['full_text_verified']


def test_reviewed_published_version_is_not_labelled_as_preprint(tmp_path, monkeypatch):
    monkeypatch.setattr(checks, 'PROJECT', tmp_path)
    data = pdf_bytes(3)
    (tmp_path / 'workspace').mkdir()
    (tmp_path / 'workspace/pdf_verifications.json').write_text(json.dumps([{
        'doi': '10.1103/example', 'sha256': hashlib.sha256(data).hexdigest(),
        'version': 'publisher version', 'version_kind': 'published', 'basis': 'Official publisher reference',
    }]), encoding='utf-8')
    row = checks.check_pdf(data, None, tmp_path, 'publisher', doi='10.1103/example')
    assert row['full_text_verified'] and '出版文件' in row['status']
    assert '预印本' not in row['status']


def test_native_probe_continues_after_unverified_pdf(tmp_path, monkeypatch):
    from test_native_documents import DOI, article_html

    from paperflow.documents import normalize_document

    xml = normalize_document(article_html(), 'html', doi=DOI)
    monkeypatch.setattr(checks, 'native_candidates', lambda *a, **kw: iter([
        (pdf_bytes(3), 'pdf', 'publisher_pdf', 'https://example.org/a.pdf'),
        (xml, 'xml', 'pmc_jats', 'https://example.org/a.xml'),
    ]))
    monkeypatch.setattr(checks, 'page_expectation', lambda *a: None)
    row = checks.acquire({'doi': DOI, 'publisher': 'eLife'}, Settings(None, None, None), tmp_path / 'paper')
    assert row['full_text_verified']
    assert row['stages'][0]['pdf']['parseable']
    assert not row['stages'][0]['full_text_verified']
    assert row['stages'][-1]['stage'] == 'pmc_jats'


def test_manuscript_version_hint_does_not_override_completeness_failure(tmp_path, monkeypatch):
    page = SimpleNamespace(extract_text=lambda: "A SUBMISSION TO IEEE TRANSACTIONS\nTitle")
    monkeypatch.setattr(checks, "PdfReader", lambda _content: SimpleNamespace(pages=[page]))
    row = checks.check_pdf(pdf_bytes(1), PdfExpectation(None, None, 2, None), tmp_path, "oa_pdf")
    assert row["version_hint"] == "author_manuscript_or_preprint"
    assert not row["full_text_verified"]
    assert row["pdf"]["status"] == "invalid_page_count"


def test_nature_no_jats_falls_back_to_pdf_without_mineru(tmp_path, monkeypatch):
    class NoJats:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def fetch_jats(self, doi):
            raise RuntimeError("Not indexed yet")

    class Pdf(NoJats):
        def fetch_pdf(self, doi):
            return SimpleNamespace(content=pdf_bytes(9))

    monkeypatch.setattr(checks, "SpringerNatureClient", NoJats)
    monkeypatch.setattr(checks, "NaturePdfClient", Pdf)
    monkeypatch.setattr(checks, "page_expectation", lambda *a: PdfExpectation(None, None, 9, None))
    row = checks.acquire({"publisher": "Nature", "doi": "10.1038/example"},
                         Settings(None, "own-oa-key", None), tmp_path / "paper")
    assert row["full_text_verified"]
    assert len(row["stages"]) == 2
    assert not row["stages"][0]["full_text_verified"]


def test_network_comparison_uses_doi_not_row_position():
    prior = {"network_label": "vpn", "papers": [{"doi": "a", "full_text_verified": False}]}
    current = {"network_label": "campus", "papers": [
        {"doi": "b", "full_text_verified": False}, {"doi": "a", "full_text_verified": True}
    ]}
    rows = checks.compare_previous(current, prior)
    assert len(rows) == 1 and rows[0]["doi"] == "a"
    assert not rows[0]["previous_full_text"] and rows[0]["current_full_text"]


def test_comparison_uses_matching_batch_instead_of_latest_single_paper(tmp_path):
    batch = tmp_path / "batch.json"
    single = tmp_path / "single.json"
    batch.write_text(json.dumps({"network_label": "vpn", "papers": [
        {"doi": "a", "full_text_verified": False}, {"doi": "b", "full_text_verified": True}
    ]}), encoding="utf-8")
    single.write_text(json.dumps({"network_label": "vpn", "papers": [
        {"doi": "a", "full_text_verified": True}
    ]}), encoding="utf-8")
    current = {"network_label": "campus", "papers": [{"doi": "a"}, {"doi": "b"}]}
    chosen = checks.choose_previous(current, [batch, single])
    assert len(chosen["papers"]) == 2


def test_elsevier_optional_institution_token_stays_out_of_repr():
    settings = Settings("own-key", None, None, elsevier_insttoken="private-institution-token")
    assert "private-institution-token" not in repr(settings)

    def handler(request):
        assert request.headers["X-ELS-Insttoken"] == "private-institution-token"
        return httpx.Response(200, content=b"<response/>")

    with ElsevierClient("own-key", insttoken=settings.elsevier_insttoken,
                        transport=httpx.MockTransport(handler)) as client:
        client.fetch_xml("10.1016/example")


def test_ieee_locked_pdf_is_tried_in_current_institution_context():
    doi = "10.1109/example"

    def handler(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json={"message": {"DOI": doi, "title": ["Test"]}})
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json={"doi": "https://doi.org/" + doi, "locations": []})
        if request.url.host == "ieeexploreapi.ieee.org":
            assert request.url.params["apikey"] == "own-ieee-key"
            return httpx.Response(200, json={"articles": [{"doi": doi, "accessType": "Locked",
                "pdf_url": "https://ieeexplore.ieee.org/paper.pdf"}]})
        assert request.url.host == "ieeexplore.ieee.org"
        assert "apikey" not in request.url.params
        return httpx.Response(200, content=pdf_bytes(9))

    metadata, content, source, _url, _warnings = discover_pdf(
        doi, Settings(None, None, None, ieee_api_key="own-ieee-key"),
        transport=httpx.MockTransport(handler)
    )
    assert content and source == "ieee_institution_pdf"
    assert metadata["publisher_access_type"] == "Locked"


def test_disabled_ieee_api_preserves_oa_pdf_and_does_not_send_saved_key():
    doi = "10.1109/example"
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        assert request.url.host != "ieeexploreapi.ieee.org"
        assert "saved-ieee-key" not in str(request.url)
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json={"message": {"DOI": doi, "title": ["Paper"]}})
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json={"doi": "https://doi.org/" + doi, "locations": [
                {"is_oa": True, "pdf_url": "https://repository.example.org/paper.pdf"}
            ]})
        from test_academic_platforms import title_pdf

        return httpx.Response(200, content=title_pdf(doi, pages=9))

    settings = Settings(None, None, None, ieee_api_key="saved-ieee-key", ieee_api_enabled=False)
    _metadata, content, source, _url, _warnings = discover_pdf(
        doi, settings, transport=httpx.MockTransport(handler)
    )
    assert content and source == "openalex_oa_pdf"
    assert "repository.example.org" in hosts
    row = checks.probe_ieee_api(doi, settings)
    assert row["api_enabled"] is False and not row["full_text_verified"]
