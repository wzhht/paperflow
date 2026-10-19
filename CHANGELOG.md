# 更新记录 / Changelog

## V3 / 0.3.0 — 2026-10-19

- 保留V2主要转换路线与科学内容QA。
- 增加公开全文定位、原生XML/HTML/EPUB/TEI导入、Wiley TDM及更多学术平台入口。
- PDF默认使用MinerU完整API，可显式选择轻量API；不再调用本地MinerU，不自动回退。
- 按论文标题命名并集中导出Markdown，同名自动区分，保护人工修改的阅读副本。
- 增加中英文一键安装和批量处理入口，保留已有配置、环境及文献。
- 生成单篇/批量补PDF入口；保留下载文件名，逐篇处理，跳过缺失/已完成项，保留警告。
- 根目录移除两个历史检测CMD，开发检测脚本继续保留。
- 文件获取、论文身份、完整性和转换分别检查；作者稿、预印本、摘要状态分别记录。
- 增加可重复运行的出版社检测与API比较工具。
- Semantic Scholar/OSTI实验路线撤回，部分ACS/SAGE/ASME/OpenReview样本仍未通过。
- 清理重复开发说明和临时smoke脚本，整合中英文README与验收记录。

不承诺取得所有出版社的所有订阅论文。历史样本与边界见 `docs/VALIDATION.md`。

## English — V3 / 0.3.0

- Retains V2 core renderers and scientific-content QA.
- Adds public/native full-text routes and full MinerU API parsing without local GPU calls.
- Includes bilingual installation, DOI batching, original-name single/batch PDF recovery and title-named reading copies.
- Keeps acquisition, identity, completeness and rendering checks distinct; manuscript/abstract limitations remain explicit.
- Removes obsolete root diagnostic CMDs and temporary development files while retaining reusable diagnostic scripts.
- Provides bilingual user/publishing guides and release notes. Product tag `v3.0.0` maps to package `0.3.0`, retaining the old `v2.0.0` product tag.

See [validation scope](docs/VALIDATION.en.md) for representative historical checks and unresolved samples.
