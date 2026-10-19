"""Flat, title-named reading copies; canonical artifacts remain intact."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from html import unescape
from pathlib import Path

from lxml import etree
from pypdf.errors import PdfReadError


def paper_title(directory: Path, text: str) -> str:
    metadata = directory / "metadata.json"
    if metadata.is_file():
        title = json.loads(metadata.read_text(encoding="utf-8")).get("title")
        if title and not str(title).lower().startswith("10."):
            return str(title)
    for name in ("paper.xml", "jats.xml"):
        path = directory / name
        if path.is_file():
            try:
                root = etree.fromstring(
                    path.read_bytes(), etree.XMLParser(resolve_entities=False, no_network=True)
                )
                nodes = root.xpath(
                    "//*[local-name()='article-title'] | //*[local-name()='title' and local-name(..)='coredata']"
                )
                if nodes:
                    return " ".join("".join(nodes[0].itertext()).split())
            except etree.XMLSyntaxError:
                pass
    match = re.search(r"(?m)^#\s+(.+)$", text)
    if match:
        return match[1].strip()
    pdfs = list(directory.glob("*.pdf"))
    if len(pdfs) == 1:
        try:
            from pypdf import PdfReader

            title = (PdfReader(pdfs[0]).metadata or {}).get("/Title")
            if (
                title
                and not str(title).lower().startswith("microsoft word")
                and str(title).strip().lower() not in {"untitled", "document", "paper"}
            ):
                return " ".join(str(title).split())
        except (OSError, ValueError, PdfReadError):
            pass
    return directory.name


def safe_title(title: str) -> str:
    title = unicodedata.normalize("NFC", title)
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    title = re.sub(r"\s+", " ", title).strip(" .")[:150].rstrip(" .") or "Untitled paper"
    if title.split(".")[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        title = "Paper " + title
    return title


def export_markdown(library_root, destination, *, include_partial=False):
    root, destination = Path(library_root).resolve(), Path(destination).resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("Flat export must be a separate directory outside the canonical library.")
    if not root.is_dir():
        raise FileNotFoundError(root)
    destination.mkdir(parents=True, exist_ok=True)
    index_path = destination / "export_manifest.csv"
    rows, used = [], set()
    # Reuse only our own mapped filenames, never overwrite unrelated Markdown files.
    old = {}
    if index_path.exists():
        with index_path.open(encoding="utf-8-sig", newline="") as handle:
            old = {row["source_path"]: row for row in csv.DictReader(handle)}
    for source in sorted(root.glob("*/paper_llm.md")):
        qa_file = source.parent / "qa.json"
        qa = json.loads(qa_file.read_text(encoding="utf-8")) if qa_file.exists() else {}
        if qa.get("status") == "failed":
            continue
        partial = qa.get("source") in {"springer_restricted_partial", "public_metadata_partial"}
        if partial and not include_partial:
            continue
        text = source.read_text(encoding="utf-8")
        title = paper_title(source.parent, text)
        # Bibliographic titles may contain inline XML/HTML; reading filenames should not.
        title = unescape(re.sub(r'</?(?:sub|sup|i|b|em|strong|span|italic|bold|scp)'
                                r'(?:\s[^>]*)?>', '', title, flags=re.IGNORECASE))
        suffix = hashlib.sha256(str(source).encode()).hexdigest()[:8]
        previous_row = old.get(str(source), {})
        previous = previous_row.get("filename")
        reusable = bool(
            previous
            and Path(previous).name == previous
            and previous.endswith(".md")
            and previous_row.get("title") == title
        )
        if reusable and (destination / previous).exists():
            reusable = hashlib.sha256(
                (destination / previous).read_bytes()
            ).hexdigest() == previous_row.get("sha256")
        if reusable:
            filename = previous
        else:
            label = " [ABSTRACT ONLY]" if partial else ""
            # Reserve the temporary extension and collision suffix under Windows MAX_PATH.
            title_budget = min(150, 240 - len(str(destination)) - 1 - 7 - 24 - len(label))
            if title_budget < 12:
                raise ValueError("Export folder path is too long; choose a shorter destination.")
            base = safe_title(title)[:title_budget].rstrip(" .") + label
            filename = base + ".md"
            if filename.casefold() in used or (destination / filename).exists():
                filename = base + " -- " + suffix + ".md"
            n = 2
            while filename.casefold() in used or (destination / filename).exists():
                filename = base + f" -- {suffix}-{n}.md"
                n += 1
        if partial and "[ABSTRACT ONLY]" not in text:
            text = "[ABSTRACT ONLY — NOT FULL TEXT]\n\n" + text
        used.add(filename.casefold())
        target = destination / filename
        temp = target.with_suffix(".md.tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(target)
        rows.append(
            {
                "filename": filename,
                "title": title,
                "doi": qa.get("doi", ""),
                "source_path": str(source),
                "status": qa.get("status", "unknown"),
                "full_text_available": not partial,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    with index_path.with_suffix(".tmp").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "filename",
                "title",
                "doi",
                "source_path",
                "status",
                "full_text_available",
                "sha256",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    index_path.with_suffix(".tmp").replace(index_path)
    return rows
