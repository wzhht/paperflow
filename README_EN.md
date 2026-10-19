# PaperFlow

[中文](README.md) | **English**

Turn a DOI list into full-text Markdown. Each batch has one reading folder, with files named after article titles and image binaries omitted.

## 1. Install

Extract the complete project, run **[Install.cmd](Install.cmd)**, choose Chinese or English, and follow the prompts.

Requires Python 3.10. If it is missing, the launcher provides the [download link](https://www.python.org/downloads/release/python-31011/); install Python and run `Install.cmd` again. Installation needs network access and preserves existing settings and papers.

## 2. Configure your APIs

Open the project's `.env` in Notepad and enter your own values:

```ini
ELSEVIER_API_KEY=your_elsevier_key
MINERU_BACKEND=api
MINERU_API_TOKEN=your_mineru_token
```

Configure only what you need: Elsevier API retrieves entitled full-text XML; PDF conversion requires MinerU API, also accepting the existing `MINERU_API` alias. No local GPU is needed. PDFs are uploaded and may consume credits. Other API settings are optional; see comments in `.env.example`.

## 3. Process a batch

1. Prepare a TXT file with one DOI per line.
2. Run **[Batch_Markdown.cmd](Batch_Markdown.cmd)**, drag the list into the window and press Enter.
3. Choose an output folder and wait for individual results.

```text
Batch/
├─ 整理好的Markdown/   Title-named reading files
└─ 原始资料/           PDFs, XML and processing records
```

Implemented acquisition routes cover Elsevier, Springer Nature and other publishers/platforms. Automatic full-text availability depends on the article and access rights; missing full text can be supplied as a PDF.

## 4. Add several missing PDFs at once

1. Find each article's folder from the terminal or `原始资料/待补PDF说明.txt`.
2. Place the matching main PDF there, **keeping its original filename**. Keep one main PDF per article folder.
3. Return to the batch's `原始资料` folder and run **`Retry_PDF_Batch.cmd`** once.

Markdown goes into the original reading folder. Missing PDFs and already converted full-text items are skipped; individual failures do not stop later papers. Read the window and `补PDF批量结果.csv` for results.

To retry one paper, use `Retry_PDF.cmd` inside its folder. If the PDF already exists and only parsing failed, fix the reported issue and retry without downloading again.

## Notes

- Review per-paper results: abstracts are not full text, and warnings require checking the original.
- Keep `.env` private. Source archives exclude your environment and papers.
- Rerun `Install.cmd` to change language. Papers are not translated; third-party logs retain their original language.
