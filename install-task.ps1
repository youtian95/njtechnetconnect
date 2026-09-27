# 功能：兼容原有安装入口，启用当前用户的无窗口后台重连任务。
# 流程：先保存学校凭据再运行；输入：本机配置；输出：已登录或锁屏时执行的计划任务。
param()
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'reconnect.py') enable
exit $LASTEXITCODE
