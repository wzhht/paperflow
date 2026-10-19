# PaperFlow

[中文](README.md) | English

Fetch papers from a DOI list and convert them to Markdown. Reading files are collected in one folder, named after article titles, without images.

## Installation

Windows, Python 3.10 ([download](https://www.python.org/downloads/release/python-31011/)).

Run [Install.cmd](Install.cmd) and choose a language. Then edit `.env` with your API credentials:

```ini
ELSEVIER_API_KEY=your_elsevier_key
MINERU_BACKEND=api
MINERU_API_TOKEN=your_mineru_token
```

Elsevier full-text XML requires entitlement. PDFs use MinerU API, may consume credits and need no local GPU. Other settings are optional; see `.env.example`. Keep `.env` private.

## Usage

Create a TXT file with one DOI per line. Run [Batch_Markdown.cmd](Batch_Markdown.cmd), drag in the TXT and choose an output folder.

Reading files are in 整理好的Markdown. PDFs, XML and processing records are in 原始资料.

## Missing PDFs

Place each matching main PDF in the article folder indicated by the window. Keep its original filename and one main PDF per article folder.

Run `Retry_PDF_Batch.cmd` in 原始资料 to convert all ready PDFs. Use `Retry_PDF.cmd` inside an article folder to retry just that paper.

Markdown goes to the original reading folder. Completed and missing-PDF items are skipped; results appear in the window and 补PDF批量结果.csv. Abstracts are not full text; review warnings against the original.
