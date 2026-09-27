# 南京工业大学校园网自动重连

Windows 命令行工具：检测外网是否可达，断网时自动用本机 Edge 登录学校统一身份认证，验证码由本地 OCR 识别。全程离线运行，不依赖云 OCR 或额外运行时，只要求本机装有 Microsoft Edge。

## 工作原理

1. 每隔三分钟（以及每次登录 Windows 时）探测两个通用外网地址，任一返回预期内容即认为已联网，本轮直接结束。
2. 确认断网后，自动重连会先检查校内网络入口 `net.njtech.edu.cn` 是否可达。不可达说明基础网络故障，本轮跳过并等待下一轮，避免反复提交认证。
3. 从业务入口 `i.njtech.edu.cn` 生成新的登录会话，用无窗口 Edge 打开学校认证页。
4. 本地 OCR 识别验证码，填写账号密码并提交。只有明确的验证码错误会在本轮重试。

## 快速开始（下载即用）

1. 从 GitHub **Releases** 下载 `njtechnetconnect-windows-x64.zip`，不是自动生成的 Source code.zip。
2. 解压到固定目录，如 `C:\Users\你的用户名\njtechnetconnect`。整包解压，保留 `_internal` 和两个 EXE；不要只复制主程序，也不要直接在压缩包内运行。
3. 安装普通桌面版 [Microsoft Edge](https://www.microsoft.com/edge/download)。支持 Windows 10/11、Intel/AMD 64 位，无需安装 Python、Node.js 或其他浏览器驱动。
4. 双击 `first-run.cmd`，按提示输入学校账号与密码。密码隐藏输入，只保存在当前 Windows 用户的凭据管理器，服务名为 `NjtechNetReconnect`。

首次配置向导依次完成：保存凭据 → 只读检查登录页与验证码 → 询问是否提交一次真实登录测试 → 询问是否启用自动重连。登录测试失败不会启用任务。

**运行前提**：Windows 保持登录状态即可（锁屏、关闭显示器都不影响），不需要 Windows 账户密码。电脑不能关机或睡眠；重启后必须先登录 Windows。

## 解压目录结构

```text
njtechnetconnect/
├── njtechnetconnect.exe             配置与管理
├── njtechnetconnect-background.exe  计划任务专用，不弹控制台
├── _internal/                       Python、驱动、依赖与 OCR 模型
├── first-run.cmd                    首次配置入口
├── THIRD_PARTY/                     第三方版本与许可文件
└── README.md
```

## 命令行参考

在解压目录打开 PowerShell，所有命令都通过 `njtechnetconnect.exe` 执行：

| 命令 | 作用 |
| --- | --- |
| `setup` | 首次配置向导：保存凭据、检查页面、测试登录、可选启用任务 |
| `configure` | 单独保存或更改学校账号密码 |
| `diagnose` | 只读检查登录页与验证码，不提交登录 |
| `self-test` | 检查本地 OCR、凭据库组件、Playwright 驱动与 Edge，不访问学校页面 |
| `test-login` | 提交一次真实登录测试，建议加 `--headed` 观察 Edge |
| `check` | 立即检测；只有外网不可用时才尝试登录 |
| `enable` | 启用每三分钟的自动重连任务 |
| `status` | 查看任务、配置与认证暂停状态 |
| `disable` | 停用任务；正在运行的任务也会停止 |
| `remove` | 移除任务，保留配置与学校凭据 |

常用全局选项：

| 选项 | 说明 |
| --- | --- |
| `--headed` | 显示 Edge 窗口，便于调试 |
| `--preview` | 配合 `enable` 只输出拟注册的任务 XML，不注册任务、不读取学校密码 |
| `--data-dir 路径` | 指定独立数据目录；配置和后续操作必须使用同一路径 |

`enable` 更新的任务名为 `NjtechNetReconnect-当前用户SID`，约一分钟后首次检查，此后每三分钟执行，登录 Windows 时也会触发。配置和运行必须使用同一个 Windows 账户。

## 手动测试与自动重连的区别

`test-login`（含首次配置向导中的登录测试）和 `diagnose` 都会跳过校内网关检查，直接访问统一认证网站。因此**在校外、家中只要网络能访问学校认证网站，就可以验证账号、密码和验证码流程**，不会出现“校内网络入口不可达”。

后台 `check`（计划任务使用）保留校内网关检查，用于在办公室基础网络故障时避免反复提交认证。

需要注意，校外或在线时的登录测试只能验证认证流程本身，**不能证明办公室校园网的断网恢复能力**；拔掉网线或关闭网卡也无法模拟认证失效。真实断网恢复仍需在同类办公室校园网中测试，宿舍网络流程可能不同。

## 数据、升级与卸载

EXE 版数据默认保存在 `%LOCALAPPDATA%\NjtechNetReconnect`：

- `config.json`：学校账号和非敏感参数，不包含密码。
- `runtime\reconnect.log`：轮转日志，不记录密码、验证码及带令牌的 URL。
- `runtime\state.json`：冷却、提交次数和暂停状态。
- `output\captcha-diagnostic.png`：诊断时截取的单张验证码。

升级前先执行 `disable`，解压完整新版本后执行 `enable`，配置和凭据会继续使用。更换程序目录必须重新执行 `enable`。换电脑需要重新运行 `setup`，复制文件不会迁移密码和任务。

卸载时先执行 `remove`，再删除程序目录。需要清理账号信息时，删除上述数据目录，并在 Windows 凭据管理器中删除 `NjtechNetReconnect` 对应条目。若源码旧版曾创建名为 `NjtechNetReconnect` 的任务，请在任务计划程序中先停用旧任务，避免重复执行。

## 开发者：本地运行与构建

工具只提供 EXE 一种使用方式，源码仅用于本机调试和构建发布包，不面向最终用户。先安装 **Python 3.12 64 位** 和 Edge。

本地运行（数据默认保存在项目目录，已被 `.gitignore` 忽略）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe reconnect.py setup
```

调试时用 `.\.venv\Scripts\python.exe reconnect.py <命令>`，命令和选项与 EXE 完全相同；此时 `enable` 注册的后台任务指向 `pythonw.exe`，仅供本机调试。`.venv` 与本机绑定，不能跨电脑复制。

构建发布包（产物给最终用户，在已安装 Edge 的 Windows x64 上执行）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

构建脚本先运行单元测试，再用 PyInstaller 文件夹模式打包，收集第三方许可，执行 EXE 自检，最后生成：

```text
dist/njtechnetconnect/                         可运行目录
dist/njtechnetconnect-windows-x64.zip          GitHub Releases 发布包
dist/njtechnetconnect-windows-x64.zip.sha256   SHA256 校验文件
```

自检禁止 Python 网络连接后加载 OCR 并识别本地生成的图片，再启动 Edge 空白页，不提交学校登录、不保存密码、不启用任务。Playwright 内置驱动及 OCR 模型包含在发布包中。构建可能花费几分钟。

仓库提交源码、`.spec` 和脚本；`.gitignore` 已排除 `.venv`、构建目录、发布包及本机配置日志。ZIP 和校验文件作为 Release 附件上传，不提交到源码仓库。当前不会自动向 GitHub 发布。

## 限制与常见问题

验证码由本地识别；仅明确的验证码错误立即重试，一轮最多三次，每天最多十二次提交，失败至少冷却三十分钟。页面提示账号、密码或访问限制问题时暂停自动提交，解决问题后运行 `configure`。网页结构或验证码类型变化需要修改适配代码。

- **自检失败**：确认完整解压并安装 Edge，查看日志。发布包目前没有代码签名，Windows 可能提示未识别的应用。
- **源码环境不可用**：将项目的 `.venv` 改名后重新安装，不能跨电脑复制虚拟环境。
- **任务注册失败**：确认使用保存学校凭据的同一 Windows 账户；单位策略限制时需管理员处理。
- **重启后不运行**：需要先登录 Windows；锁屏不影响执行，睡眠和关机会影响。
- **恢复不了网络**：检查日志，确认账号状态正常、校内站点可达且认证入口未变化。

退出码：`0` 表示操作成功或外网可用；`2` 表示本次未恢复、冷却或暂停；`1` 表示运行错误。`status` 本身成功不代表认证成功，应同时查看任务结果与日志。