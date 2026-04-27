"""
ホテル情報から投稿文（本文 + ツリー返信）を生成するモジュール
"""

import sys
import os
import random
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "")


def to_affiliate_url(hotel_url: str) -> str:
    """楽天トラベルのURLをアフィリエイトリンクに変換する"""
    if not RAKUTEN_AFFILIATE_ID or not hotel_url:
        return hotel_url
    encoded = quote(hotel_url, safe="")
    return f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_AFFILIATE_ID}/?pc={encoded}"


# 本投稿本文（10パターンをランダム）— 冒頭・フック行なし
MAIN_TEMPLATES = [
    """{feature1}、{feature2}。
{feature3}。

{access_line}マジでここ知らないと損。

宿の名前は、""",
    """{feature1}。
{feature2}、{feature3}まで揃ってる。

{access_line}この宿の名前は、""",
    """{feature1}。
{feature2}、{feature3}。

{access_line}友達に教えたくない宿No.1。

宿の名前は、""",
    """{feature1}に{feature2}、
{feature3}まである。

{access_line}泊まったら分かる。

この宿の名前は、""",
    """{feature1}、{feature2}。
{feature3}まで体験できる。

{access_line}宿の名前は、""",
    """ここ、{feature1}。
{feature2}と{feature3}、両方いける。

{access_line}コスパも納得。

この宿の名前は、""",
    """{feature1}が刺さる人向け。
{feature2}、{feature3}も捨てがたい。

{access_line}とにかく満足度高い。

宿の名前は、""",
    """{feature1}。
{feature2}。
{feature3}。

{access_line}リピート確定レベル。

宿の名前は、""",
    """{feature1}・{feature2}・{feature3}。

{access_line}旅の疲れ引いていくやつ。

この宿の名前は、""",
    """{feature1}、{feature2}、{feature3}。
全部まとめて楽しめる。

{access_line}写真映えも自然にいける。

宿の名前は、""",
]

REPLY_TEMPLATES = [
    """『{name}』です！

気になった人はここから見てみて↓
{affiliate_url}

※PR""",

    """答え合わせ『{name}』

評価{review}点。泊まった人みんな満足してるやつ。
詳しくはこっちから↓
{affiliate_url}

※PR""",

    """『{name}』/{area}

空き状況とかプランはここで見てね
{affiliate_url}

※PR""",
]

# アフィリエイトリンクなし版（A/Bテスト用）
REPLY_TEMPLATES_NO_LINK = [
    """『{name}』です！

気になった人は「{name}」で検索してみて。""",

    """答え合わせ『{name}』

評価{review}点。泊まった人みんな満足してるやつ。
「{name}」で調べてみて。""",

    """『{name}』/{area}

気になる人は「{name}」で調べてみてね。""",
]


def _format_price(price: str) -> str:
    """
    価格帯が2万円以下のときだけ「〇万円以下」形式で返す。
    「3万円台〜」以上や「要確認」は空文字を返す。
    """
    if not price:
        return ""
    import re
    m = re.search(r"(\d+)", price)
    if not m:
        return ""
    man = int(m.group(1))
    if man <= 2:
        return f"{man}万円以下"
    return ""


def _trim_access(access: str, max_len: int = 25) -> str:
    """
    アクセス文を自然な区切りで短く整形する。
    複数の交通手段が並んでいる場合は最初の1つだけ使う。
    """
    if not access:
        return ""
    # 複数の区切りパターンで最初の部分だけ取る
    for sep in ["・", "　　", "／", "/", "、"]:
        if sep in access:
            access = access.split(sep)[0].strip()
            break
    # それでも長い場合は句点か読点で切る
    if len(access) > max_len:
        for ch in ["。", "、"]:
            idx = access.rfind(ch, 0, max_len)
            if idx > 0:
                return access[:idx]
        access = access[:max_len]
    return access.rstrip("。、・")


def _trim_at_boundary(text: str, max_len: int) -> str:
    """
    文の途中で切らずに max_len 以内に収める。
    改行・句点・読点を優先して切断位置を探す。
    """
    if len(text) <= max_len:
        return text
    for ch in ["\n", "。", "、"]:
        idx = text.rfind(ch, 0, max_len)
        if idx > max_len // 2:
            return text[:idx + 1].rstrip()
    return text[:max_len] + "…"


FALLBACK_FEATURES = [
    "スタッフの対応が神レベル",
    "リピーター続出の人気宿",
    "料理が想像の上を行く",
    "眺めが最高すぎる",
    "温泉の質がとにかくいい",
    "コスパが他と比べ物にならない",
    "部屋の居心地が抜群",
    "何度でもリピートしたくなる",
]


def generate_post(
    hotel_info: dict,
    sell_point: str,
    area: str,
    price: str = "",
    include_affiliate: bool = True,
) -> dict:
    """
    ホテル情報から投稿本文とツリー返信文を生成する。
    返り値: {"main_text": str, "reply_text": str}
    本投稿は特徴・アクセス等のみ（先頭例文・フック行は使わない）。
    """
    features = [f.strip() for f in sell_point.split("・") if f.strip()]

    fallbacks = random.sample(FALLBACK_FEATURES, len(FALLBACK_FEATURES))
    fi = 0
    while len(features) < 3:
        features.append(fallbacks[fi % len(fallbacks)])
        fi += 1

    template = random.choice(MAIN_TEMPLATES)

    # アクセス系キーワードがsell_pointに含まれていたらaccess_lineは重複するので省略
    ACCESS_KEYWORDS = ["駅", "徒歩", "空港", "バス", "送迎", "圏内"]
    access_in_features = any(
        kw in f for f in features for kw in ACCESS_KEYWORDS
    )
    access_raw = hotel_info.get("access", "").strip()
    access = "" if access_in_features else _trim_access(access_raw)

    # 価格帯：2万円以下のときだけ「〜以下」形式で表示
    price_clean = _format_price(price)

    # access_line：価格を文章化してアクセスと組み合わせる
    price_sentence = f"{price_clean}で泊まれる。" if price_clean else ""
    access_sentence = f"{access}。" if access else ""
    if price_sentence and access_sentence:
        access_line = f"{price_sentence}{access_sentence}\n"
    elif price_sentence:
        access_line = f"{price_sentence}\n"
    elif access_sentence:
        access_line = f"{access_sentence}\n"
    else:
        access_line = ""

    main_text = template.format(
        feature1=features[0],
        feature2=features[1],
        feature3=features[2],
        access_line=access_line,
    )

    # 200文字に収まるよう調整（文の途中で切らない）
    if len(main_text) > 210:
        main_text = _trim_at_boundary(main_text, 207)

    review = hotel_info.get("review_average", "")

    if include_affiliate:
        raw_url = hotel_info.get("affiliate_url", "")
        affiliate_url = to_affiliate_url(raw_url)
        reply_template = random.choice(REPLY_TEMPLATES)
        reply_text = reply_template.format(
            name=hotel_info.get("name", ""),
            area=area,
            review=review,
            affiliate_url=affiliate_url,
        )
    else:
        reply_template = random.choice(REPLY_TEMPLATES_NO_LINK)
        reply_text = reply_template.format(
            name=hotel_info.get("name", ""),
            area=area,
            review=review,
        )

    return {
        "main_text": main_text.strip(),
        "reply_text": reply_text.strip(),
    }


if __name__ == "__main__":
    sample_info = {
        "name": "大磯プリンスホテル",
        "access": "JR大磯駅から徒歩圏、新宿から電車1時間10分",
        "review_average": 4.55,
        "affiliate_url": "https://travel.rakuten.co.jp/HOTEL/28921/",
    }

    result = generate_post(
        hotel_info=sample_info,
        sell_point="インフィニティプール・パノラマサウナ・大磯温泉露天風呂・新宿から1時間",
        area="神奈川",
        price="2万円台",
    )

    print("=== 本投稿 ===")
    print(result["main_text"])
    print(f"\n文字数: {len(result['main_text'])}")
    print("\n=== ツリー返信 ===")
    print(result["reply_text"])
