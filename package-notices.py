# 功能：为发布包收集构建环境的第三方包版本及许可文件。
# 流程：由 build.ps1 在打包后调用；输入：发布目录参数和已安装包元数据；输出：THIRD_PARTY 目录。
import importlib.metadata
from pathlib import Path
import shutil
import sys


def collect(destination):
    """收集版本和许可证；destination：发布包根目录，不包含用户配置或凭据。"""
    notices = destination / 'THIRD_PARTY'
    notices.mkdir(exist_ok=True)
    versions = []
    for package in importlib.metadata.distributions():
        name = package.metadata['Name']
        versions.append(f'{name}=={package.version}')
        for item in package.files or []:
            if 'license' in item.name.lower() or 'copying' in item.name.lower() or 'notice' in item.name.lower():
                source = Path(package.locate_file(item))
                if source.is_file():
                    target = notices / name / Path(*[part for part in item.parts if part not in ('..', '.')])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    (notices / 'versions.txt').write_text('\n'.join(sorted(versions)) + '\n', encoding='utf-8')


if __name__ == '__main__':
    collect(Path(sys.argv[1]))
