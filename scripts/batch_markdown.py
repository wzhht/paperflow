"""Friendly launcher for the existing process-list + flat Markdown export CLI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from paperflow.language import t

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='Batch DOI to Markdown / 批量整理Markdown')
    parser.add_argument('input_file', nargs='?', help='DOI text file / 每行一个DOI的txt清单')
    parser.add_argument('--output-dir', type=Path, help='Batch output folder / 本批保存目录')
    parser.add_argument('--mineru-backend', choices=['api', 'api-light'])
    parser.add_argument('--language', choices=['zh', 'en'], help='Override language / 本次使用的语言')
    args = parser.parse_args()
    if args.language:
        os.environ['PAPERFLOW_LANGUAGE'] = args.language
    value = args.input_file or input(t('请把 DOI 清单 txt 文件拖到这个窗口，按回车：\n',
                                      'Drag the DOI text file here and press Enter:\n')).strip().strip('"')
    source = Path(value).expanduser().resolve()
    if not source.is_file():
        parser.error(t('找不到 DOI 清单文件，请确认拖入的是 txt 文件。', 'DOI text file not found.'))
    default_parent = PROJECT / 'workspace' / '批量文献'
    if args.output_dir is None:
        text = input(t('保存在哪个位置？会自动建立与TXT同名的批次文件夹。直接回车使用：',
                       'Choose a parent folder. A batch folder named after the TXT will be created. '
                       'Press Enter to use:') + f'\n{default_parent}\n').strip().strip('"')
        parent = Path(text).expanduser().resolve() if text else default_parent
        output = parent / source.stem
    else:
        output = args.output_dir.expanduser().resolve()
    library, reading = output / '原始资料', output / '整理好的Markdown'
    print(t('\n本批保存目录：', '\nBatch folder: ') + str(output), flush=True)
    print(t('\n正文 Markdown 将集中保存在：', '\nFull-text Markdown folder: ') + str(reading), flush=True)
    print(t('文件按论文标题命名；同名自动区分。未取得全文的摘要不会混入。',
            'Files use article titles; duplicate names are disambiguated. Abstract-only results excluded.'),
          flush=True)
    print(t('原始资料保存在：', 'Source files folder: ') + str(library), flush=True)
    print(t('PDF使用MinerU API，会上传PDF、可能消耗额度；不调用本地模型。\n',
            'PDFs use MinerU API uploads and may consume credits; no local models.\n'), flush=True)
    command = [sys.executable, '-c', 'from paperflow.cli import app; app()',
               'process-list', str(source), '--library-root', str(library),
               '--markdown-dir', str(reading)]
    if args.mineru_backend:
        command.extend(['--mineru-backend', args.mineru_backend])
    return subprocess.run(command, cwd=PROJECT, check=False).returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, EOFError):
        print(t('无法读取输入或启动程序，请在项目目录双击启动文件重试。',
                'Cannot read input or start PaperFlow. Run the launcher from the project folder.'),
              file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        print(t('\n已停止；已生成的原始资料保留。', '\nStopped; existing source files are preserved.'))
        raise SystemExit(130) from None
