# PaperFlow V3 user guide

[中文](USAGE.zh-CN.md) · [Home](../README_EN.md)

## Entry points

The project root has two everyday entry points:

| Launcher | Purpose |
|---|---|
| `一键安装.cmd` | Install/update dependencies and choose Chinese or English |
| `一键批量整理Markdown.cmd` | Process a DOI list and collect title-named Markdown |

PDF recovery launchers are generated inside each batch. Local GPU models and local MinerU are not required.

## 1. First installation

1. Fully extract the source ZIP; do not launch files inside the ZIP preview.
2. Enter the folder directly containing `pyproject.toml`, `src`, `scripts` and both CMD files.
3. Run `一键安装.cmd`; choose `1` for Chinese or `2` for English.
4. If Python is missing, use the displayed official link to install full Windows 64-bit Python 3.10 with pip and the launcher, add it to PATH, and reopen the installer.
5. The installer creates this project's `.venv` or reuses a valid existing one, then installs dependencies over the network. Expect an installation-complete message and `PaperFlow 0.3.0`.
6. Read errors above the pause prompt. “Press any key” does not mean installation succeeded.

The current compatibility requirement is `>=3.10,<3.11`. Python 3.10 is end-of-life; newer versions need separate compatibility testing. Do not copy another folder's `.venv`. The installer does not download/run Python installers automatically and does not require administrator access.

Existing `.env`, papers and reports are preserved. Invalid existing environments are not automatically deleted. Manual setup remains in [README_EN.md](../README_EN.md).

## 2. API configuration

After installation, open the project's `.env` in Notepad. It is created from `.env.example` only if absent. You do not need every available API:

| Task | Required configuration |
|---|---|
| Elsevier full-text XML | `ELSEVIER_API_KEY` plus full-text entitlement; campus network access may be required |
| PDF parsing, including manually downloaded articles | `MINERU_BACKEND=api` and `MINERU_API_TOKEN`; existing `MINERU_API` / `MINERU_API_KEY` aliases work |
| Springer Nature OA XML | Corresponding `SPRINGER_OA_API_KEY`; this does not grant subscription access |
| Other metadata, public-full-text discovery or Wiley TDM | Optional settings in README; tokens do not create subscription rights |

Replace these placeholders with your own values:

```ini
ELSEVIER_API_KEY=your_own_elsevier_key
MINERU_BACKEND=api
MINERU_API_TOKEN=your_own_mineru_token
MINERU_API_MODEL=vlm
MINERU_API_TIMEOUT=600
```

PDFs are uploaded to MinerU and may consume credits. Native XML conversion does not call MinerU. API failure never falls back to local models or light mode. Old `MINERU_EXECUTABLE` and `MINERU_TIER` settings are no longer used.

Keep `.env` private. System environment variables are also supported and existing system values can take precedence over `.env`; reopen the processing window after editing configuration.

## 3. DOI batch processing

Create a TXT file with one DOI per line, for example:

```text
10.1016/j.jobe.2024.110286
10.1007/s12273-025-1335-6
10.1016/j.buildenv.2025.114072
```

These demonstrate the format; availability depends on your account, network and the article.

1. Run `一键批量整理Markdown.cmd`.
2. Drag the TXT into the window and press Enter, or drag it onto the CMD icon.
3. Choose a batch output folder, or accept the displayed default.
4. Wait for individual results. Do not close the window or move the project while processing.
5. Review the summary, then open `整理好的Markdown`.

Reading files use article titles, disambiguate collisions and exclude abstract-only copies by default. A list of 100 DOIs does not guarantee 100 full-text files.

The install-time language is remembered. For one run:

```bat
一键批量整理Markdown.cmd --language en
一键批量整理Markdown.cmd --language zh
```

Third-party logs retain their original language; papers are not translated.

## 4. Output locations and records

The window displays the destination. The default is `workspace\批量文献\list-file-stem` inside the project:

```text
batch/
├─ 整理好的Markdown/                 Reading copies
│  ├─ Article title A.md
│  ├─ Article title B.md
│  └─ export_manifest.csv
└─ 原始资料/                         Sources and processing records
   ├─ batch_results.csv
   ├─ 补齐PDF后批量转换.cmd           Batch recovery launcher
   ├─ 批量补PDF转换配置.json
   ├─ 待补PDF说明.txt                Generated for failures/abstract-only items
   ├─ 补PDF批量结果.csv              Latest batch recovery results, after running recovery
   ├─ 10.1016_article-doi/
   │  ├─ paper_llm.md               Canonical Markdown after conversion
   │  ├─ qa.json                    Article checks
   │  └─ Original PDF/XML files     Depending on the route
   └─ 10.1007_pending-article-doi/
      ├─ 补好PDF后双击转换.cmd        Single-article recovery launcher
      ├─ 补PDF转换配置.json
      └─ Original downloaded name.pdf
```

| Item | Meaning |
|---|---|
| `整理好的Markdown` | Title-named reading copies |
| Individual folders under `原始资料` | Original files, provenance, QA and where to place missing PDFs |
| `batch_results.csv` | Original DOI batch results; recovery does not rewrite this historical record |
| `补PDF批量结果.csv` | Most recent recovery results; updated on each recovery batch |
| `export_manifest.csv` | Mapping between reading files, canonical Markdown, DOI and file hashes |
| `qa.json` | Detailed success/warning/completeness checks |
| Generated conversion JSON files | DOI/path configuration for launchers, without API keys; keep in place |

Reading and source directories must be separate. Preserve sources for traceability and retries. Manually edited reading copies are protected; exporting may create a separate copy instead of overwriting edits.

## 5. Recover one missing full text

1. Read the terminal or `待补PDF说明.txt` and locate the exact DOI folder.
2. Obtain the matching main-article PDF and put it in that folder, **keeping its original name**.
3. Keep one main PDF per article folder. Move supplements, other papers and duplicate versions elsewhere.
4. Double-click `补好PDF后双击转换.cmd` inside that folder.
5. Wait for the API result and inspect Status/QA. Accepted body Markdown is added to the original reading folder.

Chinese names, spaces and uppercase `.PDF` are accepted. Renaming to `paper.pdf` is unnecessary. Only PDFs directly inside the article folder are examined; subfolders are not searched and arbitrary filenames are not used to guess a DOI.

If the PDF already exists and only parsing/API access failed, fix the network, token, quota or PDF issue and retry without downloading again. The single-paper launcher is an explicit retry and can consume credits again if run after completion.

## 6. Recover four, five or more PDFs at once

1. Keep original PDF names and place each in its corresponding article folder.
2. Return to the batch's `原始资料` folder.
3. Double-click **`补齐PDF后批量转换.cmd` once**.
4. Read per-article messages, the summary and `补PDF批量结果.csv`.

This launcher processes ready pending PDFs sequentially through the full MinerU API. It skips missing PDFs and existing successful/full-document warning results, avoiding repeat credits. Warnings remain subject to review. Ambiguous multiple PDFs are reported, and individual failures do not stop later items. Markdown remains in the original reading folder.

It scans article folders with generated recovery configurations, not arbitrary PDF folders. Do not put unrelated PDFs together at the top level and expect automatic DOI matching. When more PDFs arrive, rerun this same recovery launcher; there is no need to repeat the original DOI acquisition batch.

## 7. A standalone PDF without a DOI

For an independent local PDF, use the existing command:

```bat
.venv\Scripts\paperflow.exe parse-pdf "D:\papers\article.pdf" --output-root "D:\papers\sources" --markdown-dir "D:\papers\reading"
```

This uses MinerU API and does not invent a DOI. The friendly batch launcher starts with a DOI list; a separate one-click arbitrary no-DOI PDF batch is outside this version.

## 8. Success, warning and failure

| Result | Interpretation |
|---|---|
| `success` | Passed this route's checks; important scientific details still warrant comparison with the original |
| `warning`, abstract/metadata only | No complete article body; obtain a PDF |
| `warning`, body generated | May lack trusted page-count evidence, need version verification or have other QA warnings; inspect `qa.json` before declaring fully verified |
| `FAILED` | Article incomplete; address acquisition, configuration, network or parsing errors as appropriate |
| Batch finished / pause prompt | Processing stopped or finished; not proof every article succeeded |

Acquisition, identity verification, completeness and rendering are separate. Accepted manuscripts/preprints are distinguished from published versions. Historical representative acceptance in [VALIDATION.md](VALIDATION.md) does not guarantee every article from a publisher or automatically validate new outputs.

## 9. Troubleshooting

| Issue | Action |
|---|---|
| Missing environment/dependencies | Run the installer from the full extracted project; do not copy only launchers or another `.venv` |
| pip failure | Read the first network/download/dependency error, fix it and retry; network/proxy settings are not changed automatically |
| 401/403, purchase prompt or abstract only | Check entitlement, network and API settings; some routes require campus access, others still need manual PDFs |
| MinerU token, quota or timeout | Check account/network/configuration; adjust `MINERU_API_TIMEOUT` if needed and retry the preserved PDF |
| QA source says `local_pdf_mineru` | This describes local-file input, not local inference; check `mineru.backend`, which should be `api` |
| Old local llama-cpp/GPU error | Use `MINERU_BACKEND=api`; old `local` configurations require migration |
| Several PDFs in one article folder | Move supplements/duplicate versions out; retain the one correct main PDF without renaming |
| Original batch CSV still says failed after recovery | It is historical; inspect the recovery CSV and latest article QA |
| Launcher invalid after moving project | Environments and generated launchers contain paths; install at the new location and regenerate affected recovery launchers |
| Export existing Markdown only | Use `export-markdown` from README; no new acquisition or MinerU call |

## 10. Updates, backup and publishing

Preserve your `.env` and `workspace` when updating. Source ZIPs exclude credentials, papers and environments; a GitHub code backup is not a paper-library backup. The tool does not automatically synchronize ResearchFlow indexes.

See the [publishing guide](PUBLISH.en.md) for GitHub release preparation.
