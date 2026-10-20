import httpx
import pytest
from test_academic_platforms import TITLE, title_pdf

from paperflow.config import Settings
from paperflow.sources.public_pdf import discover_pdf


@pytest.mark.parametrize('empty_page', [b'', b'   \n\t', b'<!-- no article -->'])
def test_empty_repository_page_does_not_abort_other_sources(empty_page):
    doi = '10.1115/test'

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi, 'title': [TITLE]}})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi, 'locations': [
                {'is_oa': True, 'source': {'type': 'repository'},
                 'landing_page_url': 'https://archive.example/empty'},
                {'is_oa': True, 'source': {'type': 'repository'},
                 'landing_page_url': 'https://archive.example/paper'}]})
        if request.url.path == '/empty':
            return httpx.Response(200, content=empty_page)
        if request.url.path == '/paper':
            return httpx.Response(200, text=f'<meta name="citation_doi" content="{doi}">'
                                          '<meta name="citation_pdf_url" content="/article.pdf">')
        assert request.url.path == '/article.pdf'
        return httpx.Response(200, content=title_pdf(TITLE))

    _meta, content, source, _url, warnings = discover_pdf(
        doi, Settings(None, None, None), transport=httpx.MockTransport(handler))
    assert content and source == 'oa_repository_metadata_pdf'
    assert 'oa_repository_page_no_verified_pdf_links' in warnings


def test_empty_ieee_viewer_is_an_unusable_candidate():
    from paperflow.sources.public_pdf import _embedded_ieee_pdf

    response = httpx.Response(200, content=b'',
                             request=httpx.Request('GET', 'https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=123'))
    assert _embedded_ieee_pdf(response) == []


@pytest.mark.parametrize('correct', [True, False])
def test_oa_repository_landing_metadata_is_followed_only_after_identity_check(correct):
    doi = '10.1115/test'

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi, 'title': [TITLE]}})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi, 'locations': [
                {'is_oa': True, 'source': {'type': 'repository'}, 'landing_page_url': 'https://archive.example/paper'}]})
        if request.url.path == '/paper':
            assert request.url.host == 'archive.example'
            return httpx.Response(200, text=f'<meta name="citation_doi" content="{doi}"><meta name="citation_pdf_url" content="/article.pdf">')
        assert request.url.path == '/article.pdf'
        return httpx.Response(200, content=title_pdf(TITLE if correct else 'An unrelated research paper'))

    _meta, content, source, _url, _warnings = discover_pdf(doi, Settings(None, None, None),
        transport=httpx.MockTransport(handler))
    assert bool(content) == correct
    if correct:
        assert source == 'oa_repository_metadata_pdf'
