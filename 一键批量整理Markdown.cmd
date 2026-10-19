@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
if not exist ".venv\Scripts\python.exe" goto missing_environment
if not exist "scripts\batch_markdown.py" goto failed
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
".venv\Scripts\python.exe" -c "from paperflow.cli import app" >nul 2>&1
if errorlevel 1 goto missing_package
".venv\Scripts\python.exe" "scripts\batch_markdown.py" %*
set "PAPERFLOW_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %PAPERFLOW_EXIT%
:failed
echo 找不到PaperFlow程序文件。请完整解压，并在包含pyproject.toml的目录运行此文件。
echo PaperFlow files are missing. Fully extract the project first.
pause
exit /b 2
:missing_environment
echo 尚未创建本目录的虚拟环境。源码ZIP不包含.venv，这是首次解压后的正常状态。
echo 请先按README.md中“首次解压安装”完成安装。
echo Or run 一键安装.cmd / 或双击一键安装.cmd，选择中文或English。
echo No local environment. Run 一键安装.cmd first; see README_EN.md for English instructions.
echo.
echo 已安装Python 3.10时，在本目录打开CMD，逐行执行：
echo   py -3.10 -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -e .
echo   if not exist .env copy .env.example .env
echo   .venv\Scripts\paperflow.exe version
echo.
echo 然后填写自己的.env配置，再双击本启动文件。
pause
exit /b 2
:missing_package
echo 本目录的环境存在，但PaperFlow程序、依赖尚未安装，或环境已失效。
echo PaperFlow dependencies are missing or this environment is invalid. Run 一键安装.cmd.
echo 请在本目录执行以下命令并查看安装结果：
echo   .venv\Scripts\python.exe -m pip install -e .
echo 如仍报错，请按README.md“首次解压安装”检查Python和环境路径。
pause
exit /b 2
