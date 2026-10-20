"""Equations survive every text conversion without restoring image assets."""

import pytest
from lxml import etree

from paperflow.documents import _inline
from paperflow.parsers.jats import convert_jats_xml_to_markdown
from paperflow.parsers.mineru_api import content_list_to_structured, markdown_to_structured
from paperflow.parsers.mineru_content import convert_mineru_structured_content_to_markdown


def test_jats_mathml_structure_labels_groups_and_source_order(tmp_path):
    xml = r'''<article><body>
    <p>Before.</p>
    <disp-formula><label>(1)</label><math xmlns="http://www.w3.org/1998/Math/MathML">
    <mfrac><msub><mi>T</mi><mi>i</mi></msub><msup><mi>x</mi><mn>2</mn></msup></mfrac>
    </math></disp-formula>
    <sec><title>Methods</title><p>Inside.<disp-formula-group>
    <disp-formula><tex-math>y=2</tex-math></disp-formula>
    <disp-formula><tex-math>z=3</tex-math></disp-formula>
    </disp-formula-group>After.</p></sec></body></article>'''
    source = tmp_path / "article.xml"
    source.write_text(xml, encoding="utf-8")
    text = convert_jats_xml_to_markdown(source, tmp_path / "out.md")
    assert r"\frac{T_i}{x^2}" in text
    assert text.count("(1)") == 1
    assert text.index("Before.") < text.index(r"\frac") < text.index("Methods")
    assert text.index("Inside.") < text.index("y=2") < text.index("z=3") < text.index("After.")


@pytest.mark.parametrize("kind", ["equation", "display_equation", "interline_equation"])
@pytest.mark.parametrize("formula", [r"\frac{a}{b}=x^2", r"$$\frac{a}{b}=x^2$$"])
def test_pdf_equations_are_kept_once(tmp_path, kind, formula):
    data = content_list_to_structured([
        {"type": "text", "text": "Before"},
        {"type": kind, "text": formula},
        {"type": "image", "img_caption": ["Caption"]},
        {"type": "text", "text": "After"},
    ])
    text, stats = convert_mineru_structured_content_to_markdown(data, tmp_path / "out.md")
    assert text.count(r"\frac{a}{b}=x^2") == 1
    assert text.index("Before") < text.index(r"\frac") < text.index("After")
    assert "$$" in text and "Caption" in text and "<img" not in text
    assert stats.display_equations_removed == 0


def test_light_api_keeps_multiline_equation_and_removes_images(tmp_path):
    data = markdown_to_structured("Before\n\n$$\na=b+c\n$$\n\n![figure](x.png)\n\nAfter")
    text, _ = convert_mineru_structured_content_to_markdown(data, tmp_path / "out.md")
    assert "$$\na=b+c\n$$" in text and "![" not in text


def test_native_mathml_retains_fraction_instead_of_flattening(tmp_path):
    source = etree.fromstring(b'<p>Flux <math><mfrac><mi>a</mi><mi>b</mi></mfrac></math>.</p>')
    article = etree.Element("article")
    target = etree.SubElement(etree.SubElement(article, "body"), "p")
    _inline(source, target)
    path = tmp_path / "native.xml"
    path.write_bytes(etree.tostring(article))
    text = convert_jats_xml_to_markdown(path, tmp_path / "out.md")
    assert r"\frac{a}{b}" in text


def test_image_only_equation_has_explicit_missing_marker(tmp_path):
    path = tmp_path / "image.xml"
    path.write_text('<article><body><disp-formula><label>(2)</label>'
                    '<graphic href="eq.png"/></disp-formula></body></article>', encoding="utf-8")
    text = convert_jats_xml_to_markdown(path, tmp_path / "out.md")
    assert "Formula unavailable in source" in text and "eq.png" not in text
    assert text.count("(2)") == 1
