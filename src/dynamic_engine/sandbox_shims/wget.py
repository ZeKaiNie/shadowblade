"""
`wget` 的最小 urllib 兜底（沙箱内专用）。

白话讲解：恶意脚本常用 wget.download(url, out) 拉恶意载荷。这里用 urllib 顶上，
让下载动作触发网络审计事件（--network none 下会失败，但"企图下载"已被记录）。
"""
from __future__ import annotations

import os
import tempfile
import urllib.request


def download(url: str, out: str | None = None, bar=None) -> str:
    target = out or os.path.join(tempfile.gettempdir(), "wget_download.bin")
    try:
        urllib.request.urlretrieve(url, target)
    except Exception:
        pass
    return target
