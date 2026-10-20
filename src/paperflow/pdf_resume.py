"""Windows shortcuts for single-paper and batch PDF recovery through the existing CLI."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from paperflow.config import redact_error
from paperflow.language import get_language, t
from paperflow.recovery import MultipleLocalPdfError, find_local_pdf
from paperflow.storage import build_paper_paths

LAUNCHER_NAME = "Retry_PDF.cmd"
CONFIG_NAME = "pdf_recovery.json"
BATCH_LAUNCHER_NAME = "Retry_PDF_Batch.cmd"
BATCH_CONFIG_NAME = "pdf_recovery_batch.json"
LEGACY_CONFIG_NAME = "补PDF转换配置.json"


def create_pdf_recovery(doi, library_root, markdown_dir=None):
    library_root = Path(library_root).resolve()
    paths = build_paper_paths(doi, library_root=library_root)
    paths.directory.mkdir(parents=True, exist_ok=True)
    source_root = Path(__file__).resolve().parents[2]
    project = source_root if (source_root / "pyproject.toml").is_file() else Path.cwd()
    python = project / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        python = Path(sys.executable)
    config = {
        "doi": paths.doi,
        "library_root": str(library_root),
        "markdown_dir": str(Path(markdown_dir).resolve()) if markdown_dir is not None else None,
        "project_root": str(project),
    }
    config_path = paths.directory / CONFIG_NAME
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    launcher = paths.directory / LAUNCHER_NAME
    _write_launcher(launcher, config_path.name, project, python, require_pdf=True)
    return launcher


def create_batch_pdf_recovery(library_root, markdown_dir=None):
    root = Path(library_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source_root = Path(__file__).resolve().parents[2]
    project = source_root if (source_root / "pyproject.toml").is_file() else Path.cwd()
    python = project / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        python = Path(sys.executable)
    config = {"batch": True, "library_root": str(root), "project_root": str(project),
              "markdown_dir": str(Path(markdown_dir).resolve()) if markdown_dir is not None else None}
    path = root / BATCH_CONFIG_NAME
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    launcher = root / BATCH_LAUNCHER_NAME
    _write_launcher(launcher, path.name, project, python, require_pdf=False)
    return launcher


def _write_launcher(launcher, config_name, project, python, *, require_pdf):
    # Values stay in JSON and subprocess argument lists, never interpolated into shell commands.
    # Only filesystem paths are embedded here. Disable ! expansion and escape literal %.
    def cmd_path(path):
        text = str(path)
        if any(char in text for char in ('"', '\r', '\n')):
            raise ValueError("Unsupported Windows launcher path.")
        return text.replace("%", "%%")

    lines = [
        "@echo off", "setlocal DisableDelayedExpansion", "chcp 65001 >nul",
        *(['if not exist "%~dp0*.pdf" goto missing_pdf'] if require_pdf else []),
        f'set "PAPERFLOW_PYTHON={cmd_path(python)}"',
        'if not exist "%PAPERFLOW_PYTHON%" goto missing_environment',
        f'cd /d "{cmd_path(project)}"',
        "if errorlevel 1 goto missing_environment",
        'set "PYTHONUTF8=1"', 'set "PYTHONIOENCODING=utf-8"',
        f'set "PAPERFLOW_LANGUAGE={get_language()}"',
        '"%PAPERFLOW_PYTHON%" -m paperflow.pdf_resume "%~dp0' + config_name + '"',
        'set "PAPERFLOW_EXIT=%ERRORLEVEL%"', "echo.", "pause", "exit /b %PAPERFLOW_EXIT%",
        ":missing_pdf",
        t("echo 请下载正文PDF，保留原名，放在本CMD同目录。",
          "echo Download the main PDF here; keep its original filename."),
        t('echo PDF应放在这个目录："%~dp0"', 'echo PDF folder: "%~dp0"'),
        t("echo 放好后重新双击本文件。不要放补充材料或其他论文。",
          "echo Then double-click again. Do not put supplementary files here."),
        "pause", "exit /b 2", ":missing_environment",
        t("echo 找不到PaperFlow环境或项目目录。请按项目README安装，移动项目后重新生成本入口。",
          "echo Project/environment missing. Run the installer; regenerate this shortcut after moving the project."),
        "pause", "exit /b 2", "",
    ]
    launcher.write_bytes("\r\n".join(lines).encode("utf-8"))


def _converted(paths):
    if not paths.llm_md.is_file() or not paths.llm_md.stat().st_size:
        return None
    try:
        qa = json.loads(paths.qa_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(qa, dict) or qa.get("source") in {
        None, "springer_restricted_partial", "public_metadata_partial"
    } or qa.get("full_text_available") is False or qa.get("failures"):
        return None
    if qa.get("status") == "success":
        return "success"
    if qa.get("status") == "warning" and qa.get("mineru", {}).get("is_full_document") is True:
        return "warning"
    return None


def _input_pdf(paths):
    try:
        return find_local_pdf(paths.directory)
    except MultipleLocalPdfError:
        names = sorted(p.name for p in paths.directory.iterdir()
                       if p.is_file() and p.suffix.lower() == ".pdf")
        raise ValueError(t("同一论文目录有多个PDF，无法确定正文：", "Multiple PDFs; cannot choose the article: ")
                         + "; ".join(names) + t("。请移出补充材料或重复版本，只保留正文PDF，无需改名。",
                           ". Remove supplements/duplicate versions; keep one main PDF without renaming.")) from None


def run_batch_recovery(config_path, config):
    root = Path(config["library_root"]).resolve()
    if root != config_path.parent:
        raise ValueError(t("批量转换配置与原始资料目录不匹配，请重新生成入口。",
                           "Batch configuration folder mismatch; regenerate the launcher."))
    # Read historical Chinese config names, preferring the current file if both exist.
    by_folder = {p.parent: p for p in root.glob("*/" + LEGACY_CONFIG_NAME)}
    by_folder.update({p.parent: p for p in root.glob("*/" + CONFIG_NAME)})
    configs = [by_folder[folder] for folder in sorted(by_folder)]
    rows = []
    print(t("批量补PDF：自动识别PDF，保留原名；已有正文和缺PDF的跳过。",
            "Batch recovery: original PDF names accepted; completed/missing items skipped."), flush=True)
    print(t("PDF使用MinerU完整API，会上传PDF并可能消耗额度。",
            "PDFs are uploaded to the full MinerU API and may consume credits."), flush=True)
    for index, path in enumerate(configs, 1):
        doi = path.parent.name
        label, detail = "失败", ""
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            paths = build_paper_paths(item["doi"], library_root=root)
            doi = paths.doi
            if paths.directory.resolve() != path.parent.resolve() or Path(
                item["library_root"]
            ).resolve() != root:
                raise ValueError(t("论文配置与本批目录不匹配。", "Paper configuration folder mismatch."))
            converted = _converted(paths)
            if converted:
                label = "跳过已有正文" if converted == "success" else "跳过已有正文（有警告）"
            else:
                pdf = _input_pdf(paths)
                if pdf is None:
                    label, detail = "缺PDF", t("保留原名放入：", "Place the original PDF in: ") + str(paths.directory)
                else:
                    print(f"[{index}/{len(configs)}] {doi} " + t("开始转换", "Converting"), flush=True)
                    # Reuse batch settings while leaving the per-paper config intact.
                    item.update(project_root=config["project_root"],
                                markdown_dir=config.get("markdown_dir"))
                    code = _run_one(paths, item, pdf)
                    converted = _converted(paths) if code == 0 else None
                    if converted:
                        label = "成功" if converted == "success" else "警告"
                    else:
                        detail = t("未通过正文转换检查，请查看上方错误或该论文qa.json。",
                                   "Full-text conversion not verified; see errors above or qa.json.")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            detail = redact_error(str(exc))
        rows.append({"DOI": doi, "结果": label, "说明": detail, "论文目录": str(path.parent)})
        print(f"[{index}/{len(configs)}] {doi} → {_label(label)} {detail}", flush=True)
    if config.get("markdown_dir"):
        from paperflow.storage.flat_export import export_markdown

        export_markdown(root, config["markdown_dir"])
    report = root / t("补PDF批量结果.csv", "pdf_recovery_results.csv")
    with report.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["DOI", t("结果", "Result"), t("说明", "Details"), t("论文目录", "Paper folder")])
        writer.writerows([row['DOI'], _label(row['结果']), row['说明'], row['论文目录']] for row in rows)
    counts = {label: sum(row["结果"] == label for row in rows)
              for label in ["成功", "警告", "失败", "缺PDF", "跳过已有正文", "跳过已有正文（有警告）"]}
    print(t("\n本次汇总：", "\nSummary: ") + "; ".join(f"{_label(label)} {n}" for label, n in counts.items()),
          flush=True)
    print(t("结果清单：", "Results: ") + str(report), flush=True)
    print(t("未补齐的PDF下次放好后，再双击同一个批量入口即可。",
            "Add missing PDFs later and run this same batch launcher again."), flush=True)
    return 1 if counts["失败"] else 0


def _label(value):
    english = {"成功": "Success", "警告": "Warning", "失败": "Failed", "缺PDF": "Missing PDF",
               "跳过已有正文": "Skipped: already converted",
               "跳过已有正文（有警告）": "Skipped: converted with warnings"}
    return t(value, english.get(value, value))


def _run_one(paths, config, pdf):
    print(f"DOI: {paths.doi}", flush=True)
    print(f"PDF: {pdf}", flush=True)
    print(t("通过MinerU完整API转换，会上传PDF并可能消耗额度；不调用本地模型。",
            "Using full MinerU API: PDF upload may consume credits; no local models."), flush=True)
    command = [sys.executable, "-c", "from paperflow.cli import app; app()", "process",
               paths.doi, "--pdf", str(pdf), "--library-root", str(paths.directory.parent),
               "--mineru-backend", "api"]
    if config.get("markdown_dir"):
        command.extend(["--markdown-dir", config["markdown_dir"]])
        print(t("整理好的Markdown保存到：", "Markdown folder: ") + config['markdown_dir'], flush=True)
    result = subprocess.run(command, cwd=config["project_root"], check=False)
    print(t("请查看上方Status/QA确认正文转换结果。", "Check Status/QA above for the conversion result.")
          if result.returncode == 0 else t("转换未完成。PDF已保留，请检查上方错误。",
          "Conversion incomplete. PDF preserved; check the errors above."), flush=True)
    return result.returncode


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        if len(args) != 1:
            raise ValueError(t("请使用对应论文目录中的补PDF转换CMD。", "Use the generated PDF recovery CMD."))
        config_path = Path(args[0]).resolve()
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("batch") is True:
            return run_batch_recovery(config_path, config)
        paths = build_paper_paths(config["doi"], library_root=Path(config["library_root"]))
        if paths.directory.resolve() != config_path.parent:
            raise ValueError(t("转换配置与论文目录不匹配，请重新生成入口。",
                               "Paper configuration folder mismatch; regenerate the launcher."))
        pdf = _input_pdf(paths)
        if pdf is None:
            print(t("尚未找到正文PDF。保留原文件名，放入：", "PDF missing. Keep its original name and put it in: ")
                  + str(paths.directory))
            return 2
        return _run_one(paths, config, pdf)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(t("无法启动PDF转换：", "Cannot start PDF conversion: ") + redact_error(str(exc)), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
