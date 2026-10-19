# PaperFlow V3

中文说明如下，English follows.

## 中文

本次发布将V2的论文获取与保守科学内容检查扩展为更方便的本地批量整理工具。产品标签为 `v3.0.0`，Python包版本为 `0.3.0`；旧V2历史继续保留。

### 相比V2，新增了哪些文献来源？

V2冻结版本的自动DOI路线主要为 **Elsevier、Building Simulation、Nature Portfolio**。这些在V3中继续保留；Applied Energy、Energy and Buildings、Building and Environment、Nature Communications等原有路线覆盖的期刊，不重复算作V3新增。

V3新增或扩展的出版社/期刊路线如下。表中“通过”指已有代表样本的相应全文核验，不等于该出版社每篇论文均能获取，也不等于每篇都完成了Markdown逐字人工校对。

| 新增或扩展范围 | 已验证的代表或能力 | 当前边界 |
|---|---|---|
| Springer其他期刊及BMC DOI路线 | 从仅专门支持Building Simulation扩展到更多Springer/BMC DOI；International Journal of Computer Vision已有2篇XML/PDF代表样本 | BMC路由识别不代表所有BMC期刊已逐刊验收；订阅全文仍需权限或用户提供PDF |
| IEEE | IEEE Access已有2篇公开PDF；TPAMI覆盖已核验出版版及单独记录的预印本样本 | 稿件版本分别记录；不依赖IEEE元数据API取得全文，也不承诺IEEE订阅全文 |
| Wiley | 增加Wiley TDM与公开全文路线；International Journal of Climatology已有1篇OA PDF | 订阅样本未取得全文；填写TDM token不等于拥有全部订阅权限 |
| Taylor & Francis | Building Research & Information已有2篇公开PDF代表样本 | 具体版本与完整性需核对，不代表全出版社可下载 |
| MDPI | Energies已有2篇官方资源PDF代表样本 | 网站验证或网络限制仍可能影响其他论文 |
| PLOS | PLOS Medicine已有2篇代表样本，并含原生文档转换检查 | 具体论文继续经过身份与全文检查 |
| Frontiers | Frontiers in Energy Research已有2篇代表样本，并含原生文档转换检查 | 不能据此承诺Frontiers全部期刊逐刊通过 |
| eLife | 已有2篇代表样本，并含原生文档转换检查 | 保留论文版本与来源信息 |
| AAAS / Science系列 | Science Advances已有2篇OA样本并完成XML到Markdown转换 | 不代表Science主刊或全部子刊、订阅文章均可获取 |
| Copernicus | Geoscientific Model Development（GMD）已有2篇样本并完成XML到Markdown转换 | 其他期刊按具体论文检查 |
| ACM、IOP、AIP、APS、ASCE | 各有1篇代表论文通过相应全文核验 | 这是出版社/数字图书馆路线扩展，不等于所有期刊都已验收；ACM论文也可能属于会议文献 |

**计算机会议、预印本和公共平台另列，避免混称为期刊：**

| 新增平台 | 类型与代表验证 | 当前边界 |
|---|---|---|
| CVPR / CVF公开入口 | 会议论文，已有2篇CVPR代表样本 | 不作为期刊覆盖数量统计 |
| arXiv | 预印本，已有2篇代表样本 | 预印本不冒充正式出版版 |
| JMLR | 机器学习期刊，已有2篇获取样本，其中1篇实际Markdown转换 | 通过官方论文页入口处理，不编造DOI |
| PMLR | 会议论文集，已有1篇样本并完成实际Markdown转换 | 通过官方论文页入口处理，与期刊区分 |
| Europe PMC | 补充公开全文XML的公共仓储来源 | 不是出版社；按具体论文检查，不作为独立出版社验收通过的承诺 |

**已实现入口，但仍有受阻或待核验样本：**

- **ACS**：包括ACS Energy Letters；此前OA样本仍遇浏览器验证，另一订阅样本未取得授权全文。
- **SAGE**：公开来源已定位，但代表样本仍存在访问/证书问题。
- **ASME**：一篇OA样本受网站验证影响；另一篇有接收稿，出版版及独立完整性核验仍未完成。
- **OpenReview**：平台入口已实现，但代表样本自动访问403；同篇经PMLR入口通过，不等于OpenReview路线已验收。

其他被识别的DOI前缀可能仅使用通用公开全文定位或用户提供PDF，不据此列为已全面支持的出版社。详细历史样本与边界见[验收范围](https://github.com/wzhht/paperflow/blob/main/docs/VALIDATION.md)。

### 使用与处理能力更新

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

### New literature sources compared with V2

The frozen V2 DOI routes principally covered **Elsevier, Building Simulation and Nature Portfolio**. These remain available. Existing Elsevier/Nature journals such as Applied Energy, Energy and Buildings, Building and Environment and Nature Communications are not counted again as new V3 additions.

The following routes are new or expanded. Representative acceptance concerns specific full-text checks, not every article from a publisher or word-by-word manual review of every Markdown file.

| New/expanded scope | Representative validation or capability | Qualifications |
|---|---|---|
| Other Springer journals and BMC DOI routes | Expanded beyond the dedicated Building Simulation route; 2 International Journal of Computer Vision XML/PDF samples | BMC prefix recognition is not journal-by-journal acceptance; subscription access still requires entitlement or a supplied PDF |
| IEEE | 2 IEEE Access public PDFs; TPAMI samples include a verified published version and a separately recorded preprint | Versions remain distinct; full text does not depend on the IEEE metadata API, and subscription coverage is not guaranteed |
| Wiley | Wiley TDM/public routes added; 1 International Journal of Climatology OA PDF | Subscription sample unavailable; a TDM token is not universal subscription access |
| Taylor & Francis | 2 Building Research & Information public PDFs | Verify version/completeness per article; not publisher-wide access |
| MDPI | 2 Energies official-resource PDFs | Other articles can still encounter network or website challenges |
| PLOS | 2 PLOS Medicine samples, including native-document conversion checks | Identity and full-text checks still apply |
| Frontiers | 2 Frontiers in Energy Research samples, including native-document conversion checks | Not acceptance of every Frontiers journal |
| eLife | 2 samples, including native-document conversion checks | Version/source information retained |
| AAAS / Science family | 2 Science Advances OA samples with XML-to-Markdown conversion | Not a claim for Science itself, all sister journals or subscription content |
| Copernicus | 2 Geoscientific Model Development samples with XML-to-Markdown conversion | Other journals require article-specific checks |
| ACM, IOP, AIP, APS, ASCE | 1 representative paper each passed corresponding full-text checks | Publisher/digital-library route expansion, not complete journal coverage; ACM content can include conference papers |

**Conferences, preprints and public platforms are distinguished from journals:**

| New platform | Type and representative checks | Qualifications |
|---|---|---|
| CVPR / public CVF entry | Conference papers; 2 CVPR samples | Not counted as journal coverage |
| arXiv | Preprints; 2 samples | Not silently treated as published versions |
| JMLR | Machine-learning journal; 2 acquisition samples, including 1 actual Markdown conversion | Official paper-page input; no invented DOI |
| PMLR | Conference proceedings; 1 sample with actual Markdown conversion | Official paper-page input, distinct from journals |
| Europe PMC | Additional public full-text XML repository | Not a publisher or a separate publisher-wide acceptance claim |

**Implemented entry points with blocked or incompletely verified samples:**

- **ACS**, including ACS Energy Letters: an OA sample still met browser verification; another subscription sample lacked authorized full text.
- **SAGE**: public sources located, but the representative sample had access/certificate issues.
- **ASME**: an OA sample met website verification; another has an accepted manuscript, with published-version/independent completeness checks still incomplete.
- **OpenReview**: platform input implemented, but the sample returned HTTP 403. Acceptance through PMLR for the same paper does not validate the OpenReview route.

Other recognized DOI prefixes may only use generic public discovery or user-supplied PDFs and are not advertised as fully supported publishers. See the [detailed validation scope](https://github.com/wzhht/paperflow/blob/main/docs/VALIDATION.en.md).

### Workflow and processing changes

- One-click installation with Chinese/English selection, project-local environments and preservation of existing settings/papers.
- Full MinerU API as the PDF default; no local GPU/model calls or automatic downgrade.
- Flat, article-title Markdown reading folders with collision handling and protection of manual edits.
- Generated single/batch PDF recovery launchers; keep original PDF filenames in matching article folders.
- Batch recovery skips missing/converted items, retains warnings, continues after individual failures and writes per-article results.
- Extended public-source discovery, native XML/HTML/EPUB/TEI imports, Wiley TDM and academic platform routes.
- Detailed bilingual setup, usage, status and publishing guides; obsolete root diagnostic launchers removed.

Requires Python 3.10 and user-owned API credentials. Source archives exclude credentials, environments, papers and models. MinerU uploads may consume credits; licensed Elsevier XML depends on entitlement/network. Warnings may indicate abstract-only content or generated body text still requiring verification. Routes do not guarantee every article is available; some ACS/SAGE/ASME/OpenReview samples remain blocked or incompletely verified. Image binaries are omitted from final Markdown; important scientific details still require comparison with the source.
