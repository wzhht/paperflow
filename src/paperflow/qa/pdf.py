import re
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from lxml import etree
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

PdfValidationStatus = Literal[
    "valid",
    "candidate",
    "invalid_not_pdf",
    "invalid_parse_error",
    "invalid_page_count",
]


@dataclass(frozen=True)
class PdfExpectation:
    attachment_eid: str | None
    filename: str | None
    expected_pages: int | None
    expected_bytes: int | None
    first_page: int | None = None
    last_page: int | None = None


@dataclass(frozen=True)
class PdfValidationResult:
    status: PdfValidationStatus
    is_valid: bool

    signature_ok: bool
    parseable: bool

    actual_pages: int | None
    expected_pages: int | None
    pages_match_expected: bool | None

    actual_bytes: int
    expected_bytes: int | None
    byte_ratio_expected: float | None

    reason: str


def inspect_pdf_page_sequence(content, doi, expectation=None):
    """Additional positive proof from publisher pagination; never infer missing pages.

    Either every page carries a consistent 'page of total', or up to three
    recognizable front sheets precede the complete bibliographic page range.
    The requested DOI must be present on the first article page in both cases.
    """
    failed = {"verified": False}
    if not doi:
        return failed
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if not 2 <= len(reader.pages) <= 500:
            return failed
        texts = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, PdfStreamError, EOFError, OSError, ValueError, NotImplementedError):
        return failed
    compact_doi = re.sub(r"\s+", "", doi).casefold()

    def identity(text):
        return (compact_doi in re.sub(r"\s+", "", text).casefold()
                and bool(re.search(r"\babstract\b", text, re.IGNORECASE)))

    total = len(texts)
    first_counters = re.findall(r"(?<!\d)(\d+)\s+of\s+(\d+)(?!\d)",
                                texts[0][:900] + "\n" + texts[0][-900:], re.IGNORECASE)
    if (identity(texts[0]) and (expectation is None or expectation.expected_pages is None)
            and all(counter == ('1', str(total)) for counter in first_counters)
            and all((str(index), str(total)) in re.findall(r"(?<!\d)(\d+)\s+of\s+(\d+)(?!\d)",
                    text[:900] + "\n" + text[-900:], re.IGNORECASE)
                    for index, text in enumerate(texts[1:], 2))):
        return {"verified": True, "method": "publisher_page_of_total", "body_pages": total,
                "front_pages": 0, "doi_matched": True}
    if expectation is None or expectation.first_page is None or expectation.last_page is None:
        return failed
    first, last = expectation.first_page, expectation.last_page
    expected = last - first + 1
    front = total - expected
    if not (expected == expectation.expected_pages and 1 <= front <= 3):
        return failed
    markers = ("citation for published version", "document version", "to cite this article:")
    if not all(any(marker in text.lower() for marker in markers) for text in texts[:front]):
        return failed
    if not identity(texts[front]):
        return failed
    if not re.search(rf"\b{first}\s*[-–—]\s*{last}\b", texts[front]):
        return failed
    if not all((re.search(rf"(?m)^[^\n]*\b{number}\s*$", text[-900:])
                or re.search(rf"(?m)^\s*{number}\s+[A-Z][A-Z .,&'’–-]{{2,100}}\s*$", text[-900:]))
               for number, text in zip(range(first + 1, last + 1), texts[front + 1:])):
        return failed
    return {"verified": True, "method": "publisher_range_with_front_sheets", "front_pages": front,
            "body_pages": expected, "first_page": first, "last_page": last, "doi_matched": True}


def _safe_int(
    value: str | None,
) -> int | None:
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _child_text(
    node: etree._Element,
    local_name: str,
) -> str | None:
    values = node.xpath(f"./*[local-name()='{local_name}']/text()")

    if not values:
        return None

    value = str(values[0]).strip()

    return value or None


def extract_elsevier_pdf_expectation(
    xml_content: bytes | str,
) -> PdfExpectation:
    if isinstance(xml_content, str):
        xml_content = xml_content.encode("utf-8")

    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
    )

    root = etree.fromstring(
        xml_content,
        parser=parser,
    )

    pdf_nodes = root.xpath("//*[local-name()='web-pdf']")

    if not pdf_nodes:
        # Metadata-only API responses can still expose the article's page range.
        # A valid PDF signature alone must not allow a one-page publisher preview.
        core = root.xpath("//*[local-name()='coredata']")
        expected_pages = None
        if core:
            start = _safe_int(_child_text(core[0], "startingPage"))
            end = _safe_int(_child_text(core[0], "endingPage"))
            if start is not None and end is not None and end >= start:
                expected_pages = end - start + 1
        return PdfExpectation(
            attachment_eid=None,
            filename=None,
            expected_pages=expected_pages,
            expected_bytes=None,
        )

    selected = None

    for node in pdf_nodes:
        purpose = _child_text(
            node,
            "web-pdf-purpose",
        )

        if purpose is not None and purpose.upper() == "MAIN":
            selected = node
            break

    if selected is None:
        selected = pdf_nodes[0]

    return PdfExpectation(
        attachment_eid=_child_text(
            selected,
            "attachment-eid",
        ),
        filename=_child_text(
            selected,
            "filename",
        ),
        expected_pages=_safe_int(
            _child_text(
                selected,
                "web-pdf-page-count",
            )
        ),
        expected_bytes=_safe_int(
            _child_text(
                selected,
                "filesize",
            )
        ),
    )


def validate_pdf_bytes(
    pdf_content: bytes,
    expectation: PdfExpectation | None = None,
) -> PdfValidationResult:
    actual_bytes = len(pdf_content)

    if expectation is None:
        expectation = PdfExpectation(
            attachment_eid=None,
            filename=None,
            expected_pages=None,
            expected_bytes=None,
        )

    expected_pages = expectation.expected_pages

    expected_bytes = expectation.expected_bytes

    byte_ratio_expected = None

    if expected_bytes is not None and expected_bytes > 0:
        byte_ratio_expected = actual_bytes / expected_bytes

    signature_ok = pdf_content.startswith(b"%PDF-")

    if not signature_ok:
        return PdfValidationResult(
            status="invalid_not_pdf",
            is_valid=False,
            signature_ok=False,
            parseable=False,
            actual_pages=None,
            expected_pages=expected_pages,
            pages_match_expected=None,
            actual_bytes=actual_bytes,
            expected_bytes=expected_bytes,
            byte_ratio_expected=(byte_ratio_expected),
            reason=("Content does not begin with a PDF signature."),
        )

    try:
        reader = PdfReader(
            BytesIO(pdf_content),
            strict=False,
        )

        actual_pages = len(reader.pages)

    except (
        PdfReadError,
        PdfStreamError,
        EOFError,
        OSError,
        ValueError,
    ) as exc:
        return PdfValidationResult(
            status="invalid_parse_error",
            is_valid=False,
            signature_ok=True,
            parseable=False,
            actual_pages=None,
            expected_pages=expected_pages,
            pages_match_expected=None,
            actual_bytes=actual_bytes,
            expected_bytes=expected_bytes,
            byte_ratio_expected=(byte_ratio_expected),
            reason=str(exc),
        )

    if actual_pages <= 0:
        return PdfValidationResult(
            status="invalid_page_count",
            is_valid=False,
            signature_ok=True,
            parseable=True,
            actual_pages=actual_pages,
            expected_pages=expected_pages,
            pages_match_expected=None,
            actual_bytes=actual_bytes,
            expected_bytes=expected_bytes,
            byte_ratio_expected=(byte_ratio_expected),
            reason=("PDF contains no pages."),
        )

    if expected_pages is not None:
        pages_match_expected = actual_pages == expected_pages

        if not pages_match_expected:
            return PdfValidationResult(
                status="invalid_page_count",
                is_valid=False,
                signature_ok=True,
                parseable=True,
                actual_pages=actual_pages,
                expected_pages=expected_pages,
                pages_match_expected=False,
                actual_bytes=actual_bytes,
                expected_bytes=expected_bytes,
                byte_ratio_expected=(byte_ratio_expected),
                reason=("Downloaded PDF page count does not match source metadata."),
            )

        return PdfValidationResult(
            status="valid",
            is_valid=True,
            signature_ok=True,
            parseable=True,
            actual_pages=actual_pages,
            expected_pages=expected_pages,
            pages_match_expected=True,
            actual_bytes=actual_bytes,
            expected_bytes=expected_bytes,
            byte_ratio_expected=(byte_ratio_expected),
            reason=("PDF page count matches source metadata."),
        )

    return PdfValidationResult(
        status="candidate",
        is_valid=False,
        signature_ok=True,
        parseable=True,
        actual_pages=actual_pages,
        expected_pages=None,
        pages_match_expected=None,
        actual_bytes=actual_bytes,
        expected_bytes=expected_bytes,
        byte_ratio_expected=(byte_ratio_expected),
        reason=("PDF is parseable, but no expected page count was available for verification."),
    )
