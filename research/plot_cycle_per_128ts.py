"""
plot_cycles_per_128ts.py
------------------------
역할:
    각 Synchronization Period(T)에 대해 투기실행 구간만 추출하여,
    128 timestep 기준으로 정규화한 사이클 수의 평균/최대/최솟값을
    막대그래프로 비교합니다.

정규화 방식:
    T=4 이면 각 주기 소모 사이클 × (128/4) = × 32
    T=128이면 각 주기 소모 사이클 × (128/128) = × 1

구간 필터링:
    - Warmup 제외: timestep <= SETUP_TIMESTEP 인 구간 제외
    - Cooldown 제외: 각 T마다 마지막 주기가 T=1로 강제되는 구간 제외
      (max_timestep=1970, T∈{1,2,4,8,16,32,64,128} 이면 cooldown=0)

사용법:
    python3 plot_cycles_per_128ts.py

출력:
    {SAVE_DIR}/cycles_per_128ts_comparison.png
"""

import os
import re
import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ================================================================
# [설정]
# ================================================================
T_VALUES      = [1, 2, 4, 8, 16, 32, 64, 128]
PRETRACE_ENG  = 10
WORKLOAD      = "example1"
RUNSPACE_PATH = "./runspace/lazy_doubled_timestep/"
SAVE_DIR      = "./../result_pictures"
SETUP_TIMESTEP = 50        # warmup 구간 (이 timestep 이하 제외)
MAX_TIMESTEP   = 1971      # example.cfg의 max_timestep 1970
NORMALIZE_TO   = 128       # 정규화 기준 timestep 수
# ================================================================


def parse_log(log_path: str):
    """
    log 파일에서 (timestep, incremental_cycles) 쌍을 파싱합니다.
    incremental_cycles = 해당 sync 주기 동안 소모된 사이클 수.
    """
    if not os.path.exists(log_path):
        return None

    with open(log_path, "r") as f:
        lines = f.readlines()

    records = []
    prev_cyc = 0
    for line in lines:
        match = re.search(r"(\d+) / \d+ \.\.\. cyc (\d+)", line)
        if match:
            ts       = int(match.group(1))
            curr_cyc = int(match.group(2))
            inc_cyc  = curr_cyc - prev_cyc
            records.append((ts, inc_cyc))
            prev_cyc = curr_cyc

    return records


def extract_speculative_normalized(records, t_value: int,
                                   setup_ts: int, max_ts: int,
                                   normalize_to: int):
    """
    투기실행 구간만 추출하고 normalize_to 기준으로 정규화합니다.

    Warmup 제외: timestep <= setup_ts
    Cooldown 제외: 마지막 주기가 T=1로 강제되는 구간
        → next_sync_timestep + T >= max_ts 조건이 되는 timestep 이후
        → 즉 마지막 정상 주기의 끝 timestep = max_ts - (max_ts - setup_ts) % t_value - 1
          (단 나머지가 0이면 cooldown 없음)

    Returns:
        normalized_cycles: 정규화된 사이클 수 리스트
    """
    if not records:
        return []

    # cooldown 시작 timestep 계산
    speculative_span = max_ts - setup_ts        # 투기실행 전체 구간 길이
    remainder = speculative_span % t_value
    if remainder == 0:
        cooldown_start_ts = max_ts + 1          # cooldown 없음
    else:
        cooldown_start_ts = max_ts - remainder  # 이 timestep부터 T=1 강제

    scale = normalize_to / t_value
    normalized = []

    for ts, inc_cyc in records:
        if ts <= setup_ts + t_value:            # @@ warmup 직후 첫 투기실행 역시 제외
            continue                            # warmup 제외 
        if ts >= cooldown_start_ts:
            continue                            # cooldown 제외
        normalized.append(inc_cyc * scale)

    return normalized


def compute_stats(normalized_cycles):
    """평균/최대/최솟값 반환."""
    if not normalized_cycles:
        return None, None, None
    arr = np.array(normalized_cycles)
    return float(np.mean(arr)), float(np.max(arr)), float(np.min(arr))


def plot_bar_chart(stats_dict: dict, save_dir: str, normalize_to: int):
    """
    T 값별 avg/max/min 사이클을 그룹 막대그래프로 시각화합니다.

    stats_dict: {T값: (avg, max, min)} 딕셔너리
    """
    t_values  = sorted(stats_dict.keys())
    x_indices = np.arange(len(t_values))   # 등간격 X 위치

    avgs = [stats_dict[t][0] for t in t_values]
    maxs = [stats_dict[t][1] for t in t_values]
    mins = [stats_dict[t][2] for t in t_values]

    bar_width = 0.25
    offset_avg = -bar_width
    offset_max =  0
    offset_min =  bar_width

    color_avg = "#16A34A"   # 초록
    color_max = "#DC2626"   # 빨강
    color_min = "#2563EB"   # 파랑

    fig, ax = plt.subplots(figsize=(13, 6))
    fig.suptitle(
        f"Cycles per {normalize_to} Timesteps by Synchronization Period T\n"
        f"(Warmup & Cooldown Excluded, Normalized to {normalize_to} TS)",
        fontsize=13, fontweight="bold"
    )

    bars_avg = ax.bar(x_indices + offset_avg, avgs, bar_width,
                      label=f"Average ({normalize_to} TS)",
                      color=color_avg, alpha=0.85, edgecolor="white")
    bars_max = ax.bar(x_indices + offset_max, maxs, bar_width,
                      label=f"Max ({normalize_to} TS)",
                      color=color_max, alpha=0.85, edgecolor="white")
    bars_min = ax.bar(x_indices + offset_min, mins, bar_width,
                      label=f"Min ({normalize_to} TS)",
                      color=color_min, alpha=0.85, edgecolor="white")

    # 막대 위에 수치 표시
    for bar in bars_avg:
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.01,
                f"{bar.get_height():,.0f}",
                ha="center", va="bottom", fontsize=7.5, color=color_avg)
    for bar in bars_max:
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.01,
                f"{bar.get_height():,.0f}",
                ha="center", va="bottom", fontsize=7.5, color=color_max)
    for bar in bars_min:
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.01,
                f"{bar.get_height():,.0f}",
                ha="center", va="bottom", fontsize=7.5, color=color_min)

    ax.set_xlabel("Synchronization Period (T)", fontsize=12)
    ax.set_ylabel(f"Cycles (normalized to {normalize_to} timesteps)", fontsize=12)
    ax.set_xticks(x_indices)
    ax.set_xticklabels([f"T={t}" for t in t_values], fontsize=11)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{int(x):,}")
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    output_file = os.path.join(save_dir, "cycles_per_128ts_comparison.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"[저장 완료] {output_file}")
    plt.show()


# ================================================================
# 메인 실행
# ================================================================
if __name__ == "__main__":
    stats_dict = {}

    for t in T_VALUES:
        folder = f"{WORKLOAD}_peri{t}_{PRETRACE_ENG}pretrace_eng"
        log_path = os.path.join(RUNSPACE_PATH, folder, "log")

        print(f"[T={t:>3}] 파싱 중: {log_path}")
        records = parse_log(log_path)

        if records is None:
            print(f"  [건너뜀] log 파일 없음")
            continue

        normalized = extract_speculative_normalized(
            records, t, SETUP_TIMESTEP, MAX_TIMESTEP, NORMALIZE_TO
        )

        if not normalized:
            print(f"  [건너뜀] 투기실행 구간 데이터 없음")
            continue

        avg, mx, mn = compute_stats(normalized)
        stats_dict[t] = (avg, mx, mn)

        # cooldown 여부 출력
        remainder = (MAX_TIMESTEP - SETUP_TIMESTEP) % t
        cooldown_info = "없음" if remainder == 0 else f"{remainder} timestep"
        print(f"  주기 수: {len(normalized)}개 | "
              f"avg={avg:>12,.1f} | max={mx:>12,.1f} | min={mn:>12,.1f} | "
              f"cooldown={cooldown_info}")

    if stats_dict:
        plot_bar_chart(stats_dict, SAVE_DIR, NORMALIZE_TO)
    else:
        print("\n[오류] 유효한 데이터가 없습니다. RUNSPACE_PATH와 T_VALUES를 확인하세요.")