from __future__ import annotations

import sys
from importlib.metadata import (
    PackageNotFoundError,
)
from importlib.metadata import (
    version as package_version,
)
from pathlib import Path
from typing import Annotated

import typer

from paperflow.batch import (
    BatchItemResult,
    run_batch,
)
from paperflow.config import ConfigError, load_settings, redact_error
from paperflow.language import t
from paperflow.parsers.mineru_pdf import (
    MinerUError,
)
from paperflow.pipeline import (
    PaperResult,
    PipelineError,
    process_doi,
)
from paperflow.sources.building_simulation_pdf import (
    BuildingSimulationPdfError,
)
from paperflow.sources.elsevier import (
    ElsevierError,
)
from paperflow.sources.nature_pdf import (
    NaturePdfError,
)

DEFAULT_LIBRARY_ROOT = Path("workspace/library")


app = typer.Typer(
    name="paperflow",
    help=("Academic paper acquisition and LLM-ready conversion pipeline."),
    no_args_is_help=True,
)


def _get_version() -> str:
    try:
        return package_version("paperflow")

    except PackageNotFoundError:
        return "unknown"


def _display_result(
    result: PaperResult,
    *,
    markdown_dir: Path | None = None,
) -> None:
    typer.echo()

    typer.echo(f"DOI = {result.doi or 'unknown (local PDF)'}")

    typer.echo(f"Route = {result.route}")

    typer.echo(f"Source = {result.source}")

    typer.echo(f"Status = {result.status}")

    typer.echo("Fallback used = " + ("yes" if result.fallback_used else "no"))

    if result.raw_markdown_path is not None:
        typer.echo(f"Raw Markdown = {result.raw_markdown_path}")

    if result.llm_markdown_path is not None:
        typer.echo(f"LLM Markdown = {result.llm_markdown_path}")

    typer.echo(f"QA = {result.qa_path}")

    if result.source in {'public_metadata_partial', 'springer_restricted_partial'} and result.doi:
        typer.echo(t('当前仅有摘要/元数据，尚未取得全文。', 'Only abstract/metadata available; no full text.'))
        _display_pdf_recovery(result.doi, result.qa_path.parent.parent, markdown_dir)


def _display_batch_item(
    item: BatchItemResult,
    total: int,
    *,
    library_root: Path | None = None,
    markdown_dir: Path | None = None,
) -> None:
    prefix = f"[{item.index}/{total}] {item.doi}"

    if item.status == "failed":
        typer.echo(f"{prefix} -> FAILED")

        typer.echo(f"    {item.error}")
        if library_root is not None:
            _display_pdf_recovery(item.doi, library_root, markdown_dir)
        return

    if item.source in {"springer_restricted_partial", "public_metadata_partial"}:
        typer.echo(f"{prefix} -> warning (restricted access; partial XML/metadata)")
        if library_root is not None:
            _display_pdf_recovery(item.doi, library_root, markdown_dir)
        return

    typer.echo(f"{prefix} -> {item.status} ({item.source})")


def _display_pdf_recovery(doi, library_root, markdown_dir=None):
    for line in _pdf_recovery_lines(doi, library_root, markdown_dir):
        typer.echo('    ' + line)


def _pdf_recovery_lines(doi, library_root, markdown_dir=None):
    from paperflow.pdf_resume import create_pdf_recovery
    from paperflow.recovery import MultipleLocalPdfError, find_local_pdf
    from paperflow.storage import build_paper_paths

    try:
        paths = build_paper_paths(doi, library_root=library_root.resolve())
    except (ValueError, TypeError):
        return []
    launcher = Path(sys.executable).with_name('paperflow.exe')
    executable = f'"{launcher}"' if launcher.is_file() else 'paperflow'
    try:
        pdf = find_local_pdf(paths.directory)
        ambiguous = False
    except MultipleLocalPdfError:
        pdf, ambiguous = None, True
    pdf_example = pdf or paths.directory / '你的正文文件名.pdf'
    command = (f'{executable} process "{paths.doi}" --pdf "{pdf_example}" '
               f'--library-root "{library_root.resolve()}"')
    if markdown_dir is not None:
        command += f' --markdown-dir "{markdown_dir.resolve()}"'
    if pdf is not None:
        lines = [t('已有 PDF 已保留；若是解析/API失败，无需重新下载：',
                   'Existing PDF preserved; parsing/API failures do not require another download:'), str(pdf)]
    elif ambiguous:
        lines = [t('目录内有多个PDF，请仅保留正文，移出补充材料或重复版本，无需改名：',
                   'Multiple PDFs: keep one main article; remove supplements/duplicates without renaming:'),
                 str(paths.directory)]
    else:
        lines = [t('请自行获取这篇论文的正文 PDF，保留原文件名，放入：',
                   'Obtain the main article PDF, keep its original name and place it in:'), str(paths.directory)]
    try:
        launcher = create_pdf_recovery(doi, library_root, markdown_dir)
        lines.extend([t('PDF 必须对应这篇论文；放好后双击：',
                        'Use the matching article PDF, then double-click:'), str(launcher)])
    except (OSError, ValueError) as exc:
        lines.append(t('无法生成双击入口：', 'Cannot create launcher: ') + redact_error(str(exc)))
    return [*lines, t('也可使用下面的转换命令（请替换为实际PDF文件名）：',
                     'Alternative command (replace the example with the actual PDF filename):'), command]


@app.callback()
def main() -> None:
    """PaperFlow command line interface."""


@app.command()
def version() -> None:
    """Show PaperFlow version."""

    typer.echo(f"PaperFlow {_get_version()}")


@app.command("process")
def process_command(
    doi: Annotated[
        str,
        typer.Argument(
            help="DOI to process.",
        ),
    ],
    pdf: Annotated[
        Path | None,
        typer.Option(
            "--pdf",
            help=("Optional local PDF override for PDF-based routes."),
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    library_root: Annotated[
        Path,
        typer.Option(
            "--library-root",
            help=("PaperFlow library output directory."),
            file_okay=False,
            dir_okay=True,
            resolve_path=False,
        ),
    ] = DEFAULT_LIBRARY_ROOT,
    mineru_backend: Annotated[
        str | None,
        typer.Option(
            "--mineru-backend", help="api (default, precision token), or api-light (limited quality)"
        ),
    ] = None,
    markdown_dir: Annotated[
        Path | None,
        typer.Option("--markdown-dir", help="Mode 2: flat title-named Markdown reading copies"),
    ] = None,
    pdf_url: Annotated[
        str | None,
        typer.Option("--pdf-url", help="Authorized/public PDF URL for additional DOI routes"),
    ] = None,
    xml: Annotated[
        Path | None,
        typer.Option(
            "--xml",
            exists=True,
            dir_okay=False,
            help="Existing full Elsevier XML; no network acquisition",
        ),
    ] = None,
) -> None:
    """
    Process one DOI.
    """

    try:
        kwargs = {}
        if mineru_backend:
            from dataclasses import replace

            kwargs["settings"] = replace(load_settings(), mineru_backend=mineru_backend)
        if pdf_url:
            kwargs["pdf_url"] = pdf_url
        if xml:
            kwargs["xml_path"] = xml
        result = process_doi(doi, pdf_path=pdf, library_root=library_root, **kwargs)
        if markdown_dir:
            from paperflow.storage.flat_export import export_markdown

            export_markdown(library_root, markdown_dir)

    except (
        BuildingSimulationPdfError,
        ConfigError,
        ElsevierError,
        MinerUError,
        NaturePdfError,
        OSError,
        PipelineError,
        ValueError,
    ) as exc:
        typer.echo(
            f"ERROR: {type(exc).__name__}: {redact_error(str(exc))}",
            err=True,
        )

        if isinstance(exc, (PipelineError, ElsevierError, NaturePdfError,
                            BuildingSimulationPdfError, MinerUError)):
            _display_pdf_recovery(doi, library_root, markdown_dir)

        raise typer.Exit(code=1) from exc

    _display_result(result, markdown_dir=markdown_dir)


@app.command("process-list")
def process_list_command(
    input_file: Annotated[
        Path,
        typer.Argument(
            help=("Text file containing one DOI per line."),
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    library_root: Annotated[
        Path,
        typer.Option(
            "--library-root",
            help=("Directory containing the per-paper output directories."),
            file_okay=False,
            dir_okay=True,
            resolve_path=False,
        ),
    ] = DEFAULT_LIBRARY_ROOT,
    results: Annotated[
        Path | None,
        typer.Option(
            "--results",
            help=("Optional batch result CSV path. Defaults to <library-root>/batch_results.csv."),
            file_okay=True,
            dir_okay=False,
            resolve_path=False,
        ),
    ] = None,
    mineru_backend: Annotated[
        str | None, typer.Option("--mineru-backend", help="api (default), or api-light")
    ] = None,
    markdown_dir: Annotated[
        Path | None, typer.Option("--markdown-dir", help="Mode 2: flat Markdown reading copies")
    ] = None,
) -> None:
    """
    Process a text file containing one DOI per line.
    """

    typer.echo(f"Input = {input_file}")

    typer.echo(f"Library root = {library_root}")

    typer.echo()

    try:
        if markdown_dir:
            library, reading = library_root.resolve(), markdown_dir.resolve()
            if library == reading or reading.is_relative_to(library) or library.is_relative_to(reading):
                raise ValueError('Markdown reading folder must be separate from the canonical library.')
        kwargs = {}
        if mineru_backend:
            from dataclasses import replace

            kwargs["settings"] = replace(load_settings(), mineru_backend=mineru_backend)
        result = run_batch(
            input_file,
            library_root=library_root,
            results_path=results,
            on_result=lambda item, total: _display_batch_item(
                item, total, library_root=library_root, markdown_dir=markdown_dir),
            **kwargs,
        )
        if markdown_dir:
            from paperflow.storage.flat_export import export_markdown

            rows = export_markdown(library_root, markdown_dir)
            typer.echo(t('已集中导出完整正文 Markdown：', 'Exported full-text Markdown: ')
                       + f'{len(rows)}; {markdown_dir.resolve()}')

    except (
        OSError,
        ValueError,
    ) as exc:
        typer.echo(
            f"ERROR: {type(exc).__name__}: {redact_error(str(exc))}",
            err=True,
        )

        raise typer.Exit(code=1) from exc

    typer.echo()

    typer.echo("Batch complete")

    typer.echo(f"Total = {result.total}")

    typer.echo(f"Success = {result.success_count}")

    typer.echo(f"Warning = {result.warning_count}")

    typer.echo(f"Failed = {result.failed_count}")

    typer.echo(f"Results = {result.results_path}")
    from paperflow.pdf_resume import create_batch_pdf_recovery

    batch_launcher = create_batch_pdf_recovery(library_root, markdown_dir)
    typer.echo(t('补齐多篇PDF后，只需双击这个批量入口：',
                 'After adding PDFs, double-click this batch recovery launcher: ') + str(batch_launcher))
    pending = [item for item in result.items if item.status == 'failed' or item.source in
               {'springer_restricted_partial', 'public_metadata_partial'}]
    if pending:
        notes = [t('本批处理失败或尚未取得全文的条目', 'Failed or missing full-text items'),
                 t('请先检查失败原因；需补PDF时只放对应论文正文，勿放补充材料。',
                   'Check errors first; add matching main-article PDFs, not supplementary files.'),
                 t('多篇PDF保留原名，分别放进下列对应论文目录，然后只双击一次：',
                   'Keep original PDF names in matching paper folders, then double-click once:'),
                 str(batch_launcher),
                 t('缺PDF和已生成正文的条目会跳过；处理结果见补PDF批量结果.csv。',
                   'Missing/converted items are skipped; results: 补PDF批量结果.csv.'), '']
        for item in pending:
            notes.extend([f'DOI：{item.doi}', redact_error(item.error),
                          *_pdf_recovery_lines(item.doi, library_root, markdown_dir), ''])
        library_root.mkdir(parents=True, exist_ok=True)
        note_path = library_root / '待补PDF说明.txt'
        note_path.write_text('\n'.join(notes), encoding='utf-8')
        typer.echo(t('补 PDF 的目录和转换命令已保存：', 'PDF recovery instructions saved: ')
                   + str(note_path.resolve()))


@app.command("export-markdown")
def export_markdown_command(
    destination: Annotated[Path, typer.Argument(help="Flat reading folder (mode 2)")],
    library_root: Annotated[Path, typer.Option("--library-root")] = DEFAULT_LIBRARY_ROOT,
    include_partial: Annotated[
        bool,
        typer.Option(
            "--include-partial", help="Include clearly marked metadata/abstract-only copies"
        ),
    ] = False,
):
    """Export existing cleaned Markdown; no download, GPU, or reparsing."""
    from paperflow.storage.flat_export import export_markdown

    try:
        rows = export_markdown(library_root, destination, include_partial=include_partial)
    except (OSError, ValueError) as exc:
        typer.echo("ERROR: " + redact_error(str(exc)), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Exported = {len(rows)}; Markdown folder = {destination}")


@app.command("process-document")
def process_document_command(
    document: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output_root: Annotated[Path, typer.Option("--output-root")] = DEFAULT_LIBRARY_ROOT,
    doi: Annotated[str | None, typer.Option("--doi")] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
    markdown_dir: Annotated[Path | None, typer.Option("--markdown-dir")] = None,
):
    """Import authorized local JATS/TEI XML, article HTML or EPUB; no GPU/network."""
    import zipfile

    from paperflow.pipeline import process_document
    from paperflow.storage.flat_export import export_markdown

    try:
        result = process_document(document, doi=doi, output_root=output_root, title=title)
        if markdown_dir:
            export_markdown(output_root, markdown_dir)
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
        typer.echo("ERROR: " + redact_error(str(exc)), err=True)
        raise typer.Exit(1) from exc
    _display_result(result)


@app.command("parse-pdf")
def parse_pdf_command(
    pdf: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output_root: Annotated[Path, typer.Option("--output-root")] = DEFAULT_LIBRARY_ROOT,
    title: Annotated[str | None, typer.Option("--title")] = None,
    mineru_backend: Annotated[str | None, typer.Option("--mineru-backend")] = None,
    markdown_dir: Annotated[Path | None, typer.Option("--markdown-dir")] = None,
):
    """Parse an authorized local PDF, including papers whose DOI is unknown."""
    from dataclasses import replace

    from paperflow.pipeline import process_pdf
    from paperflow.storage.flat_export import export_markdown

    settings = load_settings()
    if mineru_backend:
        settings = replace(settings, mineru_backend=mineru_backend)
    try:
        result = process_pdf(pdf, output_root=output_root, title=title, settings=settings)
        if markdown_dir:
            export_markdown(output_root, markdown_dir)
    except (OSError, ValueError, ConfigError, MinerUError, PipelineError) as exc:
        typer.echo("ERROR: " + redact_error(str(exc)), err=True)
        raise typer.Exit(1) from exc
    _display_result(result)


@app.command("process-url")
def process_url_command(
    url: Annotated[str, typer.Argument(help="Official JMLR/PMLR paper page or OpenReview forum URL")],
    output_root: Annotated[Path, typer.Option("--output-root")] = DEFAULT_LIBRARY_ROOT,
    download_only: Annotated[bool, typer.Option("--download-only", help="Acquire/check PDF without MinerU")] = False,
    mineru_backend: Annotated[str | None, typer.Option("--mineru-backend")] = None,
    markdown_dir: Annotated[Path | None, typer.Option("--markdown-dir")] = None,
):
    """Acquire a public academic-platform paper, preserving its identity and version."""
    import json
    from dataclasses import replace

    import httpx

    from paperflow.pipeline import process_pdf
    from paperflow.sources.academic_platforms import fetch_platform_paper
    from paperflow.storage.flat_export import export_markdown

    settings = load_settings()
    if mineru_backend:
        settings = replace(settings, mineru_backend=mineru_backend)
    try:
        if markdown_dir:
            library, reading = output_root.resolve(), markdown_dir.resolve()
            if reading == library or reading.is_relative_to(library) or library.is_relative_to(reading):
                raise ValueError('Flat export must be a separate directory outside the canonical library.')
        pdf, metadata = fetch_platform_paper(url, output_root=output_root / "acquisitions",
                                            timeout=settings.http_timeout)
        typer.echo(f"Source = {metadata['source']}; PDF = {pdf}")
        typer.echo(f"Identity verified = yes; completeness verified = {metadata['completeness_verified']}")
        if metadata['platform'] == 'openreview':
            typer.echo("OpenReview: " + metadata['publication_status'])
        if download_only:
            return
        if metadata['expected_pages'] and not metadata['completeness_verified']:
            raise ValueError('PDF page count differs from official metadata; conversion stopped.')
        result = process_pdf(pdf, output_root=output_root, title=metadata['title'], settings=settings)
        directory = result.qa_path.parent
        (directory / 'acquisition.json').write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        target = directory / 'metadata.json'
        existing = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        existing.update({key: value for key, value in metadata.items()
                         if key not in {'pdf_validation', 'full_text_available'}})
        target.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
        if markdown_dir:
            export_markdown(output_root, markdown_dir)
    except (httpx.HTTPError, OSError, ValueError, ConfigError, MinerUError, PipelineError) as exc:
        # Network exceptions may include signed URLs; do not render their messages.
        message = type(exc).__name__ if isinstance(exc, httpx.HTTPError) else redact_error(str(exc))
        typer.echo("ERROR: " + message, err=True)
        raise typer.Exit(1) from exc
    _display_result(result)


if __name__ == "__main__":
    app()
