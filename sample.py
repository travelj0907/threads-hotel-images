import sys
sys.stdout.reconfigure(encoding="utf-8")
from generate_post import generate_post

hotel_info = {
    "name": "有馬温泉　有馬グランドホテル",
    "access": "神戸電鉄有馬温泉駅より徒歩10分・送迎バスあり",
    "review_average": "4.77",
    "affiliate_url": "https://travel.rakuten.co.jp/HOTEL/25128/",
}

for i in range(4):
    result = generate_post(
        hotel_info=hotel_info,
        sell_point="金泉銀泉両方楽しめる・露天風呂・展望大浴場・貸切風呂あり",
        area="有馬温泉",
        price="3万円台",
    )
    chars = len(result["main_text"])
    print(f"--- パターン{i+1} ---")
    print("【本投稿】")
    print(result["main_text"])
    print(f"（{chars}文字）")
    print()
    print("【ツリー返信】")
    print(result["reply_text"])
    print()
