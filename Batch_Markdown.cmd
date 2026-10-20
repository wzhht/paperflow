@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
set "PAPERFLOW_UI_LANGUAGE=%PAPERFLOW_LANGUAGE%"
if not defined PAPERFLOW_UI_LANGUAGE if exist ".paperflow-language" set /p PAPERFLOW_UI_LANGUAGE=<".paperflow-language"
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
if /i "%PAPERFLOW_UI_LANGUAGE%"=="en" goto failed_en
echo 找不到PaperFlow程序文件。请完整解压，并在包含pyproject.toml的目录运行此文件。
goto error_end
:failed_en
echo PaperFlow files are missing. Fully extract the project first.
goto error_end
:missing_environment
if /i "%PAPERFLOW_UI_LANGUAGE%"=="en" goto missing_environment_en
echo 尚未创建本目录的虚拟环境。源码ZIP不包含.venv，这是首次解压后的正常状态。
echo 请先双击Install.cmd，选择中文或English完成安装。详见README.md。
goto error_end
:missing_environment_en
echo No local environment. Run Install.cmd first; see README_EN.md for English instructions.
goto error_end
:missing_package
if /i "%PAPERFLOW_UI_LANGUAGE%"=="en" goto missing_package_en
echo 本目录的环境存在，但PaperFlow程序、依赖尚未安装，或环境已失效。
echo 请重新运行Install.cmd，并按窗口提示检查安装结果。详见README.md。
goto error_end
:missing_package_en
echo PaperFlow dependencies are missing or this environment is invalid. Run Install.cmd. See README_EN.md.
:error_end
pause
exit /b 2
