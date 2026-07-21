#!/usr/bin/env python3
"""运行 cross-app 上下文投毒 v1 的有毒/无毒对照。

本脚本只使用离线 mock LLM，不连接任何云 API，也不读取 API key。
"""

from __future__ import annotations

import json

from src.conformance.capabilities import Capability
from src.crossapp import (
    BenignApp,
    CrossAppSession,
    MaliciousApp,
    MockInstructionFollowingLLM,
)


def main() -> None:
    """打印同一 harness 在有毒和干净上下文下的结构化结果。"""

    llm = MockInstructionFollowingLLM()
    benign_app = BenignApp(
        app_id="calendar-helper",
        manifest={Capability.FILE_READ},
    )
    malicious_app = MaliciousApp(app_id="weather-widget")

    poisoned = CrossAppSession(benign_app=benign_app, llm=llm).run(
        user_request="帮我整理今天的日程",
        malicious_app=malicious_app,
    )
    clean = CrossAppSession(benign_app=benign_app, llm=llm).run(
        user_request="帮我整理今天的日程",
        malicious_app=None,
    )

    print("=== cross-app context poisoning demo ===")
    print(
        json.dumps(
            {"poisoned": poisoned.model_dump(), "clean": clean.model_dump()},
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
