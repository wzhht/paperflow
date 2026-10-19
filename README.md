# PaperFlow

**中文** | [English](README_EN.md)

输入论文DOI，获取全文并整理成Markdown。每批文章放在同一个阅读目录，文件按论文标题命名，不输出图片。

## 1. 安装

完整解压后，双击 **[Install.cmd](Install.cmd)**，选择中文或English，按提示完成安装。

需要Python 3.10；未安装时窗口会给出[下载地址](https://www.python.org/downloads/release/python-31011/)。安装Python后重新运行 `Install.cmd`。安装需要网络，已有配置和论文会保留。

## 2. 填写API

用记事本打开项目中的 `.env`，填写自己的配置：

```ini
ELSEVIER_API_KEY=你的Elsevier API key
MINERU_BACKEND=api
MINERU_API_TOKEN=你的MinerU API token
```

按需填写：Elsevier API用于有权限的全文XML；PDF转换需要MinerU API，兼容已有的 `MINERU_API` 字段。不需要本地GPU，PDF会上传解析并可能消耗额度。其他API可按 `.env.example` 中的注释选填。

## 3. 批量整理

1. 准备TXT清单，每行一个DOI。
2. 双击 **[Batch_Markdown.cmd](Batch_Markdown.cmd)**，将清单拖入窗口并回车。
3. 选择保存位置，等待逐篇结果。

```text
本批资料/
├─ 整理好的Markdown/   按论文标题命名的阅读文件
└─ 原始资料/          PDF、XML和处理记录
```

支持Elsevier、Springer Nature等出版社及常见论文平台的已有获取路线。能否自动获取全文取决于具体论文和访问权限；获取失败可补PDF。

## 4. 补PDF，一次处理多篇

1. 按窗口或 `原始资料/待补PDF说明.txt` 的提示，找到每篇论文的目录。
2. 把对应正文PDF放进去，**保留原文件名，不用改名**；每个论文目录只放一份正文。
3. 回到本批“原始资料”，双击 **`Retry_PDF_Batch.cmd`**，一次处理所有放好的PDF。

生成的Markdown仍进入原来的阅读目录。缺PDF或已有完整正文的条目自动跳过；某一篇失败不影响后面的处理。结果见窗口及 `补PDF批量结果.csv`。

只重试一篇时，双击其目录内的 `Retry_PDF.cmd`。如果PDF已经存在、只是解析失败，解决窗口提示的问题后直接重试，不必重新下载。

## 提示

- 查看每篇处理结果；摘要不等于全文，有警告时请核对原文。
- `.env` 包含私密配置，不上传或分享；源码包不包含你的环境和论文。
- 更换语言可重新运行 `Install.cmd`。原文不翻译，第三方日志保留原始语言。
