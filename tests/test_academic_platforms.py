import json
from io import BytesIO

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject
from typer.testing import CliRunner

from paperflow.cli import app
from paperflow.sources.academic_platforms import fetch_platform_paper, paper_link

URL = 'https://proceedings.mlr.press/v202/test23a.html'
TITLE = 'Thermal response under climate change'


def title_pdf(title=TITLE, pages=2):
    writer = PdfWriter()
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    for _ in range(pages):
        page = writer.add_blank_page(width=600, height=800)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = StreamObject()
        stream.set_data(f'BT /F1 12 Tf 30 700 Td ({title}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


def page(title=TITLE, pdf='/v202/test23a/test23a.pdf'):
    return f'''<meta name="citation_title" content="{title}">
        <meta name="citation_firstpage" content="10"><meta name="citation_lastpage" content="11">
        <meta name="citation_pdf_url" content="{pdf}">'''


def test_public_pmlr_identity_completeness_and_immutable_version(tmp_path):
    def handler(request):
        assert request.url.host == 'proceedings.mlr.press'
        assert not request.url.query and 'authorization' not in request.headers
        return httpx.Response(200, text=page()) if request.url.path.endswith('.html') else httpx.Response(200, content=title_pdf())

    pdf, meta = fetch_platform_paper(URL, output_root=tmp_path, transport=httpx.MockTransport(handler))
    assert pdf.exists() and meta['doi'] is None
    assert meta['completeness_verified'] and meta['publication_type'] == 'conference-paper'
    original = pdf.with_name('acquisition.json').read_bytes()
    again, _ = fetch_platform_paper(URL, output_root=tmp_path, transport=httpx.MockTransport(handler))
    assert again == pdf and pdf.with_name('acquisition.json').read_bytes() == original


@pytest.mark.parametrize('url', [
    'https://evil.example/paper.html', 'https://jmlr.org/papers/',
    'https://user:password@jmlr.org/papers/v25/test.html',
    'https://jmlr.org/papers/v25/test.html?api_key=secret',
    'https://openreview.net/forum?id=abcde&token=secret',
    'https://openreview.net/forum?id=abcde&id=other',
    'http://proceedings.mlr.press/v202/test23a.html',
])
def test_only_canonical_official_paper_links_are_allowed(url):
    with pytest.raises(ValueError):
        paper_link(url)


@pytest.mark.parametrize('change', ['other_title', 'external_pdf', 'other_paper', 'private_redirect', 'challenge'])
def test_wrong_document_and_verification_pages_are_not_success(tmp_path, change):
    def handler(request):
        if request.url.path.endswith('.html'):
            if change == 'private_redirect':
                return httpx.Response(302, headers={'location': 'https://127.0.0.1/secret'})
            target = 'https://evil.example/paper.pdf' if change == 'external_pdf' else '/v202/test23a/other.pdf' if change == 'other_paper' else '/v202/test23a/test23a.pdf'
            return httpx.Response(200, text=page(pdf=target))
        if change == 'challenge':
            return httpx.Response(200, headers={'content-type': 'text/html'}, text='Just a moment')
        return httpx.Response(200, content=title_pdf('Unrelated paper title'))

    with pytest.raises(ValueError):
        fetch_platform_paper(URL, output_root=tmp_path, transport=httpx.MockTransport(handler))
    assert not list(tmp_path.rglob('paper.pdf'))


def test_openreview_keeps_publication_status_unknown_and_version_identity(tmp_path):
    def handler(request):
        if request.url.path == '/notes':
            return httpx.Response(200, json={'notes': [{'id': 'abcde', 'forum': 'abcde',
                'readers': ['everyone'], 'mdate': 123, 'content': {
                    'title': {'value': TITLE}, 'pdf': {'value': '/pdf/hash.pdf'},
                    'venue': {'value': 'Submitted to ICLR'}}}]})
        return httpx.Response(200, content=title_pdf())

    pdf, meta = fetch_platform_paper('https://openreview.net/forum?id=abcde',
        output_root=tmp_path, transport=httpx.MockTransport(handler))
    assert meta['note_mdate'] == 123 and meta['pdf_attachment'] == '/pdf/hash.pdf'
    assert 'unconfirmed' in meta['publication_status'] and not meta['completeness_verified']
    assert json.loads(pdf.with_name('acquisition.json').read_text())['sha256']


@pytest.mark.parametrize('readers,forum', [(['private'], 'abcde'), (['everyone'], 'other')])
def test_openreview_private_notes_and_reviews_are_not_papers(tmp_path, readers, forum):
    def handler(request):
        return httpx.Response(200, json={'notes': [{'id': 'abcde', 'forum': forum,
            'readers': readers, 'content': {'title': {'value': TITLE}, 'pdf': {'value': '/pdf/hash.pdf'}}}]})

    with pytest.raises(ValueError):
        fetch_platform_paper('https://openreview.net/forum?id=abcde', output_root=tmp_path,
                             transport=httpx.MockTransport(handler))


def test_cli_download_only_never_invokes_mineru(monkeypatch, tmp_path):
    from paperflow import pipeline
    from paperflow.sources import academic_platforms

    monkeypatch.setattr(academic_platforms, 'fetch_platform_paper', lambda *a, **kw:
        (tmp_path / 'paper.pdf', {'source': 'pmlr_official_pdf', 'completeness_verified': True, 'platform': 'pmlr'}))
    monkeypatch.setattr(pipeline, 'process_pdf', lambda *a, **kw: pytest.fail('MinerU must not run'))
    result = CliRunner().invoke(app, ['process-url', URL, '--download-only', '--output-root', str(tmp_path)])
    assert result.exit_code == 0 and 'completeness verified = True' in result.stdout


def test_tampered_version_is_not_overwritten(tmp_path):
    def handler(request):
        return httpx.Response(200, text=page()) if request.url.path.endswith('.html') else httpx.Response(200, content=title_pdf())

    pdf, _ = fetch_platform_paper(URL, output_root=tmp_path, transport=httpx.MockTransport(handler))
    pdf.write_bytes(b'user modified file')
    with pytest.raises(ValueError, match='not overwritten'):
        fetch_platform_paper(URL, output_root=tmp_path, transport=httpx.MockTransport(handler))
    assert pdf.read_bytes() == b'user modified file'


def test_cli_invalid_export_path_is_rejected_before_download(monkeypatch, tmp_path):
    from paperflow.sources import academic_platforms

    monkeypatch.setattr(academic_platforms, 'fetch_platform_paper', lambda *a, **kw:
        pytest.fail('Invalid export path must fail before acquisition/paid parsing'))
    result = CliRunner().invoke(app, ['process-url', URL, '--output-root', str(tmp_path),
                                     '--markdown-dir', str(tmp_path / 'reading')])
    assert result.exit_code == 1 and 'separate directory' in result.output


def test_cli_conversion_retains_platform_identity_without_inventing_doi(monkeypatch, tmp_path):
    from paperflow import pipeline
    from paperflow.pipeline import PaperResult
    from paperflow.sources import academic_platforms

    library = tmp_path / 'library'
    reading = tmp_path / 'reading'
    directory = library / 'paper'
    directory.mkdir(parents=True)
    qa = directory / 'qa.json'
    qa.write_text('{"status":"success"}')
    md = directory / 'paper_llm.md'
    md.write_text('# ' + TITLE + '\n\nFull text\n\n## References\nOriginal reference.')
    meta = {'source': 'pmlr_official_pdf', 'completeness_verified': True,
            'expected_pages': 2, 'platform': 'pmlr', 'title': TITLE, 'doi': None,
            'source_url': URL, 'sha256': 'retained-version-hash', 'publication_type': 'conference-paper'}
    monkeypatch.setattr(academic_platforms, 'fetch_platform_paper', lambda *a, **kw:
        (tmp_path / 'paper.pdf', meta))
    monkeypatch.setattr(pipeline, 'process_pdf', lambda *a, **kw:
        PaperResult(None, 'public_pdf', 'local_pdf_mineru', 'success', None, md, qa, False))
    result = CliRunner().invoke(app, ['process-url', URL, '--output-root', str(library),
                                     '--markdown-dir', str(reading)])
    assert result.exit_code == 0, result.output
    saved = json.loads((directory / 'metadata.json').read_text())
    assert saved['doi'] is None and saved['sha256'] == 'retained-version-hash'
    assert saved['publication_type'] == 'conference-paper' and saved['source_url'] == URL
    assert len(list(reading.glob('*.md'))) == 1
