# PaperFlow

Inline and display equations are retained as LaTeX math. PDF equations depend on MinerU recognition; check important formulas against the source. Existing Markdown files are not updated automatically.

[中文](README.md) | English

Fetch papers from a DOI list and convert them to Markdown. Reading files are collected in one folder, named after article titles, without images.

## Sources

| Source | Example journals or platforms |
|---|---|
| Elsevier | Applied Energy, Energy and Buildings, Building and Environment, Journal of Building Engineering |
| Springer Nature | Building Simulation, Nature Communications, International Journal of Computer Vision, and other implemented OA routes |
| IEEE | IEEE Access, TPAMI, CVPR conference papers |
| Other publishers | Wiley, Taylor & Francis, MDPI, PLOS, Frontiers, eLife, AAAS, Copernicus, ACM, IOP, AIP, APS, ASCE |
| Paper platforms | arXiv, JMLR, PMLR |

Full-text availability depends on the article's access status and your entitlement. Missing full text can be supplied as a PDF.

## Installation

Windows, Python 3.10 ([download](https://www.python.org/downloads/release/python-31011/)).

Run [Install.cmd](Install.cmd) and choose a language. Then edit `.env` with your API credentials:

```ini
ELSEVIER_API_KEY=your_elsevier_key
MINERU_BACKEND=api
MINERU_API_TOKEN=your_mineru_token
```

Elsevier full-text XML requires entitlement. PDFs use MinerU API, may consume credits and need no local GPU. Other settings are optional; see `.env.example`. Keep `.env` private.

<details>
<summary>Manual installation (CMD)</summary>

Open the project folder in File Explorer, type `cmd` in its address bar and press Enter. Run the following commands one at a time. Skip the first command if a working `.venv` already exists.

```bat
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
if not exist .env copy .env.example .env
echo en>.paperflow-language
.venv\Scripts\paperflow.exe version
notepad .env
```

Save your credentials in `.env`, then run `Batch_Markdown.cmd`. Use `echo zh` instead of `echo en` for Chinese prompts.

</details>

## Usage

Create a TXT with one DOI per line, without a heading or numbering. Example: [example_dois.txt](example_dois.txt).

```text
10.1016/j.jobe.2024.110286
10.1007/s12273-025-1335-6
10.1016/j.buildenv.2025.114072
```

Run [Batch_Markdown.cmd](Batch_Markdown.cmd), drag in the TXT and choose a parent folder. A batch folder is created using the TXT filename without its extension: `UK_retrofit_priority_18_dois.txt` → `UK_retrofit_priority_18_dois`. Press Enter to use `workspace\批量文献` as the parent. Full-text availability depends on your access and network.

Reading files are in 整理好的Markdown. PDFs, XML and processing records are in 原始资料.

## Missing PDFs

Place each matching main PDF in the article folder indicated by the window. Keep its original filename and one main PDF per article folder.

Run `Retry_PDF_Batch.cmd` in 原始资料 to convert all ready PDFs. Use `Retry_PDF.cmd` inside an article folder to retry just that paper.

Markdown goes to the original reading folder. Completed and missing-PDF items are skipped; results appear in the window and 补PDF批量结果.csv. Abstracts are not full text; review warnings against the original.
