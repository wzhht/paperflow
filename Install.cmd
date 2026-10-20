@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
if not exist "scripts\install.py" goto failed
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PAPERFLOW_INSTALL_LANGUAGE=zh"
if "%~1"=="--help" goto find_python
if "%~1"=="--language" goto find_python
echo PaperFlow installation / PaperFlow安装
echo 1. 中文
echo 2. English
choice /c 12 /n /m "Select language / 选择语言 [1/2]: "
if errorlevel 2 goto english
set "PAPERFLOW_INSTALL_LANGUAGE=zh"
goto find_python
:english
set "PAPERFLOW_INSTALL_LANGUAGE=en"
:find_python
if not exist ".venv\Scripts\python.exe" goto try_launcher
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,10)" >nul 2>&1
if errorlevel 1 goto try_launcher
".venv\Scripts\python.exe" scripts\install.py --language %PAPERFLOW_INSTALL_LANGUAGE% %*
goto finished
:try_launcher
py -3.10 -c "import sys; assert sys.version_info[:2] == (3,10)" >nul 2>&1
if errorlevel 1 goto try_python
py -3.10 scripts\install.py --language %PAPERFLOW_INSTALL_LANGUAGE% %*
goto finished
:try_python
python -c "import sys; assert sys.version_info[:2] == (3,10)" >nul 2>&1
if errorlevel 1 goto missing_python
python scripts\install.py --language %PAPERFLOW_INSTALL_LANGUAGE% %*
goto finished
:finished
set "PAPERFLOW_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %PAPERFLOW_EXIT%
:missing_python
if "%PAPERFLOW_INSTALL_LANGUAGE%"=="en" goto missing_python_en
echo 未找到Python 3.10。请先安装Python 3.10，再双击本文件。
goto python_link
:missing_python_en
echo Python 3.10 not found. Install Python 3.10, then run this file again.
:python_link
echo https://www.python.org/downloads/release/python-31011/
if "%PAPERFLOW_INSTALL_LANGUAGE%"=="en" echo See README_EN.md. No existing environment was deleted.
if not "%PAPERFLOW_INSTALL_LANGUAGE%"=="en" echo 详见README.md。没有删除现有环境。
pause
exit /b 2
:failed
echo Please fully extract the project first. / 请先完整解压项目，并在项目根目录运行。
pause
exit /b 2
