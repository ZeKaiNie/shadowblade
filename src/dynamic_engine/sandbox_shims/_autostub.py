"""
沙箱内的"缺失依赖自动兜底"—— 让技能代码即使缺第三方库也能继续跑到暴露行为的那一步。

白话讲解：
- MalSkillBench 里大量恶意脚本 `import requests / yaml / cryptography / psutil ...`，
  这些库在最小镜像里没有 → 一 import 就崩，还没来得及联网/起子进程/读凭据，
  行为审计就抓不到任何东西（这正是我们此前观测全空的原因）。
- 对策：
  1) 联网类库（requests/httpx/wget/urllib3）用**真的 urllib 实现**，这样 get/post 会触发
     socket/urllib 审计事件，被 harness 记为 network；若外传的 URL/body 里带蜜罐标记，
     还能被坐实为凭据外传。
  2) 其它非联网库（yaml/cryptography/psutil/PIL/torch...）用**宽容占位对象**顶上，
     只求 import 成功、调用不报错，让脚本能继续执行到真正的敏感操作。
- 占位对象绝不联网、绝不真执行危险操作，只是"温和地什么都不做"。
- 该兜底 finder 挂在 sys.meta_path **末尾**：只有正常 import 失败时才启用，
  绝不遮蔽标准库或镜像里已装的真库。
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
import types


class _Stub:
    """宽容占位：任何属性访问/调用/运算都返回自身或惰性默认值，尽量不抛错。"""

    def __init__(self, name: str = "stub"):
        object.__setattr__(self, "_name", name)

    # 属性 / 调用 —— 始终返回一个新的占位对象
    def __getattr__(self, item):
        return _Stub(f"{object.__getattribute__(self, '_name')}.{item}")

    def __call__(self, *args, **kwargs):
        return _Stub(f"{object.__getattribute__(self, '_name')}()")

    def __setattr__(self, key, value):
        pass

    # 迭代 / 容器协议 —— 表现为空
    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __contains__(self, _item):
        return False

    def __getitem__(self, _item):
        return _Stub("item")

    def __setitem__(self, _k, _v):
        pass

    # 数值 / 布尔 —— 给出温和默认值，避免比较/运算炸掉控制流
    def __bool__(self):
        return False

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0

    def _num(self, *_a, **_k):
        return 0

    __add__ = __radd__ = __sub__ = __rsub__ = _num
    __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _num
    __floordiv__ = __mod__ = __pow__ = _num

    def __lt__(self, _o):
        return False

    def __le__(self, _o):
        return False

    def __gt__(self, _o):
        return False

    def __ge__(self, _o):
        return False

    def __eq__(self, _o):
        return False

    def __ne__(self, _o):
        return True

    def __hash__(self):
        return id(self)

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def __str__(self):
        return ""

    def __repr__(self):
        return f"<Stub {object.__getattribute__(self, '_name')}>"


class _StubModule(types.ModuleType):
    """把整个缺失模块表现为占位：任何 from x import y / x.y 都能拿到占位对象。"""

    def __getattr__(self, item):
        if item.startswith("__") and item.endswith("__"):
            raise AttributeError(item)
        return _Stub(f"{self.__name__}.{item}")


# 有真实 urllib 实现的联网类库（值 = 兜底 finder 里对应的构造函数名）
_REAL_NET_MODULES = {"requests", "httpx", "wget", "urllib3"}


class _AutoStubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """import 失败时的兜底：为任意缺失模块合成一个占位模块。"""

    def find_spec(self, fullname, path=None, target=None):
        # 联网类库交给对应真实 shim（它们是 _shims 目录下的真实 .py），此处不接管
        top = fullname.split(".")[0]
        if top in _REAL_NET_MODULES:
            return None
        return importlib.machinery.ModuleSpec(fullname, self)

    def create_module(self, spec):
        return _StubModule(spec.name)

    def exec_module(self, module):
        return None


def install() -> None:
    """把兜底 finder 挂到 meta_path 末尾（只在正常 import 失败后才生效）。"""
    if not any(isinstance(f, _AutoStubFinder) for f in sys.meta_path):
        sys.meta_path.append(_AutoStubFinder())
