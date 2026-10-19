# PaperFlow V3

中文说明如下，English follows.

## 中文

本次发布将V2的论文获取与保守科学内容检查扩展为更方便的本地批量整理工具。产品标签为 `v3.0.0`，Python包版本为 `0.3.0`；旧V2历史继续保留。

- 新增一键安装，支持中文/English选择，创建或复用项目环境，保留已有配置与论文。
- PDF默认使用MinerU完整API，不要求本地GPU，不调用本地模型，不自动降级。
- 一批正文Markdown集中保存，以论文标题命名；保护人工修改的阅读副本。
- 无法获取全文时生成补PDF指引和单篇/批量CMD；原PDF保留文件名，每篇放入对应目录，一次处理多篇。
- 批量补PDF跳过缺文件、已有成功正文及已生成完整正文的警告条目，单篇失败后继续；输出逐篇清单。
- 扩展公开全文定位、原生XML/HTML/EPUB/TEI导入、Wiley TDM及更多平台入口。
- 提供详细中英文安装、操作、状态解释和发布说明；根目录移除历史检测CMD，开发检测脚本保留。

需要Python 3.10和自己的API配置。源码包不含 `.env`、虚拟环境、论文或模型。PDF上传MinerU可能消耗额度；Elsevier全文XML仍取决于授权及网络。warning可能表示摘要，也可能是已有正文但仍待核验，需查看QA。公开路线不等于所有文章均可获取；部分ACS/SAGE/ASME/OpenReview样本仍受阻或待核验。原文图像不进入最终MD，复杂排版与科学量需要回看原文。

## English

This release extends the V2 acquisition and conservative scientific-content checks with a more accessible local batch workflow. Product tag: `v3.0.0`; Python package: `0.3.0`. V2 history is retained.

- One-click installation with Chinese/English selection, project-local environments and preservation of existing settings/papers.
- Full MinerU API as the PDF default; no local GPU/model calls or automatic downgrade.
- Flat, article-title Markdown reading folders with collision handling and protection of manual edits.
- Generated single/batch PDF recovery launchers; keep original PDF filenames in matching article folders.
- Batch recovery skips missing/converted items, retains warnings, continues after individual failures and writes per-article results.
- Extended public-source discovery, native XML/HTML/EPUB/TEI imports, Wiley TDM and academic platform routes.
- Detailed bilingual setup, usage, status and publishing guides; obsolete root diagnostic launchers removed.

Requires Python 3.10 and user-owned API credentials. Source archives exclude credentials, environments, papers and models. MinerU uploads may consume credits; licensed Elsevier XML depends on entitlement/network. Warnings may indicate abstract-only content or generated body text still requiring verification. Routes do not guarantee every article is available; some ACS/SAGE/ASME/OpenReview samples remain blocked or incompletely verified. Image binaries are omitted from final Markdown; important scientific details still require comparison with the source.
