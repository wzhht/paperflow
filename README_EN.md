# PaperFlow

[中文](README.md) | English

**Turn papers into Markdown that is easier to use with AI reading and retrieval tools.**

PDFs are designed for people, but columns, headers, footers and broken lines can make extracted text difficult to follow. PaperFlow fetches full text from a DOI list and organizes the body, headings, tables, equations and references into Markdown for reading, comparing and discussing papers with tools such as ChatGPT, or for local knowledge bases and evidence retrieval.

Start with one DOI list and collect papers in a single folder, named after their titles, instead of downloading, converting and organizing each one manually. Images are excluded; check visual information and important conclusions against the original paper.

Inline and display equations are retained as LaTeX math. Check important PDF formulas against the source. Existing Markdown is not updated automatically.

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

Run [Install.cmd](Install.cmd), select **2. English**, then edit `.env` with your API credentials:

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

Run [Batch_Markdown.cmd](Batch_Markdown.cmd), drag in the TXT and choose a parent folder. Press Enter to use `workspace\batches`. The TXT filename becomes the batch folder name:

```text
workspace/batches/UK_retrofit_priority_18_dois/
├── markdown/     # Papers named after article titles
└── sources/      # PDFs, XML and processing records
```

English mode uses English output names. Existing batch folders keep their original paths when switching languages. User-supplied filenames and article titles are not translated.

## Missing PDFs

Place each matching main PDF in the article folder indicated by the window. Keep its original filename and one main PDF per article folder.

Read `sources/missing_pdfs.txt` for the matching paper folders. Run `Retry_PDF_Batch.cmd` in `sources` to convert all ready PDFs, or `Retry_PDF.cmd` inside an article folder to retry one paper.

Markdown goes to the original reading folder. Completed and missing-PDF items are skipped; results appear in the window and `sources/pdf_recovery_results.csv`. Abstracts are not full text; review warnings against the original.
