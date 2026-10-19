"""Small native-source adapters. Official APIs and authorized public documents only."""

from __future__ import annotations

import re
from urllib.parse import quote, urljoin, urlsplit

import httpx
from lxml import html

from paperflow.sources.public_pdf import _access_warning, _public_url


def fetch_wiley_pdf(doi, settings, *, transport=None):
    if not settings.wiley_api_key:
        return None
    # Never forward the TDM token to a redirect target or another publisher.
    with httpx.Client(timeout=settings.http_timeout, transport=transport,
                      follow_redirects=False) as client:
        response = client.get(
            "https://api.wiley.com/onlinelibrary/tdm/v1/articles/" + quote(doi, safe=""),
            headers={"Wiley-TDM-Client-Token": settings.wiley_api_key,
                     "User-Agent": "PaperFlow/0.3 (authorized TDM)", "Accept": "application/pdf"},
        )
        for _ in range(4):
            if response.status_code not in {301, 302, 303, 307, 308}:
                break
            target = urljoin(str(response.url), response.headers.get("location", ""))
            if not _public_url(target):
                raise ValueError("Wiley TDM returned an unsafe redirect")
            response = client.get(target, headers={"Accept": "application/pdf"})
        if response.status_code != 200:
            raise RuntimeError(f"Wiley TDM HTTP {response.status_code}")
        if not response.content.startswith(b"%PDF-"):
            raise ValueError("Wiley TDM returned non-PDF content")
        return response.content


def native_candidates(doi, settings, *, transport=None, diagnostics=None):
    """Yield (bytes, format, source, public_url); validation belongs to the caller.

    Publisher API errors never imply full text and never expose provider bodies.
    No browser, subscription credentials or Mdtero deployment is used.
    """
    with httpx.Client(timeout=settings.http_timeout, transport=transport,
                      follow_redirects=False, headers={"User-Agent": "PaperFlow/0.3"}) as client:

        def get(url, **kwargs):
            if not _public_url(url):
                return None
            try:
                for attempt in range(2):
                    try:
                        response = client.get(url, **kwargs)
                        break
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        if attempt:
                            raise
                # Follow ordinary public redirects, with no credentials on these requests.
                for _ in range(4):
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    target = urljoin(str(response.url), response.headers.get("location", ""))
                    if not _public_url(target):
                        return None
                    response = client.get(target)
                if diagnostics is not None:
                    diagnostics.append({"host": urlsplit(url).hostname,
                                        "http_status": response.status_code})
                if _access_warning(response).startswith('browser_verification_required:'):
                    if diagnostics is not None:
                        diagnostics.append({'host': urlsplit(url).hostname,
                                            'reason': 'browser_verification_required'})
                    return None
                return response if response.status_code == 200 else None
            except httpx.HTTPError as exc:
                if diagnostics is not None:
                    diagnostics.append({"host": urlsplit(url).hostname,
                                        "error_type": type(exc).__name__})
                return None

        if doi.startswith("10.48550/arxiv."):
            identifier = doi.split("arxiv.", 1)[1]
            response = get("https://arxiv.org/html/" + identifier)
            if response is not None:
                yield response.content, "html", "arxiv_native_html", str(response.url)
            return

        if doi.startswith("10.1371/"):
            slug = doi.split("/journal.", 1)[-1].split(".")[0]
            journal = {"pone": "plosone", "pbio": "plosbiology", "pcbi": "ploscompbiol",
                       "pgen": "plosgenetics", "pmed": "plosmedicine", "pntd": "plosntds",
                       "ppat": "plospathogens", "pclm": "climate", "pwat": "water"}.get(slug)
            if journal:
                url = f"https://journals.plos.org/{journal}/article/file"
                response = get(url, params={"id": doi, "type": "manuscript"})
                if response is not None:
                    yield response.content, "xml", "plos_jats", str(response.url)
        if doi.startswith("10.7554/elife."):
            identifier = doi.split("elife.", 1)[1]
            if re.fullmatch(r"\d+", identifier):
                response = get(f"https://elifesciences.org/articles/{identifier}.xml")
                if response is not None:
                    yield response.content, "xml", "elife_jats", str(response.url)
        if doi.startswith("10.3389/"):
            code = doi.split("/", 1)[1].split(".", 1)[0]
            slug = {"fenrg": "energy-research", "fpubh": "public-health",
                    "fther": "thermal-engineering"}.get(code)
            base = f"https://www.frontiersin.org/journals/{slug}/articles/" if slug else "https://www.frontiersin.org/articles/"
            response = get(base + doi + "/xml")
            if response is not None:
                yield response.content, "xml", "frontiers_jats", str(response.url)
        if doi.startswith("10.1101/"):
            for server in ("biorxiv", "medrxiv"):
                response = get(f"https://api.biorxiv.org/details/{server}/{doi}")
                if response is None:
                    continue
                try:
                    entries = [x for x in response.json().get("collection", [])
                               if str(x.get("doi", "")).lower() == doi
                               and x.get("server", server).lower() == server]
                    entries.sort(key=lambda x: int(x.get("version", 0)), reverse=True)
                    if entries:
                        url = str(entries[0].get("jatsxml", "")).replace("http://", "https://", 1)
                        host = urlsplit(url).hostname or ""
                        if host == f"www.{server}.org" or host == f"{server}.org":
                            full = get(url)
                            if full is not None:
                                yield full.content, "xml", server + "_jats", str(full.url)
                except (ValueError, TypeError, AttributeError):
                    continue

        # Metadata API results are just locators, never full text.
        response = get("https://api.crossref.org/works/" + quote(doi, safe=""))
        work = {}
        if response is not None:
            try:
                candidate = response.json().get("message", {})
                if str(candidate.get("DOI", "")).lower() == doi:
                    work = candidate
            except (ValueError, AttributeError):
                pass
        for link in work.get("link", []):
            url = link.get("URL", "")
            kind = link.get("content-type", "")
            if kind in {"application/xml", "text/xml", "application/jats+xml", "application/epub+zip"}:
                document = get(url)
                if document is not None:
                    yield document.content, "epub" if "epub" in kind else "xml", "crossref_native", str(document.url)

        landing = (work.get("resource", {}).get("primary", {}).get("URL") or work.get("URL") or "")
        if landing.startswith("http://"):
            landing = "https://" + landing[len("http://"):]
        host = urlsplit(landing).hostname or ""
        urls = []
        if doi.startswith('10.5194/') and host.endswith('.copernicus.org'):
            # Only the DOI-matched Crossref landing page supplies the base path.
            match = re.fullmatch(r'10\.5194/([a-z]+)-(\d+)-(\d+)-(\d{4})', doi)
            if match:
                journal, volume, page, year = match.groups()
                expected = f'/articles/{volume}/{page}/{year}/'
                base = landing.rsplit('/', 1)[0] + '/' if not landing.endswith('/') else landing
                if urlsplit(base).path == expected and host == journal + '.copernicus.org':
                    urls.append((base + doi.split('/')[1] + '.xml', 'xml', 'copernicus_jats'))
        if doi.startswith("10.3389/") and (host == "frontiersin.org" or host.endswith(".frontiersin.org")):
            urls.append((re.sub(r"/(full|abstract|pdf|xml)$", "", landing).rstrip("/") + "/xml", "xml", "frontiers_jats"))
        if doi.startswith("10.3390/") and host in {"mdpi.com", "www.mdpi.com"}:
            urls.append((re.sub(r"/(htm|pdf)$", "", landing).rstrip("/") + "/xml", "xml", "mdpi_jats"))
        if landing and host not in {"doi.org", "dx.doi.org"}:
            urls.append((landing, "html", "publisher_native_html"))
        for url, kind, source in urls:
            document = get(url)
            if document is not None:
                if "captcha" in document.text[:2000].lower() or "verify you are human" in document.text[:5000].lower():
                    continue
                yield document.content, kind, source, str(document.url)
                if kind == "html":
                    try:
                        tree = html.fromstring(document.content)
                        identifiers = tree.xpath('//meta[@name="citation_doi"]/@content')
                        if doi in [x.strip().lower() for x in identifiers]:
                            for href in tree.xpath('//meta[@name="citation_pdf_url"]/@content'):
                                full = get(urljoin(str(document.url), href))
                                if full is not None and full.content.startswith(b"%PDF-"):
                                    yield full.content, "pdf", "publisher_metadata_pdf", str(full.url)
                    except (ValueError, TypeError):
                        pass

        # HAL is a legitimate archive locator, independent of publisher subscriptions.
        response = get("https://api.archives-ouvertes.fr/search/",
                       params={"q": f'doiId_s:"{doi}"', "fl": "doiId_s,fileMain_s", "wt": "json"})
        if response is not None:
            try:
                for record in response.json().get("response", {}).get("docs", []):
                    identifiers = record.get("doiId_s", [])
                    identifiers = [identifiers] if isinstance(identifiers, str) else identifiers
                    if doi not in [x.lower() for x in identifiers]:
                        continue
                    full = get(record.get("fileMain_s", ""))
                    if full is not None and full.content.startswith(b"%PDF-"):
                        yield full.content, "pdf", "hal_archive_pdf", str(full.url)
            except (ValueError, TypeError, AttributeError):
                pass

        # OA biomedical fallback; both DOI and OA flag must agree before requesting XML.
        if doi.startswith(("10.7554/", "10.1371/", "10.3389/", "10.1101/", "10.3390/",
                           "10.1126/", "10.1021/", "10.1039/", "10.1073/")):
            response = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                           params={"query": 'DOI:"' + doi + '"', "format": "json", "resultType": "core"})
            if response is not None:
                try:
                    entries = response.json().get("resultList", {}).get("result", [])
                    for entry in entries:
                        pmcid = entry.get("pmcid", "")
                        if (str(entry.get("doi", "")).lower() == doi and entry.get("isOpenAccess") == "Y"
                                and re.fullmatch(r"PMC\d+", pmcid)):
                            full = get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML")
                            if full is not None:
                                yield full.content, "xml", "europe_pmc_jats", str(full.url)
                except (ValueError, TypeError, AttributeError):
                    pass
