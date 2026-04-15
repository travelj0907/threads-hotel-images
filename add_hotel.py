"""
hotel_urls.txt に記載されたURLのホテル情報を楽天トラベルから取得し、
hotels.csv に追記 + images/ホテル名/ フォルダを自動作成するスクリプト
取得できなかった項目は自動で補完します
"""

import sys
import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

HOTELS_CSV = Path(__file__).parent / "hotels.csv"
IMAGES_DIR = Path(__file__).parent / "images"
URLS_FILE = Path(__file__).parent / "hotel_urls.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Referer": "https://www.google.co.jp/",
}

PREF_KEYWORDS = [
    "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島",
    "茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川",
    "新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜",
    "静岡", "愛知", "三重", "滋賀", "京都", "大阪", "兵庫",
    "奈良", "和歌山", "鳥取", "島根", "岡山", "広島", "山口",
    "徳島", "香川", "愛媛", "高知", "福岡", "佐賀", "長崎",
    "熊本", "大分", "宮崎", "鹿児島", "沖縄",
]

ONSEN_KEYWORDS = ["温泉", "湯", "源泉", "露天", "大浴", "湯治"]
RESORT_KEYWORDS = ["リゾート", "海", "山", "高原", "島", "ビーチ", "プール"]


def load_existing_hotels() -> list[dict]:
    if not HOTELS_CSV.exists():
        return []
    with open(HOTELS_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_hotels(hotels: list[dict]) -> None:
    fieldnames = ["ホテル名", "エリア", "価格帯", "アフィリエイトURL", "売り文句", "アクセス", "評価", "投稿済み"]
    with open(HOTELS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(hotels)


def extract_hotel_no(url: str) -> str | None:
    match = re.search(r"/HOTEL/(\d+)", url)
    return match.group(1) if match else None


def guess_area_from_text(text: str) -> str:
    for pref in PREF_KEYWORDS:
        if pref in text:
            return pref
    return ""


def guess_sell_point(name: str, page_text: str) -> str:
    points = []

    if any(k in page_text for k in ["金泉", "銀泉"]):
        points.append("金泉銀泉両方楽しめる")
    if "露天風呂" in page_text:
        points.append("露天風呂")
    if "展望" in page_text and "風呂" in page_text:
        points.append("展望大浴場")
    if "貸切" in page_text and "風呂" in page_text:
        points.append("貸切風呂あり")
    if any(k in page_text for k in ["源泉かけ流し", "源泉掛け流し"]):
        points.append("源泉かけ流し")
    if "部屋食" in page_text or "お部屋食" in page_text:
        points.append("お部屋食")
    if "送迎" in page_text:
        points.append("送迎バスあり")
    if "プール" in page_text:
        points.append("プールあり")
    if "絶景" in page_text or "眺望" in page_text:
        points.append("絶景の眺め")
    if "神戸牛" in page_text or "松阪牛" in page_text or "和牛" in page_text:
        points.append("和牛会席")

    # 最低1つはつける
    if not points:
        if any(k in name for k in ONSEN_KEYWORDS) or any(k in page_text for k in ONSEN_KEYWORDS):
            points.append("温泉")
        if any(k in name for k in RESORT_KEYWORDS):
            points.append("絶好のロケーション")
        if not points:
            points.append("高評価の宿")

    return "・".join(points[:4])


def guess_price(page_text: str) -> str:
    patterns = [
        (r"(\d+,\d{3})円[〜～]", lambda m: format_price(int(m.group(1).replace(",", "")))),
        (r"¥\s?(\d+,\d{3})", lambda m: format_price(int(m.group(1).replace(",", "")))),
    ]
    for pattern, formatter in patterns:
        match = re.search(pattern, page_text)
        if match:
            try:
                return formatter(match)
            except Exception:
                pass
    return "要確認"


def format_price(yen: int) -> str:
    if yen < 10000:
        return f"{yen // 1000}千円台〜"
    else:
        return f"{yen // 10000}万円台〜"


def scrape_hotel_info(url: str) -> dict | None:
    base_url = re.sub(r"(/HOTEL/\d+/).*", r"\1", url)

    session = requests.Session()
    session.headers.update(HEADERS)

    # まずトップページを訪問してCookieを取得
    try:
        session.get("https://travel.rakuten.co.jp/", timeout=10)
        time.sleep(1)
    except Exception:
        pass

    try:
        r = session.get(base_url, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"  ページ取得エラー: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    page_text = soup.get_text()

    # ホテル名
    name = ""
    for selector in ["h2.hotel-name", "h1", "h2"]:
        tag = soup.select_one(selector)
        if tag:
            name = tag.get_text(strip=True)
            name = re.sub(r"\s*(宿泊予約|【楽天トラベル】|日帰り.*).*", "", name).strip()
            if name:
                break

    # 評価
    rating = ""
    rating_match = re.search(r"\b([4-5]\.\d{2})\b", page_text)
    if rating_match:
        rating = rating_match.group(1)

    # アクセス（駅・分数が含まれる行を優先）
    access = ""
    access_candidates = re.findall(r"([^\n。]{5,60}(?:駅|バス停)[^\n。]{0,30}(?:徒歩|分|送迎)[^\n。]{0,20})", page_text)
    if access_candidates:
        access = access_candidates[0].strip()[:60]
    if not access:
        access_match = re.search(r"(?:交通アクセス|アクセス情報)[^\n]*\n([^\n]{10,60})", page_text)
        if access_match:
            access = access_match.group(1).strip()[:60]

    # エリア（温泉地名を優先）
    onsen_area_match = re.search(r"([^\s「」【】]{2,8}温泉)", page_text)
    if onsen_area_match:
        area = onsen_area_match.group(1)
    else:
        area = guess_area_from_text(page_text)

    # 売り文句
    sell_point = guess_sell_point(name, page_text)

    # 価格帯
    price = guess_price(page_text)

    return {
        "name": name,
        "rating": rating,
        "access": access,
        "area": area,
        "sell_point": sell_point,
        "price": price,
        "url": base_url,
    }


def load_urls() -> list[str]:
    if not URLS_FILE.exists():
        print(f"{URLS_FILE} が見つかりません。")
        return []

    urls = []
    with open(URLS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "travel.rakuten.co.jp/HOTEL/" in line:
                    urls.append(line)
                else:
                    print(f"  スキップ（楽天トラベルのURLではありません）: {line}")
    return urls


def main():
    urls = load_urls()
    if not urls:
        print("hotel_urls.txt にURLが記載されていません。")
        return

    existing_hotels = load_existing_hotels()
    existing_names = {h["ホテル名"] for h in existing_hotels}
    existing_urls = {re.sub(r"(/HOTEL/\d+/).*", r"\1", h["アフィリエイトURL"]) for h in existing_hotels}

    added = 0
    skipped = 0

    for url in urls:
        print(f"\n処理中: {url}")
        base_url = re.sub(r"(/HOTEL/\d+/).*", r"\1", url)

        if base_url in existing_urls:
            print(f"  スキップ（既にCSVに存在します）")
            skipped += 1
            continue

        info = scrape_hotel_info(url)
        if not info or not info["name"]:
            print(f"  情報取得失敗。スキップします。")
            skipped += 1
            continue

        if info["name"] in existing_names:
            print(f"  スキップ（同名ホテルが既に存在します: {info['name']}）")
            skipped += 1
            continue

        new_hotel = {
            "ホテル名": info["name"],
            "エリア": info["area"] or "日本",
            "価格帯": info["price"],
            "アフィリエイトURL": base_url,
            "売り文句": info["sell_point"],
            "アクセス": info["access"],
            "評価": info["rating"],
            "投稿済み": "FALSE",
        }

        existing_hotels.append(new_hotel)
        existing_names.add(info["name"])

        # 画像フォルダ作成
        img_folder = IMAGES_DIR / info["name"]
        img_folder.mkdir(parents=True, exist_ok=True)

        print(f"  ホテル名: {info['name']}")
        print(f"  エリア:   {new_hotel['エリア']}")
        print(f"  価格帯:   {new_hotel['価格帯']}")
        print(f"  評価:     {new_hotel['評価']}")
        print(f"  売り文句: {new_hotel['売り文句']}")
        print(f"  アクセス: {new_hotel['アクセス']}")
        print(f"  画像フォルダ: images/{info['name']}/")
        print(f"  → 追加完了")

        added += 1
        time.sleep(1)

    if added > 0:
        save_hotels(existing_hotels)
        print(f"\n{added}件をhotels.csvに追加しました。")
        print("\n次のステップ:")
        print("1. images/ホテル名/ フォルダに画像を4〜5枚入れる")
        print("2. python main.py で投稿")
    else:
        print(f"\n追加はありませんでした。")

    if skipped > 0:
        print(f"{skipped}件をスキップしました。")


if __name__ == "__main__":
    main()
