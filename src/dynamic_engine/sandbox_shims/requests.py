"""
`requests` 的最小 urllib 兜底实现（沙箱内专用）。

白话讲解：
- MalSkillBench 里 836 个恶意脚本用 requests 联网/外传。真镜像没装 requests 就崩，
  行为审计抓不到。这里用标准库 urllib 顶上，让 requests.get/post 真的走一次
  urllib.request —— 从而触发 socket/urllib 审计事件，被 harness 记为 network；
  若外传 URL/body 里带蜜罐标记，还能被坐实为凭据外传。
- 沙箱是 --network none，真实连接会立即失败；但审计钩子在"发起连接的那一刻"就已记录，
  所以哪怕连不出去，"企图外传"依然被抓到。失败时返回一个温和的假 Response。
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request


class RequestException(Exception):
    pass


class Response:
    """极简响应对象，覆盖常见访问方式。"""

    def __init__(self, url: str = "", status_code: int = 0, content: bytes = b""):
        self.url = url
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", "replace") if content else ""
        self.headers: dict[str, str] = {}
        self.ok = 200 <= status_code < 400

    def json(self):
        import json

        try:
            return json.loads(self.text)
        except Exception:
            return {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int = 1024):
        if self.content:
            yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _encode_body(data=None, json=None):
    if json is not None:
        import json as _json

        return _json.dumps(json).encode("utf-8"), "application/json"
    if data is None:
        return None, None
    if isinstance(data, (bytes, bytearray)):
        return bytes(data), None
    if isinstance(data, str):
        return data.encode("utf-8"), None
    if isinstance(data, dict):
        return urllib.parse.urlencode(data).encode("utf-8"), (
            "application/x-www-form-urlencoded"
        )
    return str(data).encode("utf-8"), None


def request(method: str, url: str, **kwargs) -> Response:
    params = kwargs.get("params")
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params)

    body, ctype = _encode_body(kwargs.get("data"), kwargs.get("json"))
    headers = dict(kwargs.get("headers") or {})
    if ctype and "Content-Type" not in headers:
        headers["Content-Type"] = ctype

    # 构造 Request 会触发 urllib.Request 审计事件；urlopen 触发 socket 审计事件
    req = urllib.request.Request(
        url, data=body, headers=headers, method=method.upper()
    )
    timeout = kwargs.get("timeout", 3) or 3
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            return Response(url, getattr(resp, "status", 200), content)
    except urllib.error.HTTPError as e:
        return Response(url, e.code, b"")
    except Exception:
        # --network none 下会走到这里：连接失败，但审计已记录"企图外传"
        return Response(url, 0, b"")


def get(url, **kwargs):
    return request("GET", url, **kwargs)


def post(url, **kwargs):
    return request("POST", url, **kwargs)


def put(url, **kwargs):
    return request("PUT", url, **kwargs)


def delete(url, **kwargs):
    return request("DELETE", url, **kwargs)


def head(url, **kwargs):
    return request("HEAD", url, **kwargs)


def patch(url, **kwargs):
    return request("PATCH", url, **kwargs)


class Session:
    """会话对象：转调模块级函数即可（沙箱里不需要真正保持连接）。"""

    def __init__(self):
        self.headers: dict[str, str] = {}

    def request(self, method, url, **kwargs):
        return request(method, url, **kwargs)

    def get(self, url, **kwargs):
        return get(url, **kwargs)

    def post(self, url, **kwargs):
        return post(url, **kwargs)

    def put(self, url, **kwargs):
        return put(url, **kwargs)

    def delete(self, url, **kwargs):
        return delete(url, **kwargs)

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class exceptions:  # noqa: N801  (模拟 requests.exceptions 命名空间)
    RequestException = RequestException
    ConnectionError = RequestException
    Timeout = RequestException
    HTTPError = RequestException
