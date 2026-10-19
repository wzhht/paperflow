import json
import zipfile
from io import BytesIO

import httpx
import pytest
from typer.testing import CliRunner

from paperflow.cli import app
from paperflow.config import Settings, load_settings
from paperflow.documents import normalize_document
from paperflow.pipeline import PipelineContentError, process_document
from paperflow.sources.native import fetch_wiley_pdf, native_candidates

DOI = "10.7554/elife.12345"
PARAGRAPHS = [f"PARAGRAPH_{n} " + "Measured thermal response under controlled experimental conditions. " * 12
              for n in range(12)]


def article_html():
    return ('<html><head><meta name="citation_doi" content="' + DOI + '">'
            '<meta name="citation_title" content="Thermal evidence"/></head><body>'
            '<div itemprop="articleBody"><h2>Results</h2>'
            + ''.join('<p>' + text + '</p>' for text in PARAGRAPHS)
            + '<figure><table><tr><th>U</th><th>Value</th></tr><tr><td>Test</td><td>1.23</td></tr></table>'
            '<figcaption>Table caption 99.8</figcaption></figure>'
            '<section id="references"><ol><li>Author. Original reference. 2024. DOI 10.1234/ref.</li></ol></section>'
            '</div></body></html>').encode()


def test_local_html_preserves_paragraphs_tables_references_and_identity(tmp_path):
    source = tmp_path / "article.html"
    source.write_bytes(article_html())
    result = process_document(source, doi=DOI, output_root=tmp_path / "library")
    text = result.llm_markdown_path.read_text(encoding="utf-8")
    for paragraph in PARAGRAPHS:
        assert paragraph.strip() in text
    assert "1.23" in text and "99.8" in text and "Original reference" in text
    assert "<img" not in text and "![" not in text
    qa = json.loads(result.qa_path.read_text(encoding="utf-8"))
    assert qa["full_text_available"] and qa["structured"]["table_count"] == 1
    assert qa["table_numeric_audit"]["values_match"]
    with pytest.raises(ValueError, match="identity"):
        process_document(source, doi="10.7554/elife.other", output_root=tmp_path / "other")


def test_abstract_only_and_unhandled_body_are_rejected(tmp_path):
    source = tmp_path / "short.html"
    source.write_bytes(article_html().replace(''.join('<p>' + p + '</p>' for p in PARAGRAPHS).encode(), b'<p>Abstract only</p>'))
    with pytest.raises(PipelineContentError):
        process_document(source, doi=DOI, output_root=tmp_path / "library")
    content = article_html().replace(b'<h2>Results</h2>', b'<h2>Results</h2><custom>Hidden scientific content</custom>')
    with pytest.raises(ValueError, match="silent content loss"):
        normalize_document(content, "html", doi=DOI)


def test_tei_import_and_epub_spine(tmp_path):
    tei = ('<TEI><teiHeader><fileDesc><titleStmt><title>Native TEI</title></titleStmt>'
           '<idno type="DOI">' + DOI + '</idno></fileDesc></teiHeader><text><body><div><head>Results</head>'
           + ''.join('<p>' + text + '</p>' for text in PARAGRAPHS)
           + '</div></body><back><listBibl><bibl>Original reference 2024</bibl></listBibl></back></text></TEI>')
    path = tmp_path / "source.tei"
    path.write_text(tei, encoding="utf-8")
    result = process_document(path, doi=DOI, output_root=tmp_path / "tei_library")
    assert "PARAGRAPH_11" in result.llm_markdown_path.read_text(encoding="utf-8")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OPS/package.opf"/></rootfiles></container>')
        archive.writestr("OPS/package.opf", '<package><metadata><title>Native EPUB</title><identifier>doi:' + DOI
                         + '</identifier></metadata><manifest><item id="a" href="article.html"/></manifest>'
                         '<spine><itemref idref="a"/></spine></package>')
        archive.writestr("OPS/article.html", article_html())
    path = tmp_path / "source.epub"
    path.write_bytes(buffer.getvalue())
    result = process_document(path, doi=DOI, output_root=tmp_path / "epub_library")
    text = result.llm_markdown_path.read_text(encoding="utf-8")
    assert "PARAGRAPH_11" in text and "1.23" in text


def test_wiley_key_alias_and_token_is_not_forwarded(monkeypatch):
    from paperflow import config

    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for name in ("WILEY_API_KEY", "Wiley_API_KEY", "WILEY_TDM_API_KEY", "TDM_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("Wiley_API_KEY", "private-wiley-token")
    settings = load_settings()
    assert settings.wiley_api_key == "private-wiley-token"
    assert "private-wiley-token" not in repr(settings)
    calls = []

    def handler(request):
        calls.append(request)
        assert "private-wiley-token" not in str(request.url)
        if request.url.host == "api.wiley.com":
            assert request.headers["Wiley-TDM-Client-Token"] == "private-wiley-token"
            return httpx.Response(302, headers={"Location": "https://other.example/pdf"})
        assert request.url.host == "other.example"
        assert "Wiley-TDM-Client-Token" not in request.headers
        return httpx.Response(200, content=b"%PDF-1.7 test")

    assert fetch_wiley_pdf("10.1002/example", settings, transport=httpx.MockTransport(handler)).startswith(b"%PDF-")
    assert len(calls) == 2


def test_plos_uses_direct_xml_before_generic_sources():
    def handler(request):
        assert request.url.host == "journals.plos.org"
        assert request.url.params["type"] == "manuscript"
        return httpx.Response(200, content=b"<article/>")

    generator = native_candidates("10.1371/journal.pone.0123456", Settings(None, None, None),
                                  transport=httpx.MockTransport(handler))
    try:
        content, kind, source, _url = next(generator)
        assert content == b"<article/>" and kind == "xml" and source == "plos_jats"
    finally:
        generator.close()


def test_process_document_cli_uses_same_verified_pipeline(tmp_path):
    source = tmp_path / "article.html"
    source.write_bytes(article_html())
    result = CliRunner().invoke(app, ["process-document", str(source), "--doi", DOI,
                                      "--output-root", str(tmp_path / "library")])
    assert result.exit_code == 0, result.output
    assert "Status = success" in result.output


def test_wiley_tdm_pipeline_precedes_generic_acquisition(tmp_path, monkeypatch):
    from paperflow import pipeline
    from paperflow.sources import native

    monkeypatch.setattr(native, "fetch_wiley_pdf", lambda *args: b"%PDF-1.7 verified-source")
    calls = []

    def parse(paths, settings, **kwargs):
        calls.append(kwargs)
        return "parsed-wiley"

    monkeypatch.setattr(pipeline, "_process_pdf_with_mineru", parse)
    result = pipeline.process_doi("10.1002/example", library_root=tmp_path,
                                  settings=Settings(None, None, None, wiley_api_key="own-key"))
    assert result == "parsed-wiley"
    assert calls[0]["source"] == "wiley_tdm_pdf_mineru"


def test_jats_boxed_scientific_text_is_preserved(tmp_path):
    from lxml import etree

    tree = etree.fromstring(normalize_document(article_html(), "html", doi=DOI))
    box = etree.SubElement(tree.xpath("./body/sec")[0], "boxed-text")
    etree.SubElement(box, "p").text = "Distinct scientific text in a boxed argument 123.456."
    source = tmp_path / "source.xml"
    source.write_bytes(etree.tostring(tree))
    result = process_document(source, doi=DOI, output_root=tmp_path / "library")
    assert "Distinct scientific text in a boxed argument 123.456." in result.llm_markdown_path.read_text(encoding="utf-8")


def test_disjoint_body_roots_are_not_silently_truncated():
    content = article_html().replace(b'</body>', b'<div itemprop="articleBody"><p>Second body</p></div></body>')
    with pytest.raises(ValueError, match="disjoint"):
        normalize_document(content, "html", doi=DOI)


def test_plos_alternative_spanning_table_keeps_grid_values_and_attachment_text(tmp_path):
    from lxml import etree

    tree = etree.fromstring(normalize_document(article_html(), "html", doi=DOI))
    section = tree.xpath('./body/sec')[0]
    section.append(etree.fromstring(b'''<table-wrap><label>Table 2</label><alternatives>
      <graphic href="table-image.png"/><table><thead><tr><th>Group</th><th colspan="2">Values</th></tr></thead>
      <tbody><tr><td rowspan="2">A</td><td>11.25</td><td>22.50</td></tr>
      <tr><td>33.75</td><td>44.00</td></tr></tbody></table></alternatives></table-wrap>'''))
    section.append(etree.fromstring(b'''<supplementary-material xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="appendix.zip">
      <label>S1 Appendix</label><caption><title>Original appendix description</title>
      <p>Supporting methods 987.65.</p></caption></supplementary-material>'''))
    source = tmp_path / 'source.xml'
    source.write_bytes(etree.tostring(tree))
    result = process_document(source, doi=DOI, output_root=tmp_path / 'library')
    text = result.llm_markdown_path.read_text(encoding='utf-8')
    assert '| A | 11.25 | 22.50 |' in text
    assert '|  | 33.75 | 44.00 |' in text
    assert all(text.count(value) == 1 for value in ['11.25', '22.50', '33.75', '44.00'])
    assert 'Original appendix description' in text and 'Supporting methods 987.65.' in text
    assert 'external attachment not retrieved' in text and 'appendix.zip' in text
    assert 'table-image.png' not in text
    qa = json.loads(result.qa_path.read_text(encoding='utf-8'))
    assert qa['table_numeric_audit']['values_match']


@pytest.mark.parametrize('attribute', ['rowspan="9999"', 'colspan="0"', 'colspan="abc"'])
def test_invalid_table_spans_are_rejected(attribute):
    from lxml import etree

    tree = etree.fromstring(normalize_document(article_html(), "html", doi=DOI))
    cell = tree.xpath('//table//td')[0]
    name, value = attribute.replace('"', '').split('=')
    cell.set(name, value)
    with pytest.raises(ValueError, match='span'):
        normalize_document(etree.tostring(tree), 'xml', doi=DOI)


def test_native_pipeline_continues_after_pdf_to_later_structured_source(tmp_path, monkeypatch):
    from paperflow import pipeline
    from paperflow.sources import native

    xml = normalize_document(article_html(), 'html', doi=DOI)
    monkeypatch.setattr(native, 'native_candidates', lambda *a, **kw: iter([
        (b'%PDF-1.7 candidate', 'pdf', 'early_pdf', 'https://example.org/p.pdf'),
        (xml, 'xml', 'late_jats', 'https://example.org/a.xml'),
    ]))
    monkeypatch.setattr(pipeline, '_process_pdf_with_mineru',
                        lambda *a, **kw: pytest.fail('Must prefer verified structured text'))
    result = pipeline.process_doi(DOI, library_root=tmp_path, settings=Settings(None, None, None))
    assert result.source == 'late_jats' and result.status == 'success'


def test_frontiers_uses_current_xml_endpoint_and_safe_diagnostics():
    diagnostics = []

    def handler(request):
        assert request.url.host == 'www.frontiersin.org'
        assert request.url.path == '/journals/energy-research/articles/10.3389/fenrg.2022.1078938/xml'
        return httpx.Response(200, content=b'<article/>')

    generator = native_candidates('10.3389/fenrg.2022.1078938', Settings(None, None, None),
                                  transport=httpx.MockTransport(handler), diagnostics=diagnostics)
    assert next(generator)[2] == 'frontiers_jats'
    generator.close()
    assert diagnostics == [{'host': 'www.frontiersin.org', 'http_status': 200}]


def test_pmc_body_references_and_definitions_are_preserved(tmp_path):
    from lxml import etree

    tree = etree.fromstring(normalize_document(article_html(), 'html', doi=DOI))
    body = tree.xpath('./body')[0]
    body.append(etree.fromstring(b'<def-list><def-item><term>U</term><def><p>Heat transfer 1.234.</p></def></def-item></def-list>'))
    body.append(tree.xpath('./back/ref-list')[0])
    body.append(etree.Comment('Archival formatting only'))
    source = tmp_path / 'pmc.xml'
    source.write_bytes(etree.tostring(tree))
    result = process_document(source, doi=DOI, output_root=tmp_path / 'library')
    text = result.llm_markdown_path.read_text(encoding='utf-8')
    assert 'Heat transfer 1.234.' in text and 'Original reference' in text
    assert text.count('Original reference') == 1 and 'References' in text
    assert 'PARAGRAPH_11' in text


def test_transient_public_connect_error_retries_once():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == 'journals.plos.org'
        if len(calls) == 1:
            raise httpx.ConnectError('Transient network failure', request=request)
        return httpx.Response(200, content=b'<article/>')

    generator = native_candidates('10.1371/journal.pone.0123456', Settings(None, None, None),
                                  transport=httpx.MockTransport(handler))
    assert next(generator)[2] == 'plos_jats'
    generator.close()
    assert len(calls) == 2


def test_numbered_sections_and_back_appendices_preserve_text(tmp_path):
    from lxml import etree

    tree = etree.fromstring(normalize_document(article_html(), 'html', doi=DOI))
    section = tree.xpath('./body/sec')[0]
    label = etree.Element('label')
    label.text = '2.1'
    section.insert(0, label)
    title = etree.Element('title')
    title.text = 'Measured heat response'
    section.insert(1, title)
    tree.xpath('./back')[0].append(etree.fromstring(b'<app-group><app><label>Appendix A</label><title>Validation</title><p>APPENDIX_VALUE 52.75</p></app></app-group>'))
    tree.xpath('./back')[0].append(etree.fromstring(b'<notes><title>Data availability</title><p>DATA_SOURCE 19.25</p></notes>'))
    source = tmp_path / 'appendix.xml'
    source.write_bytes(etree.tostring(tree))
    result = process_document(source, doi=DOI, output_root=tmp_path / 'library')
    text = result.llm_markdown_path.read_text(encoding='utf-8')
    assert '2.1 Measured heat response' in text
    assert 'Appendix A Validation' in text and 'APPENDIX_VALUE 52.75' in text
    assert 'Data availability' in text and 'DATA_SOURCE 19.25' in text
