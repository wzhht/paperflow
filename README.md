# PaperFlow

中文 | [English](README_EN.md)

按DOI批量获取论文，转换为Markdown。文件按论文标题集中保存，不含图片。

保留行内和独立公式，使用 LaTeX 数学格式。PDF 公式依赖 MinerU 识别，重要公式请对照原文；以前生成的 Markdown 不会自动更新。

## 文献来源

| 来源 | 期刊或平台举例 |
|---|---|
| Elsevier | Applied Energy、Energy and Buildings、Building and Environment、Journal of Building Engineering |
| Springer Nature | Building Simulation、Nature Communications、International Journal of Computer Vision，以及其他已有OA获取路线 |
| IEEE | IEEE Access、TPAMI、CVPR会议论文 |
| 其他出版社 | Wiley、Taylor & Francis、MDPI、PLOS、Frontiers、eLife、AAAS、Copernicus、ACM、IOP、AIP、APS、ASCE |
| 论文平台 | arXiv、JMLR、PMLR |

全文获取取决于文章开放状态和已有权限，获取失败可自行补PDF。

## 安装

Windows，Python 3.10（[下载](https://www.python.org/downloads/release/python-31011/)）。

双击 [Install.cmd](Install.cmd)，选择语言。安装完成后打开 `.env`，填写自己的API：

```ini
ELSEVIER_API_KEY=你的Elsevier key
MINERU_BACKEND=api
MINERU_API_TOKEN=你的MinerU token
```

Elsevier全文XML需要相应权限；PDF由MinerU API解析，无需本地GPU，可能消耗额度。其他配置按 `.env.example` 选填。请勿公开 `.env`。

<details>
<summary>手动安装（CMD）</summary>

在项目文件夹的资源管理器地址栏输入 `cmd` 并回车，再逐行执行。已有可用的 `.venv` 时跳过第一行。

```bat
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
if not exist .env copy .env.example .env
echo zh>.paperflow-language
.venv\Scripts\paperflow.exe version
notepad .env
```

填写自己的API后保存 `.env`，再运行 `Batch_Markdown.cmd`。使用英文可将 `echo zh` 改为 `echo en`。

</details>

## 使用

准备一个TXT，每行一个DOI，不加标题或编号。例如 [example_dois.txt](example_dois.txt)：

```text
10.1016/j.jobe.2024.110286
10.1007/s12273-025-1335-6
10.1016/j.buildenv.2025.114072
```

双击 [Batch_Markdown.cmd](Batch_Markdown.cmd)，拖入TXT，选择保存位置。示例可直接试用，是否取得全文取决于你的权限和网络。

结果在“整理好的Markdown”；PDF、XML和处理记录在“原始资料”。

## 补PDF

未取得全文时，按窗口提示把正文PDF放进对应论文目录，保留原文件名，每篇只放一份正文。

然后双击“原始资料”中的 `Retry_PDF_Batch.cmd`，一次转换所有放好的PDF。只重试一篇可用其目录里的 `Retry_PDF.cmd`。

Markdown仍保存到原来的阅读目录。已有完整正文或缺PDF的自动跳过；处理结果见窗口和 `补PDF批量结果.csv`。摘要不算全文，有警告时请核对原文。
