"""Public JMLR/PMLR/OpenReview paper links, without inventing DOI identifiers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import httpx
from lxml import html
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from paperflow.qa.pdf import PdfExpectation, validate_pdf_bytes
from paperflow.sources.public_pdf import _access_warning

HOSTS = {'jmlr.org', 'www.jmlr.org', 'proceedings.mlr.press',
         'openreview.net', 'api2.openreview.net', 'api.openreview.net'}


def _safe_url(url):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname in HOSTS
            and parsed.port in {None, 443} and not parsed.username and not parsed.password
            and not parsed.fragment and not re.search(r'%2f|%5c|\.\.', parsed.path, re.IGNORECASE))


def paper_link(value):
    """Accept an article page, not a journal listing, arbitrary URL or signed link."""
    parsed = urlsplit(value.strip())
    if not _safe_url(value.strip()):
        raise ValueError('Use an official HTTPS JMLR, PMLR or OpenReview paper-page URL.')
    if parsed.hostname in {'jmlr.org', 'www.jmlr.org'}:
        if parsed.query or not re.fullmatch(r'/papers/(?:v\d+|volume\d+)/[\w-]+\.html', parsed.path):
            raise ValueError('JMLR requires an individual /papers/v<volume>/<paper>.html page.')
        return 'jmlr', 'https://jmlr.org' + parsed.path
    if parsed.hostname == 'proceedings.mlr.press':
        if parsed.query or not re.fullmatch(r'/v\d+/[\w-]+\.html', parsed.path):
            raise ValueError('PMLR requires an individual /v<volume>/<paper>.html page.')
        return 'pmlr', 'https://proceedings.mlr.press' + parsed.path
    if parsed.hostname == 'openreview.net' and parsed.path in {'/forum', '/pdf'}:
        params = parse_qs(parsed.query)
        identifier = params.get('id', [''])[0]
        if set(params) == {'id'} and len(params['id']) == 1 and re.fullmatch(r'[A-Za-z0-9_-]{5,100}', identifier):
            return 'openreview', 'https://openreview.net/forum?' + urlencode({'id': identifier})
    raise ValueError('OpenReview requires a public /forum?id=<note-id> paper link.')


def _get(client, url, **kwargs):
    for _ in range(5):
        if not _safe_url(url):
            raise ValueError('The paper endpoint redirected outside the allowed official hosts.')
        response = client.get(url, **kwargs)
        kwargs = {}
        if response.status_code in {301, 302, 303, 307, 308}:
            url = urljoin(str(response.url), response.headers.get('location', ''))
            continue
        if _access_warning(response).startswith('browser_verification_required:'):
            raise ValueError('Publisher verification is required; no PDF was acquired.')
        if response.status_code not in {200, 404}:
            raise ValueError(f'Public paper endpoint HTTP {response.status_code}; no PDF was acquired.')
        return response
    raise ValueError('Too many paper endpoint redirects.')


def _page_metadata(response, platform):
    tree = html.fromstring(response.content)

    def values(key):
        return tree.xpath('//meta[@name=$key]/@content', key=key)

    def first(key):
        return next(iter(values(key)), None)

    title = first('citation_title')
    url = first('citation_pdf_url')
    if not title or not url:
        raise ValueError('The official page contains no unambiguous paper title/PDF metadata.')
    url = urljoin(str(response.url), url)
    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    source = urlsplit(str(response.url))
    target = urlsplit(url)
    if (not _safe_url(url) or target.query or not target.path.endswith('.pdf')
            or source.hostname.removeprefix('www.') != target.hostname.removeprefix('www.')):
        raise ValueError('The PDF metadata does not point to the same official platform.')
    # Both layouts repeat the article identifier immediately before .pdf.
    if Path(source.path).stem != Path(target.path).stem:
        raise ValueError('The PDF filename does not match the requested article identifier.')
    first_page, last_page = first('citation_firstpage'), first('citation_lastpage')
    expected = None
    if first_page and last_page and first_page.isdigit() and last_page.isdigit():
        count = int(last_page) - int(first_page) + 1
        if count > 0:
            expected = count
    return {'platform': platform, 'title': title, 'authors': values('citation_author'),
            'year': first('citation_publication_date'), 'doi': first('citation_doi'),
            'journal': first('citation_journal_title'),
            'venue': first('citation_conference_title'),
            'publication_type': 'journal-article' if platform == 'jmlr' else 'conference-paper',
            'expected_pages': expected, 'first_page': first_page, 'last_page': last_page,
            'pdf_url': url, 'publication_status': 'published'}


def _openreview_metadata(client, url):
    identifier = parse_qs(urlsplit(url).query)['id'][0]
    for api in ('https://api2.openreview.net', 'https://api.openreview.net'):
        response = _get(client, api + '/notes?' + urlencode({'id': identifier}))
        if response.status_code == 404:
            continue
        notes = response.json().get('notes', [])
        notes = [note for note in notes if note.get('id') == identifier]
        if not notes:
            continue
        if len(notes) != 1:
            raise ValueError('OpenReview returned ambiguous note identity.')
        note = notes[0]
        if ('everyone' not in note.get('readers', []) or note.get('ddate')
                or note.get('forum') != identifier):
            raise ValueError('Only public, non-deleted top-level paper notes can be acquired.')
        content = note.get('content', {})

        def value(key, content=content):
            result = content.get(key)
            return result.get('value') if isinstance(result, dict) else result

        if not isinstance(value('title'), str) or not value('pdf'):
            raise ValueError('OpenReview note has no paper title/PDF attachment.')
        venue = value('venue') or ''
        return {'platform': 'openreview', 'title': value('title'), 'authors': value('authors'),
                'abstract': value('abstract'), 'doi': value('doi'), 'venue': venue,
                'venue_id': value('venueid'), 'publication_type': 'openreview-paper',
                'publication_status': 'unconfirmed; inspect venue/decision before treating as accepted',
                'note_id': identifier, 'note_mdate': note.get('mdate'),
                'note_cdate': note.get('cdate'), 'pdf_attachment': value('pdf'),
                'pdf_url': api + '/pdf?' + urlencode({'id': identifier}), 'expected_pages': None}
    raise ValueError('No matching public OpenReview paper note was found.')


def fetch_platform_paper(url, *, output_root, timeout=30, transport=None):
    """Download and identify one public PDF; retain immutable, version-specific files.

    Acquisition is independent from MinerU. Missing completeness evidence is
    explicit; a parseable PDF alone is never reported as completeness verified.
    """
    platform, canonical = paper_link(url)
    with httpx.Client(timeout=timeout, transport=transport, follow_redirects=False,
                      headers={'User-Agent': 'PaperFlow/0.3 (public academic paper acquisition)'}) as client:
        if platform == 'openreview':
            meta = _openreview_metadata(client, canonical)
        else:
            response = _get(client, canonical)
            if response.status_code != 200:
                raise ValueError('The requested official paper page was not found.')
            meta = _page_metadata(response, platform)
        response = _get(client, meta['pdf_url'])
        validation = validate_pdf_bytes(response.content,
            PdfExpectation(None, None, meta['expected_pages'], None))
        if not (validation.signature_ok and validation.parseable and validation.actual_pages):
            raise ValueError('The public paper endpoint did not return a parseable PDF.')
        try:
            reader = PdfReader(BytesIO(response.content), strict=False)
            text = '\n'.join(p.extract_text() or '' for p in reader.pages[:2])
        except (PdfReadError, PdfStreamError, ValueError, OSError, NotImplementedError) as exc:
            raise ValueError('Could not verify the downloaded PDF title.') from exc
        normalize = lambda value: re.sub(r'[^\w]', '', value).casefold()
        if len(normalize(meta['title'])) < 12 or normalize(meta['title']) not in normalize(text):
            raise ValueError('The downloaded PDF title does not match the official paper record.')
        digest = hashlib.sha256(response.content).hexdigest()
        meta.update(source_url=canonical, source=platform + '_official_pdf', sha256=digest,
                    acquired_at=datetime.now(timezone.utc).isoformat(), identity_verified=True,
                    full_text_available=True, completeness_verified=validation.is_valid,
                    pdf_validation=asdict(validation))
        folder = Path(output_root) / (platform + '_' + hashlib.sha256(canonical.encode()).hexdigest()[:12]) / digest
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / 'paper.pdf'
        manifest = folder / 'acquisition.json'
        if pdf.exists() and hashlib.sha256(pdf.read_bytes()).hexdigest() != digest:
            raise ValueError('An existing version file differs from its recorded hash; not overwritten.')
        if not pdf.exists():
            pdf.write_bytes(response.content)
        if not manifest.exists():
            manifest.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        return pdf, meta
