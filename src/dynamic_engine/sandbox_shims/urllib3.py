"""
`urllib3` 的最小兜底（沙箱内专用）：用 requests shim 的 urllib 实现顶上常见用法。
"""
from __future__ import annotations

import requests as _r


class HTTPResponse:
    def __init__(self, resp: "_r.Response"):
        self.status = resp.status_code
        self.data = resp.content


class PoolManager:
    def request(self, method, url, **kwargs):
        return HTTPResponse(_r.request(method, url, **kwargs))

    def urlopen(self, method, url, **kwargs):
        return HTTPResponse(_r.request(method, url, **kwargs))


def disable_warnings(*_a, **_k):
    return None
