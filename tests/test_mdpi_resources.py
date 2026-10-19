from types import SimpleNamespace

import httpx
import pytest
from test_publisher_pdf_links import pdf

from paperflow.config import Settings
from paperflow.sources import public_pdf

DOI = '10.3390/en17133262'


def metadata():
    return {'DOI': DOI, 'container-title': ['Energies'], 'volume': '17', 'issue': '13',
            'page': '3262', 'resource': {'primary': {
                'URL': 'https://www.mdpi.com/1996-1073/17/13/3262'}}}


@pytest.mark.parametrize('field,value', [
    ('DOI', '10.3390/other'), ('volume', '18'), ('issue', '12'),
    ('page', '3263'), ('page', '3262-3280'), ('container-title', ['Other']),
    ('resource', {'primary': {'URL': 'https://example.org/1996-1073/17/13/3262'}}),
])
def test_resource_locator_rejects_inconsistent_metadata(field, value):
    work = metadata()
    work[field] = value
    assert public_pdf._mdpi_resource_pdf_links(DOI, work) == []


@pytest.mark.parametrize('identity', [DOI, DOI + '9', '10.3390/en18236107'])
def test_mdpi_resource_fallback_checks_document_identity(monkeypatch, identity):
    seen = []
    monkeypatch.setattr(public_pdf, 'PdfReader', lambda *a, **kw: SimpleNamespace(
        pages=[SimpleNamespace(extract_text=lambda: 'Abstract https://doi.org/' + identity + ';')]))

    def handler(request):
        seen.append(request)
        if request.url.host == 'api.crossref.org':
            work = metadata()
            work['link'] = [{'URL': work['resource']['primary']['URL'] + '/pdf',
                             'content-type': 'application/pdf'}]
            return httpx.Response(200, json={'message': work})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(404)
        assert not request.url.query and 'authorization' not in request.headers
        if request.url.host == 'www.mdpi.com':
            return httpx.Response(403, headers={'content-type': 'text/html'}, text='Access Denied')
        assert request.url.host == 'mdpi-res.com'
        assert request.url.path.endswith('/energies-17-03262.pdf')
        return httpx.Response(200, content=pdf())

    _meta, content, source, _url, warnings = public_pdf.discover_pdf(
        DOI, Settings(None, None, None), transport=httpx.MockTransport(handler))
    if identity == DOI:
        assert content and source == 'mdpi_resource_pdf'
    else:
        assert content is None
        assert 'mdpi_resource_pdf_doi_mismatch_or_unreadable' in warnings
    assert len([r for r in seen if r.url.host == 'mdpi-res.com']) == 1


def test_mdpi_resource_verification_html_is_never_a_pdf():
    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': metadata()})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(404)
        return httpx.Response(200, headers={'content-type': 'text/html'},
                              text='<iframe src="/akamai/interstitial.html"></iframe>')

    assert public_pdf.discover_pdf(DOI, Settings(None, None, None),
        transport=httpx.MockTransport(handler))[1] is None
