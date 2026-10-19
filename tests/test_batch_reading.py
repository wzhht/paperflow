import csv
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paperflow import batch, cli
from paperflow.pipeline import PaperResult, PipelineContentError
from paperflow.storage import build_paper_paths
from paperflow.storage.flat_export import export_markdown

ROOT = Path(__file__).resolve().parents[1]


def test_100_papers_export_to_one_folder_without_reparse_or_overwrite(tmp_path, monkeypatch):
    source = tmp_path / 'dois.txt'
    source.write_text('\n'.join(f'10.1016/test.{n}' for n in range(100)), encoding='utf-8')
    library, reading = tmp_path / '原始资料', tmp_path / '整理好的Markdown'
    calls = []

    def process(doi, **kwargs):
        calls.append(doi)
        paths = build_paper_paths(doi, library_root=kwargs['library_root'])
        paths.ensure()
        number = int(doi.rsplit('.', 1)[1])
        title = 'Same: title' if number < 2 else f'Building study {number}'
        paths.llm_md.write_text(f'# {title}\n\n完整正文{number}\n\n## References\nA reference.', encoding='utf-8')
        paths.qa_json.write_text(json.dumps({'doi': doi, 'source': 'elsevier_xml',
                                             'status': 'success'}), encoding='utf-8')
        return PaperResult(doi, 'elsevier', 'elsevier_xml', 'success', None, paths.llm_md, paths.qa_json)

    monkeypatch.setattr(batch, 'process_doi', process)
    result = CliRunner().invoke(cli.app, ['process-list', str(source), '--library-root',
                                          str(library), '--markdown-dir', str(reading)])
    assert result.exit_code == 0, result.output
    assert len(calls) == 100 and len(list(reading.glob('*.md'))) == 100
    assert not any(p.is_dir() for p in reading.iterdir())
    with (reading / 'export_manifest.csv').open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert len({r['filename'].casefold() for r in rows}) == 100
    for row in rows:
        assert (reading / row['filename']).read_bytes() == Path(row['source_path']).read_bytes()
    assert len(export_markdown(library, reading)) == 100 and len(calls) == 100
    assert len(list(reading.glob('*.md'))) == 100


def test_failed_paper_has_pdf_folder_and_resume_command_in_terminal_and_file(tmp_path, monkeypatch):
    source = tmp_path / 'dois.txt'
    doi = '10.1021/acsenergylett.4c01233'
    source.write_text(doi)
    library, reading = tmp_path / 'library', tmp_path / 'reading'

    def process(*args, **kwargs):
        raise PipelineContentError('No full text')

    monkeypatch.setattr(batch, 'process_doi', process)
    result = CliRunner().invoke(cli.app, ['process-list', str(source), '--library-root',
                                          str(library), '--markdown-dir', str(reading)])
    assert result.exit_code == 0, result.output
    pdf = build_paper_paths(doi, library_root=library).pdf
    notes = (library / '待补PDF说明.txt').read_text(encoding='utf-8')
    assert str(pdf.parent) in result.output and str(pdf.parent) in notes
    assert '保留原文件名' in notes and '重命名' not in notes
    assert '--pdf' in notes and '--markdown-dir' in notes
    assert (pdf.parent / 'Retry_PDF.cmd').is_file()
    assert 'Retry_PDF.cmd' in notes and 'Retry_PDF.cmd' in result.output
    assert (library / 'Retry_PDF_Batch.cmd').is_file()
    assert 'Retry_PDF_Batch.cmd' in notes
    assert not list(reading.glob('*.md'))


def test_single_metadata_only_paper_also_shows_pdf_recovery_with_reading_folder(tmp_path, monkeypatch):
    doi = '10.1021/acsenergylett.4c01233'
    library, reading = tmp_path / 'library', tmp_path / 'reading'
    paths = build_paper_paths(doi, library_root=library)
    paths.ensure()
    paths.llm_md.write_text('# Paper\n\nAbstract only.')
    paths.qa_json.write_text(json.dumps({'status': 'warning', 'source': 'public_metadata_partial'}))
    monkeypatch.setattr(cli, 'process_doi', lambda *a, **k: PaperResult(
        doi, 'public_pdf', 'public_metadata_partial', 'warning', None, paths.llm_md, paths.qa_json))
    result = CliRunner().invoke(cli.app, ['process', doi, '--library-root', str(library),
                                         '--markdown-dir', str(reading)])
    assert result.exit_code == 0, result.output
    assert str(paths.directory) in result.output and '--markdown-dir' in result.output
    assert not list(reading.glob('*.md'))


def test_invalid_reading_destination_fails_before_batch(tmp_path, monkeypatch):
    source = tmp_path / 'dois.txt'
    source.write_text('10.1016/test')
    monkeypatch.setattr(cli, 'run_batch', lambda *a, **k: pytest.fail('must fail before acquisition'))
    result = CliRunner().invoke(cli.app, ['process-list', str(source), '--library-root',
                                          str(tmp_path / 'library'), '--markdown-dir',
                                          str(tmp_path / 'library/reading')])
    assert result.exit_code == 1


def test_inline_scientific_title_markup_is_not_part_of_reading_filename(tmp_path):
    library = tmp_path / 'library'
    folder = library / 'a'
    folder.mkdir(parents=True)
    (folder / 'metadata.json').write_text(json.dumps({'title': 'FAPbI<sub>3</sub> &amp; energy'}))
    (folder / 'paper_llm.md').write_text('# Paper\n\nOriginal body.')
    rows = export_markdown(library, tmp_path / 'reading')
    assert rows[0]['filename'] == 'FAPbI3 & energy.md'


def test_friendly_script_only_delegates_to_existing_cli(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('batch_reading', ROOT / 'scripts/batch_markdown.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / 'list.txt'
    source.write_text('10.1016/test')
    output = tmp_path / 'my reading'
    monkeypatch.setattr(sys, 'argv', ['batch_markdown', str(source), '--output-dir', str(output)])

    def run(command, **kwargs):
        assert command[0] == sys.executable
        assert 'process-list' in command and str(output / '整理好的Markdown') in command
        assert str(output / '原始资料') in command and kwargs['check'] is False
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, 'run', run)
    assert module.main() == 0


@pytest.mark.skipif(os.name != 'nt', reason='Windows launcher')
def test_real_windows_launcher_help_does_not_start_downloads():
    launcher = ROOT / 'Batch_Markdown.cmd'
    content = launcher.read_bytes()
    assert b'\n' not in content.replace(b'\r\n', b'')
    result = subprocess.run(['cmd.exe', '/d', '/c', 'call', str(launcher), '--help'],
                            input=b'\n', capture_output=True, timeout=15, check=False)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    assert result.returncode == 0 and '--output-dir' in output, output
    assert 'not recognized' not in output


@pytest.mark.skipif(os.name != 'nt', reason='Windows first-extraction guidance')
def test_fresh_extraction_launcher_shows_install_steps_without_creating_environment(tmp_path):
    launcher = tmp_path / 'start.cmd'
    launcher.write_bytes((ROOT / 'Batch_Markdown.cmd').read_bytes())
    result = subprocess.run(['cmd.exe', '/d', '/c', 'call', str(launcher)], input=b'\n',
                            capture_output=True, timeout=10, check=False)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    assert result.returncode == 2, output
    assert 'Install.cmd' in output
    assert 'README.md' in output and 'not recognized' not in output
    assert not (tmp_path / '.venv').exists()


@pytest.mark.parametrize('filename', ['paper.pdf', '下载的论文 (最终版) & 100%!.PDF'])
def test_recovery_preserves_pdf_and_calls_existing_cli_with_api_and_reading_folder(
    tmp_path, monkeypatch, filename
):
    from paperflow import pdf_resume as recovery

    library, reading = tmp_path / '资料 & 100% !', tmp_path / '阅读目录'
    doi = '10.1016/test.recovery'
    launcher = recovery.create_pdf_recovery(doi, library, reading)
    paths = build_paper_paths(doi, library_root=library)
    pdf = paths.directory / filename
    pdf.write_bytes(b'existing-pdf-content')
    assert recovery.create_pdf_recovery(doi, library, reading) == launcher
    config = launcher.parent / recovery.CONFIG_NAME
    contents = json.loads(config.read_text(encoding='utf-8'))
    assert contents['doi'] == doi and contents['markdown_dir'] == str(reading.resolve())
    assert 'TOKEN' not in config.read_text(encoding='utf-8')

    def run(command, **kwargs):
        assert command[0] == sys.executable
        assert command[command.index('--pdf') + 1] == str(pdf)
        assert command[command.index('--mineru-backend') + 1] == 'api'
        assert command[command.index('--markdown-dir') + 1] == str(reading.resolve())
        assert command[command.index('--library-root') + 1] == str(library.resolve())
        assert kwargs.get('shell', False) is False and kwargs['check'] is False
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(recovery.subprocess, 'run', run)
    assert recovery.main([str(config)]) == 1
    assert pdf.read_bytes() == b'existing-pdf-content'
    assert list(paths.directory.glob('*.PDF' if filename.endswith('.PDF') else '*.pdf')) == [pdf]


def test_recovery_without_pdf_does_not_start_api(tmp_path, monkeypatch, capsys):
    from paperflow import pdf_resume as recovery

    launcher = recovery.create_pdf_recovery('10.1016/test', tmp_path)
    monkeypatch.setattr(recovery.subprocess, 'run', lambda *a, **k: pytest.fail('missing PDF'))
    assert recovery.main([str(launcher.parent / recovery.CONFIG_NAME)]) == 2
    assert str(launcher.parent) in capsys.readouterr().out


@pytest.mark.skipif(os.name != 'nt', reason='Windows recovery launcher')
def test_real_recovery_cmd_shows_pdf_location_without_flashing_closed(tmp_path):
    from paperflow import pdf_resume as recovery

    launcher = recovery.create_pdf_recovery('10.1016/test', tmp_path / '资料 & 100% !')
    assert b'\n' not in launcher.read_bytes().replace(b'\r\n', b'')
    result = subprocess.run(['cmd.exe', '/d', '/c', 'call', str(launcher)],
                            input=b'\n', capture_output=True, timeout=10, check=False)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    assert result.returncode == 2, output
    assert 'PDF' in output and 'not recognized' not in output and '重命名' not in output, output


def test_single_mineru_failure_offers_recovery_for_existing_pdf(tmp_path, monkeypatch):
    from paperflow.parsers.mineru_pdf import MinerUExecutionError

    doi = '10.1007/s12273-025-1335-6'
    paths = build_paper_paths(doi, library_root=tmp_path)
    paths.ensure()
    paths.pdf.write_bytes(b'keep-existing-pdf')

    def fail(*a, **k):
        raise MinerUExecutionError('API quota exhausted')

    monkeypatch.setattr(cli, 'process_doi', fail)
    result = CliRunner().invoke(cli.app, ['process', doi, '--library-root', str(tmp_path)])
    assert result.exit_code == 1
    assert '已有 PDF 已保留' in result.output and 'Retry_PDF.cmd' in result.output
    assert paths.pdf.read_bytes() == b'keep-existing-pdf'


def test_batch_recovery_processes_ready_pdfs_skips_completed_and_continues_after_failure(
    tmp_path, monkeypatch
):
    from paperflow import pdf_resume as recovery

    library, reading = tmp_path / '原始资料', tmp_path / '整理好的Markdown'
    entries, pdfs = {}, {}
    # Five placed PDFs: one previously complete, one API failure, two new successes, one warning.
    # A sixth item still needs its PDF. Abstract-only files must never count as completed.
    for number in range(6):
        doi = f'10.1016/test.{number}'
        recovery.create_pdf_recovery(doi, library, reading)
        paths = build_paper_paths(doi, library_root=library)
        entries[doi] = paths
        if number != 5:
            pdfs[doi] = paths.directory / f'Publisher download ({number}).PDF'
            pdfs[doi].write_bytes(b'user-pdf')
    entries['10.1016/test.0'].llm_md.write_text('# Completed\n\nBody')
    entries['10.1016/test.0'].qa_json.write_text(json.dumps(
        {'status': 'success', 'source': 'elsevier_xml'}))
    entries['10.1016/test.2'].llm_md.write_text('# Partial\n\nAbstract')
    entries['10.1016/test.2'].qa_json.write_text(json.dumps(
        {'status': 'warning', 'source': 'springer_restricted_partial'}))
    calls = []

    def run(command, **kwargs):
        doi = command[command.index('process') + 1]
        calls.append(doi)
        assert command[command.index('--mineru-backend') + 1] == 'api'
        assert command[command.index('--pdf') + 1] == str(pdfs[doi])
        if doi.endswith('.1'):
            return subprocess.CompletedProcess(command, 1)
        paths = entries[doi]
        paths.llm_md.write_text(f'# Title {doi}\n\nConverted body.')
        paths.qa_json.write_text(json.dumps({
            'doi': doi, 'status': 'warning' if doi.endswith('.4') else 'success',
            'source': 'local_pdf_mineru', 'mineru': {'is_full_document': True},
        }))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(recovery.subprocess, 'run', run)
    launcher = recovery.create_batch_pdf_recovery(library, reading)
    config = launcher.parent / recovery.BATCH_CONFIG_NAME
    assert recovery.main([str(config)]) == 1
    assert calls == [f'10.1016/test.{n}' for n in (1, 2, 3, 4)]
    with (library / '补PDF批量结果.csv').open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert [row['结果'] for row in rows] == ['跳过已有正文', '失败', '成功', '成功', '警告', '缺PDF']
    assert len(list(reading.glob('*.md'))) == 4
    assert all(pdf.read_bytes() == b'user-pdf' for pdf in pdfs.values())
    assert not any(paths.pdf.exists() for paths in entries.values())
    # Second click must not spend credits on the newly converted successes or warnings.
    calls.clear()
    assert recovery.main([str(config)]) == 1
    assert calls == ['10.1016/test.1']


@pytest.mark.skipif(os.name != 'nt', reason='Windows batch recovery launcher')
def test_real_batch_recovery_cmd_skips_missing_pdfs_without_api(tmp_path):
    from paperflow import pdf_resume as recovery

    library = tmp_path / '批量 & 100% !'
    recovery.create_pdf_recovery('10.1016/test', library)
    launcher = recovery.create_batch_pdf_recovery(library)
    assert b'\n' not in launcher.read_bytes().replace(b'\r\n', b'')
    result = subprocess.run(['cmd.exe', '/d', '/c', 'call', str(launcher)],
                            input=b'\n', capture_output=True, timeout=15, check=False)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    assert result.returncode == 0 and 'not recognized' not in output, output
    with (library / '补PDF批量结果.csv').open(encoding='utf-8-sig', newline='') as handle:
        assert next(csv.DictReader(handle))['结果'] == '缺PDF'


def test_multiple_pdfs_are_not_guessed_or_uploaded_and_other_items_continue(tmp_path, monkeypatch):
    from paperflow import pdf_resume as recovery

    recovery.create_pdf_recovery('10.1016/test.1', tmp_path)
    recovery.create_pdf_recovery('10.1016/test.2', tmp_path)
    folder = build_paper_paths('10.1016/test.1', library_root=tmp_path).directory
    for name in ('paper.pdf', '另一版本.PDF'):
        (folder / name).write_bytes(b'unchanged')
    monkeypatch.setattr(recovery.subprocess, 'run', lambda *a, **k: pytest.fail('ambiguous PDF'))
    recovery.create_batch_pdf_recovery(tmp_path)
    assert recovery.main([str(tmp_path / recovery.BATCH_CONFIG_NAME)]) == 1
    with (tmp_path / '补PDF批量结果.csv').open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert [row['结果'] for row in rows] == ['失败', '缺PDF']
    assert '多个PDF' in rows[0]['说明'] and '无需改名' in rows[0]['说明']
    assert all((folder / name).read_bytes() == b'unchanged' for name in ('paper.pdf', '另一版本.PDF'))
