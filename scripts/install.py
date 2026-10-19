"""Standard-library-only installer; never deletes an environment or reads credentials."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def install(root, language, *, check_only=False):
    def say(zh, en):
        print(en if language == "en" else zh, flush=True)

    try:
        if sys.version_info[:2] != (3, 10):
            raise ValueError("Python 3.10 required / 需要Python 3.10")
        if not (root / "pyproject.toml").is_file() or not (root / "src/paperflow").is_dir():
            raise ValueError("Extract the complete project first / 请先完整解压项目")
        environment = root / ".venv"
        python = environment / "Scripts/python.exe"
        if environment.exists():
            if not python.is_file():
                raise ValueError("Existing .venv is incomplete; preserved / 现有.venv不完整，已保留")
            subprocess.run([str(python), "-c", "import sys; assert sys.version_info[:2] == (3,10)"],
                           check=True, capture_output=True)
        if check_only:
            say("检查通过；未安装依赖或修改配置。", "Checks passed; no packages installed or settings changed.")
            return 0
        if not environment.exists():
            say("[1/4] 创建本目录的虚拟环境……", "[1/4] Creating this project's virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", str(environment)], cwd=root, check=True)
        else:
            say("[1/4] 使用现有虚拟环境。", "[1/4] Reusing the existing virtual environment.")
        say("[2/4] 更新pip，需要网络……", "[2/4] Updating pip; network access required...")
        subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=root, check=True)
        say("[3/4] 安装PaperFlow及依赖……", "[3/4] Installing PaperFlow and its dependencies...")
        subprocess.run([str(python), "-m", "pip", "install", "-e", str(root)], cwd=root, check=True)
        subprocess.run([str(python), "-c", ("from paperflow.cli import app, _get_version; "
                        "print('PaperFlow ' + _get_version())")], cwd=root, check=True)
        if not (root / ".env").exists():
            shutil.copyfile(root / ".env.example", root / ".env")
        (root / ".paperflow-language").write_text(language + "\n", encoding="utf-8")
        say("[4/4] 安装完成。已有.env及文献保留，不安装本地MinerU或GPU模型。",
            "[4/4] Installed. Existing .env and papers are preserved. No local MinerU/GPU models installed.")
        say("下一步：用记事本打开.env，填写自己的API，然后双击一键批量整理Markdown.cmd。",
            "Next: edit .env in Notepad with your own API credentials, then run 一键批量整理Markdown.cmd.")
        say("PDF默认上传MinerU API转换，可能消耗额度。不要公开.env。",
            "PDFs use the MinerU API and may consume credits. Keep .env private.")
        say("切换语言：重新运行一键安装.cmd并选择语言；也可用--language zh/en运行批量入口。",
            "To change language, rerun 一键安装.cmd or pass --language zh/en to the batch launcher.")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        say("安装未完成。请检查Python 3.10、网络或上方安装错误。已有配置和资料没有删除；"
            "若现有.venv失效，请按README处理，不要复制其他目录的环境。",
            "Installation incomplete. Check Python 3.10, network access and the errors above. "
            "Existing settings and papers were not deleted. See README_EN.md for invalid .venv issues.")
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="PaperFlow installation / PaperFlow安装")
    parser.add_argument("--language", choices=["zh", "en"], default="zh")
    parser.add_argument("--check", action="store_true", help="Check only; no installation / 仅检查，不安装")
    args = parser.parse_args(argv)
    return install(PROJECT, args.language, check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
