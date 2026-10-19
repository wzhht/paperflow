# PaperFlow

**中文** | [English](README_EN.md)

本地学术论文获取与 Markdown 转换工具：输入 DOI 或已有论文文件，优先使用结构化全文；需要解析 PDF 时调用 MinerU API，不启动本地 MinerU 或 GPU 模型。

支持公开全文获取、原生XML/HTML/EPUB/TEI导入、MinerU API解析，以及按论文标题集中保存Markdown。

**第一次解压源码包，请先完成下面的安装步骤，再双击一键入口。** 源码ZIP不是免安装软件，不含 `.venv`、`.env` 或MinerU。

| 我现在要做什么 | 去哪里 |
|---|---|
| 第一次安装、选择语言、填写API | 下方“首次解压安装” |
| 批量输入DOI并整理MD | 下方“日常使用” |
| 自己下载了四五篇PDF，想一次转完 | [操作手册：补PDF完整步骤](docs/USAGE.zh-CN.md) |
| 看懂文件位置、warning、重复运行和常见错误 | [详细操作手册](docs/USAGE.zh-CN.md) |

英文对应文档：[README](README_EN.md)、[User guide](docs/USAGE.en.md)。


## 首次解压安装（Windows）

**推荐：完整解压后双击 [一键安装.cmd](一键安装.cmd)。**

1. 选择 `1 中文` 或 `2 English`。
2. 程序检查Python 3.10，在当前项目内创建或复用 `.venv`，安装PaperFlow及依赖。安装需要网络，不需要管理员权限。
3. 安装完成后用记事本打开 `.env`，填写自己的API，再双击 `一键批量整理Markdown.cmd`。

缺少Python时会显示官方安装链接；安装程序不会自动下载运行Python安装包。已有 `.env`、文献和历史结果不会删除或覆盖；可用的虚拟环境会复用并更新项目依赖。损坏的环境会提示处理，不会自动清除。
安装时选择的语言用于日常批量处理、补PDF提示和结果汇总。原始论文不翻译，文件夹名称和已有数据结构保持兼容。语言保存在本机 `.paperflow-language`，不提交Git。重新运行安装入口可以切换语言；临时切换可使用 `一键批量整理Markdown.cmd --language en` 或 `--language zh`。第三方pip/MinerU日志保留其原始语言。

只检查安装条件、不安装或修改配置：

```bat
一键安装.cmd --language en --check
```

下面保留手动安装步骤，供缺少Python或需要排错时使用。

### 1. 解压并确认位置

例如解压到 `D:\paper\paperflow-v3`。这个目录内应该直接看到 `pyproject.toml`、`README.md`、`src`、`scripts` 和 `一键安装.cmd`、`一键批量整理Markdown.cmd`。
不要在ZIP预览窗口里直接运行。如果多套了一层文件夹，应进入真正包含这些文件的目录。

### 2. 准备Python 3.10

在CMD中运行：

```bat
py -3.10 --version
```

看到 `Python 3.10.x` 才继续。如果提示找不到 `py` 或没有合适的Python，请先安装 [Python 3.10的Windows 64位安装程序](https://www.python.org/downloads/release/python-31011/)，安装时保留pip和Python Launcher，勾选添加Python到PATH，然后重新打开CMD。

当前项目要求 `>=3.10,<3.11`，不要直接用电脑上默认的3.11/3.12等版本代替。Python 3.10已结束官方维护；这里是现有V3的兼容安装步骤，更高Python版本尚需另行验收。

### 3. 在解压目录创建环境并安装

打开CMD，**逐行执行**下面命令。若解压位置不同，只替换第一行的目录：

```bat
cd /d "D:\paper\paperflow-v3"
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
if not exist .env copy .env.example .env
.venv\Scripts\paperflow.exe version
```

最后应显示 `PaperFlow 0.3.0`。其中 `pip install` 需要网络；失败时先解决上方报错，不要继续双击运行。
不必激活虚拟环境，也不需要修改PowerShell执行策略。

不要把旧项目的 `.venv` 文件夹复制过来：虚拟环境记录了原Python路径。新解压目录应建立自己的环境；原项目已能运行的环境无需重建。

如果没有 `py`，但知道已安装的Python 3.10完整路径，可用 `"C:\实际安装位置\python.exe" -m venv .venv` 代替第二行，后续命令不变。

### 4. 填写配置

```bat
notepad .env
```

按下方配置表填写自己的API和MinerU设置。已有 `.env` 不会被上述复制命令覆盖。
这台电脑原来有配置时，可以自行从旧 `.env` 复制所需配置项；密钥只保存在本机，不上传GitHub。

PDF默认使用MinerU完整API：保留 `MINERU_BACKEND=api`，填写自己的 `MINERU_API_TOKEN`（兼容已有 `MINERU_API` / `MINERU_API_KEY`）。PDF将上传MinerU服务，可能消耗API额度，不需要安装本地MinerU或GPU依赖。
旧配置中的 `MINERU_BACKEND=local` 请改为 `api`；`MINERU_EXECUTABLE` 和 `MINERU_TIER` 已不再使用。API缺少token或调用失败会明确报错，不会切回本地。
只有XML获取和转换时不需要调用MinerU。

### 5. 开始使用

安装和配置完成后，双击 `一键批量整理Markdown.cmd`。以后日常使用不必重复安装。
若提示“尚未创建本目录的虚拟环境”，回到第3步；若提示“程序或依赖尚未安装”，重新执行 `.venv\Scripts\python.exe -m pip install -e .` 并查看错误。

## 日常使用：一批论文，一个阅读目录

1. 准备 TXT，每行一个 DOI。
2. 双击 **`一键批量整理Markdown.cmd`**，把 TXT 拖进窗口并回车；也可把 TXT 直接拖到启动文件上。
3. 选择保存目录，或回车使用默认位置。

```text
本批资料/
├─ 整理好的Markdown/
│  ├─ 第一篇论文标题.md
│  ├─ 第二篇论文标题.md
│  └─ export_manifest.csv
└─ 原始资料/
   ├─ 每篇论文的原始文件和处理记录/
   ├─ batch_results.csv
   ├─ 补齐PDF后批量转换.cmd
   ├─ 批量补PDF转换配置.json
   └─ 待补PDF说明.txt（有失败或仅摘要条目时生成）
```

100篇全部转换成功，就在一个阅读目录得到100个正文MD。重名自动区分，非法文件名字符清理，过长标题缩短；完整标题保留在清单里。默认不混入摘要，不覆盖自行修改的阅读副本。

下不了全文时，查看终端或 `待补PDF说明.txt`，按以下步骤操作：

1. 自行下载对应论文的正文PDF，保留原文件名，放进提示的论文目录，无需改名。
2. 双击该目录中的 **`补好PDF后双击转换.cmd`**。
3. 窗口显示API转换结果；通过正文检查后，Markdown会补进原来的阅读目录，无需复制命令。

一次补四五篇或更多PDF：保留下载时的原文件名，分别放进各自提示的论文目录，然后只需双击本批 **“原始资料”目录中的 `补齐PDF后批量转换.cmd`**。它逐篇处理已放好的PDF，缺PDF和已有合格正文的会跳过；一篇失败不影响后面的论文。查看终端汇总或 `补PDF批量结果.csv`，下一次补齐后仍双击同一个入口。已生成正文但有核验警告的会保留警告并跳过，避免重复消耗API额度。每个论文目录只放对应的正文PDF；若有多个PDF，程序会提示移出补充材料或重复版本，不会猜选。

若已有PDF、只是解析/API失败，不必重新下载，排除故障后直接双击重试。窗口会停留以便查看错误。入口旁的 `补PDF转换配置.json` 记录DOI和输出位置，请保留；不包含密钥。转换会上传PDF到MinerU并可能消耗额度，不启动本地模型。移动项目后应重新生成入口。命令行方式仍保留。

简短操作说明：[批量Markdown使用说明.txt](批量Markdown使用说明.txt)。更详细的目录示意、单篇/多篇补PDF、无DOI本地PDF、状态解释和排错见 [完整操作手册](docs/USAGE.zh-CN.md)。

补PDF不会重写原来的 `batch_results.csv` 历史记录；查看最近的 `补PDF批量结果.csv` 及本篇最新 `qa.json`。批量入口跳过已生成完整正文但带核验警告的论文，不代表警告已经解决。

## 环境和配置

完整安装步骤见上文。已有环境的用户只需在项目根目录更新本项目；需要pytest/Ruff开发工具时安装可选依赖：

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\paperflow.exe version
```

复制 `.env.example` 为 `.env`，按需填写，也兼容系统环境变量。密钥不提交Git、不粘贴到日志或GitHub。

| 配置 | 用途 |
|---|---|
| `ELSEVIER_API_KEY` | Elsevier全文XML；仍受授权和网络约束 |
| `ELSEVIER_INSTTOKEN` | 可选机构token |
| `SPRINGER_OA_API_KEY` | Springer Nature OA XML，不增加订阅权限 |
| `SPRINGER_META_API_KEY` | 可选元数据；元数据不是全文 |
| `WILEY_API_KEY` | 可选Wiley TDM；兼容 `Wiley_API_KEY`、`WILEY_TDM_API_KEY` |
| `OPENALEX_API_KEY` | 可选公开全文定位及符合条件时的OA存档 |
| `CROSSREF_MAILTO`、`UNPAYWALL_EMAIL` | 元数据联系邮箱、Unpaywall定位 |
| `IEEE_API_KEY`、`IEEE_API_ENABLED` | 可选IEEE元数据；停用API不影响公开PDF入口 |
| `MINERU_BACKEND` | `api`（默认，完整API）、`api-light`（能力有限，需显式选择）；不支持本地模型 |
| `MINERU_API_TOKEN` | API token；兼容 `MINERU_API_KEY`、`MINERU_API` |
| `MINERU_API_MODEL`、`MINERU_API_TIMEOUT` | 默认 `vlm`、600秒 |

PaperFlow不再调用本地MinerU，环境不必装GPU PyTorch。API转换可能消耗额度，轻量API与完整API的能力、质量不同；不会自动降级。
校园网/VPN会影响访问范围；程序不自行切换网络。Elsevier已在具有授权的校园网出口验证全文XML。

## CLI

以下命令适用于PowerShell和CMD；CMD先用 `cd /d` 进入项目目录。

```powershell
# 批量处理并集中导出
.venv\Scripts\paperflow.exe process-list "D:\papers\dois.txt" --library-root "D:\papers\本批资料\原始资料" --markdown-dir "D:\papers\本批资料\整理好的Markdown"

# 已有结果只导出，不下载、不用GPU或MinerU
.venv\Scripts\paperflow.exe export-markdown "D:\papers\阅读目录" --library-root "D:\papers\原始资料"

# 单篇DOI
.venv\Scripts\paperflow.exe process "10.1016/j.apenergy.2011.11.048" --library-root workspace\library

# 已有正文PDF，显式使用MinerU API
.venv\Scripts\paperflow.exe process "10.1021/acsenergylett.4c01233" --pdf "D:\papers\article.pdf" --library-root workspace\library --mineru-backend api --markdown-dir workspace\reading

# 无DOI本地PDF，不编造DOI
.venv\Scripts\paperflow.exe parse-pdf "D:\papers\article.pdf" --output-root workspace\library --markdown-dir workspace\reading

# 已有Elsevier全文XML，不重新获取
.venv\Scripts\paperflow.exe process "10.1016/j.apenergy.2011.11.048" --xml "D:\papers\article.xml" --library-root workspace\library

# 原生XML、论文HTML、EPUB；可选--doi，提供时须匹配
.venv\Scripts\paperflow.exe process-document "D:\papers\article.xml" --output-root workspace\library --markdown-dir workspace\reading

# 官方论文页，只有下载与核验
.venv\Scripts\paperflow.exe process-url "https://proceedings.mlr.press/v202/dettmers23a.html" --download-only
```

`--pdf`、`--pdf-url`、`--xml` 三选一。阅读目录与原始目录必须分开，不能相互包含。`export-markdown --include-partial` 可显式导出带 `[ABSTRACT ONLY]` 标记的摘要。更多参数用各命令的 `--help` 查看。

## 范围和质量边界

已有Elsevier、Springer/Nature、Building Simulation、IEEE/CVF/arXiv、Wiley、PLOS、Frontiers、eLife、Europe PMC、Copernicus、MDPI资源文件、JMLR/PMLR等路线。**识别DOI不代表该出版社全部期刊都能下载**。代表样本及未解决项目见 [验收范围](docs/VALIDATION.md)。

正文、References和可靠的结构化表格数值尽量保留；不输出图片本体，独立展示公式可移除，行内科学量尽量保留。不会伪造图片表格。OCR、公式、复杂排版仍可能有错，重要内容需回看原文。

获取文件、论文身份、完整性、Markdown转换是不同阶段。作者稿/预印本不冒充出版版，摘要不冒充全文。只用公开或已有授权的来源，不绕过付费墙、网站挑战或TLS验证。

## 检测与开发

- `scripts/check_elsevier_api.py`：比较自己的API，不必反复修改 `.env`，见 [检测说明](scripts/Elsevier_API检测说明.txt)。

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe scripts\check_public_extensions.py --group PMLR
```

检测报告保存在 `workspace` 中；具体使用方法见 [操作手册](docs/USAGE.zh-CN.md)。
