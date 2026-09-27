# 功能：在 Windows 上打包可离线运行的命令行发布包。
# 流程：先安装 requirements-build.txt，再执行此脚本；输入：本地源码和依赖；输出：dist 下的 ZIP 与 SHA256。
param(
    # 用于构建的 Python 路径，默认使用项目虚拟环境。
    [string]$Python = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & $Python -m unittest -v
    if ($LASTEXITCODE -ne 0) { throw '关键逻辑测试失败，停止打包。' }
    & $Python -m PyInstaller --noconfirm njtechnetconnect.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失败。' }
    $bundle = Join-Path $PSScriptRoot 'dist\njtechnetconnect'
    Copy-Item -LiteralPath 'first-run.cmd', 'README.md' -Destination $bundle
    # 保留依赖清单与第三方许可，便于分发和追溯版本。
    & $Python package-notices.py $bundle
    if ($LASTEXITCODE -ne 0) { throw '第三方许可收集失败。' }
    & (Join-Path $bundle 'njtechnetconnect.exe') self-test --data-dir (Join-Path $PSScriptRoot 'output\build-smoke')
    if ($LASTEXITCODE -ne 0) { throw 'EXE 自检失败，停止制作发布 ZIP。' }
    $zipPath = Join-Path $PSScriptRoot 'dist\njtechnetconnect-windows-x64.zip'
    # 自检刚结束，EXE 可能被 Windows 短暂占用；重试几次压缩，避免偶发失败。
    for ($attempt = 1; ; $attempt++) {
        try { Compress-Archive -LiteralPath $bundle -DestinationPath $zipPath -Force; break }
        catch { if ($attempt -ge 3) { throw }; Start-Sleep -Seconds 3 }
    }
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLower()
    Set-Content -LiteralPath ($zipPath + '.sha256') -Value ($hash + '  ' + [System.IO.Path]::GetFileName($zipPath)) -Encoding ascii
    Write-Output ('发布包：' + $zipPath)
} finally {
    Pop-Location
}
