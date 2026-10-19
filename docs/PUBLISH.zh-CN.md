# 将PaperFlow V3发布到现有GitHub仓库

[English](PUBLISH.en.md) · [首页](../README.md)

## 发布目标

- GitHub仓库继续使用：<https://github.com/wzhht/paperflow-v2>。
- 产品名称：PaperFlow V3。
- Python包版本：`0.3.0`，与当前代码一致。
- GitHub发布标签：`v3.0.0`，沿用历史 `v2.0.0` 的产品版本命名。
- Release标题：`PaperFlow V3`。

Git标签是产品发布标记，Python包版本是安装元数据；本项目V2也采用不同的两套编号。这里明确记录对应关系，不覆盖旧标签，也不需要改GitHub仓库名。

2026-10-19只读核对：远端 `main` 与本机基线均为 `fe85eb0`。本机有指向V2冻结基线的 `v2.0.0`，远端当时还没有标签；这是发布前快照，实际推送前仍应重新读取远端。

## 1. 从哪个目录上传

这台电脑保留Git历史的工作目录是 `D:\paper\paperflow-v2`，已配置origin指向上面的仓库。
`D:\paper\paperflow-v3` 是安装使用副本，包含自己的环境、配置和论文，不是用于发布的Git工作目录。

**在 `paperflow-v2` 工作目录提交源码；不要把整个V3使用目录拖进GitHub网页。** 不要在V3使用副本里重新 `git init` 或删除原仓库。

发布代码包括：`src`、`scripts`、`tests`、`docs`、README、CHANGELOG、`pyproject.toml`、`.env.example` 和两个根目录CMD。

不上传：`.env`、`.venv`、`.paperflow-language`、`workspace`、论文PDF/XML/Markdown数据、API响应、模型缓存、日志。`.env.example` 是空配置模板，可以上传；`.gitignore` 不会自动移除以前已被Git追踪的文件，因此还需检查提交清单。

## 2. 发布前检查

打开CMD，逐行执行。每一步失败就先处理错误，不要继续提交或推送：

```bat
cd /d D:\paper\paperflow-v2
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check --no-cache src tests scripts
git -c safe.directory=D:/paper/paperflow-v2 status --short
git -c safe.directory=D:/paper/paperflow-v2 remote -v
git -c safe.directory=D:/paper/paperflow-v2 tag --list
git -c safe.directory=D:/paper/paperflow-v2 ls-files .env .venv workspace .paperflow-language
```

最后一条应没有输出。确认origin为 `https://github.com/wzhht/paperflow-v2.git`，旧 `v2.0.0` 标签仍存在。
若缺pytest/Ruff，只在该项目环境安装开发依赖：`.venv\Scripts\python.exe -m pip install -e ".[dev]"`。

命令中的 `-c safe.directory=...` 仅作用于这一次Git调用，处理该工作目录的所有权检查，不修改全局Git配置。

## 3. 先读取远端，再提交

GitHub访问需要能连接GitHub的网络；它与论文获取时所需的校园网条件可能不同。不要为了推送而修改论文授权设置。

```bat
git -c safe.directory=D:/paper/paperflow-v2 fetch origin
git -c safe.directory=D:/paper/paperflow-v2 branch --show-current
git -c safe.directory=D:/paper/paperflow-v2 rev-list --left-right --count origin/main...HEAD
```

本次发布预期在 `main`。最后一条的两个数分别是远端独有提交数、本地独有提交数。提交V3前两者为 `0 0` 时可按下列步骤继续。
如果远端独有提交数不为0，先比较并整合远端变化；不要盲目覆盖、重置或强制推送。若本地有尚未推送的提交，也先确认其内容属于这次发布。

明确添加源码和说明，不使用全盘文件上传：

```bat
git -c safe.directory=D:/paper/paperflow-v2 add .env.example .gitignore .gitattributes pyproject.toml README.md README_EN.md CHANGELOG.md docs scripts src tests "一键安装.cmd" "一键批量整理Markdown.cmd" "批量Markdown使用说明.txt"
git -c safe.directory=D:/paper/paperflow-v2 diff --cached --stat
git -c safe.directory=D:/paper/paperflow-v2 diff --cached --name-only
git -c safe.directory=D:/paper/paperflow-v2 diff --cached --check
```

检查清单中没有真实 `.env`、论文数据、虚拟环境或日志。确认删除的是废弃开发文件，新增的是已检查的V3源码和说明。

检查无误后：

```bat
git -c safe.directory=D:/paper/paperflow-v2 commit -m "Release PaperFlow V3"
git -c safe.directory=D:/paper/paperflow-v2 push origin main
git -c safe.directory=D:/paper/paperflow-v2 push origin v2.0.0
```

第二条推送命令把已有的本机V2冻结标签补到GitHub，保留旧版入口；不新建、不移动该标签。若远端后来出现同名标签，先核对，不要强制覆盖。

登录GitHub时使用Git自己的凭据管理或浏览器授权，不把token写入远程URL或命令历史。推送失败先解决认证或网络，不要添加 `--force`。

这些命令是发布说明；整理文档和生成ZIP不会自动替你提交、推送或发布。

## 4. 在GitHub创建V3 Release

代码推送成功后，打开 [新建Release页面](https://github.com/wzhht/paperflow-v2/releases/new)：

1. Choose a tag：输入 `v3.0.0` 并创建新标签。
2. Target：选择包含V3提交的 `main`，核对提交确实是本次更新。
3. Previous tag：可选 `v2.0.0`，旧版本继续保留。
4. Release title：填写 `PaperFlow V3`。
5. 将 [RELEASE_NOTES_V3.md](RELEASE_NOTES_V3.md) 的中英文说明粘贴到正文。
6. 可添加经过检查的源码ZIP及SHA-256校验文件；不能添加整个本机使用目录。
7. 选择“Set as latest release”。需要先检查时先“Save draft”，全部确认后再“Publish release”。

不要仅把ZIP作为附件上传就认为仓库代码已经更新。代码推送与Release附件是两个动作。

GitHub官方步骤：[Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。

## 5. 发布后的确认

- 仓库首页显示PaperFlow V3和新的中英文README。
- 根目录只有安装、批量整理两个CMD，已移除旧检测CMD。
- Release存在 `v3.0.0`，旧 `v2.0.0` 标签仍可访问。
- 下载公开源码ZIP后能看到安装入口、操作手册、空 `.env.example`；不包含真实密钥和论文。
- 新用户按README安装，`paperflow version` 显示 `PaperFlow 0.3.0`。
- 本机原有 `.env`、文献和ResearchFlow索引未因发布被替换或删除。
