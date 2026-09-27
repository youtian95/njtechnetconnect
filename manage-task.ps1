# 功能：管理当前 Windows 用户的校园网计划任务；无需 Windows 密码。
# 流程：由命令行程序调用，按需注册、查看、停用或移除任务；后台使用无控制台程序。
# 输入：操作和后台命令参数；输出：任务状态或供检查的 XML。Preview 不注册或启动任务。
param(
    # 任务操作名称。
    [ValidateSet('enable', 'status', 'disable', 'remove')][string]$Operation,
    # 后台可执行文件的绝对路径。
    [string]$Executable,
    # 传递给后台程序的命令行参数。
    [string]$TaskArguments,
    # 程序运行目录。
    [string]$WorkingDirectory,
    # 只生成任务 XML，便于不改动系统地验证配置。
    [switch]$Preview
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
# 用 SID 区分不同 Windows 账户，防止多个用户覆盖彼此的任务。
$taskName = 'NjtechNetReconnect-' + $identity.User.Value
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
switch ($Operation) {
    'enable' {
        # 用系统 COM 定义生成 XML；此过程只创建内存对象，不注册任务。
        $service = New-Object -ComObject 'Schedule.Service'
        $service.Connect()
        $definition = $service.NewTask(0)
        $definition.Principal.UserId = $identity.Name
        $definition.Principal.LogonType = 3
        $definition.Principal.RunLevel = 0
        $definition.Settings.MultipleInstances = 2
        $definition.Settings.ExecutionTimeLimit = 'PT10M'
        $definition.Settings.StartWhenAvailable = $true
        $definition.Settings.DisallowStartIfOnBatteries = $false
        $definition.Settings.StopIfGoingOnBatteries = $false
        $definition.Settings.WakeToRun = $true
        $timer = $definition.Triggers.Create(1)
        $timer.StartBoundary = (Get-Date).AddMinutes(1).ToString('s')
        $timer.Repetition.Interval = 'PT3M'
        $login = $definition.Triggers.Create(9)
        $login.UserId = $identity.Name
        $exec = $definition.Actions.Create(0)
        $exec.Path = $Executable
        $exec.Arguments = $TaskArguments
        $exec.WorkingDirectory = $WorkingDirectory
        if ($Preview) { Write-Output $definition.XmlText; break }
        Register-ScheduledTask -TaskName $taskName -Xml $definition.XmlText -Force | Out-Null
        Write-Output '自动重连已启用：每三分钟检查，Windows 登录后及锁屏时运行，不需要 Windows 密码。'
    }
    'status' {
        if (!$existing) { Write-Output '自动重连任务尚未创建。'; break }
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        Write-Output ('任务：' + $taskName)
        Write-Output ('状态：' + $existing.State)
        Write-Output ('上次运行：' + $info.LastRunTime + '；结果代码：' + $info.LastTaskResult)
        Write-Output ('下次运行：' + $info.NextRunTime)
    }
    'disable' {
        if ($existing) {
        Disable-ScheduledTask -TaskName $taskName | Out-Null
        if ($existing.State -eq 'Running') { Stop-ScheduledTask -TaskName $taskName }
        }
        Write-Output '自动重连已停用，配置与凭据保留。'
    }
    'remove' {
        if ($existing) {
        if ($existing.State -eq 'Running') { Stop-ScheduledTask -TaskName $taskName }
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        }
        Write-Output '自动重连任务已移除，配置与凭据保留。'
    }
}
