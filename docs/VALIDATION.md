# V3 验收范围

[English](VALIDATION.en.md) · [操作手册](USAGE.zh-CN.md)

截至2026-10-19的本机历史验收，来自不同日期、网络与独立复核，**不是同一时刻重跑全部样本的成功率**，不保证同一期刊每篇都能获取。

## 已有代表样本通过相应全文核验

| 期刊／平台 | 范围及注意事项 |
|---|---|
| Applied Energy | 3篇Elsevier全文XML，具备授权的校园网出口 |
| Energy and Buildings、Building and Environment、Energy、Renewable and Sustainable Energy Reviews | 各2篇Elsevier全文XML，同上 |
| Building Simulation | 2篇PDF |
| Nature Communications | 3篇OA全文XML |
| International Journal of Computer Vision | 2篇XML/PDF |
| IEEE Access | 2篇公开PDF，不依赖停用的IEEE API |
| TPAMI | 1篇出版版、1篇核验过的预印本，版本分别记录 |
| CVPR、arXiv | 各2篇，分别是会议论文和预印本 |
| International Journal of Climatology | 1篇OA PDF；订阅样本未通过 |
| PLOS Medicine、Frontiers in Energy Research、eLife | 各2篇，含原生文档转换检查 |
| Building Research & Information | 2篇公开PDF，核对正文页码与前置封面 |
| Energies | 2篇官方资源PDF，逐页页码/总页数与DOI核对 |
| JMLR、PMLR | 分别2篇、1篇；各有1篇实际Markdown转换 |
| Science Advances、Copernicus/GMD | 各2篇，并实际转换XML到Markdown |
| ACM、IOP、AIP、APS、ASCE | 各1篇；不代表整个出版社均通过 |

获取/完整性通过不等于该样本已经实际调用MinerU。新增扩展中，JMLR/PMLR各1篇、Science Advances/Copernicus各2篇共6篇完成真实Markdown转换；PDF使用已有MinerU API，XML使用本地转换。没有宣称全部论文逐字人工校对。

## 受阻或未完成

| 样本 | 状态 |
|---|---|
| ACS `10.1021/acsenergylett.4c01233` | 确认OA，官方PDF仍遇浏览器验证，未取得独立全文 |
| ACS `10.1021/acsenergylett.3c02406` | 非OA，未取得授权全文 |
| SAGE `10.1177/01436244211001497` | OA和大学仓储已定位，访问/证书问题，未取得可核验PDF |
| ASME `10.1115/1.4072593` | OA，官方PDF遇验证 |
| ASME `10.1115/1.4069386` | 有23页接收稿，身份/结构确认；独立完整性及10页出版版核验未完成 |
| OpenReview `i8tGb1ab1j` | 自动入口403；同篇PMLR正式入口通过，不代表OpenReview通过 |
| Nature Climate Change `10.1038/nclimate2841`、`10.1038/nclimate1580` | 订阅样本未取得全文 |
| Wiley `10.1002/joc.8834` | 未取得全文 |

Semantic Scholar/OSTI实验路线已删除。不自动处理网站挑战，不关闭TLS验证。能在浏览器取得正文时可使用本地PDF入口。

## 核验规则与复测

结构化全文核对DOI、章节/段落规模、References和表格数值。PDF分别检查签名、可解析性、可信页数、连续正文页码/封面或独立版本对照。稿件版本必须区分，不能因页数不同就直接判断缺页，亦不能因结构齐全就直接放行。

曾发现IOP的169页候选标题不匹配，已拒绝；后取得67页正确出版正文加封面并与独立机构版逐页对照。AIP、ASCE、APS、IOP后续完成出版版复核，旧的初轮待核验报告不应作为最终状态。

本机 `workspace/pdf_verifications.json` 只有DOI和完整SHA-256均匹配才复用已审查结论，记录不随源码发布。新机器不能自动继承本机核验。

两个历史检测CMD入口已移除；开发者可运行 `scripts/check_publishers.py` 或 `scripts/check_public_extensions.py` 检测。默认不调用MinerU/GPU；XML另做本地转换。显式 `--parse-pdf` 才调用已有MinerU API，可能消耗额度。

原始报告保留在本机 `workspace/publisher_checks`、`workspace/public_extensions` 等目录，不打包进GitHub。只有完成的报告用于整批统计；获取失败、待核验和通过分别报告。新机器需自行测试并检查实际授权网络。
