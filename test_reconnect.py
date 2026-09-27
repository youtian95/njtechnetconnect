# 功能：验证网络误判、认证域名和重试限速等关键逻辑，不访问网络、不提交学校登录。
# 流程：运行 python -m unittest -v；输入：模拟网络响应和状态；输出：测试结果。
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import reconnect as app


class ReconnectTests(unittest.TestCase):
    """测试无人值守时必须保持的认证边界和停止条件。"""

    def test_captive_redirect_is_not_online(self):
        """门户页面即使返回 HTTP 200，也不应被认为已联网；无参数。"""
        with patch.object(app, "fetch", return_value=(200, "https://sfgl.njtech.edu.cn/", b"login")):
            self.assertFalse(app.internet_available(1))

    def test_second_probe_can_confirm_online(self):
        """一个探测站不可达时允许另一个确认联网；无参数。"""
        with patch.object(app, "fetch", side_effect=[OSError(), (204, app.PROBES[1][0], b"")]):
            self.assertTrue(app.internet_available(1))

    def test_wrong_body_is_not_online(self):
        """状态码正确但内容不符时，不认定联网；无参数。"""
        with patch.object(app, "fetch", return_value=(200, app.PROBES[0][0], b"authentication required")):
            self.assertFalse(app.internet_available(1))

    def test_credentials_only_go_to_exact_https_host(self):
        """限制密码填写目标的协议、主机和端口；无参数。"""
        self.assertTrue(app.trusted_auth_url("https://sfgl.njtech.edu.cn/cas/login"))
        for url in ["http://sfgl.njtech.edu.cn/", "https://sfgl.njtech.edu.cn.evil.test/", "https://sfgl.njtech.edu.cn:444/", "https://evil.test/?next=sfgl.njtech.edu.cn"]:
            self.assertFalse(app.trusted_auth_url(url))

    def test_retry_limits_survive_between_runs(self):
        """冷却、每日上限和暂停状态分别阻止提交；无参数。"""
        config = {"max_daily_submissions": 12}
        self.assertTrue(app.allowed_to_submit({}, config))
        for state in [{"next_attempt": time.time() + 600}, {"submissions": 12}, {"blocked": True}]:
            self.assertFalse(app.allowed_to_submit(state, config))

    def test_error_classification(self):
        """验证码错误可重试，账号异常必须停止；无参数。"""
        self.assertEqual(app.classify_error("校验码错误"), "captcha")
        self.assertEqual(app.classify_error("用户名或密码不正确"), "blocked")
        self.assertEqual(app.classify_error("账号已锁定"), "blocked")
        self.assertEqual(app.classify_error("服务器维护中"), "unknown")

    def test_packaged_task_uses_background_executable(self):
        """发布版必须调用无窗口程序，并正确处理带空格的数据路径；无参数。"""
        with tempfile.TemporaryDirectory(prefix='njtech test ') as directory:
            root = Path(directory)
            (root / 'njtechnetconnect-background.exe').touch()
            with patch.object(app.sys, 'frozen', True, create=True), patch.object(app, 'ROOT', root), patch.object(app, 'DATA', root / 'user data'):
                executable, arguments = app.background_command()
            self.assertEqual(Path(executable).name, 'njtechnetconnect-background.exe')
            self.assertIn('--data-dir "', arguments)
            self.assertTrue(arguments.startswith('check '))

    def test_source_task_uses_pythonw(self):
        """源码版任务使用 pythonw.exe，避免控制台弹窗；无参数。"""
        executable, arguments = app.background_command()
        self.assertEqual(Path(executable).name, 'pythonw.exe')
        self.assertIn('reconnect.py', arguments)

    def test_preview_does_not_request_credentials(self):
        """任务 XML 预览不能读取学校密码；无参数。"""
        with patch.object(app, 'vault', side_effect=AssertionError('不应访问凭据库')), patch.object(app, 'background_command', return_value=('worker.exe', 'check')), patch.object(app.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '<Task />'
            self.assertEqual(app.manage_task('enable', preview=True), 0)
            self.assertIn('-Preview', run.call_args.args[0])

    def test_disable_remains_available_during_authentication(self):
        """后台持有认证锁时也可以停用任务；无参数。"""
        with patch.object(app.sys, 'argv', ['reconnect.py', 'disable']), patch.object(app, 'configure_logging'), patch.object(app, 'single_instance', side_effect=AssertionError('管理命令不应获取认证锁')), patch.object(app, 'manage_task', return_value=0) as manage:
            self.assertEqual(app.main(), 0)
            manage.assert_called_once_with('disable', False)


if __name__ == "__main__":
    unittest.main()
