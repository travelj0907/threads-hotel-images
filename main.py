"""
メイン実行スクリプト
hotels.csv を読んで、未投稿のホテルを1件投稿する。
全ホテルが投稿済みになったら投稿回数をリセットしてローテーション。
"""

import copy
import csv
import sys
import random
import argparse
from pathlib import Path

ROTATION_INTERVAL = 20  # 何投稿後に同じホテルを再投稿するか

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


def latest_post_serial(hotels: list[dict]) -> int:
    """
    投稿済み列の「通し番号」の最大値。
    TRUE は 1 扱い。全セルの数字を足すのではなく max を取る（足し算バグ防止）。
    """
    m = 0
    for hotel in hotels:
        val = str(hotel.get("投稿済み", "0"))
        if val.upper() == "TRUE":
            m = max(m, 1)
        elif val.isdigit():
            m = max(m, int(val))
    return m


def revive_hotels_for_rotation(hotels: list[dict]) -> bool:
    """
    未投稿（FALSE）が1件もないとき、通算番号が古いホテルを FALSE に戻す。
    hotels をその場で更新する。いずれかを復活させたら True。
    """
    pending = [h for h in hotels if str(h.get("投稿済み", "FALSE")).upper() == "FALSE"]
    if pending:
        return False

    latest_serial = latest_post_serial(hotels)
    revived = False
    for hotel in hotels:
        val = str(hotel.get("投稿済み", "0"))
        posted_at = 0
        if val.upper() == "TRUE":
            posted_at = 1
        elif val.isdigit():
            posted_at = int(val)

        if posted_at > 0 and (latest_serial - posted_at) >= ROTATION_INTERVAL:
            hotel["投稿済み"] = "FALSE"
            revived = True
    return revived


def find_next_hotel(hotels: list[dict]) -> dict | None:
    """
    投稿済み = FALSE のホテルを上から順に選ぶ。
    全て投稿済みの場合、投稿回数が ROTATION_INTERVAL 以上経過したホテルをFALSEに戻してから選ぶ。
    """
    pending = [h for h in hotels if str(h.get("投稿済み", "FALSE")).upper() == "FALSE"]
    if pending:
        return random.choice(pending)

    if revive_hotels_for_rotation(hotels):
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


def build_posting_candidates(hotels: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """(未投稿FALSE一覧, そのうち画像あり, 画像なしのFALSE) を返す"""
    pending = [h for h in hotels if str(h.get("投稿済み", "FALSE")).upper() == "FALSE"]
    with_img = [h for h in pending if has_images(h["ホテル名"])]
    missing = [h for h in pending if not has_images(h["ホテル名"])]
    return pending, with_img, missing


def run_check() -> int:
    """投稿可否の診断（投稿はしない）。main() と同様にローテーション復活後の可否も見る。"""
    hotels = load_hotels()
    pending, with_img, missing = build_posting_candidates(hotels)
    print("=== 投稿診断（hotels.csv × images/）===\n")
    for h in hotels:
        name = h["ホテル名"]
        st = h.get("投稿済み", "")
        img = has_images(name)
        if str(st).upper() == "FALSE":
            ok = "投稿候補" if img else "画像なし（要フォルダ）"
        else:
            ok = "—（投稿済/通算管理）"
        print(f"  [{ok}] {name}  投稿済み={st}  画像={'あり' if img else 'なし'}")
    print()
    if with_img:
        print(f"→ いま投稿できる件数: {len(with_img)}（FALSE かつ images/ に jpg/png あり）")
        return 0
    if pending and missing:
        print("→ 未投稿（FALSE）はありますが、どれも画像フォルダが空か未作成です。")
        print("  ローカルで画像を入れたら git add / commit / push し、GitHub 上にも images/ を載せてください。")
        print("→ この状態で --auto を実行しても投稿されません。")
        return 1
    if not pending:
        preview = copy.deepcopy(hotels)
        if revive_hotels_for_rotation(preview):
            p2, w2, m2 = build_posting_candidates(preview)
            if w2:
                print(
                    f"→ CSV 上は FALSE がありませんが、{ROTATION_INTERVAL} 投稿以上経過した行は "
                    f"--auto 実行時に FALSE に戻ります。"
                )
                print(f"→ 復活後に投稿できる件数: {len(w2)}（FALSE かつ images/ に jpg/png あり）")
                return 0
            if p2 and m2:
                print("→ ローテーションで FALSE に戻る行はありますが、画像フォルダが無い行のみです。")
                print("→ この状態で --auto を実行しても投稿されません。")
                return 1
        print("→ 未投稿の FALSE がありません。いまの通算番号ではローテーション条件（満了）を満たす行もありません。")
        print("→ この状態で --auto を実行しても投稿されません。")
        return 1


def main(auto_mode: bool = False):
    hotels = load_hotels()

    # 画像が揃っているホテルだけを対象にして選ぶ
    pending, pending_with_images, pending_missing_images = build_posting_candidates(hotels)

    if not pending_with_images:
        if pending_missing_images:
            print(f"未投稿のホテルはありますが、画像が準備できていません。")
            print("以下のホテルフォルダに画像を入れてください:")
            for h in pending_missing_images[:10]:
                print(f"  images/{h['ホテル名']}/")
            if auto_mode:
                print(
                    "\n[エラー] 自動モード: FALSE かつ画像ありのホテルがありません。"
                    " GitHub Actions なら main に images/ が push されているか確認してください。"
                )
                sys.exit(1)
        else:
            # ローテーション処理
            find_next_hotel(hotels)
            save_hotels(hotels)
            pending_with_images = [
                h
                for h in hotels
                if str(h.get("投稿済み", "FALSE")).upper() == "FALSE" and has_images(h["ホテル名"])
            ]
            if not pending_with_images:
                print("投稿できるホテルがありません。画像を準備してください。")
                sys.exit(1 if auto_mode else 0)

    if not pending_with_images:
        sys.exit(1 if auto_mode else 0)

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
    next_serial = latest_post_serial(hotels) + 1
    include_affiliate = next_serial % 2 == 0
    print(f"アフィリエイトリンク: {'あり' if include_affiliate else 'なし'} (この投稿は通算{next_serial}回目)")

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
        # 投稿済みフラグを「直近までの最大通し番号 + 1」で記録（全行の合計ではない）
        new_serial = latest_post_serial(hotels) + 1
        for hotel in hotels:
            if hotel["ホテル名"] == hotel_name:
                hotel["投稿済み"] = str(new_serial)
                break
        save_hotels(hotels)
        print(f"\n投稿済みフラグを更新しました: {hotel_name}（通算{new_serial}投稿目）")
    else:
        print("\n投稿に失敗しました。ログを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="確認プロンプトをスキップして自動投稿")
    parser.add_argument(
        "--check",
        action="store_true",
        help="投稿せず、CSVとimages/の突き合わせだけ表示（終了コード1＝FALSEかつ画像ありが無く、ローテーション後も同様）",
    )
    args = parser.parse_args()
    if args.check:
        sys.exit(run_check())
    main(auto_mode=args.auto)
