# PaperFlow

中文 | [English](README_EN.md)

按DOI批量获取论文，转换为Markdown。文件按论文标题集中保存，不含图片。

## 安装

Windows，Python 3.10（[下载](https://www.python.org/downloads/release/python-31011/)）。

双击 [Install.cmd](Install.cmd)，选择语言。安装完成后打开 `.env`，填写自己的API：

```ini
ELSEVIER_API_KEY=你的Elsevier key
MINERU_BACKEND=api
MINERU_API_TOKEN=你的MinerU token
```

Elsevier全文XML需要相应权限；PDF由MinerU API解析，无需本地GPU，可能消耗额度。其他配置按 `.env.example` 选填。请勿公开 `.env`。

## 使用

准备一个TXT，每行一个DOI。双击 [Batch_Markdown.cmd](Batch_Markdown.cmd)，拖入TXT，选择保存位置。

结果在“整理好的Markdown”；PDF、XML和处理记录在“原始资料”。

## 补PDF

未取得全文时，按窗口提示把正文PDF放进对应论文目录，保留原文件名，每篇只放一份正文。

然后双击“原始资料”中的 `Retry_PDF_Batch.cmd`，一次转换所有放好的PDF。只重试一篇可用其目录里的 `Retry_PDF.cmd`。

Markdown仍保存到原来的阅读目录。已有完整正文或缺PDF的自动跳过；处理结果见窗口和 `补PDF批量结果.csv`。摘要不算全文，有警告时请核对原文。
