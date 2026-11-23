import os
import json
import random
import time
import requests
import pandas as pd
from collections import Counter

CSV_FILE = "lotto_history.csv"
PICKS_FILE = "weekly_picks.json"
API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}"

# 크롬 브라우저로 위장하는 헤더 추가
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.dhlottery.co.kr/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

session = requests.Session()
session.headers.update(HEADERS)


def fetch_draw(drw_no):
    try:
        res = session.get(API_URL.format(drw_no), timeout=10)
        if res.status_code != 200:
            print(f"{drw_no}회차 HTTP 오류: {res.status_code}")
            return None
        data = res.json()
        if data.get("returnValue") == "success":
            return {
                "drwNo": data["drwNo"],
                "drwNoDate": data["drwNoDate"],
                "n1": data["drwtNo1"],
                "n2": data["drwtNo2"],
                "n3": data["drwtNo3"],
                "n4": data["drwtNo4"],
                "n5": data["drwtNo5"],
                "n6": data["drwtNo6"],
                "bonus": data["bnusNo"],
            }
    except Exception as e:
        print(f"{drw_no}회차 조회 오류: {e}")
        try:
            print("응답 일부:", res.text[:150].replace("\n", " "))
        except Exception:
            pass
    return None


def update_history():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        next_drw = int(df["drwNo"].max()) + 1
    else:
        df = pd.DataFrame(
            columns=["drwNo", "drwNoDate", "n1", "n2", "n3", "n4", "n5", "n6", "bonus"]
        )
        next_drw = 1

    new_rows = []
    while True:
        row = fetch_draw(next_drw)
        if row is None:
            break
        new_rows.append(row)
        next_drw += 1
        time.sleep(0.1)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)
        print(f"{len(new_rows)}개 회차 업데이트 완료 (최신: {df['drwNo'].max()}회)")
    else:
        print("이미 최신 회차입니다.")
    return df


def generate_weekly_picks(df):
    num_cols = ["n1", "n2", "n3", "n4", "n5", "n6"]

    # 1~3세트: 역대 최다 출현 상위 15개 중 가중치 추출
    all_nums = df[num_cols].values.flatten()
    total_counts = Counter(all_nums)
    top_15 = total_counts.most_common(15)
    top_nums = [num for num, _ in top_15]
    top_weights = [cnt for _, cnt in top_15]

    sets_hot = []
    while len(sets_hot) < 3:
        pick = set()
        while len(pick) < 6:
            pick.add(random.choices(top_nums, weights=top_weights, k=1)[0])
        sorted_pick = sorted(int(x) for x in pick)
        if sorted_pick not in sets_hot:
            sets_hot.append(sorted_pick)

    # 4~5세트: 최근 20회차 미출현 번호 기반 추출
    recent_20 = df.tail(20)
    recent_counts = Counter(recent_20[num_cols].values.flatten())
    cold_nums = [n for n in range(1, 46) if recent_counts[n] == 0]

    pool_cold = list(cold_nums)
    if len(pool_cold) < 8:
        least_recent = sorted(
            [n for n in range(1, 46) if n not in pool_cold],
            key=lambda x: recent_counts[x],
        )
        pool_cold.extend(least_recent[: 8 - len(pool_cold)])

    sets_cold = []
    while len(sets_cold) < 2:
        sorted_pick = sorted(int(x) for x in random.sample(pool_cold, 6))
        if sorted_pick not in sets_cold:
            sets_cold.append(sorted_pick)

    latest = df.iloc[-1]
    latest_drw = int(latest["drwNo"])
    result = {
        "base_drwNo": latest_drw,
        "target_drwNo": latest_drw + 1,
        "latest_nums": [int(latest[c]) for c in num_cols],
        "latest_bonus": int(latest["bonus"]),
        "cold_pool_20": cold_nums,
        "sets": {
            "set_1_hot": sets_hot[0],
            "set_2_hot": sets_hot[1],
            "set_3_hot": sets_hot[2],
            "set_4_cold": sets_cold[0],
            "set_5_cold": sets_cold[1],
        },
    }

    with open(PICKS_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def send_kakao_memo(picks):
    """카카오톡 나에게 보내기 발송"""
    rest_api_key = os.environ.get("KAKAO_REST_API_KEY")
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")
    dashboard_url = os.environ.get("DASHBOARD_URL") or "http://localhost:3000"

    if not rest_api_key or not refresh_token:
        print("카카오 API 키가 설정되지 않아 알림을 건너뜁니다.")
        return

    token_res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
    ).json()

    access_token = token_res.get("access_token")
    if not access_token:
        print("카카오 토큰 갱신 실패:", token_res)
        return

    s = picks["sets"]
    latest_str = ",".join(map(str, picks["latest_nums"]))
    msg = (
        f"🎱 {picks['target_drwNo']}회 로또 추천\n"
        f"(직전 {picks['base_drwNo']}회: {latest_str}+{picks['latest_bonus']})\n"
        f"[최다출현]\n"
        f"1) {','.join(map(str, s['set_1_hot']))}\n"
        f"2) {','.join(map(str, s['set_2_hot']))}\n"
        f"3) {','.join(map(str, s['set_3_hot']))}\n"
        f"[20주미출]\n"
        f"4) {','.join(map(str, s['set_4_cold']))}\n"
        f"5) {','.join(map(str, s['set_5_cold']))}"
    )

    headers = {"Authorization": f"Bearer {access_token}"}
    template = {
        "object_type": "text",
        "text": msg,
        "link": {"web_url": dashboard_url, "mobile_web_url": dashboard_url},
        "button_title": "대시보드 보기",
    }
    send_res = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers=headers,
        data={"template_object": json.dumps(template)},
    )
    print("카카오톡 발송 결과:", send_res.status_code, send_res.text)


if __name__ == "__main__":
    df_history = update_history()
    if not df_history.empty:
        weekly_picks = generate_weekly_picks(df_history)
        send_kakao_memo(weekly_picks)
