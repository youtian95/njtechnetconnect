@echo off
chcp 65001 >nul
rem 功能：配置本地环境和凭据，然后注册 Windows 自动重连任务。
rem 流程：安装依赖、输入学校账号密码、检查页面、选择后台运行方式。
rem 输入：本机输入的凭据；输出：凭据库记录、配置和任务计划；--environment-only 仅安装检查环境。
cd /d "%~dp0"
set PYTHONUTF8=1
rem 检查已安装的 Edge，运行时直接使用它，无需另行下载 Playwright 浏览器。
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" goto edge_ready
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" goto edge_ready
echo 未找到 Microsoft Edge，请安装后重新运行。参见 README.md。
goto failed
:edge_ready
if exist ".venv\Scripts\python.exe" goto environment_ready
rem 优先使用 Python 启动器选择 3.12，否则检查 PATH 中的 python。
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 goto use_launcher
python -c "import sys, struct; assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto missing_python
python -m venv .venv
goto environment_created
:use_launcher
py -3.12 -m venv .venv
:environment_created
if errorlevel 1 goto failed
:environment_ready
rem 虚拟环境不能跨电脑直接复制，先检查解释器是否仍可用。
".venv\Scripts\python.exe" -c "import sys, struct; assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto invalid_environment
".venv\Scripts\python.exe" -c "import playwright, ddddocr, keyring" >nul 2>&1
if errorlevel 1 ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo 环境检查完成：Python 3.12 64 位、Edge 和所需依赖已就绪。
if /i "%~1"=="--environment-only" exit /b 0
".venv\Scripts\python.exe" reconnect.py setup
if errorlevel 1 goto failed
pause
exit /b 0
:missing_python
echo 未找到 Python 3.12 64 位，请按 README.md 安装，并勾选 Add python.exe to PATH。
goto failed
:invalid_environment
echo 当前 .venv 不可用或版本不符。请将它改名为 .venv-old，再重新运行以创建本机环境。
goto failed
:failed
echo 配置失败，请查看 runtime\reconnect.log 和 README.md。
pause
exit /b 1
