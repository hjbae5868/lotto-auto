import json
import random
import pandas as pd
import streamlit as st
from collections import Counter

st.set_page_config(page_title="로또 자동 분석 대시보드", layout="wide")
st.title("🎱 로또 6/45 자동 분석 & 주간 추천 대시보드")

# 데이터 로드
df = pd.read_csv("lotto_history.csv")
with open("weekly_picks.json", "r", encoding="utf-8") as f:
    picks = json.load(f)

num_cols = ["n1", "n2", "n3", "n4", "n5", "n6"]

# 1. 최신 당첨 번호 섹션
latest = df.iloc[-1]
st.subheader(f"🏆 최신 당첨 번호 ({int(latest['drwNo'])}회 | {latest['drwNoDate']})")
cols = st.columns(7)
for i, col_name in enumerate(num_cols):
    cols[i].metric(label=f"번호 {i+1}", value=int(latest[col_name]))
cols[6].metric(label="보너스", value=int(latest["bonus"]))

st.divider()

# 2. 이번 주 자동 추천 번호 5세트 (카톡 발송분과 동일)
st.subheader(f"🎯 {picks['target_drwNo']}회차 자동 추천 번호 5세트 (주간 고정)")
c1, c2 = st.columns(2)

with c1:
    st.markdown("#### 🔥 1~3세트: 역대 최다 출현 번호 기반")
    for idx, key in enumerate(["set_1_hot", "set_2_hot", "set_3_hot"], start=1):
        nums_str = "  ·  ".join(f"**{n}**" for n in picks["sets"][key])
        st.info(f"**세트 {idx}** : {nums_str}")

with c2:
    st.markdown("#### ❄️ 4~5세트: 최근 20회차 미출현 번호 기반")
    for idx, key in enumerate(["set_4_cold", "set_5_cold"], start=4):
        nums_str = "  ·  ".join(f"**{n}**" for n in picks["sets"][key])
        st.success(f"**세트 {idx}** : {nums_str}")
    st.caption(f"최근 20회차 미출현 번호 목록: {picks['cold_pool_20']}")

st.divider()

# 3. [신규] 원하는 만큼 즉시 추가 추출기
st.subheader("🎰 추가 번호 즉시 추출하기")
st.caption("카톡으로 받은 5세트 외에 번호가 더 필요할 때 원하는 방식과 개수로 바로 뽑을 수 있습니다.")

opt_col1, opt_col2 = st.columns([2, 1])
with opt_col1:
    mode = st.radio(
        "추출 기준 선택",
        ["🔥 역대 최다 출현 기반", "❄️ 최근 20회차 미출현 기반", "⚡ 혼합형 (최다출현 3 + 미출현 3)"],
        horizontal=True,
    )
with opt_col2:
    num_sets = st.slider("추가 추출할 세트 수", min_value=1, max_value=20, value=5)

if st.button("🎲 번호 추가 생성하기", type="primary"):
    # 전체 빈도 및 최근 20회차 빈도 계산
    total_counts = Counter(df[num_cols].values.flatten())
    top_15 = total_counts.most_common(15)
    top_nums = [num for num, _ in top_15]
    top_weights = [cnt for _, cnt in top_15]

    recent_counts = Counter(df.tail(20)[num_cols].values.flatten())
    cold_nums = [n for n in range(1, 46) if recent_counts[n] == 0]
    pool_cold = list(cold_nums)
    # 조합 다양성 확보를 위해 후보군이 10개 미만이면 최근 최소 출현 번호로 보충
    if len(pool_cold) < 10:
        least_recent = sorted(
            [n for n in range(1, 46) if n not in pool_cold],
            key=lambda x: recent_counts[x],
        )
        pool_cold.extend(least_recent[: 10 - len(pool_cold)])

    extra_sets = []
    attempts = 0
    while len(extra_sets) < num_sets and attempts < 1000:
        attempts += 1
        if "최다 출현" in mode:
            pick = set()
            while len(pick) < 6:
                pick.add(random.choices(top_nums, weights=top_weights, k=1)[0])
        elif "미출현" in mode:
            pick = set(random.sample(pool_cold, 6))
        else:  # 혼합형
            pick = set()
            while len(pick) < 3:
                pick.add(random.choices(top_nums, weights=top_weights, k=1)[0])
            remain_cold = [n for n in pool_cold if n not in pick]
            pick.update(random.sample(remain_cold, 3))

        sorted_pick = sorted(int(x) for x in pick)
        if sorted_pick not in extra_sets:
            extra_sets.append(sorted_pick)

    st.session_state["extra_sets"] = extra_sets
    st.session_state["extra_mode"] = mode

if "extra_sets" in st.session_state:
    st.markdown(f"**✨ 생성 결과 ({st.session_state['extra_mode']} · {len(st.session_state['extra_sets'])}세트)**")
    copy_lines = []
    for idx, s in enumerate(st.session_state["extra_sets"], start=1):
        nums_str = "  ·  ".join(f"**{n}**" for n in s)
        st.write(f"추가 {idx:02d})  {nums_str}")
        copy_lines.append(f"{idx}) {', '.join(map(str, s))}")

    with st.expander("📋 카톡·메모장에 복사하기 편한 텍스트 보기"):
        st.code("\n".join(copy_lines), language="text")

st.divider()

# 4. 전체 회차 번호별 출현 빈도 차트
st.subheader("📊 1회차 ~ 현재 번호별 누적 출현 빈도")
all_nums = df[num_cols].values.flatten()
counts = Counter(all_nums)
freq_df = pd.DataFrame(
    {"번호": range(1, 46), "출현 횟수": [counts[n] for n in range(1, 46)]}
).set_index("번호")
st.bar_chart(freq_df)

# 5. 최근 10회차 당첨 이력 표
st.subheader("📋 최근 10회차 당첨 이력")
st.dataframe(df.tail(10).sort_values("drwNo", ascending=False), use_container_width=True, hide_index=True)
