"""English batches must not require users to interpret generated Chinese names."""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paperflow import batch, cli, pdf_resume
from paperflow.pipeline import PipelineContentError

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('existing_legacy', [False, True])
def test_english_batch_names_and_legacy_directory_reuse(tmp_path, monkeypatch, capsys, existing_legacy):
    monkeypatch.setenv('PAPERFLOW_LANGUAGE', 'en')
    spec = importlib.util.spec_from_file_location('english_outputs', ROOT / 'scripts/batch_markdown.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'PROJECT', tmp_path)
    source = tmp_path / 'UK_retrofit_priority_18_dois.txt'
    source.write_text('10.1016/test')
    output = tmp_path / 'workspace/batches' / source.stem
    if existing_legacy:
        (output / '原始资料').mkdir(parents=True)
        (output / '整理好的Markdown').mkdir()
        (output / '整理好的Markdown/kept.md').write_text('Keep')
    monkeypatch.setattr(sys, 'argv', ['batch', str(source)])
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    def run(command, **kwargs):
        assert str(output / ('原始资料' if existing_legacy else 'sources')) in command
        assert str(output / ('整理好的Markdown' if existing_legacy else 'markdown')) in command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, 'run', run)
    assert module.main() == 0
    if existing_legacy:
        assert (output / '整理好的Markdown/kept.md').read_text() == 'Keep'
    else:
        assert not re.search('[一-龥]', capsys.readouterr().out)


def test_english_failed_batch_generates_english_recovery_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('PAPERFLOW_LANGUAGE', 'en')
    source = tmp_path / 'dois.txt'
    source.write_text('10.1016/test')
    library = tmp_path / 'sources'

    def fail(*args, **kwargs):
        raise PipelineContentError('No full text')

    monkeypatch.setattr(batch, 'process_doi', fail)
    result = CliRunner().invoke(cli.app, ['process-list', str(source), '--library-root', str(library)])
    assert result.exit_code == 0, result.output
    notes = library / 'missing_pdfs.txt'
    assert notes.is_file()
    assert not re.search('[一-龥]', notes.read_text(encoding='utf-8') + result.output)
    for path in library.rglob('*'):
        assert not re.search('[一-龥]', path.name)
        if path.suffix == '.cmd':
            text = path.read_text(encoding='utf-8')
            assert not re.search('[一-龥]', text)
            assert 'PAPERFLOW_LANGUAGE=en' in text
    assert pdf_resume.main([str(library / pdf_resume.BATCH_CONFIG_NAME)]) == 0
    report = library / 'pdf_recovery_results.csv'
    assert 'Missing PDF' in report.read_text(encoding='utf-8-sig')
    assert not re.search('[一-龥]', capsys.readouterr().out)


def test_legacy_recovery_configs_are_read_once_even_with_current_copy(tmp_path, monkeypatch):
    monkeypatch.setenv('PAPERFLOW_LANGUAGE', 'en')
    launcher = pdf_resume.create_pdf_recovery('10.1016/test', tmp_path)
    current = launcher.parent / pdf_resume.CONFIG_NAME
    legacy = launcher.parent / pdf_resume.LEGACY_CONFIG_NAME
    legacy.write_bytes(current.read_bytes())
    pdf_resume.create_batch_pdf_recovery(tmp_path)
    config_path = tmp_path / pdf_resume.BATCH_CONFIG_NAME
    config = json.loads(config_path.read_text(encoding='utf-8'))
    assert pdf_resume.run_batch_recovery(config_path, config) == 0
    report = tmp_path / 'pdf_recovery_results.csv'
    assert report.read_text(encoding='utf-8-sig').count('10.1016/test') == 1
    current.unlink()
    assert pdf_resume.run_batch_recovery(config_path, config) == 0
    assert report.read_text(encoding='utf-8-sig').count('10.1016/test') == 1


def test_english_windows_launcher_missing_environment(tmp_path):
    launcher = tmp_path / 'Batch_Markdown.cmd'
    launcher.write_bytes((ROOT / launcher.name).read_bytes())
    (tmp_path / '.paperflow-language').write_text('en')
    result = subprocess.run(['cmd.exe', '/d', '/c', 'call', str(launcher)],
                            input=b'\n', capture_output=True, check=False, timeout=15,
                            env={**os.environ, 'PAPERFLOW_LANGUAGE': 'en'})
    output = result.stdout.decode('utf-8', errors='replace')
    assert result.returncode == 2 and 'Run Install.cmd' in output
    # Windows itself may localize PAUSE; check only application echo text.
    assert '尚未创建' not in output and '请先双击' not in output
