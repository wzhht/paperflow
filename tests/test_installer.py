import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def installer():
    spec = importlib.util.spec_from_file_location('paperflow_install', ROOT / 'scripts/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project(root):
    (root / 'src/paperflow').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[project]\nname="paperflow"')
    (root / '.env.example').write_text('MINERU_BACKEND=api\nMINERU_API_TOKEN=\n')


@pytest.mark.parametrize('language', ['zh', 'en'])
@pytest.mark.parametrize('existing', [False, True])
def test_install_creates_or_reuses_env_preserves_credentials_and_saves_language(
    tmp_path, monkeypatch, capsys, language, existing
):
    module = installer()
    project(tmp_path)
    env = tmp_path / '.env'
    env.write_text('MINERU_API=private-do-not-print\n')
    pdf = tmp_path / 'my-paper.pdf'
    pdf.write_bytes(b'keep')
    python = tmp_path / '.venv/Scripts/python.exe'
    created, calls = [], []

    if existing:
        python.parent.mkdir(parents=True)
        python.write_bytes(b'fake-python')
    def run(command, **kwargs):
        calls.append(command)
        if command[:3] == [sys.executable, '-m', 'venv']:
            created.append(command[-1])
            python.parent.mkdir(parents=True)
            python.write_bytes(b'fake-python')
            return subprocess.CompletedProcess(command, 0)
        assert command[0] == str(python) and kwargs['check'] is True
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, 'run', run)
    assert module.install(tmp_path, language) == 0
    assert len(created) == (0 if existing else 1)
    assert len([c for c in calls if 'pip' in c]) == 2
    assert (tmp_path / '.paperflow-language').read_text().strip() == language
    assert env.read_text() == 'MINERU_API=private-do-not-print\n' and pdf.read_bytes() == b'keep'
    output = capsys.readouterr().out
    assert 'private-do-not-print' not in output
    assert ('Installed.' if language == 'en' else '安装完成') in output


def test_check_only_and_failed_install_never_write_credentials_or_delete_data(tmp_path, monkeypatch):
    module = installer()
    project(tmp_path)
    assert module.install(tmp_path, 'en', check_only=True) == 0
    assert not (tmp_path / '.venv').exists() and not (tmp_path / '.env').exists()
    python = tmp_path / '.venv/Scripts/python.exe'
    python.parent.mkdir(parents=True)
    python.write_bytes(b'keep-env')
    (tmp_path / '.env').write_text('MINERU_API=keep-key\n')

    def fail(command, **kwargs):
        if 'pip' in command:
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, 'run', fail)
    assert module.install(tmp_path, 'en') == 1
    assert python.read_bytes() == b'keep-env'
    assert (tmp_path / '.env').read_text() == 'MINERU_API=keep-key\n'
    assert not (tmp_path / '.paperflow-language').exists()


def test_language_setting_and_env_override(tmp_path, monkeypatch):
    from paperflow import language

    fake_source = tmp_path / 'src/paperflow/language.py'
    monkeypatch.setattr(language, '__file__', str(fake_source))
    monkeypatch.delenv('PAPERFLOW_LANGUAGE', raising=False)
    (tmp_path / '.paperflow-language').write_text('en\n')
    assert language.t('你好', 'Hello') == 'Hello'
    monkeypatch.setenv('PAPERFLOW_LANGUAGE', 'zh')
    assert language.t('你好', 'Hello') == '你好'


def test_english_batch_and_recovery_prompts(tmp_path, monkeypatch, capsys):
    from paperflow import pdf_resume

    monkeypatch.setenv('PAPERFLOW_LANGUAGE', 'en')
    pdf_resume.create_pdf_recovery('10.1016/test', tmp_path)
    pdf_resume.create_batch_pdf_recovery(tmp_path)
    assert pdf_resume.main([str(tmp_path / pdf_resume.BATCH_CONFIG_NAME)]) == 0
    output = capsys.readouterr().out
    assert 'Batch recovery' in output and 'Missing PDF' in output
    assert '保留原名' not in output
    assert 'Result,Details,Paper folder' in (tmp_path / '补PDF批量结果.csv').read_text(encoding='utf-8-sig')

    spec = importlib.util.spec_from_file_location('batch_english', ROOT / 'scripts/batch_markdown.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / 'dois.txt'
    source.write_text('10.1016/test')
    monkeypatch.setattr(sys, 'argv', ['batch', str(source), '--output-dir', str(tmp_path / 'out'),
                                     '--language', 'en'])
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a[0], 0))
    assert module.main() == 0
    assert 'Full-text Markdown folder' in capsys.readouterr().out


@pytest.mark.skipif(os.name != 'nt', reason='Windows installer bootstrap')
def test_real_installer_cmd_check_and_help_never_install():
    launcher = ROOT / '一键安装.cmd'
    assert b'\n' not in launcher.read_bytes().replace(b'\r\n', b'')
    for args, expected in [(['--help'], '--language'),
                           (['--language', 'en', '--check'], 'Checks passed')]:
        result = subprocess.run(['cmd.exe', '/d', '/c', 'call', str(launcher), *args],
                                input=b'\n', capture_output=True, check=False, timeout=20)
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        assert result.returncode == 0 and expected in output, output
        assert 'not recognized' not in output
