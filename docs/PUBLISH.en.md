# Publishing PaperFlow V3 to the existing repository

[中文](PUBLISH.zh-CN.md) · [Home](../README_EN.md)

## Naming

Use repository name `paperflow` at <https://github.com/wzhht/paperflow>. Use product/release title **PaperFlow V3**, Git tag **`v3.0.0`**, and the existing Python package version **`0.3.0`**. This continues the historical product-tag naming (`v2.0.0`), which is separate from package metadata. Preserve the old tag; the homepage and repository name use PaperFlow, while versions remain in release history.

Read-only check on 2026-10-19: remote `main` and the local baseline both pointed to `fe85eb0`. The local `v2.0.0` frozen-baseline tag had not yet been pushed; no remote tags were listed. Recheck before publishing.

## Rename the GitHub repository first

In the existing repository, open Settings → General, enter `paperflow` in Repository name and click Rename. Keep the existing repository/history rather than deleting it or creating an empty replacement. GitHub redirects the old URL. Then update the local remote without renaming the local folder:

```bat
git -C D:\paper\paperflow-v2 -c safe.directory=D:/paper/paperflow-v2 remote set-url origin https://github.com/wzhht/paperflow.git
```

## Working directory and publishable files

The Git checkout on this machine is `D:\paper\paperflow-v2`. The `paperflow-v3` folder is a user installation with its own environment, credentials and papers; do not upload that entire directory or initialize a replacement repository there.

Publish source, reusable scripts, tests, documentation, `pyproject.toml`, `.env.example` and the two root CMD launchers. Exclude `.env`, `.venv`, `.paperflow-language`, `workspace`, downloaded papers, raw responses, logs and caches. Ignore rules do not remove previously tracked secrets; inspect the staged file list.

## Validate and inspect

Run one command at a time in CMD; stop and resolve any error:

```bat
cd /d D:\paper\paperflow-v2
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check --no-cache src tests scripts
git -c safe.directory=D:/paper/paperflow-v2 status --short
git -c safe.directory=D:/paper/paperflow-v2 remote -v
git -c safe.directory=D:/paper/paperflow-v2 tag --list
git -c safe.directory=D:/paper/paperflow-v2 ls-files .env .venv workspace .paperflow-language
```

The last command should print nothing. Confirm the expected origin and old `v2.0.0` tag. If developer tools are absent, install them in this checkout's environment with `python -m pip install -e ".[dev]"` using its `.venv\Scripts\python.exe`.

The per-command `safe.directory` option handles this checkout's ownership check without changing global Git configuration.

## Fetch before committing

Use a network that can reach GitHub; this may differ from the campus connection needed for licensed publisher content:

```bat
git -c safe.directory=D:/paper/paperflow-v2 fetch origin
git -c safe.directory=D:/paper/paperflow-v2 branch --show-current
git -c safe.directory=D:/paper/paperflow-v2 rev-list --left-right --count origin/main...HEAD
```

Expect branch `main`. Before the release commit, `0 0` means neither side has unique commits. If the remote is ahead, inspect and integrate its changes first; do not reset or force-push. Inspect any local-only commits as well.

Stage the intended files and review:

```bat
git -c safe.directory=D:/paper/paperflow-v2 add .env.example .gitignore .gitattributes pyproject.toml README.md README_EN.md CHANGELOG.md docs scripts src tests "一键安装.cmd" "一键批量整理Markdown.cmd" "批量Markdown使用说明.txt"
git -c safe.directory=D:/paper/paperflow-v2 diff --cached --stat
git -c safe.directory=D:/paper/paperflow-v2 diff --cached --name-only
git -c safe.directory=D:/paper/paperflow-v2 diff --cached --check
```

Ensure no credentials, environments, paper data or logs are staged and obsolete-file deletions are intentional. Then:

```bat
git -c safe.directory=D:/paper/paperflow-v2 commit -m "Release PaperFlow V3"
git -c safe.directory=D:/paper/paperflow-v2 push origin main
git -c safe.directory=D:/paper/paperflow-v2 push origin v2.0.0
```

The second push preserves the existing local V2 frozen-baseline tag on GitHub without recreating or moving it. If a remote tag with that name later appears, compare it rather than overwriting it.

Use Git's credential manager/browser authentication. Never embed tokens in remote URLs or commands. These are instructions, not actions performed automatically by documentation/ZIP preparation.

## Create the GitHub release

After the push succeeds, open [New release](https://github.com/wzhht/paperflow/releases/new):

1. Create tag `v3.0.0`, targeting the `main` commit containing V3.
2. Optionally choose previous tag `v2.0.0`.
3. Title: `PaperFlow V3`.
4. Paste [RELEASE_NOTES_V3.md](RELEASE_NOTES_V3.md).
5. Optionally attach the checked source ZIP and SHA-256 file, never the whole local installation.
6. Select “Set as latest release”. Save a draft for inspection or publish when ready.

Uploading a release asset alone does not update repository source. Follow the [official GitHub release instructions](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

After publishing, check the V3 README, both root launchers, the new tag, retained old tag, and a fresh source download. Installation should report `PaperFlow 0.3.0`. Local credentials, papers and ResearchFlow indexes remain separate from source publishing.
