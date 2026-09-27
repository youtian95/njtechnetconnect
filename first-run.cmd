@echo off
chcp 65001 >nul
rem 功能：EXE 发布包的首次配置入口，不需要安装 Python。
rem 流程：本机输入学校凭据、检查页面、按提示测试和启用；输出：当前用户的配置及计划任务。
cd /d "%~dp0"
njtechnetconnect.exe setup
if errorlevel 1 echo 配置未完成，请查看上方提示或运行 njtechnetconnect.exe status。
pause
