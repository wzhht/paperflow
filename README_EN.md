# PaperFlow V3

[中文](README.md) | **English**

Local academic full-text acquisition and Markdown conversion. V3 is package version **0.3.0**. Existing checkouts named `paperflow-v2` can keep their paths.

V3 preserves the V2 core renderers and QA while adding public-source discovery, native XML/HTML/EPUB/TEI imports, MinerU API parsing and title-named flat reading copies. Publisher recognition does not guarantee subscription access.

## Documentation

| Task | Guide |
|---|---|
| Install, choose language and configure APIs | Quick start below |
| Process a DOI batch | [Detailed user guide](docs/USAGE.en.md) |
| Add several downloaded PDFs and recover them in one run | [PDF recovery and file locations](docs/USAGE.en.md) |
| Understand warnings, repeat runs and errors | [Status and troubleshooting](docs/USAGE.en.md) |
| Publish V3 in the existing GitHub repository | [Publishing guide](docs/PUBLISH.en.md) |

## Quick start

**Recommended: extract the full project and double-click [一键安装.cmd](一键安装.cmd).**

1. Select `1 中文` or `2 English`.
2. The installer checks Python 3.10, creates/reuses this project's `.venv`, and installs dependencies. Network access is required; administrator privileges are not needed.
3. Edit `.env` in Notepad with your API credentials, then run `一键批量整理Markdown.cmd`.

If Python is missing, the launcher provides the official installer link; it does not automatically download/run Python installers. Existing `.env` and papers are preserved; a valid environment is reused and project dependencies are updated. Broken environments produce guidance instead of being deleted.

Your selected language is saved in the local, Git-ignored `.paperflow-language` file. It controls batch/recovery prompts and summaries; papers are not translated, and existing folder names/data remain compatible. Rerun the installer to change language, or use `一键批量整理Markdown.cmd --language en` / `--language zh` for one run. Third-party pip/MinerU messages keep their original language.

Check prerequisites without installing or changing configuration:

```bat
一键安装.cmd --language en --check
```

Manual setup remains available below for troubleshooting.

The source ZIP is **not a portable installed app**: it excludes `.venv`, credentials and MinerU. Extract it first; the project root must directly contain `pyproject.toml`, `src` and `scripts`.

Requires Python **3.10** (`>=3.10,<3.11`). Check `py -3.10 --version`. If unavailable, install the [official Windows 64-bit Python 3.10 installer](https://www.python.org/downloads/release/python-31011/), including pip and the launcher, then reopen CMD. Python 3.10 is end-of-life; these are compatibility instructions for the currently tested V3, not a claim of support for newer Python versions.

For a fresh extraction, run these commands **one at a time in CMD**, adjusting only the first path:

```bat
cd /d "D:\paper\paperflow-v3"
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
if not exist .env copy .env.example .env
.venv\Scripts\paperflow.exe version
notepad .env
```

Expect `PaperFlow 0.3.0`. Configure your own credentials and parser before launching the `.cmd` files. Pip installation requires network access. No environment activation is required. Do not copy another checkout's `.venv`; create one at the new location. Existing working environments need not be recreated.

PDF parsing defaults to the full MinerU API: set your token in `.env`. PDFs are uploaded to MinerU and may incur charges. No local MinerU or GPU installation is needed. XML conversion does not call MinerU. API errors never trigger a local-model or light-mode fallback.

Existing installations can add development/test tools with:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\paperflow.exe version
.venv\Scripts\paperflow.exe process-list "D:\papers\dois.txt" --library-root "D:\papers\batch\sources" --markdown-dir "D:\papers\batch\reading"
```

On Windows, `一键批量整理Markdown.cmd` accepts a text file with one DOI per line and asks for an output folder. Successful body Markdown files are placed together and named after paper titles. Duplicate titles are disambiguated, manually edited reading copies preserved, and abstract-only results excluded by default.

## Missing full text: add your PDFs

1. Read the terminal or `原始资料/待补PDF说明.txt` and locate each matching article folder.
2. Put the corresponding main PDF there, keeping its original name; no rename is required.
3. For one article, run its `补好PDF后双击转换.cmd`. For several PDFs, run `补齐PDF后批量转换.cmd` once from the batch's `原始资料` folder.
4. Review the result and find title-named Markdown in the original reading folder.

Batch recovery skips missing and already converted/full-document warning items, continues after individual failures, and writes `补PDF批量结果.csv`. Warnings remain to be reviewed. Keep one main PDF per paper folder, retain adjacent configuration JSON files, and regenerate shortcuts after moving the project. If parsing alone failed, reuse the existing PDF. PDF uploads may consume MinerU credits; local models are not called.

The original `batch_results.csv` remains historical and is not rewritten by recovery. Check the recovery CSV and latest per-article `qa.json`. See the [full user guide](docs/USAGE.en.md) for folder diagrams, standalone no-DOI PDFs and troubleshooting.


## Configuration

- Elsevier: `ELSEVIER_API_KEY`, optional `ELSEVIER_INSTTOKEN`; entitlement may depend on campus IP.
- Springer Nature: `SPRINGER_OA_API_KEY`, optional `SPRINGER_META_API_KEY`; metadata does not grant full-text access.
- Wiley: `WILEY_API_KEY` (aliases `Wiley_API_KEY`, `WILEY_TDM_API_KEY`).
- Optional discovery: `OPENALEX_API_KEY`, `CROSSREF_MAILTO`, `UNPAYWALL_EMAIL`.
- Optional IEEE metadata: `IEEE_API_KEY`, `IEEE_API_ENABLED`; public PDF routes work independently.
- MinerU: `MINERU_BACKEND=api` (default, full API), or explicitly `api-light` (limited quality). Uses `MINERU_API_TOKEN` (aliases `MINERU_API_KEY`/`MINERU_API`), optional `MINERU_API_MODEL` and `MINERU_API_TIMEOUT`. Migrate old `local` settings to `api`; `MINERU_EXECUTABLE` and `MINERU_TIER` are no longer used.

PaperFlow no longer invokes local MinerU and does not need GPU PyTorch. API parsing may incur charges, and light mode differs in capabilities and quality. `.env` is ignored by Git; never publish credentials. Network settings are not changed automatically.

## Commands

```powershell
# Export existing conversions without downloading or parsing
.venv\Scripts\paperflow.exe export-markdown "D:\papers\reading" --library-root "D:\papers\sources"
# Existing main PDF
.venv\Scripts\paperflow.exe process "10.1021/acsenergylett.4c01233" --pdf "D:\papers\article.pdf" --library-root workspace\library --markdown-dir workspace\reading --mineru-backend api
# Local PDF without a DOI
.venv\Scripts\paperflow.exe parse-pdf "D:\papers\article.pdf" --output-root workspace\library --markdown-dir workspace\reading
# Native XML/HTML/EPUB; optional DOI must match
.venv\Scripts\paperflow.exe process-document "D:\papers\article.xml" --output-root workspace\library --markdown-dir workspace\reading
# Official platform paper page; no MinerU
.venv\Scripts\paperflow.exe process-url "https://proceedings.mlr.press/v202/dettmers23a.html" --download-only
```

Reading and source folders must be separate and non-nested. `--include-partial` explicitly exports labeled abstract-only copies. `--pdf`, `--pdf-url` and Elsevier `--xml` are mutually exclusive. See each command's `--help`.

## Scope and verification

See [docs/VALIDATION.md](docs/VALIDATION.en.md) for historical representative-paper acceptance and unresolved samples. Routes include Elsevier, Springer/Nature, Building Simulation, IEEE/CVF/arXiv, Wiley, PLOS, Frontiers, eLife, Europe PMC, Copernicus, MDPI resources, JMLR and PMLR. ACS/SAGE/ASME/OpenReview still have blocked or incompletely verified samples. Semantic Scholar/OSTI experimental fallbacks were removed.

Acquisition, article identity, completeness and Markdown conversion are separate stages. Accepted manuscripts/preprints are not silently treated as published versions. Preserve body text, references and reliable structured tables; omit image binaries and standalone display equations. OCR and scientific notation may require human review.

Only use authorized/public content. No paywall, browser-challenge or TLS-verification bypass.

## Tests and backup

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests scripts
```

The two diagnostic CMD launchers have been removed. The root now has installation and batch Markdown entry points; developer diagnostic scripts remain under `scripts/`. PDF acquisition tests do not automatically call MinerU. Source, tests, reusable scripts/sample lists, documentation and `.env.example` belong in Git. Credentials, virtual environments, `workspace`, models and caches do not. A source backup is not a paper-library backup.

Local reviewed PDF fingerprints in `workspace/pdf_verifications.json` are not automatically inherited by a fresh clone. ResearchFlow and its indexes remain independent. See [CHANGELOG.md](CHANGELOG.md).

## Publishing V3

Keep repository `wzhht/paperflow-v2`, create release title `PaperFlow V3` and product tag `v3.0.0`; the Python package remains `0.3.0`, matching the existing separate product/package numbering. Preserve the old `v2.0.0` tag.

The Git checkout is `D:\paper\paperflow-v2`; `paperflow-v3` is a user installation, not the upload source. Follow the [publishing guide](docs/PUBLISH.en.md) and use the prepared [bilingual release notes](docs/RELEASE_NOTES_V3.md).
