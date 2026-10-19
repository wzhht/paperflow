from types import SimpleNamespace

import pytest

from paperflow.qa import pdf
from paperflow.qa.pdf import PdfExpectation, inspect_pdf_page_sequence

DOI = '10.1080/example'


def reader(monkeypatch, pages):
    monkeypatch.setattr(pdf, 'PdfReader', lambda *a, **kw: SimpleNamespace(
        pages=[SimpleNamespace(extract_text=lambda text=text: text) for text in pages]))


def test_cover_sheets_require_identity_and_complete_continuous_published_pages(monkeypatch):
    pages = ['Citation for published version. Document version.', 'To cite this article:']
    pages += [f'ABSTRACT Research article {DOI} 388–391',
              'Research text\nJOURNAL 389', 'Research text\n390 A. AUTHOR ET AL.', 'References\nJOURNAL 391']
    reader(monkeypatch, pages)
    result = inspect_pdf_page_sequence(b'pdf', DOI, PdfExpectation(None, None, 4, None, 388, 391))
    assert result['verified'] and result['front_pages'] == 2 and result['body_pages'] == 4


@pytest.mark.parametrize('change', ['missing_middle', 'wrong_doi', 'unrecognized_cover'])
def test_incomplete_or_unidentified_pdf_cannot_pass_cover_adjustment(monkeypatch, change):
    pages = ['To cite this article:', f'ABSTRACT {DOI} 388–391',
             'Text\n389 A. AUTHOR ET AL.', 'Text\nJOURNAL 390', 'References\nJOURNAL 391']
    if change == 'missing_middle':
        pages[3] = 'Text\nJOURNAL 391'
    elif change == 'wrong_doi':
        pages[1] = 'ABSTRACT 10.1080/other 388–391'
    else:
        pages[0] = 'Unknown page containing scientific text.'
    reader(monkeypatch, pages)
    assert not inspect_pdf_page_sequence(b'pdf', DOI, PdfExpectation(None, None, 4, None, 388, 391))['verified']


def test_internal_total_requires_every_body_page_and_identity(monkeypatch):
    reader(monkeypatch, [f'ABSTRACT {DOI}', 'Text\n2 of 3', 'References\n3 of 3'])
    assert inspect_pdf_page_sequence(b'pdf', DOI)['verified']
    reader(monkeypatch, [f'ABSTRACT {DOI}', 'Text\n2 of 4', 'References\n4 of 4'])
    assert not inspect_pdf_page_sequence(b'pdf', DOI)['verified']
    reader(monkeypatch, [f'ABSTRACT {DOI}\n2 of 3', 'Text\n2 of 3', 'References\n3 of 3'])
    assert not inspect_pdf_page_sequence(b'pdf', DOI)['verified']
