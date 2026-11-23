import os
import re
import glob
import json
import random
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from collections import Counter

CSV_FILE = "lotto_history.csv"
PICKS_FILE = "weekly_picks.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def calc_draw_date(drw_no):
    first_draw = datetime(2002, 12, 7)
    return (first_draw + timedelta(days=(int(drw_no) - 1) * 7)).strftime("%Y-%m-%d")


def init_from_excel():
    excel_files = glob.glob("*.xlsx") + glob.glob("*.xls")
    if not excel_files:
        print("엑셀 파일을 찾을 수 없습니다.")
        return pd.DataFrame()

    target_file = excel_files[0]
    print(f"엑셀 파일 읽는 중: {target_file}")

    try:
        raw_df = pd.read_excel(target_file, header=None)
    except Exception:
        raw_df = pd.read_html(target_file)[0]

    rows = []
    for _, row in raw_df.iterrows():
        if len(row) < 9:
            continue
        try:
            drw_no = int(float(str(row.iloc[1]).strip()))
            nums = [int(float(str(row.iloc[i]).strip())) for i in range(2, 9)]
            if 1 <= drw_no <= 5000 and all(1 <= n <= 45 for n in nums):
                rows.append({
                    "drwNo": drw_no,
                    "drwNoDate": calc_draw_date(drw_no),
                    "n1": nums[0], "n2": nums[1], "n3": nums[2],
                    "n4": nums[3], "n5": nums[4], "n6": nums[5],
                    "bonus": nums[6],
                })
        except Exception:
            continue

    df = pd.DataFrame(rows).drop_duplicates(subset=["drwNo"]).sort_values("drwNo").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"엑셀에서 총 {len(df)}개 회차 초기 적재 완료 (최신: {df['drwNo'].max()}회)")
    return df


def fetch_latest_from_naver():
    url = "https://search.naver.com/search.naver?where=nexearch&query=로또+당첨번호"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        match = re.search(r"(\d+)회\s*\((\d{4}\.\d{2}\.\d{2})\.?\)", text)
        if not match:
            return None

        drw_no = int(match.group(1))
        drw_date = match.group(2).replace(".", "-")
        win_balls = [int(b.get_text(strip=True)) for b in soup.select(".winning_number .ball")]
        bonus_balls = [int(b.get_text(strip=True)) for b in soup.select(".bonus_number .ball")]

        if len(win_balls) == 6 and len(bonus_balls) == 1:
            return {
                "drwNo": drw_no, "drwNoDate": drw_date,
                "n1": win_balls[0], "n2": win_balls[1], "n3": win_balls[2],
                "n4": win_balls[3], "n5": win_balls[4], "n6": win_balls[5],
                "bonus": bonus_balls[0],
            }
    except Exception as e:
        print(f"네이버 조회 오류: {e}")
    return None


def update_history():
    df = pd.read_csv(CSV_FILE) if os.path.exists(CSV_FILE) else init_from_excel()
    if df.empty:
        return df

    latest_saved = int(df["drwNo"].max())
    naver_row = fetch_latest_from_naver()

    if naver_row and naver_row["drwNo"] > latest_saved:
        df = pd.concat([df, pd.DataFrame([naver_row])], ignore_index=True)
        df = df.drop_duplicates(subset=["drwNo"]).sort_values("drwNo").reset_index(drop=True)
        df.to_csv(CSV_FILE, index=False)
        print(f"네이버에서 최신 {naver_row['drwNo']}회차 업데이트 완료!")
    else:
        print(f"현재 최신 회차 유지 중 ({latest_saved}회)")
    return df


def generate_weekly_picks(df):
    num_cols = ["n1", "n2", "n3", "n4", "n5", "n6"]

    # 1~3세트: 역대 최다 출현 상위 15개 중 가중치 추출
    total_counts = Counter(df[num_cols].values.flatten())
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
    recent_counts = Counter(df.tail(20)[num_cols].values.flatten())
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
