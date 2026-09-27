# 功能：生成共享依赖目录的命令行 EXE 与无窗口后台 EXE。
# 流程：由 build.ps1 调用 PyInstaller；输入：源码、默认配置及已安装依赖；输出：dist/njtechnetconnect。
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

root = Path(SPECPATH)
data = [(str(root / 'config.example.json'), '.'), (str(root / 'manage-task.ps1'), '.')]
# 带上所有 OCR 模型与数据，避免依赖内部选择模型时缺文件；Playwright 自带 hook 会收集驱动。
data += collect_data_files('ddddocr')
analysis = Analysis([str(root / 'reconnect.py')], pathex=[str(root)], binaries=collect_dynamic_libs('onnxruntime'), datas=data, hiddenimports=collect_submodules('ddddocr') + ['keyring.backends.Windows'], excludes=['tkinter'], noarchive=False)
archive = PYZ(analysis.pure)
console = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='njtechnetconnect', console=True, upx=False)
background = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='njtechnetconnect-background', console=False, upx=False)
collection = COLLECT(console, background, analysis.binaries, analysis.datas, strip=False, upx=False, name='njtechnetconnect')
