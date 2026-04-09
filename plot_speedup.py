"""
plot_speedup_comparison.py
--------------------------
역할:
    여러 Synchronization Period(T) 값에 대한 시뮬레이션 결과를 비교하는 그래프를 생성합니다.
    - 왼쪽: T 값에 따른 총 사이클 수 변화
    - 오른쪽: T=1(Time-Precise baseline) 대비 Speedup

사용법:
    python3 plot_speedup_comparison.py

출력:
    speedup_comparison.png  (RUNSPACE_PATH 기준으로 저장)
"""

import os
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

# ================================================================
# [설정] @@
# ================================================================
RUNSPACE_PATH = "./runspace/lazy_doubled_timestep/"          # 실험 결과 폴더 경로
SAVE_PATH     = "./../result_pictures"          # 그래프 저장 경로
PRETRACE_ENG  = 10                          # pretrace_engine 값 (폴더명 필터용)
# ================================================================


def parse_results(runspace_path: str, pretrace_eng: int) -> pd.DataFrame:
    """
    runspace 내 각 실험 폴더에서 T 값과 최종 사이클 수를 추출합니다.

    폴더명 형식: example1_peri{T}_{pretrace_eng}pretrace_eng
    log 파일 형식 (한 줄 예시): 992 / 992 ... cyc 1234567, elapsed 3.14 (s)
    """
    records = []

    for folder_name in os.listdir(runspace_path):
        # pretrace_engine 값이 맞는 폴더만 처리
        if f"{pretrace_eng}pretrace_eng" not in folder_name:
            continue

        # 폴더명에서 T(sync period) 값 추출
        match = re.search(r"peri(\d+)", folder_name)
        if not match:
            continue
        t_value = int(match.group(1))

        log_path = os.path.join(runspace_path, folder_name, "log")
        if not os.path.exists(log_path):
            print(f"  [경고] log 파일 없음: {log_path}")
            continue

        # log 파일의 마지막 유효 줄에서 최종 누적 사이클 추출
        with open(log_path, "r") as f:
            lines = f.readlines()

        for line in reversed(lines):
            cyc_match = re.search(r"cyc (\d+)", line)
            if cyc_match:
                total_cyc = int(cyc_match.group(1))
                records.append({"T": t_value, "Total_Cycles": total_cyc})
                break

    if not records:
        raise ValueError(f"유효한 실험 결과를 찾을 수 없습니다: {runspace_path}")

    df = pd.DataFrame(records).sort_values("T").reset_index(drop=True)
    return df


def compute_speedup(df: pd.DataFrame) -> pd.DataFrame:
    """T=1(Time-Precise baseline) 대비 Speedup을 계산합니다."""
    baseline_rows = df[df["T"] == 1]
    if baseline_rows.empty:
        raise ValueError("T=1 baseline 데이터가 없습니다. sync_period 목록에 1이 포함되어 있는지 확인하세요.")
    baseline_cyc = baseline_rows["Total_Cycles"].values[0]
    df["Speedup"] = baseline_cyc / df["Total_Cycles"]
    return df


def plot_comparison(df: pd.DataFrame, save_path: str, pretrace_eng: int) -> None:
    """총 사이클 수와 Speedup을 나란히 비교하는 그래프를 저장합니다."""

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        f"NeuroSync: Effect of Synchronization Period T\n"
        f"(pretrace_engine={pretrace_eng})",
        fontsize=14, fontweight="bold"
    )

    t_vals = df["T"].tolist()

    # --- 왼쪽: 총 사이클 수 ---
    ax1.plot(df["T"], df["Total_Cycles"], marker="o", color="#2563EB",
             linewidth=2, markersize=7, label="Total Cycles")
    ax1.set_title("Total Simulation Cycles", fontsize=12)
    ax1.set_xlabel("Synchronization Period (T)", fontsize=11)
    ax1.set_ylabel("Total Cycles", fontsize=11)
    ax1.set_xticks(t_vals)
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend()

    # --- 오른쪽: Speedup ---
    ax2.plot(df["T"], df["Speedup"], marker="s", color="#DC2626",
             linewidth=2, markersize=7, label="Speedup")
    ax2.axhline(y=1.0, color="gray", linestyle="--", linewidth=1.2, label="Baseline (T=1)")

    # 각 점 위에 수치 표시
    for _, row in df.iterrows():
        ax2.annotate(
            f"{row['Speedup']:.2f}x",
            xy=(row["T"], row["Speedup"]),
            xytext=(0, 10), textcoords="offset points",
            ha="center", fontsize=9, color="#DC2626"
        )

    ax2.set_title("Speedup over Time-Precise (T=1)", fontsize=12)
    ax2.set_xlabel("Synchronization Period (T)", fontsize=11)
    ax2.set_ylabel("Speedup", fontsize=11)
    ax2.set_xticks(t_vals)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend()

    plt.tight_layout()

    os.makedirs(save_path, exist_ok=True)
    # @@@
    output_file = os.path.join(save_path, "speedup_comparison.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"[저장 완료] {output_file}")
    plt.show()


# ================================================================
# 메인 실행
# ================================================================
if __name__ == "__main__":
    print(f"데이터 추출 중: {RUNSPACE_PATH}")
    df = parse_results(RUNSPACE_PATH, PRETRACE_ENG)
    df = compute_speedup(df)

    print("\n[추출된 결과]")
    print(df.to_string(index=False))

    plot_comparison(df, SAVE_PATH, PRETRACE_ENG)