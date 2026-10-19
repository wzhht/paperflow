import httpx
from test_academic_platforms import TITLE, title_pdf

from paperflow.config import Settings
from paperflow.sources.public_pdf import discover_pdf


def test_wrong_title_oa_candidate_is_rejected_and_next_candidate_is_used():
    doi = '10.1088/2515-7655/example'

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi, 'title': [TITLE]}})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi, 'locations': [
                {'is_oa': True, 'pdf_url': 'https://archive.example/unconfirmed.pdf'},
                {'is_oa': True, 'pdf_url': 'https://archive.example/published.pdf'}]})
        title = TITLE if request.url.path == '/published.pdf' else 'An older differently titled manuscript'
        return httpx.Response(200, content=title_pdf(title))

    _meta, content, _source, url, warnings = discover_pdf(doi, Settings(None, None, None),
        transport=httpx.MockTransport(handler))
    assert content and url.endswith('/published.pdf')
    assert 'oa_pdf_identity_unverified:openalex_oa_pdf' in warnings


def test_aps_official_fulltext_is_tried_before_public_archive_copies():
    doi = '10.1103/prxquantum.3.030101'

    def handler(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': doi, 'title': [TITLE]}})
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'doi': 'https://doi.org/' + doi, 'locations': []})
        assert request.url.host == 'harvest.aps.org'
        assert request.url.path == '/v2/journals/articles/' + doi + '/fulltext'
        assert 'authorization' not in request.headers and not request.url.query
        return httpx.Response(200, content=title_pdf(TITLE))

    assert discover_pdf(doi, Settings(None, None, None), transport=httpx.MockTransport(handler))[2] == 'aps_harvest_pdf'
