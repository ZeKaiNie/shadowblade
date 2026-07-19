"""
`httpx` 的最小兜底（沙箱内专用）：转调 requests shim，复用其 urllib 实现。

白话讲解：httpx 的 get/post/Client 用法与 requests 高度相似，直接借用同一套
urllib 实现即可让联网动作被审计到。
"""
from __future__ import annotations

import requests as _r

Response = _r.Response


def get(url, **kwargs):
    return _r.get(url, **kwargs)


def post(url, **kwargs):
    return _r.post(url, **kwargs)


def put(url, **kwargs):
    return _r.put(url, **kwargs)


def delete(url, **kwargs):
    return _r.delete(url, **kwargs)


def request(method, url, **kwargs):
    return _r.request(method, url, **kwargs)


class Client:
    def __init__(self, *a, **k):
        pass

    def get(self, url, **kwargs):
        return _r.get(url, **kwargs)

    def post(self, url, **kwargs):
        return _r.post(url, **kwargs)

    def request(self, method, url, **kwargs):
        return _r.request(method, url, **kwargs)

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


AsyncClient = Client
