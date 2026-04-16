"""
メイン実行スクリプト
hotels.csv を読んで、未投稿のホテルを1件投稿する。
全ホテルが投稿済みになったら投稿回数をリセットしてローテーション。
"""

import csv
import sys
import random
import argparse
from pathlib import Path

ROTATION_INTERVAL = 30  # 何投稿後に同じホテルを再投稿するか

sys.stdout.reconfigure(encoding="utf-8")

from generate_post import generate_post
from threads_post import post_hotel

HOTELS_CSV = Path(__file__).parent / "hotels.csv"
IMAGES_DIR = Path(__file__).parent / "images"


def load_hotels() -> list[dict]:
    with open(HOTELS_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_hotels(hotels: list[dict]) -> None:
    fieldnames = hotels[0].keys()
    with open(HOTELS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(hotels)


def count_total_posted(hotels: list[dict]) -> int:
    """投稿済み回数の合計を返す（投稿済みフラグの数字の合計）"""
    total = 0
    for hotel in hotels:
        val = hotel.get("投稿済み", "0")
        if val.upper() == "TRUE":
            total += 1
        elif val.isdigit():
            total += int(val)
    return total


def find_next_hotel(hotels: list[dict]) -> dict | None:
    """
    投稿済み = FALSE のホテルを上から順に選ぶ。
    全て投稿済みの場合、投稿回数が ROTATION_INTERVAL 以上経過したホテルをFALSEに戻してから選ぶ。
    """
    pending = [h for h in hotels if str(h.get("投稿済み", "FALSE")).upper() == "FALSE"]
    if pending:
        return random.choice(pending)

    # 全て投稿済みの場合 → 投稿回数が最も多いものからリセット
    total_posted = count_total_posted(hotels)
    revived = False
    for hotel in hotels:
        val = str(hotel.get("投稿済み", "0"))
        posted_at = 0
        if val.upper() == "TRUE":
            posted_at = 1
        elif val.isdigit():
            posted_at = int(val)

        if posted_at > 0 and (total_posted - posted_at) >= ROTATION_INTERVAL:
            hotel["投稿済み"] = "FALSE"
            revived = True

    if revived:
        pending = [h for h in hotels if str(h.get("投稿済み", "FALSE")).upper() == "FALSE"]
        if pending:
            print(f"（{ROTATION_INTERVAL}投稿経過したホテルを復活させました）")
            return random.choice(pending)

    return None


def has_images(hotel_name: str) -> bool:
    """画像フォルダに画像が1枚以上あるか確認する"""
    folder = IMAGES_DIR / hotel_name
    if not folder.exists():
        return False
    supported = [".jpg", ".jpeg", ".png"]
    return any(f.suffix.lower() in supported for f in folder.iterdir())


def main(auto_mode: bool = False):
    hotels = load_hotels()

    # 画像が揃っているホテルだけを対象にして選ぶ
    pending = [h for h in hotels if str(h.get("投稿済み", "FALSE")).upper() == "FALSE"]
    pending_with_images = [h for h in pending if has_images(h["ホテル名"])]

    if not pending_with_images:
        if pending:
            print(f"未投稿のホテルはありますが、画像が準備できていません。")
            print("以下のホテルフォルダに画像を入れてください:")
            for h in pending[:5]:
                print(f"  images/{h['ホテル名']}/")
        else:
            # ローテーション処理
            find_next_hotel(hotels)
            save_hotels(hotels)
            pending_with_images = [h for h in hotels if str(h.get("投稿済み", "FALSE")).upper() == "FALSE" and has_images(h["ホテル名"])]
            if not pending_with_images:
                print("投稿できるホテルがありません。画像を準備してください。")
                sys.exit(0)

    if not pending_with_images:
        sys.exit(0)

    target = random.choice(pending_with_images)
    hotel_name = target["ホテル名"]
    area = target["エリア"]
    price = target["価格帯"]
    sell_point = target["売り文句"]
    affiliate_url = target["アフィリエイトURL"]
    access = target.get("アクセス", "")
    review = target.get("評価", "")

    print(f"対象ホテル: {hotel_name}")
    image_folder = IMAGES_DIR / hotel_name

    # CSVの情報をホテル情報として使用
    hotel_info = {
        "name": hotel_name,
        "access": access,
        "review_average": review,
        "affiliate_url": affiliate_url,
    }

    # 通算投稿数が偶数のときだけアフィリエイトリンクを入れる（A/Bテスト）
    total_so_far = count_total_posted(hotels)
    include_affiliate = (total_so_far % 2 == 0)
    print(f"アフィリエイトリンク: {'あり' if include_affiliate else 'なし'} (通算{total_so_far}投稿目)")

    # 投稿文生成
    print("投稿文を生成中...")
    post_texts = generate_post(
        hotel_info=hotel_info,
        sell_point=sell_point,
        area=area,
        price=price,
        include_affiliate=include_affiliate,
    )

    print("\n=== 生成された投稿文 ===")
    print("【本投稿】")
    print(post_texts["main_text"])
    print(f"（{len(post_texts['main_text'])}文字）")
    print("\n【ツリー返信】")
    print(post_texts["reply_text"])

    # 確認プロンプト（--autoの場合はスキップ）
    if not auto_mode:
        confirm = input("\nこの内容でThreadsに投稿しますか？ [y/N]: ").strip().lower()
        if confirm != "y":
            print("投稿をキャンセルしました。")
            sys.exit(0)
    else:
        print("\n[自動モード] 確認をスキップして投稿します。")

    # Threadsへ投稿
    success = post_hotel(
        main_text=post_texts["main_text"],
        reply_text=post_texts["reply_text"],
        image_folder=image_folder,
    )

    if success:
        # 投稿済みフラグを「何投稿目か」の通算番号で記録
        total_posted = count_total_posted(hotels) + 1
        for hotel in hotels:
            if hotel["ホテル名"] == hotel_name:
                hotel["投稿済み"] = str(total_posted)
                break
        save_hotels(hotels)
        print(f"\n投稿済みフラグを更新しました: {hotel_name}（通算{total_posted}投稿目）")
    else:
        print("\n投稿に失敗しました。ログを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="確認プロンプトをスキップして自動投稿")
    args = parser.parse_args()
    main(auto_mode=args.auto)
