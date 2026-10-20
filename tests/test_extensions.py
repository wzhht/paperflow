import io
import json
import zipfile
from dataclasses import replace

import httpx
import pytest
from pypdf import PdfWriter
from typer.testing import CliRunner

from paperflow.cli import app
from paperflow.config import Settings
from paperflow.models import Route
from paperflow.parsers.mineru_api import (
    content_list_to_structured,
    markdown_to_structured,
    normalize_archive,
    parse_pdf_with_mineru_api,
)
from paperflow.parsers.mineru_content import convert_mineru_structured_content_to_markdown
from paperflow.parsers.mineru_pdf import MinerUArtifactError, MinerUExecutionError
from paperflow.qa.mineru import audit_mineru_markdown
from paperflow.routing import route_doi
from paperflow.sources.public_pdf import discover_pdf
from paperflow.storage.flat_export import export_markdown, safe_title


def pdf_file(tmp_path):
    path = tmp_path / "input.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def archive(items):
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as z:
        z.writestr("nested/paper_content_list.json", json.dumps(items))
    return content.getvalue()


def items():
    return [
        {"type": "text", "text": "Actual paper title", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "Methods", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "Retain R², 1.25, °C, and inline $U$.", "page_idx": 0},
        {
            "type": "table",
            "table_body": '<table><tr><td>1.25</td><td><img src="x.png"/>°C</td></tr></table>',
            "table_caption": ["Table 1"],
            "page_idx": 0,
        },
        {"type": "image", "img_caption": ["Figure caption retained"], "page_idx": 0},
        {"type": "equation", "text": "$$x=1$$", "page_idx": 0},
        {"type": "text", "text": "References", "text_level": 1, "page_idx": 1},
        {"type": "text", "text": "[1] A verified bibliography item.", "page_idx": 1},
    ]


def test_cloud_conversion_preserves_tables_text_references_without_images(tmp_path):
    data = normalize_archive(archive(items()))
    text, stats = convert_mineru_structured_content_to_markdown(data, tmp_path / "paper.md")
    audit = audit_mineru_markdown(data, text)
    assert "# Actual paper title" in text
    assert "1.25" in text and "°C" in text and "inline $U$" in text
    assert "Figure caption retained" in text and "[1]" in text
    assert "<img" not in text and "$$x=1$$" in text
    assert (
        audit.table_content_exact_match
        and audit.table_numeric_values_match
        and audit.has_references
    )
    assert stats.page_count == 2


def test_precision_api_keeps_token_off_upload_and_artifact_hosts(tmp_path):
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path.endswith("/file-urls/batch"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "id",
                        "file_urls": ["https://store.example/upload?signature=secret"],
                    },
                },
            )
        if request.url.host == "store.example":
            assert "authorization" not in request.headers
            return httpx.Response(200)
        if request.url.path.endswith("/id"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {"state": "done", "full_zip_url": "https://cdn.example/artifact"}
                        ]
                    },
                },
            )
        assert "authorization" not in request.headers
        return httpx.Response(200, content=archive(items()))

    result = parse_pdf_with_mineru_api(
        pdf_file(tmp_path),
        tmp_path / "out.zip",
        token="test-secret-token",
        transport=httpx.MockTransport(handle),
    )
    assert result.output_zip.exists()
    assert requests[0].headers["authorization"] == "Bearer test-secret-token"
    assert content_list_to_structured(items())["pages"][1]["page_idx"] == 1


@pytest.mark.parametrize("kind", ["http", "quota", "failed", "invalid_zip"])
def test_cloud_failures_never_expose_provider_body_or_token(tmp_path, kind):
    def handle(request):
        if kind == "http":
            return httpx.Response(401, text="test-secret-token https://signed.example/key")
        if kind == "quota":
            return httpx.Response(200, json={"code": -60018, "msg": "test-secret-token"})
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"batch_id": "id", "file_urls": ["https://store.example/upload"]},
                },
            )
        if request.method == "PUT":
            return httpx.Response(200)
        if request.url.host == "mineru.net":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {
                                "state": "failed" if kind == "failed" else "done",
                                "err_msg": "test-secret-token",
                                "full_zip_url": "https://cdn.example/zip",
                            }
                        ]
                    },
                },
            )
        return httpx.Response(200, content=b"not a zip")

    with pytest.raises((MinerUExecutionError, MinerUArtifactError)) as exc:
        parse_pdf_with_mineru_api(
            pdf_file(tmp_path),
            tmp_path / "out.zip",
            token="test-secret-token",
            transport=httpx.MockTransport(handle),
        )
    assert "test-secret-token" not in str(exc.value) and "https://" not in str(exc.value)
    assert not (tmp_path / "out.zip").exists()


def test_missing_precision_token_and_lightweight_quality_are_explicit(tmp_path):
    with pytest.raises(MinerUExecutionError, match="MINERU_API_TOKEN"):
        parse_pdf_with_mineru_api(pdf_file(tmp_path), tmp_path / "out.zip")
    data = markdown_to_structured(
        "# Title\n\nSome body $U$.\n\n![image](x.png)\n\n$$x=1$$\n\n## References\n\n[1] Citation"
    )
    text, _ = convert_mineru_structured_content_to_markdown(data, tmp_path / "light.md")
    assert data["is_full_document"] is False and data["warnings"]
    assert "![" not in text and "$$x=1$$" in text and "$U$" in text


def test_cloud_bad_schema_is_not_faked():
    with pytest.raises(MinerUArtifactError):
        normalize_archive(archive([]))


@pytest.mark.parametrize(
    "doi,route",
    [
        ("10.1109/cvpr.2013.98", Route.IEEE),
        ("10.1109/tpami.2020.3008413", Route.IEEE),
        ("10.48550/arxiv.2403.12534", Route.ARXIV),
        ("10.1007/s11263-024-02273-7", Route.SPRINGER),
        ("10.1002/test", Route.PUBLIC_PDF),
        ("10.1145/test", Route.PUBLIC_PDF),
    ],
)
def test_added_routes(doi, route):
    assert route_doi(doi).route == route and route_doi(doi).supported


def test_public_pdf_rejects_mismatched_metadata_and_html_paywall(tmp_path):
    settings = Settings(None, None, None)

    def handle(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1109/example",
                        "title": ["Correct title"],
                        "link": [
                            {
                                "URL": "https://publisher.example/full.pdf",
                                "content-type": "application/pdf",
                            }
                        ],
                    }
                },
            )
        return (
            httpx.Response(200, text="<html>Sign in to obtain access</html>")
            if request.url.host == "publisher.example"
            else httpx.Response(403)
        )

    metadata, pdf, _, _, warnings = discover_pdf(
        "10.1109/example", settings, transport=httpx.MockTransport(handle)
    )
    assert metadata["title"] == "Correct title" and pdf is None and warnings
    with pytest.raises(ValueError, match="different DOI"):
        discover_pdf("10.1109/other", settings, transport=httpx.MockTransport(handle))


def test_flat_export_collisions_idempotence_partial_and_source_preservation(tmp_path):
    root, dest = tmp_path / "canonical", tmp_path / "flat"
    for n in range(3):
        folder = root / str(n)
        folder.mkdir(parents=True)
        (folder / "paper_llm.md").write_text(
            "# Same: title / name\n\nOriginal body.", encoding="utf-8"
        )
        (folder / "qa.json").write_text(
            json.dumps(
                {
                    "doi": f"10.1234/{n}",
                    "source": "public_metadata_partial" if n == 2 else "elsevier_xml",
                    "status": "warning" if n == 2 else "success",
                }
            )
        )
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    rows = export_markdown(root, dest)
    assert len(rows) == 2 and len({r["filename"].casefold() for r in rows}) == 2
    assert rows == export_markdown(root, dest)
    rows = export_markdown(root, dest, include_partial=True)
    assert len(rows) == 3 and "[ABSTRACT ONLY]" in rows[2]["filename"]
    assert "[ABSTRACT ONLY" in (dest / rows[2]["filename"]).read_text(encoding="utf-8")
    assert before == {p: p.read_bytes() for p in before}
    with pytest.raises(ValueError):
        export_markdown(root, root / "flat")
    assert safe_title("CON") == "Paper CON"
    assert "/" not in safe_title("a/b?")


def test_export_command_does_not_load_models_or_require_keys(tmp_path):
    folder = tmp_path / "library/a"
    folder.mkdir(parents=True)
    (folder / "paper_llm.md").write_text("# Title\n\nBody")
    result = CliRunner().invoke(
        app, ["export-markdown", str(tmp_path / "flat"), "--library-root", str(folder.parent)]
    )
    assert result.exit_code == 0 and "Exported = 1" in result.stdout


def test_flat_export_uses_pdf_metadata_when_heading_is_not_title(tmp_path):
    root = tmp_path / "library"
    folder = root / "10.1109_example"
    folder.mkdir(parents=True)
    (folder / "paper_llm.md").write_text("## Methods\n\nBody", encoding="utf-8")
    pdf = pdf_file(tmp_path)
    writer = PdfWriter()
    writer.append(pdf)
    writer.add_metadata({"/Title": "Actual article name"})
    with (folder / "paper.pdf").open("wb") as handle:
        writer.write(handle)
    assert export_markdown(root, tmp_path / "flat")[0]["filename"] == "Actual article name.md"


def test_lightweight_first_title_is_preserved_as_document_title(tmp_path):
    data = markdown_to_structured("# Real paper title\n\nBody.\n\n## References\n\n[1] Ref")
    text, _ = convert_mineru_structured_content_to_markdown(data, tmp_path / "paper.md")
    assert text.startswith("# Real paper title\n")


def test_flat_export_does_not_overwrite_manual_changes(tmp_path):
    folder = tmp_path / "library/a"
    folder.mkdir(parents=True)
    (folder / "paper_llm.md").write_text("# Actual title\n\nOriginal body")
    destination = tmp_path / "flat"
    row = export_markdown(folder.parent, destination)[0]
    original = destination / row["filename"]
    original.write_text("My manual notes")
    new_row = export_markdown(folder.parent, destination)[0]
    assert original.read_text() == "My manual notes"
    assert new_row["filename"] != row["filename"]


def test_doi_unknown_local_pdf_uses_same_renderer_and_no_fake_identifier(tmp_path, monkeypatch):
    from paperflow.parsers import mineru_api
    from paperflow.parsers.mineru_pdf import MinerUParseResult
    from paperflow.pipeline import process_pdf

    def fake_parse(pdf, output_zip, **kwargs):
        structured = content_list_to_structured(items())
        with zipfile.ZipFile(output_zip, "w") as z:
            z.writestr("structured_content.json", json.dumps(structured))
        return MinerUParseResult(pdf, output_zip, ("structured_content.json",))

    monkeypatch.setattr(mineru_api, "parse_pdf_with_mineru_api", fake_parse)
    settings = replace(Settings(None, None, None), mineru_api_token="test-token")
    result = process_pdf(
        pdf_file(tmp_path),
        output_root=tmp_path / "library",
        title="Research paper",
        settings=settings,
    )
    assert result.doi is None and result.status == "warning"
    qa = json.loads(result.qa_path.read_text(encoding="utf-8"))
    assert qa["doi"] is None and qa["mineru"]["backend"] == "api"
    assert qa["mineru"]["tier"] == "vlm"
    assert "mineru_page_count_mismatch" in qa["warnings"]
    rows = export_markdown(tmp_path / "library", tmp_path / "flat")
    assert rows[0]["filename"] == "Research paper.md"
    assert "References" in (tmp_path / "flat/Research paper.md").read_text(encoding="utf-8")


def test_user_mineru_api_alias_loads_without_exposing_value(monkeypatch):
    from paperflow.config import load_settings, redact_error

    monkeypatch.setenv("MINERU_API", "private-test-value-not-a-real-token")
    monkeypatch.delenv("MINERU_API_TOKEN", raising=False)
    monkeypatch.delenv("MINERU_API_KEY", raising=False)
    # Do not load the real project .env in this isolated alias test.
    monkeypatch.setattr("paperflow.config.load_dotenv", lambda: None)
    settings = load_settings()
    assert settings.mineru_api_token == "private-test-value-not-a-real-token"
    assert "private-test-value-not-a-real-token" not in redact_error(
        "error private-test-value-not-a-real-token"
    )


def test_mineru_defaults_to_api_without_env(monkeypatch):
    from paperflow.config import load_settings

    monkeypatch.setattr("paperflow.config.load_dotenv", lambda: None)
    monkeypatch.delenv("MINERU_BACKEND", raising=False)
    assert Settings(None, None, None).mineru_backend == "api"
    assert load_settings().mineru_backend == "api"


def test_missing_api_token_never_starts_local_mineru(tmp_path, monkeypatch):
    import subprocess

    from paperflow.pipeline import process_pdf

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("local process started"))
    with pytest.raises(MinerUExecutionError, match="MINERU_API_TOKEN is required"):
        process_pdf(pdf_file(tmp_path), output_root=tmp_path / "library",
                    settings=Settings(None, None, None))


def test_api_failure_never_falls_back_to_local_or_light(tmp_path, monkeypatch):
    import subprocess

    from paperflow.parsers import mineru_api
    from paperflow.pipeline import process_pdf

    calls = []

    def fail_api(*args, **kwargs):
        calls.append(kwargs)
        raise MinerUExecutionError("MinerU request failed (HTTP 429); check access/quota.")

    monkeypatch.setattr(mineru_api, "parse_pdf_with_mineru_api", fail_api)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("local process started"))
    with pytest.raises(MinerUExecutionError, match="HTTP 429"):
        process_pdf(pdf_file(tmp_path), output_root=tmp_path / "library",
                    settings=Settings(None, None, None, mineru_api_token="test-token"))
    assert len(calls) == 1 and calls[0]["lightweight"] is False


def test_old_local_backend_has_migration_error_without_starting_process(tmp_path, monkeypatch):
    import subprocess

    from paperflow.pipeline import process_pdf

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("local process started"))
    with pytest.raises(ValueError, match="Set MINERU_BACKEND=api"):
        process_pdf(pdf_file(tmp_path), output_root=tmp_path / "library",
                    settings=Settings(None, None, None, mineru_backend="local"))


def test_cloud_reference_block_mapping_is_lossless():
    from paperflow.parsers.mineru_api import normalize_structured

    original = "[27] O. Oreifej, Z. Liu. HON4D. DOI 10.1109/CVPR.2013.98"
    data = {"pages": [{"blocks": [{"type": "ref_text", "content": original}]}]}
    block = normalize_structured(data)["pages"][0]["blocks"][0]
    assert block["content"] == original and block["type"] == "list"
    assert block["sub_type"] == "ref_text"


def test_settings_repr_never_contains_credentials():
    settings = Settings(
        "elsevier-private",
        "oa-private",
        "meta-private",
        mineru_api_token="mineru-private",
        openalex_api_key="openalex-private",
        ieee_api_key="ieee-private",
    )
    assert "private" not in repr(settings)


def test_markdown_title_precedes_office_pdf_filename(tmp_path):
    folder = tmp_path / "library/paper"
    folder.mkdir(parents=True)
    (folder / "paper_llm.md").write_text("# Real article title\n\nBody", encoding="utf-8")
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "Microsoft Word - 00165.doc"})
    with (folder / "paper.pdf").open("wb") as f:
        writer.write(f)
    row = export_markdown(folder.parent, tmp_path / "flat")[0]
    assert row["filename"] == "Real article title.md"


def test_elsevier_explicit_pdf_does_not_require_xml_api_entitlement(tmp_path, monkeypatch):
    from paperflow import pipeline

    seen = {}

    def fake(paths, settings, **kwargs):
        seen.update(kwargs)
        return "parsed-local-pdf"

    monkeypatch.setattr(pipeline, "_process_pdf_with_mineru", fake)
    result = pipeline.process_doi(
        "10.1016/j.apenergy.example",
        pdf_path=tmp_path / "authorized.pdf",
        library_root=tmp_path / "library",
        settings=Settings(None, None, None),
    )
    assert result == "parsed-local-pdf" and seen["source_file"] == tmp_path / "authorized.pdf"
    assert seen["route"] == Route.ELSEVIER


def test_existing_xml_checks_identity_and_conflicting_inputs(tmp_path):
    from paperflow.pipeline import process_doi

    source = tmp_path / "paper.xml"
    source.write_text("<response><coredata><doi>10.1016/another-paper</doi></coredata></response>")
    with pytest.raises(ValueError, match="does not match"):
        process_doi(
            "10.1016/requested-paper",
            xml_path=source,
            library_root=tmp_path / "library",
            settings=Settings(None, None, None),
        )
    with pytest.raises(ValueError, match="only one"):
        process_doi(
            "10.1016/requested-paper",
            xml_path=source,
            pdf_path=tmp_path / "paper.pdf",
            library_root=tmp_path / "library",
            settings=Settings(None, None, None),
        )


def test_flat_partial_export_reserves_windows_path_length(tmp_path):
    folder = tmp_path / "library" / "paper"
    folder.mkdir(parents=True)
    title = "A comparative study on energy demand " * 6
    (folder / "paper_llm.md").write_text("# " + title + "\n\nAbstract", encoding="utf-8")
    (folder / "qa.json").write_text(
        json.dumps({"status": "warning", "source": "springer_restricted_partial"}),
        encoding="utf-8",
    )
    destination = tmp_path / ("d" * 60)
    rows = export_markdown(folder.parent, destination, include_partial=True)
    target = destination / rows[0]["filename"]
    assert len(str(target.with_suffix(".md.tmp"))) <= 240
    assert "[ABSTRACT ONLY]" in target.name
    assert "NOT FULL TEXT" in target.read_text(encoding="utf-8")
    assert rows[0]["title"] == title.strip()


@pytest.mark.parametrize("pages", [1, 9])
def test_elsevier_pdf_fallback_checks_completeness_before_mineru(tmp_path, monkeypatch, pages):
    from io import BytesIO

    from paperflow import pipeline
    from paperflow.pipeline import PipelineContentError

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    xml = b"<root><coredata><startingPage>274</startingPage><endingPage>282</endingPage></coredata></root>"

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def fetch_xml(self, doi):
            return xml

        def fetch_pdf(self, doi):
            return buffer.getvalue()

    calls = []

    def parse(paths, settings, **kwargs):
        calls.append(kwargs)
        return "complete-pdf-parsed"

    monkeypatch.setattr(pipeline, "ElsevierClient", Client)
    monkeypatch.setattr(pipeline, "_process_pdf_with_mineru", parse)
    settings = Settings("test-key", None, None)
    if pages == 1:
        with pytest.raises(PipelineContentError, match="actual_pages=1; expected_pages=9"):
            pipeline.process_doi("10.1016/example", library_root=tmp_path, settings=settings)
        assert not calls
        qa = json.loads((tmp_path / "10.1016_example/qa.json").read_text(encoding="utf-8"))
        assert qa["status"] == "failed" and qa["full_text_available"] is False
    else:
        assert pipeline.process_doi("10.1016/example", library_root=tmp_path, settings=settings) == "complete-pdf-parsed"
        assert calls[0]["source"] == "elsevier_pdf_mineru"
