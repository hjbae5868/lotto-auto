import json
import pandas as pd
import streamlit as st
from collections import Counter

st.set_page_config(page_title="로또 자동 분석 대시보드", layout="wide")
st.title("🎱 로또 6/45 자동 분석 & 주간 추천 대시보드")

df = pd.read_csv("lotto_history.csv")
with open("weekly_picks.json", "r", encoding="utf-8") as f:
    picks = json.load(f)

latest = df.iloc[-1]
st.subheader(f"🏆 최신 당첨 번호 ({int(latest['drwNo'])}회 | {latest['drwNoDate']})")
cols = st.columns(7)
for i, col_name in enumerate(["n1", "n2", "n3", "n4", "n5", "n6"]):
    cols[i].metric(label=f"번호 {i+1}", value=int(latest[col_name]))
cols[6].metric(label="보너스", value=int(latest["bonus"]))

st.divider()

st.subheader(f"🎯 {picks['target_drwNo']}회차 추천 번호 5세트")
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

st.subheader("📊 1회차 ~ 현재 번호별 누적 출현 빈도")
all_nums = df[["n1", "n2", "n3", "n4", "n5", "n6"]].values.flatten()
counts = Counter(all_nums)
freq_df = pd.DataFrame(
    {"번호": range(1, 46), "출현 횟수": [counts[n] for n in range(1, 46)]}
).set_index("번호")
st.bar_chart(freq_df)

st.subheader("📋 최근 10회차 당첨 이력")
st.dataframe(df.tail(10).sort_values("drwNo", ascending=False), use_container_width=True, hide_index=True)
