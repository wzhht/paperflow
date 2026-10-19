from io import BytesIO

import httpx
import pytest
from pypdf import PdfWriter
from test_academic_platforms import title_pdf

from paperflow.config import Settings
from paperflow.sources.public_pdf import _crossref_pdf_links, _embedded_ieee_pdf, discover_pdf


def pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


def test_crossref_unspecified_pdf_is_used_and_ieee_issue_is_preserved():
    doi = '10.1109/access.2022.3177744'
    rows = _crossref_pdf_links(doi, {
        'link': [{'URL': 'http://xplorestaging.ieee.org/ielx7/6287639/9668973/09781403.pdf',
                  'content-type': 'unspecified'}],
        'resource': {'primary': {'URL': 'https://ieeexplore.ieee.org/document/9781403/'}},
    })
    assert rows[0][0] == 'https://ieeexplore.ieee.org/ielx7/6287639/9668973/09781403.pdf'
    assert rows[1][0].endswith('arnumber=9781403')
    mdpi = _crossref_pdf_links('10.3390/en17133262', {'link': [
        {'URL': 'https://www.mdpi.com/1996-1073/17/13/3262/pdf', 'content-type': 'unspecified'},
        {'URL': 'https://example.org/abstract', 'content-type': 'unspecified'},
    ]})
    assert len(mdpi) == 1 and mdpi[0][0].endswith('/3262/pdf')


def test_ieee_viewer_resolves_same_article_without_api_or_credentials():
    doi = '10.1109/access.2022.3177744'
    seen = []

    def handler(request):
        seen.append(request)
        assert 'api_key' not in str(request.url) and 'saved-secret' not in str(request.url)
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi, 'title': ['Paper'],
                'resource': {'primary': {'URL': 'https://ieeexplore.ieee.org/document/9781403/'}}}})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi, 'locations': []})
        assert request.url.host == 'ieeexplore.ieee.org'
        if request.url.path == '/stamp/stamp.jsp':
            return httpx.Response(200, headers={'content-type': 'text/html'}, content=b'''
                <iframe src="/ielx7/6287639/9668973/09781403.pdf?arnumber=9781403"></iframe>''')
        assert request.url.path.endswith('/09781403.pdf')
        return httpx.Response(200, content=pdf())

    settings = Settings(None, None, None, ieee_api_key='saved-secret', ieee_api_enabled=False)
    _meta, content, source, _url, _warnings = discover_pdf(doi, settings,
        transport=httpx.MockTransport(handler))
    assert content and source == 'ieee_viewer_pdf'
    assert all(r.url.host != 'ieeexploreapi.ieee.org' for r in seen)


def test_viewer_rejects_other_article_external_and_private_iframes():
    request = httpx.Request('GET', 'https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=9781403')
    response = httpx.Response(200, request=request, content=b'''
        <iframe src="/ielx7/999.pdf"></iframe>
        <iframe src="https://other.example/09781403.pdf"></iframe>
        <iframe src="https://127.0.0.1/09781403.pdf"></iframe>''')
    assert _embedded_ieee_pdf(response) == []


def test_acs_challenge_is_explicit_not_claimed_as_paid_access_or_pdf():
    doi = '10.1021/acsenergylett.4c01233'

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi, 'title': ['Paper'],
                'link': [{'URL': 'https://pubs.acs.org/doi/pdf/' + doi, 'content-type': 'application/pdf'}]}})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi, 'locations': []})
        return httpx.Response(403, headers={'content-type': 'text/html'},
                              text='<title>Just a moment...</title>')

    _meta, content, _source, _url, warnings = discover_pdf(doi, Settings(None, None, None),
        transport=httpx.MockTransport(handler))
    assert content is None
    assert 'browser_verification_required:pubs.acs.org' in warnings


def test_openalex_oa_cache_keeps_key_off_redirects_and_provenance():
    doi = '10.3390/en18236107'
    archive = 'https://content.openalex.org/works/W12345.pdf'
    secret = 'private-openalex-key'

    def handler(request):
        host = request.url.host
        if host == 'api.crossref.org':
            assert secret not in str(request.url)
            return httpx.Response(200, json={'message': {'DOI': doi, 'title': ['Article']}})
        if host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi,
                'id': 'https://openalex.org/W12345', 'locations': [],
                'open_access': {'is_oa': True}, 'has_content': {'pdf': True},
                'content_urls': {'pdf': archive}})
        if host == 'content.openalex.org':
            assert request.url.params['api_key'] == secret
            return httpx.Response(302, headers={'location': 'https://assets.example.org/paper.pdf?signature=transient'})
        assert host == 'assets.example.org' and secret not in str(request.url)
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=title_pdf(doi))

    _meta, content, source, url, warnings = discover_pdf(doi,
        Settings(None, None, None, openalex_api_key=secret), transport=httpx.MockTransport(handler))
    assert content and source == 'openalex_cached_pdf'
    assert url == archive and 'signature' not in url and secret not in repr(warnings)


@pytest.mark.parametrize('is_oa,content_url', [
    (False, 'https://content.openalex.org/works/W12345.pdf'),
    (True, 'https://other.example/works/W12345.pdf'),
    (True, 'https://content.openalex.org/works/W99999.pdf'),
])
def test_unverified_or_closed_content_metadata_cannot_receive_openalex_key(is_oa, content_url):
    doi = '10.3390/example'

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi}})
        assert request.url.host == 'api.openalex.org'
        return httpx.Response(200, json={'doi': 'https://doi.org/' + doi,
            'id': 'https://openalex.org/W12345', 'locations': [],
            'open_access': {'is_oa': is_oa}, 'has_content': {'pdf': True},
            'content_urls': {'pdf': content_url}})

    _meta, content, _source, _url, _warnings = discover_pdf(doi,
        Settings(None, None, None, openalex_api_key='secret'), transport=httpx.MockTransport(handler))
    assert content is None


def test_mdpi_http200_akamai_page_is_not_a_pdf():
    doi = '10.3390/example'

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi,
                'link': [{'URL': 'https://www.mdpi.com/article/pdf', 'content-type': 'unspecified'}]}})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi, 'locations': []})
        return httpx.Response(200, headers={'content-type': 'text/html'}, text='''
            <iframe src="/akamai/interstitial.html"></iframe><script src="/_sec/verify"></script>''')

    _meta, content, _source, _url, warnings = discover_pdf(doi, Settings(None, None, None),
        transport=httpx.MockTransport(handler))
    assert content is None and 'browser_verification_required:www.mdpi.com' in warnings
