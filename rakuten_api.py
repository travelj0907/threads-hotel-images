"""
楽天トラベル施設情報APIから宿情報を取得するモジュール
"""

import os
import sys
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID")
RAKUTEN_ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY")
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID")

HOTEL_DETAIL_URL = "https://openapi.rakuten.co.jp/engine/api/Travel/HotelDetailSearch/20170426"


def get_hotel_info(hotel_no: str) -> dict | None:
    """
    楽天トラベルAPIからホテルの詳細情報を取得する。
    hotel_no: 楽天トラベルのホテル番号（URLの /HOTEL/xxxxx/ の部分）
    """
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "affiliateId": RAKUTEN_AFFILIATE_ID,
        "hotelNo": hotel_no,
        "formatVersion": 2,
        "hotelThumbnailSize": 3,
    }
    headers = {
        "X-RakutenAW-AccessKey": RAKUTEN_ACCESS_KEY,
    }

    try:
        response = requests.get(HOTEL_DETAIL_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"楽天API取得エラー: {e}")
        return None

    try:
        hotel = data["hotels"][0]["hotel"]
        basic = next(h["hotelBasicInfo"] for h in hotel if "hotelBasicInfo" in h)

        return {
            "name": basic.get("hotelName", ""),
            "address": basic.get("address1", "") + basic.get("address2", ""),
            "access": basic.get("access", ""),
            "min_charge": basic.get("hotelMinCharge"),
            "review_average": basic.get("reviewAverage"),
            "image_url": basic.get("hotelImageUrl", ""),
            "thumbnail_url": basic.get("hotelThumbnailUrl", ""),
            "affiliate_url": basic.get("hotelInformationUrl", ""),
            "special": basic.get("hotelSpecial", ""),
        }
    except (KeyError, IndexError, StopIteration) as e:
        print(f"データ解析エラー: {e}")
        return None


if __name__ == "__main__":
    info = get_hotel_info("28921")
    if info:
        print(f"ホテル名: {info['name']}")
        print(f"アクセス: {info['access']}")
        print(f"最低料金: {info['min_charge']}")
        print(f"画像URL: {info['image_url']}")
    else:
        print("取得失敗")
