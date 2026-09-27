# 功能：生成共享依赖目录的命令行 EXE 与无窗口后台 EXE。
# 流程：由 build.ps1 调用 PyInstaller；输入：源码、默认配置及已安装依赖；输出：dist/njtechnetconnect。
import _ctypes
from pathlib import Path
from PyInstaller.depend.bindepend import get_imports
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


def _ctypes_ffi_libs():
    """补齐 _ctypes 依赖的 ffi DLL；Anaconda 版 Python 把 ffi-8.dll 放在 Library\\bin，PyInstaller 默认找不到，会导致 ctypes 及 Windows 凭据库失效。"""
    dll_dir = Path(_ctypes.__file__).resolve().parent
    candidates = [dll_dir, dll_dir.parent / 'Library' / 'bin', dll_dir / 'Library' / 'bin']
    result = []
    for name, resolved in get_imports(str(dll_dir / '_ctypes.pyd')):
        if resolved is None:
            for directory in candidates:
                found = directory / name
                if found.is_file():
                    result.append((str(found), '.'))
                    break
    return result


root = Path(SPECPATH)
data = [(str(root / 'config.example.json'), '.'), (str(root / 'manage-task.ps1'), '.')]
# 带上所有 OCR 模型与数据，避免依赖内部选择模型时缺文件；Playwright 自带 hook 会收集驱动。
data += collect_data_files('ddddocr')
# keyring 的 Windows 后端在 try/except 中导入 win32ctypes，PyInstaller 不会自动收集，必须手动带上，否则凭据读写会失败。
hidden = collect_submodules('ddddocr') + collect_submodules('win32ctypes') + ['keyring.backends.Windows']
binaries = collect_dynamic_libs('onnxruntime') + _ctypes_ffi_libs()
# 排除项说明：setuptools 会触发 PyInstaller 启动钩子调用 platform.system()，在计划任务的无窗口环境下会经 Anaconda 的 _wmi 查询而永久阻塞；
# 运行期没有任何模块需要 setuptools，故连同 pkg_resources、_distutils_hack、_wmi 一起排除。
excludes = ['tkinter', 'setuptools', 'pkg_resources', '_distutils_hack', '_wmi']
analysis = Analysis([str(root / 'reconnect.py')], pathex=[str(root)], binaries=binaries, datas=data, hiddenimports=hidden, excludes=excludes, noarchive=False)
archive = PYZ(analysis.pure)
console = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='njtechnetconnect', console=True, upx=False)
background = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='njtechnetconnect-background', console=False, upx=False)
collection = COLLECT(console, background, analysis.binaries, analysis.datas, strip=False, upx=False, name='njtechnetconnect')
