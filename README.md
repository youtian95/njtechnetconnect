# 南京工业大学办公室校园网自动重连

纯命令行 Windows 工具：检测外网、调用本机 Edge 登录统一身份认证、在本地识别验证码。提前下载完整发布包后，断外网时不依赖 Python 安装、云端 OCR 或 Codex；校内认证页面仍需可访问。

## 普通用户：下载后直接运行

1. 从 GitHub **Releases** 下载 `njtechnetconnect-windows-x64.zip`，不是自动生成的 Source code.zip。
2. 解压到固定本地目录，如 `C:\Users\你的用户名\njtechnetconnect`。整包解压，保留 `_internal` 和两个 EXE，不能只复制主 EXE，不能直接在 ZIP 内运行。
3. 确认已安装普通桌面版 [Microsoft Edge](https://www.microsoft.com/edge/download)。支持 Windows 10/11、Intel/AMD 64 位；无需安装 Python、Node.js、Anaconda 或浏览器驱动。
4. 双击 `first-run.cmd`，输入学校账号、密码及确认密码。密码隐藏输入，只保存在当前 Windows 用户的凭据管理器，服务名为 `NjtechNetReconnect`。
5. 程序检查页面和 OCR，询问是否提交真实登录测试，再询问是否启用自动重连。测试失败时不会启用任务；可输入 `n` 跳过测试，稍后单独测试。

**默认使用模式 1：Windows 保持登录时运行，包括锁屏和关闭显示器，不需要 Windows 账户密码。** 新版流程不再提供模式 2。电脑不能关机或自动睡眠；重启后必须先登录 Windows。

```text
njtechnetconnect/
├── njtechnetconnect.exe             命令行配置与管理
├── njtechnetconnect-background.exe  计划任务专用，不弹控制台
├── _internal/                      Python、驱动、依赖及 OCR 模型
├── first-run.cmd                   首次配置入口
├── THIRD_PARTY/                    第三方版本与许可文件
└── README.md
```

## 命令行操作

在解压目录打开 PowerShell：

```powershell
# 首次配置向导
.\njtechnetconnect.exe setup
# 单独保存或更改学校账号密码
.\njtechnetconnect.exe configure
# 只读检查校内页面及验证码，不提交登录
.\njtechnetconnect.exe diagnose
# 检查本地模型、运行依赖与 Edge；不访问学校页面
.\njtechnetconnect.exe self-test
# 提交真实登录测试，显示 Edge 便于观察
.\njtechnetconnect.exe test-login --headed
# 启用已登录或锁屏时每三分钟执行的无窗口任务
.\njtechnetconnect.exe enable
# 查看任务、配置及认证暂停状态
.\njtechnetconnect.exe status
# 停用任务；正在运行的任务也会停止
.\njtechnetconnect.exe disable
# 移除任务，保留配置和学校凭据
.\njtechnetconnect.exe remove
# 立即检测；只有外网不可用时才尝试登录
.\njtechnetconnect.exe check
```

`enable` 更新当前 Windows 用户的任务，约一分钟后首次检查，此后每三分钟执行；登录 Windows 时也触发。任务名为 `NjtechNetReconnect-当前用户SID`。配置和运行需使用同一个 Windows 账户。

开发调试可用 `enable --preview`，只输出拟注册的 XML，不注册任务、不读取学校密码。`--data-dir 路径` 可指定独立数据目录；配置和后续操作必须使用同一路径。

## 数据、升级与删除

EXE 版数据默认保存在 `%LOCALAPPDATA%\NjtechNetReconnect`：

- `config.json`：学校账号和非敏感参数，不包含密码。
- `runtime\reconnect.log`：轮转日志，不记录密码、验证码及带令牌的 URL。
- `runtime\state.json`：冷却、提交次数和暂停状态。
- `output\captcha-diagnostic.png`：诊断时截取的单张验证码。

更新前先执行 `disable`，解压完整新版本后执行 `enable`，配置和凭据会继续使用。更换程序目录必须重新执行 `enable`。换电脑需要重新运行 `setup`，复制文件不会迁移密码和任务。

卸载时先执行 `remove`，再删除程序目录。需要清理账号信息时，删除上述数据目录，并在 Windows 凭据管理器中删除 `NjtechNetReconnect` 对应条目。源码旧版若曾创建名为 `NjtechNetReconnect` 的任务，请在任务计划程序中先停用旧任务，避免重复执行。

## 从源码安装运行

开发者或没有 EXE 的用户使用以下流程。首次安装需要外网，可先手动登录校园网。

1. 安装 **Python 3.12 64 位** 和 Edge。可从 [Python 3.12.10 官方页面](https://www.python.org/downloads/release/python-31210/) 下载 Windows installer (64-bit)，安装时勾选 Add python.exe to PATH，保留 pip 和 Launcher。
2. 下载或克隆源码到固定目录。不要复制其他电脑的 `.venv`、`config.json`、`runtime`、`output` 或 `.playwright-cli`。
3. 双击 `1_setup.cmd`，自动创建环境、安装依赖并进入配置向导。仅安装检查环境可执行 `1_setup.cmd --environment-only`。

手动安装的等价命令：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe reconnect.py setup
```

没有 `py` 时可用 `python`，但需确认版本为 3.12.x 64 位。其他命令也支持源码运行，例如 `.\.venv\Scripts\python.exe reconnect.py status`。源码版默认把配置和日志保存在项目目录。

## 本地制作 EXE 发布包

在已安装 Edge 的 Windows x64 上执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

构建脚本先运行单元测试，再使用 PyInstaller 文件夹模式打包，收集第三方许可，执行 EXE 自检，最后生成：

```text
dist/njtechnetconnect/                         可运行目录
dist/njtechnetconnect-windows-x64.zip          GitHub Releases 发布包
dist/njtechnetconnect-windows-x64.zip.sha256   SHA256 校验文件
```

自检禁止 Python 网络连接后加载 OCR 并识别本地生成的图片，再启动 Edge 空白页，不提交学校登录、保存密码或启用任务。Playwright 内置驱动及 OCR 模型包含在发布包中。构建可能花费几分钟。

仓库提交源码、`.spec` 和脚本；`.gitignore` 已排除 `.venv`、构建目录、发布包及本机配置日志。ZIP 和校验文件作为 Release 附件上传，不提交到源码仓库。当前不会自动向 GitHub 发布。

## 工作方式与限制

两个外网探测地址任一返回指定内容即认为已联网。全部失败并复查后，检查校内入口，再用无窗口 Edge 认证。从 `https://i.njtech.edu.cn/` 生成新的 `sfgl.njtech.edu.cn` 业务跳转，不保存临时登录链接。

验证码本地识别；仅明确的验证码错误立即重试，一轮最多三次，每天最多十二次提交，失败至少冷却三十分钟。账号、密码或访问限制提示会暂停自动提交，解决问题后运行 `configure`。网页结构或验证码类型变化需要修改适配代码。

真实断网恢复仍需在目标电脑测试。在线登录测试不能证明断网恢复；拔掉网线或关闭网卡无法模拟认证失效。目标电脑应处于同类办公室校园网，宿舍网络流程可能不同。

常见问题：

- **自检失败**：确认完整解压并安装 Edge，查看日志。发布包目前没有代码签名，Windows 可能提示未识别的应用。
- **源码环境不可用**：将项目的 `.venv` 改名后重新安装，不能跨电脑复制虚拟环境。
- **任务注册失败**：确认使用保存学校凭据的同一 Windows 账户；单位策略限制时需管理员处理。
- **重启后不运行**：需要先登录 Windows；锁屏不影响执行，睡眠和关机会影响。
- **恢复不了网络**：检查日志，确认账号状态正常、校内站点可达且认证入口未变化。

退出码：0 表示操作成功或外网可用；2 表示本次未恢复、冷却或暂停；1 表示运行错误。`status` 本身成功不代表认证成功，应同时查看任务结果与日志。
