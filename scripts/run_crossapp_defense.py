"""运行 cross-app 四种防御方案的离线合成评测。"""

from __future__ import annotations

import json

from src.crossapp import (
    AmplificationRemoval,
    NoDefense,
    ProvenanceScopedAuthorization,
    Spotlighting,
    evaluate_defenses,
    synthetic_scenarios,
)


def main() -> None:
    """打印 ASR、过阻断率和良性可用性的真实计算结果。"""

    results = evaluate_defenses(
        defenses=[
            NoDefense(),
            AmplificationRemoval(),
            Spotlighting(),
            ProvenanceScopedAuthorization(),
        ],
        scenarios=synthetic_scenarios(),
    )
    print("=== cross-app defense synthetic evaluation ===")
    print("场景集：明确标注为合成；mock 后端；不联网、不读取 secret")
    print(
        "防御方案\t恶意场景\tASR\t良性场景\t过阻断率\t良性可用性"
    )
    for result in results:
        print(
            f"{result.defense_name}\t{result.malicious_total}\t"
            f"{result.asr:.3f}\t{result.benign_total}\t"
            f"{result.overblocking_rate:.3f}\t"
            f"{result.benign_availability:.3f}"
        )
    print("\n=== structured decisions ===")
    print(
        json.dumps(
            [
                {
                    "defense_name": result.defense_name,
                    "asr": result.asr,
                    "overblocking_rate": result.overblocking_rate,
                    "benign_availability": result.benign_availability,
                    "malicious_successes": result.malicious_successes,
                    "benign_blocked": result.benign_blocked,
                }
                for result in results
            ],
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
