"""Conservative native-document normalization into the existing JATS renderer.

No generic page scraping: HTML needs an article-body root, a matching identifier,
and explicit references. Ambiguous pages are rejected rather than summarized.
"""

from __future__ import annotations

import copy
import json
import posixpath
import re
import zipfile
from io import BytesIO
from urllib.parse import unquote

from lxml import etree, html


def _name(node):
    return etree.QName(node).localname.lower() if isinstance(node.tag, str) else ""


def _text(node):
    return " ".join("".join(node.itertext()).split())


def _article(title, doi):
    article = etree.Element("article")
    meta = etree.SubElement(etree.SubElement(article, "front"), "article-meta")
    if doi:
        etree.SubElement(meta, "article-id", {"pub-id-type": "doi"}).text = doi
    etree.SubElement(etree.SubElement(meta, "title-group"), "article-title").text = title or doi or "Untitled document"
    return article


def _inline(source, target):
    target.text = source.text
    for child in source:
        if not isinstance(child.tag, str):
            if len(target):
                target[-1].tail = (target[-1].tail or "") + (child.tail or "")
            else:
                target.text = (target.text or "") + (child.tail or "")
            continue
        tag = _name(child)
        if tag in {"img", "script", "style", "noscript", "iframe"}:
            if child.tail:
                if len(target):
                    target[-1].tail = (target[-1].tail or "") + child.tail
                else:
                    target.text = (target.text or "") + child.tail
            continue
        if tag in {"math", "formula"} and child.get("display") == "block":
            tag = "disp-formula"
        else:
            tag = {"strong": "bold", "b": "bold", "em": "italic", "i": "italic",
                   "sup": "sup", "sub": "sub", "math": "inline-formula", "formula": "inline-formula"}.get(tag, "named-content")
        node = etree.SubElement(target, tag)
        _inline(child, node)
        node.tail = child.tail


def _html_to_jats(content, doi=None, title=None, *, allow_body=False, source_doi=None):
    document = html.fromstring(content)
    for node in document.xpath("//script|//style|//noscript|//iframe|//nav|//header|//footer|//form"):
        node.drop_tree()
    identifiers = document.xpath(
        '//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="citation_doi"]/@content'
    )
    identifiers += document.xpath('//meta[@name="DC.Identifier" or @name="dc.identifier"]/@content')
    found_dois = [re.sub(r"^(https?://doi.org/|doi:)\s*", "", x.strip(), flags=re.IGNORECASE).lower()
                  for x in identifiers if "10." in x]
    if doi and doi.startswith("10.48550/arxiv."):
        arxiv_ids = document.xpath('//meta[@name="citation_arxiv_id"]/@content')
        target_id = doi.split("arxiv.", 1)[1]
        if any((x.lower().removeprefix("arxiv:") == target_id or (
            "v" not in target_id and re.sub(r"v\d+$", "", x.lower().removeprefix("arxiv:")) == target_id
        )) for x in arxiv_ids):
            found_dois.append(doi)
    if source_doi:
        found_dois.append(source_doi)
    if doi and doi not in found_dois:
        raise ValueError("Native HTML DOI identity could not be verified")
    doi = doi or (found_dois[0] if found_dois else None)
    titles = document.xpath('//meta[@name="citation_title"]/@content') or document.xpath("//h1")
    if not title and titles:
        title = titles[0] if isinstance(titles[0], str) else _text(titles[0])
    article = _article(title, doi)
    author_names = document.xpath('//meta[@name="citation_author"]/@content')
    meta = article.xpath("./front/article-meta")[0]
    if author_names:
        group = etree.SubElement(meta, "contrib-group")
        for author in author_names:
            name = etree.SubElement(etree.SubElement(group, "contrib"), "name")
            etree.SubElement(name, "given-names").text = author
    for node in document.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," ltx_authors ")]'):
        node.drop_tree()
    roots = document.xpath(
        '//*[@itemprop="articleBody"] | //*[@id="body" or @id="article-body" or @id="full-text"] | '
        '//*[contains(concat(" ",normalize-space(@class)," ")," c-article-body ")] | '
        '//*[contains(concat(" ",normalize-space(@class)," ")," article-body ")] | '
        '//*[contains(concat(" ",normalize-space(@class)," ")," ltx_document ")] | '
        '//*[contains(concat(" ",normalize-space(@class)," ")," article__body ")] | '
        '//*[contains(concat(" ",normalize-space(@class)," ")," hlFld-Fulltext ")] | '
        '//*[contains(concat(" ",normalize-space(@class)," ")," article_content ")] | '
        '//*[contains(concat(" ",normalize-space(@class)," ")," fulltext-view ")]'
    )
    if allow_body and not roots:
        roots = document.xpath("//body") or [document]
    if not roots:
        raise ValueError("No unambiguous article-body root in HTML")
    root = roots[0]
    if any(other is not root and root not in other.iterancestors() for other in roots):
        raise ValueError("Multiple disjoint article bodies; refusing a partial selection")
    if root.text and root.text.strip():
        raise ValueError("Unwrapped article-body text would be lost")
    references = []
    reference_roots = []
    for node in document.iter():
        if not isinstance(node.tag, str):
            continue
        label = (node.get("id", "") + " " + node.get("class", "")).lower()
        if (re.search(r"(?:^|[ _-])(references|ref-list|bibliography)(?:$|[ _-])", label)
                and not any(parent in reference_roots for parent in node.iterancestors())):
            reference_roots.append(node)
            entries = node.xpath(".//li") or node.xpath(".//p")
            references.extend(_text(entry) for entry in entries if _text(entry))
    if not references:
        raise ValueError("No explicit reference list in native HTML/EPUB")
    body = etree.SubElement(article, "body")

    def emit(container, parent):
        current = parent
        for node in container:
            if node in reference_roots:
                continue
            tag = _name(node)
            if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                current = etree.SubElement(parent, "sec")
                etree.SubElement(current, "title").text = _text(node)
            elif tag == "p":
                _inline(node, etree.SubElement(current, "p"))
            elif tag == "table":
                wrap = etree.SubElement(current, "table-wrap")
                table = etree.SubElement(wrap, "table")
                tbody = etree.SubElement(table, "tbody")
                for row in node.xpath(".//tr"):
                    tr = etree.SubElement(tbody, "tr")
                    for cell in row.xpath("./th|./td"):
                        td = etree.SubElement(tr, _name(cell))
                        for attr in ("rowspan", "colspan"):
                            if cell.get(attr):
                                td.set(attr, cell.get(attr))
                        _inline(cell, td)
            elif tag in {"ul", "ol"}:
                target = etree.SubElement(current, "list", {"list-type": "order" if tag == "ol" else "bullet"})
                for item in node.xpath("./li"):
                    _inline(item, etree.SubElement(etree.SubElement(target, "list-item"), "p"))
            elif tag == "figure":
                for nested_table in node.xpath(".//table"):
                    wrapper = etree.Element("div")
                    wrapper.append(copy.deepcopy(nested_table))
                    emit(wrapper, current)
                captions = node.xpath(".//figcaption")
                if captions:
                    figure = etree.SubElement(current, "fig")
                    etree.SubElement(etree.SubElement(figure, "caption"), "p").text = _text(captions[0])
            elif tag in {"div", "section", "article", "main", "body", "blockquote"}:
                if node.text and node.text.strip():
                    raise ValueError("Unwrapped HTML text would be lost; use PDF or structured XML")
                emit(node, current)
            elif tag not in {"img", "hr", "br"} and _text(node):
                raise ValueError("Unsupported HTML body block; refusing silent content loss")

    emit(root, etree.SubElement(body, "sec"))
    if len(root.xpath(".//table")) != len(body.xpath(".//table")):
        raise ValueError("HTML table count changed during normalization")
    refs = etree.SubElement(etree.SubElement(article, "back"), "ref-list")
    for reference in references:
        etree.SubElement(etree.SubElement(refs, "ref"), "mixed-citation").text = reference
    return article


def _tei_to_jats(tree, doi=None):
    ids = tree.xpath('//*[local-name()="teiHeader"]//*[local-name()="idno" and @type="DOI"]/text()')
    found = [x.strip().lower() for x in ids]
    if doi and doi not in found:
        raise ValueError("TEI DOI identity mismatch")
    doi = doi or (found[0] if found else None)
    titles = tree.xpath('//*[local-name()="titleStmt"]/*[local-name()="title"]')
    article = _article(_text(titles[0]) if titles else doi, doi)
    bodies = tree.xpath('//*[local-name()="text"]/*[local-name()="body"]')
    if len(bodies) != 1:
        raise ValueError("TEI needs exactly one full-text body")
    body = etree.SubElement(article, "body")

    def emit(container, target):
        for child in container:
            tag = _name(child)
            if tag == "div":
                emit(child, etree.SubElement(target, "sec"))
            elif tag == "head":
                etree.SubElement(target, "title").text = _text(child)
            elif tag == "p":
                _inline(child, etree.SubElement(target, "p"))
            elif tag == "table":
                table = etree.SubElement(etree.SubElement(target, "table-wrap"), "table")
                tbody = etree.SubElement(table, "tbody")
                for row in child.xpath('./*[local-name()="row"]'):
                    tr = etree.SubElement(tbody, "tr")
                    for cell in row:
                        _inline(cell, etree.SubElement(tr, "td"))
            elif tag == "list":
                node = etree.SubElement(target, "list")
                for item in child:
                    _inline(item, etree.SubElement(etree.SubElement(node, "list-item"), "p"))
            elif tag in {"figure", "formula"}:
                captions = child.xpath('./*[local-name()="figDesc"]')
                if captions:
                    node = etree.SubElement(target, "fig")
                    etree.SubElement(etree.SubElement(node, "caption"), "p").text = _text(captions[0])
            else:
                raise ValueError("Unsupported TEI body block; refusing silent content loss")

    emit(bodies[0], etree.SubElement(body, "sec"))
    refs = etree.SubElement(etree.SubElement(article, "back"), "ref-list")
    for node in tree.xpath('//*[local-name()="listBibl"]/*'):
        etree.SubElement(etree.SubElement(refs, "ref"), "mixed-citation").text = _text(node)
    return article


def _epub_to_jats(content, doi=None, title=None):
    with zipfile.ZipFile(BytesIO(content)) as archive:
        if len(archive.infolist()) > 2000 or sum(x.file_size for x in archive.infolist()) > 100_000_000:
            raise ValueError("EPUB exceeds safe document size limits")
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        container = etree.fromstring(archive.read("META-INF/container.xml"), parser)
        paths = container.xpath('//*[local-name()="rootfile"]/@full-path')
        if len(paths) != 1:
            raise ValueError("EPUB must have a single package")
        package_path = posixpath.normpath(paths[0])
        if package_path.startswith(("/", "..")):
            raise ValueError("Unsafe EPUB package path")
        package = etree.fromstring(archive.read(package_path), parser)
        ids = package.xpath('//*[local-name()="metadata"]/*[local-name()="identifier"]/text()')
        found = [re.sub(r"^(https?://doi.org/|doi:)\s*", "", x, flags=re.IGNORECASE).lower() for x in ids if "10." in x]
        if doi and doi not in found:
            raise ValueError("EPUB DOI identity mismatch")
        source_doi = doi or (found[0] if found else None)
        titles = package.xpath('//*[local-name()="metadata"]/*[local-name()="title"]/text()')
        manifest = {x.get("id"): x for x in package.xpath('//*[local-name()="manifest"]/*')}
        merged = html.fromstring("<html><body></body></html>")
        body = merged.xpath("//body")[0]
        spine = package.xpath('//*[local-name()="spine"]/*')
        if len(spine) > 500:
            raise ValueError("EPUB spine exceeds safe document limits")
        total_read = 0
        for item in spine:
            if item.get("linear", "yes") == "no":
                continue
            entry = manifest[item.get("idref")]
            if "nav" in entry.get("properties", "").split():
                continue
            name = posixpath.normpath(posixpath.join(posixpath.dirname(package_path), unquote(entry.get("href", "").split("#")[0])))
            if name.startswith(("/", "..")):
                raise ValueError("Unsafe EPUB spine path")
            total_read += archive.getinfo(name).file_size
            if total_read > 100_000_000:
                raise ValueError("EPUB repeated spine content exceeds safe document limits")
            document = html.fromstring(archive.read(name))
            roots = document.xpath("//body") or [document]
            section = etree.SubElement(body, "section")
            for child in roots[0]:
                section.append(copy.deepcopy(child))
        return _html_to_jats(etree.tostring(merged), source_doi, title or (titles[0] if titles else None),
                             allow_body=True, source_doi=source_doi)


def _expand_table_spans(table):
    """Place each original cell once on its grid; continuations remain empty.

    Reject overlapping, unbounded or cross-row-group spans. The raw XML remains
    the source of truth; the normalized XML records every original span position.
    """
    if not table.xpath('.//*[@rowspan or @colspan]'):
        return
    if table.xpath('.//*[local-name()="table"]'):
        raise ValueError("Nested spanning tables require manual review")
    layout = []
    for group_index, group in enumerate(table.xpath('./*[local-name()="thead" or local-name()="tbody"]')):
        rows = group.xpath('./*[local-name()="tr"]')
        occupied = {}
        grids = []
        if len(rows) > 2000:
            raise ValueError("Spanning table exceeds row limit")
        for row_index, row in enumerate(rows):
            grid = {}; column = 0
            for cell in list(row):
                if _name(cell) not in {"td", "th"}:
                    raise ValueError("Unsupported spanning table row content")
                while (row_index, column) in occupied:
                    column += 1
                try:
                    height = int(cell.get("rowspan", "1"))
                    width = int(cell.get("colspan", "1"))
                except ValueError:
                    raise ValueError("Invalid table span") from None
                if not (1 <= height <= len(rows) - row_index and 1 <= width <= 200 and column + width <= 200):
                    raise ValueError("Table span exceeds grid bounds")
                if any((r, c) in occupied for r in range(row_index, row_index + height)
                       for c in range(column, column + width)):
                    raise ValueError("Overlapping table spans")
                if height > 1 or width > 1:
                    layout.append([group_index, row_index, column, height, width])
                for r in range(row_index, row_index + height):
                    for c in range(column, column + width):
                        occupied[r, c] = True
                cell.attrib.pop("rowspan", None)
                cell.attrib.pop("colspan", None)
                grid[column] = cell
                column += width
            grids.append(grid)
        width = max((c + 1 for _, c in occupied), default=0)
        for row, grid in zip(rows, grids):
            for cell in list(row):
                row.remove(cell)
            for column in range(width):
                cell = grid.get(column)
                if cell is None:
                    cell = etree.Element("td")
                row.append(cell)
    if layout:
        table.set("paperflow-span-layout", json.dumps(layout, separators=(",", ":")))
        wrapper = table.getparent()
        if _name(wrapper) != "table-wrap":
            raise ValueError("Spanning table needs an explicit table wrapper")
        feet = wrapper.xpath('./*[local-name()="table-wrap-foot"]')
        foot = feet[0] if feet else etree.SubElement(wrapper, "table-wrap-foot")
        etree.SubElement(foot, "p").text = (
            "[PaperFlow: merged cells expanded with blank continuation cells; "
            "original span positions retained in the source and normalized XML.]"
        )


def normalize_document(content, kind, *, doi=None, title=None):
    if kind == "html":
        article = _html_to_jats(content, doi, title)
    elif kind == "epub":
        article = _epub_to_jats(content, doi, title)
    elif kind in {"xml", "jats", "tei"}:
        tree = etree.fromstring(content, etree.XMLParser(resolve_entities=False, no_network=True))
        if _name(tree) == "tei":
            article = _tei_to_jats(tree, doi)
        else:
            articles = [tree] if _name(tree) == "article" else tree.xpath('//*[local-name()="article"]')
            if len(articles) != 1:
                raise ValueError("Expected exactly one JATS article")
            article = copy.deepcopy(articles[0])
            found = article.xpath('./*[local-name()="front"]//*[local-name()="article-id" and @pub-id-type="doi"]/text()')
            if doi and doi not in [x.strip().lower() for x in found]:
                raise ValueError("JATS DOI identity mismatch")
    else:
        raise ValueError("Supported native formats: XML/JATS/TEI, HTML, EPUB")
    # Preserve mixed body order: the existing renderer processes direct sections before paragraphs.
    bodies = article.xpath('./*[local-name()="body"]')
    if len(bodies) == 1:
        body = bodies[0]
        # The renderer handles back/sec, but not app-group/app containers.
        # Keep appendices in their original back-matter position as sections.
        for appendix in article.xpath('./*[local-name()="back"]//*[local-name()="app-group" or local-name()="app" or local-name()="notes"]'):
            namespace = etree.QName(appendix).namespace
            appendix.tag = ("{" + namespace + "}" if namespace else "") + "sec"
        for section in article.xpath('.//*[local-name()="sec"]'):
            labels = section.xpath('./*[local-name()="label"]')
            titles = section.xpath('./*[local-name()="title"]')
            for label in labels:
                if len(labels) == len(titles) == 1 and not len(label) and not (label.tail or '').strip():
                    titles[0].text = (_text(label) + ' ' + (titles[0].text or '')).strip()
                    section.remove(label)
                else:
                    namespace = etree.QName(label).namespace
                    label.tag = ("{" + namespace + "}" if namespace else "") + "p"
        references = body.xpath('.//*[local-name()="ref-list"]')
        if references:
            if len(references) != 1 or article.xpath('./*[local-name()="back"]//*[local-name()="ref-list"]'):
                raise ValueError("Ambiguous primary reference lists")
            backs = article.xpath('./*[local-name()="back"]')
            back = backs[0] if backs else etree.SubElement(article, "back")
            back.append(references[0])
        for definition in body.xpath('.//*[local-name()="def-list" or local-name()="def-item" or local-name()="def" or local-name()="term"]'):
            namespace = etree.QName(definition).namespace
            prefix = "{" + namespace + "}" if namespace else ""
            definition.tag = prefix + ("p" if _name(definition) == "term" else "sec")
        # PLOS supplies the same table as an image and an XML table. Select the
        # unique structured representation; the renderer expects it directly.
        for alternatives in body.xpath('.//*[local-name()="table-wrap"]/*[local-name()="alternatives"]'):
            tables = alternatives.xpath('./*[local-name()="table"]')
            if len(tables) != 1 or any(_name(x) not in {"table", "graphic"} for x in alternatives):
                raise ValueError("Ambiguous alternative table representations")
            alternatives.addprevious(tables[0])
            alternatives.getparent().remove(alternatives)
        for media in body.xpath('.//*[local-name()="media"]'):
            # Media assets are external attachments, not downloaded paper text.
            namespace = etree.QName(media).namespace
            prefix = "{" + namespace + "}" if namespace else ""
            media.tag = prefix + "p"
            media.text = "[PaperFlow: external media not retrieved.] " + (media.text or "")
            href = media.get("{http://www.w3.org/1999/xlink}href")
            if href:
                media.text += " Source: " + href
        # PLOS places attachment descriptions in the body. Preserve their text and
        # links without implying that the external attachment itself was retrieved.
        for attachment in body.xpath('.//*[local-name()="supplementary-material"]'):
            namespace = etree.QName(attachment).namespace
            prefix = "{" + namespace + "}" if namespace else ""
            attachment.tag = prefix + "sec"
            for label in attachment.xpath('./*[local-name()="label"]'):
                label.tag = prefix + "title"
            for caption in attachment.xpath('./*[local-name()="caption"]'):
                caption.tag = prefix + "sec"
            note = etree.SubElement(attachment, prefix + "p")
            note.text = "[PaperFlow: attachment description only; external attachment not retrieved.]"
            href = attachment.get("{http://www.w3.org/1999/xlink}href")
            if href:
                etree.SubElement(attachment, prefix + "p").text = "Attachment source: " + href
        for box in body.xpath('.//*[local-name()="boxed-text"]'):
            namespace = etree.QName(box).namespace
            box.tag = "{" + namespace + "}sec" if namespace else "sec"
            for label in box.xpath('./*[local-name()="label"]'):
                label.tag = "{" + namespace + "}p" if namespace else "p"
        for wrapper in body.xpath('.//*[local-name()="fig-group" or local-name()="disp-quote" or local-name()="fn-group"]'):
            namespace = etree.QName(wrapper).namespace
            prefix = "{" + namespace + "}" if namespace else ""
            original = _name(wrapper)
            wrapper.tag = prefix + "sec"
            if original == "fn-group":
                for fn in wrapper.xpath('./*[local-name()="fn"]'):
                    fn.tag = prefix + "sec"
            if original == "disp-quote":
                title = etree.Element(prefix + "title")
                title.text = "Quoted text" + (" (" + wrapper.get("content-type") + ")" if wrapper.get("content-type") else "")
                wrapper.insert(0, title)
        for section in [body, *body.xpath('.//*[local-name()="sec"]')]:
            for child in section:
                if not isinstance(child.tag, str):
                    if child.tail and child.tail.strip():
                        raise ValueError("Unwrapped body text after XML comment")
                    continue
                if _name(child) not in {"title", "p", "sec", "table-wrap", "fig", "list", "disp-formula"}:
                    raise ValueError(f"Unsupported native body block: {_name(child)}; refusing silent content loss")
        ordered = etree.Element("sec")
        for child in list(body):
            ordered.append(child)
        body.append(ordered)
        for table in body.xpath('.//*[local-name()="table"]'):
            direct_rows = table.xpath('./*[local-name()="tr"]')
            if direct_rows:
                if table.xpath('./*[local-name()="thead" or local-name()="tbody"]'):
                    raise ValueError("Ambiguous mixed direct/grouped table rows")
                tbody = etree.SubElement(table, "tbody")
                for row in direct_rows:
                    tbody.append(row)
            _expand_table_spans(table)
    return etree.tostring(article, encoding="utf-8", xml_declaration=True)
