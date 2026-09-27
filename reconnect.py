# 功能：检查南京工业大学办公室网络，通过 Edge 和本地 OCR 完成统一身份认证。
# 流程：setup 完成首次配置；enable/status/disable/remove 管理任务；check 仅在断网时重连。
# 输入：config.json、当前 Windows 用户的凭据库和校内页面；输出：用户数据目录中的状态和脱敏日志。
import argparse
import contextlib
import datetime as dt
import getpass
import json
import logging
from logging.handlers import RotatingFileHandler
import msvcrt
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

ASSETS = Path(__file__).resolve().parent
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ASSETS
DATA = Path(os.environ["LOCALAPPDATA"]) / "NjtechNetReconnect" if getattr(sys, "frozen", False) else ROOT
RUNTIME = DATA / "runtime"
CONFIG = DATA / "config.json"
STATE = RUNTIME / "state.json"
SERVICE = "NjtechNetReconnect"
AUTH_HOST = "sfgl.njtech.edu.cn"
CAPTCHA_SELECTOR = "img.code-img"
PROBES = [
    ("http://www.msftconnecttest.com/connecttest.txt", 200, b"Microsoft Connect Test"),
    ("https://cp.cloudflare.com/generate_204", 204, b""),
]


def read_json(path, default):
    """读取 JSON；path：文件路径；default：文件不存在时使用的值。"""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default.copy()


def write_json(path, value):
    """原子写入 JSON；path：目标路径；value：需要保存的对象。"""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def configure_logging():
    """建立轮转日志；无参数，日志不包含账号、密码、验证码及带令牌的页面地址。"""
    RUNTIME.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(RUNTIME / "reconnect.log", maxBytes=500_000, backupCount=3, encoding="utf-8")
    handlers = [handler] + ([logging.StreamHandler()] if sys.stderr is not None else [])
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)


@contextlib.contextmanager
def single_instance():
    """用文件锁阻止多个任务同时登录；无参数，进程退出后锁自动释放。"""
    with (RUNTIME / "run.lock").open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def vault():
    """明确使用 Windows 凭据管理器；无参数，不允许回退到明文密码存储。"""
    from keyring.backends.Windows import WinVaultKeyring
    return WinVaultKeyring()


def fetch(url, timeout):
    """直接请求网络资源；url：检测地址；timeout：超时秒数。不使用系统代理或环境代理。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "NjtechNetReconnect/1.0"})
    with opener.open(request, timeout=timeout) as response:
        return response.status, response.geturl(), response.read(4096)


def internet_available(timeout):
    """核对外网响应，防止认证重定向误判；timeout：每个探测的超时秒数。"""
    for url, status, body in PROBES:
        try:
            actual_status, final_url, actual_body = fetch(url, timeout)
            if actual_status == status and urlparse(final_url).hostname == urlparse(url).hostname and actual_body.strip() == body:
                return True
        except (OSError, ValueError):
            continue
    return False


def load_config():
    """读取并验证用户配置；无参数，未配置时要求先运行 configure。"""
    if not CONFIG.exists():
        raise RuntimeError("尚未配置，请先运行 configure 或 setup。")
    config = read_json(CONFIG, {})
    for key in ("entry_url", "portal_url"):
        host = urlparse(config[key]).hostname or ""
        if not host.endswith(".njtech.edu.cn"):
            raise ValueError("登录入口必须是学校域名。")
    if not 1 <= config["max_attempts"] <= 3 or config["cooldown_minutes"] < 30 or not 1 <= config["max_daily_submissions"] <= 12:
        raise ValueError("重试最多 3 次，冷却至少 30 分钟，每天最多提交 12 次。")
    return config


def configure():
    """在本机交互配置；无参数，密码通过隐藏输入保存到当前 Windows 用户凭据库。"""
    config = read_json(CONFIG, read_json(ASSETS / "config.example.json", {}))
    username = input("学校账号（学工号）：").strip()
    password = getpass.getpass("学校密码（输入不显示）：")
    if not username or not password:
        raise ValueError("账号与密码不能为空。")
    if password != getpass.getpass("再次输入学校密码："):
        raise ValueError("两次密码不同。")
    vault().set_password(SERVICE, username, password)
    config["username"] = username
    write_json(CONFIG, config)
    write_json(STATE, {})
    print("凭据已保存到 Windows 凭据管理器，配置文件不保存密码。")


def current_state():
    """读取持久化重试状态；无参数，每个自然日重置提交计数，保留冷却和停用标记。"""
    state = read_json(STATE, {})
    today = dt.date.today().isoformat()
    if state.get("day") != today:
        state.update(day=today, submissions=0)
    return state


def allowed_to_submit(state, config):
    """判断能否尝试认证；state：重试状态；config：次数和冷却配置。"""
    return not state.get("blocked") and state.get("next_attempt", 0) <= time.time() and state.get("submissions", 0) < config["max_daily_submissions"]


def trusted_auth_url(url):
    """仅允许向实际认证域名填写凭据；url：浏览器当前页面地址。"""
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == AUTH_HOST and parsed.port in (None, 443)


def classify_error(text):
    """分类认证失败原因；text：网页可见文本。未知情况不立即重复提交。"""
    if re.search(r"(密码|账号|帐号|用户).{0,16}(错误|不正确|不存在|锁定|冻结|禁用|失败)|尝试次数|频繁|锁定|冻结", text):
        return "blocked"
    if re.search(r"(验证码|校验码).{0,16}(错误|不正确|失效|过期)", text):
        return "captcha"
    return "unknown"


def open_form(page, config):
    """从业务入口取得新会话并定位登录表单；page：Edge 页面；config：入口配置。"""
    page.goto(config["entry_url"], wait_until="domcontentloaded", timeout=45_000)
    username = page.get_by_placeholder("请输入学工号", exact=True)
    username.wait_for(state="visible", timeout=45_000)
    if not trusted_auth_url(page.url):
        raise RuntimeError("当前表单不在可信认证域名，已停止。")
    return username, page.get_by_placeholder("请输入密码", exact=True), page.locator('input[name="captcha_code"]'), page.locator(CAPTCHA_SELECTOR)


def captcha_bytes(image):
    """取得当前会话中的验证码图片；image：页面验证码定位器。"""
    image.wait_for(state="visible", timeout=15_000)
    image.evaluate("el => el.decode()")
    return image.screenshot()


def new_ocr():
    """加载已安装的本地 OCR 模型；无参数，推理不调用外部服务。"""
    import ddddocr
    return ddddocr.DdddOcr(show_ad=False)


def browser_context(playwright, headed):
    """创建独立 Edge 会话；playwright：自动化实例；headed：是否显示窗口。"""
    return playwright.chromium.launch(channel="msedge", headless=not headed, args=["--no-proxy-server"])


def diagnose(config, headed):
    """只读检查页面及 OCR；config：配置；headed：是否显示窗口。不填写或提交凭据。"""
    from playwright.sync_api import sync_playwright
    ocr = new_ocr()
    with sync_playwright() as playwright:
        browser = browser_context(playwright, headed)
        try:
            page = browser.new_page()
            _, _, _, image = open_form(page, config)
            data = captcha_bytes(image)
            output = DATA / "output"
            output.mkdir(exist_ok=True)
            (output / "captcha-diagnostic.png").write_bytes(data)
            text = ocr.classification(data)
            print(f"Edge 页面检查通过；表单定位成功；本地 OCR 结果：{text}")
            print(f"验证码样本：{output / 'captcha-diagnostic.png'}；本次没有提交登录。")
        finally:
            browser.close()


def authenticate(config, state, headed):
    """执行有限次登录；config：配置；state：持久化限速状态；headed：是否显示窗口。返回恢复联网与否。"""
    from playwright.sync_api import sync_playwright
    password = vault().get_password(SERVICE, config["username"])
    if not password:
        raise RuntimeError("当前 Windows 用户无法读取学校密码，请重新运行 configure。")
    ocr = new_ocr()
    with sync_playwright() as playwright:
        browser = browser_context(playwright, headed)
        try:
            page = browser.new_page()
            for attempt in range(config["max_attempts"]):
                if state.get("submissions", 0) >= config["max_daily_submissions"]:
                    break
                # 每次从入口生成新流程和验证码，避免使用过期会话。
                username_input, password_input, code_input, image = open_form(page, config)
                code = ocr.classification(captcha_bytes(image)).strip()
                if not re.fullmatch(r"[A-Za-z0-9]{4}", code):
                    logging.info("验证码识别格式不符，重新获取。")
                    continue
                if not trusted_auth_url(page.url):
                    raise RuntimeError("认证页面地址发生异常变化。")
                username_input.fill(config["username"])
                password_input.fill(password)
                code_input.fill(code)
                # 先落盘计数及冷却，即使进程被中断也不会持续撞库式重试。
                state["submissions"] = state.get("submissions", 0) + 1
                state["next_attempt"] = time.time() + config["cooldown_minutes"] * 60
                write_json(STATE, state)
                page.get_by_role("button", name=re.compile(r"^登\s*录$")).click(timeout=15_000)
                logging.info("已提交认证，第 %d 次尝试。", attempt + 1)
                # 等待认证结果；只对明确的验证码错误进行本轮重试。
                result = "unknown"
                for _ in range(6):
                    page.wait_for_timeout(2500)
                    result = classify_error(page.locator("body").inner_text(timeout=5000))
                    if result != "unknown":
                        break
                    if not username_input.is_visible():
                        break
                if result == "unknown" and not username_input.is_visible() and internet_available(config["timeout_seconds"]):
                    state["next_attempt"] = 0
                    state["last_success"] = dt.datetime.now().isoformat(timespec="seconds")
                    write_json(STATE, state)
                    logging.info("登录表单已离开，已验证外网可用。")
                    return True
                if result == "blocked":
                    state["blocked"] = True
                    write_json(STATE, state)
                    logging.error("页面提示账号、密码或访问限制问题；已暂停自动登录，请检查后运行 configure。")
                    return False
                if result != "captcha":
                    logging.warning("未能确认恢复联网，进入冷却；可能需要调整认证入口。")
                    return False
                logging.info("页面提示验证码错误，将重新获取验证码。")
            return False
        finally:
            browser.close()


def run_check(config, force, headed):
    """检查并重连；config：配置；force：人工测试时即使在线也认证；headed：是否显示窗口。"""
    state = current_state()
    if not force:
        # 连续检测两次，正常联网时不启动浏览器。
        for index in range(2):
            if internet_available(config["timeout_seconds"]):
                logging.info("网络正常，无需登录。")
                return 0
            if index == 0:
                time.sleep(5)
    if not allowed_to_submit(state, config):
        logging.warning("处于冷却、每日次数上限或暂停状态，本轮不提交登录。")
        return 2
    # 校内入口也不可达时，只等待基础网络恢复，不尝试认证。
    try:
        fetch(config["portal_url"], config["timeout_seconds"])
    except OSError:
        logging.warning("校内网络入口不可达，等待下一轮检查。")
        return 2
    state["next_attempt"] = time.time() + config["cooldown_minutes"] * 60
    write_json(STATE, state)
    if force:
        logging.info("人工登录测试：在线时的测试不能证明断网恢复能力。")
    return 0 if authenticate(config, state, headed) else 2


def background_command():
    """生成不弹控制台的后台命令；无参数，返回可执行文件路径和参数字符串。"""
    if getattr(sys, "frozen", False):
        executable = ROOT / "njtechnetconnect-background.exe"
        arguments = ["check", "--data-dir", str(DATA)]
    else:
        executable = Path(sys.executable).with_name("pythonw.exe")
        arguments = [str(ASSETS / "reconnect.py"), "check", "--data-dir", str(DATA)]
    if not executable.is_file():
        raise FileNotFoundError("后台程序缺失，请重新解压完整发布包。")
    return str(executable), subprocess.list2cmdline(arguments)


def manage_task(operation, preview=False):
    """管理当前用户的任务；operation：enable/status/disable/remove；preview：只输出任务 XML，不注册。"""
    powershell = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    command = [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ASSETS / "manage-task.ps1"), "-Operation", operation]
    if operation == "enable":
        if not preview:
            config = load_config()
            if not vault().get_password(SERVICE, config["username"]):
                raise RuntimeError("当前 Windows 账户未保存学校密码，请先运行 configure。")
        executable, arguments = background_command()
        command += ["-Executable", executable, "-TaskArguments", arguments, "-WorkingDirectory", str(ROOT)]
        if preview:
            command.append("-Preview")
    result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode:
        # 不输出 PowerShell 异常中可能包含的环境数据；详细操作可手动检查任务计划权限。
        logging.error("任务管理失败，请检查当前 Windows 账户的任务计划权限。")
    return result.returncode


def self_test():
    """检查发布包运行依赖；无参数，OCR 测试禁止网络，只启动 Edge 空白页，不读取或提交学校凭据。"""
    import io
    from unittest.mock import patch
    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright
    # 用本地生成的图片检验模型和 ONNX 动态库是否完整。
    sample = Image.new("RGB", (120, 40), "white")
    ImageDraw.Draw(sample).text((8, 8), "abcd", fill="black", font_size=24)
    buffer = io.BytesIO()
    sample.save(buffer, format="PNG")
    with patch("socket.socket", side_effect=RuntimeError("离线测试禁止联网")), patch("socket.create_connection", side_effect=RuntimeError("离线测试禁止联网")):
        result = new_ocr().classification(buffer.getvalue())
        if not isinstance(result, str) or not result:
            raise RuntimeError("OCR 自检未返回字符。")
    vault()
    with sync_playwright() as playwright:
        browser = browser_context(playwright, False)
        try:
            page = browser.new_page()
            page.goto("about:blank")
        finally:
            browser.close()
    print("自检通过：离线 OCR、Windows 凭据库组件、Playwright 驱动和无窗口 Edge 均可用。")


def setup():
    """首次配置向导；无参数，依次保存凭据、诊断、可选真实测试并按用户选择启用任务。"""
    configure()
    config = load_config()
    diagnose(config, False)
    if input("现在提交一次真实登录测试？[Y/n]：").strip().lower() != "n":
        result = run_check(config, True, False)
        if result:
            print("登录测试未通过，尚未启用任务。请检查日志后重试。")
            return result
    if input("启用每三分钟自动重连（已登录或锁屏时运行，无需 Windows 密码）？[Y/n]：").strip().lower() != "n":
        return manage_task("enable")
    print("配置已保存，尚未启用自动任务。")
    return 0


def main():
    """处理命令并隔离错误；无参数，返回任务计划可识别的退出码。"""
    # 固定输出编码，避免 EXE 输出被 PowerShell 或其他程序捕获时中文乱码。
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="南京工业大学校园网本地自动重连")
    parser.add_argument("command", choices=["setup", "configure", "diagnose", "self-test", "check", "test-login", "enable", "status", "disable", "remove"])
    parser.add_argument("--headed", action="store_true", help="调试时显示 Edge 窗口")
    parser.add_argument("--preview", action="store_true", help="配合 enable 只生成任务 XML，不启用任务")
    parser.add_argument("--data-dir", type=Path, help="指定配置及日志目录，默认使用当前用户的应用数据目录（EXE 版）")
    args = parser.parse_args()
    global DATA, RUNTIME, CONFIG, STATE
    if args.data_dir:
        DATA = args.data_dir.resolve()
        RUNTIME, CONFIG = DATA / "runtime", DATA / "config.json"
        STATE = RUNTIME / "state.json"
    configure_logging()
    # 管理命令不占认证锁，确保后台正在检测网络时仍可停用任务。
    lock = contextlib.nullcontext(True) if args.command in ("enable", "status", "disable", "remove") else single_instance()
    with lock as acquired:
        if not acquired:
            logging.info("已有任务运行，本次退出。")
            return 0
        try:
            if args.command in ("enable", "status", "disable", "remove"):
                result = manage_task(args.command, args.preview)
                if args.command == "status":
                    print(f"数据目录：{DATA}")
                    print(f"配置状态：{'已配置' if CONFIG.exists() else '未配置'}")
                    state = current_state()
                    print(f"认证暂停：{'是' if state.get('blocked') else '否'}；今日已提交：{state.get('submissions', 0)} 次")
                return result
            if args.command == "setup":
                return setup()
            if args.command == "self-test":
                self_test()
                return 0
            if args.command == "configure":
                configure()
                return 0
            if args.command == "diagnose":
                config = load_config() if CONFIG.exists() else read_json(ASSETS / "config.example.json", {})
                diagnose(config, args.headed)
                return 0
            config = load_config()
            return run_check(config, args.command == "test-login", args.headed)
        except Exception as error:
            # 不记录异常原文，避免 Playwright 把密码填充参数或 URL 令牌写入日志。
            logging.error("执行失败（%s）；请运行 diagnose 检查页面，或 configure 重新配置。", type(error).__name__)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
