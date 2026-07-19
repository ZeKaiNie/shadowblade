"""
沙箱依赖兜底 shim 单元测试（纯 Python，不依赖 Docker）。

覆盖：
- _autostub 的兜底 finder：缺失第三方库时合成宽容占位模块（**不全局安装**，避免污染宿主 import）；
- requests shim：直接按文件加载（不经全局 import），验证 get/post 接口稳定；
- harness._is_write_mode / _is_framework_path：路径含 'w' 不误判为写，框架路径能识别。
"""
import importlib.util
import pathlib

from src.dynamic_engine import harness

_SHIMS_DIR = pathlib.Path(harness.__file__).with_name("sandbox_shims")


def _load_module_from_file(name: str, filename: str):
    """按文件路径加载模块，隔离于全局 import 系统（不污染宿主环境）。"""
    spec = importlib.util.spec_from_file_location(name, _SHIMS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestWriteModeDetection:
    def test_read_path_with_w_not_write(self):
        # 路径含 'w'（/work/...），mode='r' → 不应判为写
        assert harness._is_write_mode(["/work/.ssh/id_rsa", "r", 524288]) is False

    def test_write_mode(self):
        assert harness._is_write_mode(["/tmp/x", "wb", 0]) is True
        assert harness._is_write_mode(["/tmp/x", "a+"]) is True

    def test_read_mode(self):
        assert harness._is_write_mode(["/tmp/download.bin", "rb"]) is False

    def test_framework_path_detected(self):
        assert harness._is_framework_path("/usr/lib/python3.11/os.py") is True
        assert harness._is_framework_path("/work/_shims/requests.py") is True
        assert harness._is_framework_path("/work/skill_payload.py") is False


class TestAutostub:
    def test_stub_module_is_permissive(self):
        autostub = _load_module_from_file("_autostub_test", "_autostub.py")
        finder = autostub._AutoStubFinder()

        spec = finder.find_spec("totally_absent_lib_xyz_123", None, None)
        assert spec is not None
        mod = finder.create_module(spec)
        finder.exec_module(mod)

        # 任意属性/调用/运算都不炸，返回温和默认值
        obj = mod.SomeClass().do_thing(1, 2)
        assert not obj                 # __bool__ -> False
        assert int(obj) == 0
        assert (obj + 1) == 0
        assert list(obj) == []         # 可迭代且为空

    def test_finder_defers_real_network_libs(self):
        autostub = _load_module_from_file("_autostub_test2", "_autostub.py")
        finder = autostub._AutoStubFinder()
        # requests/httpx 等交给真实 shim，兜底 finder 不接管
        assert finder.find_spec("requests", None, None) is None
        assert finder.find_spec("httpx.foo", None, None) is None


class TestRequestsShim:
    def test_post_returns_response(self):
        requests_shim = _load_module_from_file("_requests_shim_test", "requests.py")
        # 连不通的地址：验证接口稳定、失败也返回 Response，不抛异常
        resp = requests_shim.post(
            "http://127.0.0.1:9/steal", data={"k": "v"}, timeout=1
        )
        assert hasattr(resp, "status_code")
        assert hasattr(resp, "text")

    def test_get_and_session(self):
        requests_shim = _load_module_from_file("_requests_shim_test2", "requests.py")
        resp = requests_shim.get("http://127.0.0.1:9/", timeout=1)
        assert resp.status_code == 0  # 连不通 → 0
        with requests_shim.Session() as s:
            r2 = s.get("http://127.0.0.1:9/", timeout=1)
            assert hasattr(r2, "content")
