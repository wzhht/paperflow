import httpx
import pytest

from paperflow.config import Settings
from paperflow.models import Route
from paperflow.routing import route_doi
from paperflow.sources.native import native_candidates


def test_copernicus_doi_reaches_official_xml_and_is_not_unsupported():
    doi = '10.5194/gmd-18-1119-2025'
    assert route_doi(doi).route == Route.PUBLIC_PDF

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi, 'resource': {'primary': {
                'URL': 'https://gmd.copernicus.org/articles/18/1119/2025/'}}}})
        assert request.url.host == 'gmd.copernicus.org'
        assert request.url.path == '/articles/18/1119/2025/gmd-18-1119-2025.xml'
        return httpx.Response(200, content=b'<article/>')

    generator = native_candidates(doi, Settings(None, None, None), transport=httpx.MockTransport(handler))
    assert next(generator)[2] == 'copernicus_jats'
    generator.close()


@pytest.mark.parametrize('oa,record_doi,expected', [
    ('Y', '10.1126/sciadv.example', True),
    ('N', '10.1126/sciadv.example', False),
    ('Y', '10.1126/sciadv.other', False),
])
def test_science_pmc_requires_matching_doi_and_explicit_oa(oa, record_doi, expected):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith('/search'):
            return httpx.Response(200, json={'resultList': {'result': [
                {'doi': record_doi, 'isOpenAccess': oa, 'pmcid': 'PMC12345'}]}})
        if request.url.path.endswith('/fullTextXML'):
            return httpx.Response(200, content=b'<article/>')
        return httpx.Response(404)

    rows = list(native_candidates('10.1126/sciadv.example', Settings(None, None, None),
                                   transport=httpx.MockTransport(handler)))
    assert bool(rows) == expected
    assert any(r.url.path.endswith('/fullTextXML') for r in requests) == expected
