"""Public PDF discovery for additional publishers; restricted access stays explicit."""

from __future__ import annotations

import re
from io import BytesIO
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit

import httpx
from lxml import html
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from paperflow.qa.pdf import validate_pdf_bytes
from paperflow.sources.ieee import describe_ieee_error


def _public_url(url: str) -> bool:
    import ipaddress

    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        return ipaddress.ip_address(parsed.hostname).is_global
    except ValueError:
        return "." in parsed.hostname


def _crossref_pdf_links(doi, message):
    """Use DOI-matched publisher metadata, including PDF links typed unspecified."""
    result = []
    for link in message.get("link", []):
        url = link.get("URL", "")
        parsed = urlsplit(url)
        is_pdf_path = parsed.path.lower().endswith('.pdf') or re.search(r'/pdf(?:/|$)', parsed.path.lower())
        if link.get("content-type") != "application/pdf" and not is_pdf_path:
            continue
        if parsed.scheme == "http":
            parsed = parsed._replace(scheme="https")
        # Crossref can expose IEEE's staging host; preserve its actual issue/path
        # while using the official production host, not a guessed issue number.
        if doi.startswith('10.1109/') and parsed.hostname == 'xplorestaging.ieee.org' and parsed.path.startswith('/ielx7/'):
            parsed = parsed._replace(netloc='ieeexplore.ieee.org')
        result.append((urlunsplit(parsed), 'crossref_pdf'))
    primary = message.get('resource', {}).get('primary', {}).get('URL', '')
    parsed = urlsplit(primary)
    if doi.startswith('10.1109/') and parsed.hostname == 'ieeexplore.ieee.org':
        match = re.search(r'/document/(\d+)', parsed.path)
        if match:
            result.append(('https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=' + match[1], 'ieee_pdf_viewer'))
    return result


def _mdpi_resource_pdf_links(doi, message):
    """Verified Energies resource layout; require matching DOI and bibliographic fields.

    These are public publisher files, not a challenge-solving transport. Other
    journal layouts remain on existing routes until separately verified.
    """
    if str(message.get('DOI', '')).lower() != doi:
        return []
    if message.get('container-title') != ['Energies']:
        return []
    volume, issue = str(message.get('volume', '')), str(message.get('issue', ''))
    article = str(message.get('article-number') or message.get('page') or '')
    if not all(re.fullmatch(r'[1-9]\d*', value) for value in (volume, issue, article)):
        return []
    if doi != f'10.3390/en{volume}{int(issue):02d}{article}':
        return []
    primary = urlsplit(message.get('resource', {}).get('primary', {}).get('URL', ''))
    if (primary.hostname not in {'www.mdpi.com', 'mdpi.com'}
            or primary.path.rstrip('/') != f'/1996-1073/{volume}/{issue}/{article}'):
        return []
    name = f'energies-{int(volume):02d}-{int(article):05d}'
    return [(f'https://mdpi-res.com/d_attachment/energies/{name}/article_deploy/{name}.pdf',
             'mdpi_resource_pdf')]


def _mdpi_pdf_identity(content, doi):
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        text = '\n'.join(page.extract_text() or '' for page in reader.pages[:2])
    except (PdfReadError, PdfStreamError, EOFError, OSError, ValueError, NotImplementedError):
        # A malformed/unextractable candidate is not evidence of identity.
        return False
    pattern = r'\s*'.join(re.escape(char) for char in doi)
    return bool(re.search(pattern + r'(?![a-z0-9./_-])', text, re.IGNORECASE))


def _repository_pdf_links(response, doi, title):
    """Read ordinary citation metadata on an OA repository's article page."""
    if _access_warning(response).startswith('browser_verification_required:'):
        return []
    try:
        tree = html.fromstring(response.content)
    except (ValueError, TypeError):
        return []
    identifiers = tree.xpath('//meta[@name="citation_doi"]/@content')
    titles = tree.xpath('//meta[@name="citation_title"]/@content')
    normalized = re.sub(r'\W', '', title).casefold()
    matched = any(value.strip().lower().removeprefix('https://doi.org/') == doi for value in identifiers)
    if not matched and not (len(normalized) >= 20 and any(
            re.sub(r'\W', '', value).casefold() == normalized for value in titles)):
        return []
    return [(urljoin(str(response.url), url), 'oa_repository_metadata_pdf')
            for url in tree.xpath('//meta[@name="citation_pdf_url"]/@content')
            if _public_url(urljoin(str(response.url), url))][:2]


def _pdf_title_identity(content, title):
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        text = '\n'.join(page.extract_text() or '' for page in reader.pages[:2])
    except (PdfReadError, PdfStreamError, EOFError, OSError, ValueError, NotImplementedError):
        return False
    normalized = re.sub(r'\W', '', title).casefold()
    return len(normalized) >= 20 and normalized in re.sub(r'\W', '', text).casefold()


def _embedded_ieee_pdf(response):
    """Read the PDF iframe in IEEE's ordinary viewer; never process challenges."""
    parsed = urlsplit(str(response.url))
    if parsed.hostname != 'ieeexplore.ieee.org' or parsed.path != '/stamp/stamp.jsp':
        return []
    number = parse_qs(parsed.query).get('arnumber', [''])[0]
    if not number.isdigit():
        return []
    try:
        tree = html.fromstring(response.content)
    except (ValueError, TypeError):
        return []
    urls = tree.xpath('//iframe/@src|//embed/@src|//object/@data')
    result = []
    for href in urls:
        target = urljoin(str(response.url), href)
        parts = urlsplit(target)
        match = re.search(r'/(\d+)\.pdf$', parts.path, flags=re.IGNORECASE)
        if parts.hostname == parsed.hostname and match and int(match[1]) == int(number) and _public_url(target):
            result.append((target, 'ieee_viewer_pdf'))
    return result


def _access_warning(response):
    host = response.url.host
    if host == 'content.openalex.org' and response.status_code in {401, 402, 403, 429}:
        return 'openalex_content_http_' + str(response.status_code)
    if 'html' in response.headers.get('content-type', '').lower():
        text = response.text[:12000].lower()
        if any(marker in text for marker in ('just a moment', 'verify you are human', 'captcha',
                                             'cf-chl-', '/akamai/interstitial', '/_sec/verify', 'bm-verify=')):
            return 'browser_verification_required:' + host
    if response.status_code in {401, 403, 429}:
        return 'publisher_http_' + str(response.status_code) + ':' + host
    return 'public_pdf_unavailable_or_restricted'


def _cached_pdf_response(client, url, key):
    """Authenticate only to OpenAlex; redirect downloads never receive its key."""
    response = client.get(url, params={'api_key': key}, follow_redirects=False)
    for _ in range(5):
        if response.status_code not in {301, 302, 303, 307, 308}:
            break
        target = urljoin(str(response.url), response.headers.get('location', ''))
        if not _public_url(target) or 'api_key' in parse_qs(urlsplit(target).query):
            raise ValueError('Unsafe OpenAlex content redirect')
        response = client.get(target, follow_redirects=False)
    response.raise_for_status()
    return response


def discover_pdf(doi, settings, *, transport=None, explicit_url=None):
    metadata = {"doi": doi, "title": doi}
    candidates, warnings = [], []
    cached_pdf = None
    repository_pages = []
    with httpx.Client(
        timeout=settings.http_timeout,
        follow_redirects=True,
        transport=transport,
        headers={"User-Agent": "PaperFlow/0.2 (academic fulltext acquisition)"},
    ) as client:

        def get(url, **kwargs):
            response = client.get(url, **kwargs)
            response.raise_for_status()
            return response

        def optional(url, **kwargs):
            try:
                return get(url, **kwargs)
            except httpx.HTTPStatusError as exc:
                if exc.request.url.host == "ieeexploreapi.ieee.org":
                    warnings.append("ieee_api_" + describe_ieee_error(exc.response)["api_error_code"])
                warnings.append("metadata_or_public_endpoint_unavailable")
                return None
            except httpx.HTTPError:
                warnings.append("metadata_or_public_endpoint_unavailable")
                return None

        if doi.startswith("10.48550/arxiv."):
            identifier = doi.split("arxiv.", 1)[1]
            if not re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", identifier):
                raise ValueError("Unsupported arXiv identifier format.")
            candidates.append(("https://arxiv.org/pdf/" + identifier, "arxiv_pdf"))
        else:
            response = optional(
                "https://api.crossref.org/works/" + quote(doi, safe=""),
                params={"mailto": settings.crossref_mailto} if settings.crossref_mailto else {},
            )
            if response is not None:
                message = response.json().get("message", {})
                if str(message.get("DOI", "")).lower() != doi:
                    raise ValueError(
                        "Crossref returned a different DOI; refusing metadata mismatch."
                    )
                metadata.update(
                    title=(message.get("title") or [doi])[0],
                    journal=(message.get("container-title") or [""])[0],
                    year=((message.get("published") or {}).get("date-parts") or [[None]])[0][0],
                    authors=message.get("author", []),
                    source="crossref",
                )
                if message.get("abstract"):
                    metadata["abstract"] = " ".join(html.fromstring(message["abstract"]).text_content().split())
                candidates.extend(_crossref_pdf_links(doi, message))
                candidates.extend(_mdpi_resource_pdf_links(doi, message))
                if doi.startswith('10.1103/'):
                    # APS's public OA fulltext endpoint; no API key or paid entitlement assumed.
                    candidates.insert(0, ('https://harvest.aps.org/v2/journals/articles/' + doi + '/fulltext',
                                          'aps_harvest_pdf'))
            params = {"api_key": settings.openalex_api_key} if settings.openalex_api_key else {}
            response = optional(
                "https://api.openalex.org/works/https://doi.org/" + doi, params=params
            )
            if response is not None:
                work = response.json()
                if str(work.get("doi", "")).lower() == "https://doi.org/" + doi:
                    if metadata['title'] == doi and isinstance(work.get('title'), str):
                        metadata['title'] = work['title']
                    for location in work.get("locations", []):
                        if location.get("is_oa") and location.get("pdf_url"):
                            candidates.append((location["pdf_url"], "openalex_oa_pdf"))
                        elif (location.get('is_oa') and (location.get('source') or {}).get('type') == 'repository'
                              and _public_url(location.get('landing_page_url') or '')):
                            repository_pages.append(location['landing_page_url'])
                    # content_urls are OpenAlex's own archive, unlike locations'
                    # original publisher URLs. Match work ID and OA before auth.
                    work_id = str(work.get('id', '')).rsplit('/', 1)[-1]
                    canonical = 'https://content.openalex.org/works/' + work_id + '.pdf'
                    if (settings.openalex_api_key and re.fullmatch(r'W\d+', work_id)
                            and (work.get('open_access') or {}).get('is_oa') is True
                            and (work.get('has_content') or {}).get('pdf') is True
                            and (work.get('content_urls') or {}).get('pdf') == canonical):
                        cached_pdf = (canonical, 'openalex_cached_pdf')
            if settings.unpaywall_email:
                response = optional(
                    "https://api.unpaywall.org/v2/" + doi,
                    params={"email": settings.unpaywall_email},
                )
                if response is not None:
                    work = response.json()
                    if str(work.get("doi", "")).lower() == doi:
                        candidates.extend(
                            (loc["url_for_pdf"], "unpaywall_oa_pdf")
                            for loc in work.get("oa_locations", [])
                            if loc.get("url_for_pdf")
                        )
        if doi.startswith(("10.1007/", "10.1186/")):
            candidates.insert(
                0, ("https://link.springer.com/content/pdf/" + doi + ".pdf", "springer_public_pdf")
            )
        if doi.startswith("10.1109/") and settings.ieee_api_key and settings.ieee_api_enabled:
            response = optional(
                "https://ieeexploreapi.ieee.org/api/v1/search/articles",
                params={"doi": doi, "apikey": settings.ieee_api_key, "format": "json"},
            )
            if response is not None:
                for article in response.json().get("articles", []):
                    if str(article.get("doi", "")).lower() != doi:
                        continue
                    if metadata["title"] == doi and article.get("title"):
                        metadata["title"] = article["title"]
                    metadata["publisher_access_type"] = article.get("accessType", "unknown")
                    metadata["ieee_article_number"] = article.get("article_number")
                    # Locked describes publication access, not the current institution's rights.
                    # Try the official PDF in this network context; HTML/login pages stay rejected.
                    if article.get("pdf_url"):
                        source = "ieee_oa_pdf" if article.get("accessType") in {
                            "Open Access", "Ephemera"
                        } else "ieee_institution_pdf"
                        candidates.append((article["pdf_url"], source))
        # CVF's official proceedings are open; DOI matching uses Crossref's actual title.
        conference = re.search(r"/(cvpr|iccv|wacv)\.(\d{4})\.", doi)
        if conference and metadata["title"] != doi:
            event, year = conference.groups()
            if int(year) >= 2013:
                response = optional(f"https://openaccess.thecvf.com/{event.upper()}{year}?day=all")
                if response is not None:
                    tree = html.fromstring(response.content)
                    expected = re.sub(r"\W", "", metadata["title"]).casefold()
                    for link in tree.xpath('//dt[@class="ptitle"]/a'):
                        if re.sub(r"\W", "", link.text_content()).casefold() == expected:
                            page = optional(urljoin(str(response.url), link.get("href")))
                            if page is not None:
                                for href in html.fromstring(page.content).xpath("//a/@href"):
                                    if href.lower().endswith(".pdf") and "/papers/" in href:
                                        candidates.append(
                                            (urljoin(str(page.url), href), "cvf_open_pdf")
                                        )
        if explicit_url:
            candidates.insert(0, (explicit_url, "user_authorized_pdf_url"))
        for landing in list(dict.fromkeys(repository_pages))[:3]:
            candidates.append((landing, 'oa_repository_page'))
        if cached_pdf:
            candidates.append(cached_pdf)
        seen = set()
        for url, source in candidates:
            if url in seen or not _public_url(url):
                continue
            seen.add(url)
            try:
                response = (_cached_pdf_response(client, url, settings.openalex_api_key)
                            if source == 'openalex_cached_pdf' else get(url))
                if not _public_url(str(response.url)):
                    continue
                if source == 'oa_repository_page':
                    candidates.extend(_repository_pdf_links(response, doi, metadata['title']))
                    continue
                validation = validate_pdf_bytes(response.content)
                if validation.signature_ok and validation.parseable and validation.actual_pages:
                    if source == 'mdpi_resource_pdf' and not _mdpi_pdf_identity(response.content, doi):
                        warnings.append('mdpi_resource_pdf_doi_mismatch_or_unreadable')
                        continue
                    if (source in {'oa_repository_metadata_pdf', 'openalex_oa_pdf',
                                   'openalex_cached_pdf', 'aps_harvest_pdf'}
                            and not (_mdpi_pdf_identity(response.content, doi)
                                     or _pdf_title_identity(response.content, metadata['title']))):
                        warnings.append('oa_pdf_identity_unverified:' + source)
                        continue
                    # The authenticated URL and any signed redirect are transient.
                    provenance_url = url if source == 'openalex_cached_pdf' else str(response.url)
                    return metadata, response.content, source, provenance_url, warnings
                warning = _access_warning(response)
                if warning.startswith('browser_verification_required:'):
                    warnings.append(warning)
                    continue
                candidates.extend(_embedded_ieee_pdf(response))
                warnings.append("candidate_not_a_parseable_pdf")
            except httpx.HTTPStatusError as exc:
                warnings.append(_access_warning(exc.response))
            except httpx.HTTPError:
                warnings.append("public_pdf_unavailable_or_restricted")
            except ValueError:
                warnings.append('unsafe_or_invalid_pdf_redirect')
    return metadata, None, None, None, sorted(set(warnings))
