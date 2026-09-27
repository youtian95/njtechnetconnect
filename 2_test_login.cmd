@echo off
chcp 65001 >nul
rem 功能：手动验证真实登录；流程：读取本机凭据、打开 Edge、提交并检查结果。
rem 输入：保存的配置和凭据；输出：runtime\reconnect.log 中的执行结果。
cd /d "%~dp0"
set PYTHONUTF8=1
echo 将使用已保存的账号进行真实登录测试。如不需要，请关闭此窗口。
pause
".venv\Scripts\python.exe" reconnect.py test-login --headed
pause
