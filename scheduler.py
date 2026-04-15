"""
自動投稿スケジューラー
1日4回（8:00 / 12:00 / 18:00 / 20:00）に自動でThreadsへ投稿する。
起動したままにしておくと毎日自動で投稿される。
"""

import sys
import schedule
import time
import subprocess
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).parent
MAIN_PY = SCRIPT_DIR / "main.py"

POST_TIMES = ["08:00", "12:00", "18:00", "20:00"]


def run_post():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] 自動投稿を開始します...")
    try:
        result = subprocess.run(
            [sys.executable, str(MAIN_PY), "--auto"],
            cwd=str(SCRIPT_DIR),
            capture_output=False,
            text=True,
            encoding="utf-8",
        )
        if result.returncode == 0:
            print(f"[{now}] 投稿完了")
        else:
            print(f"[{now}] 投稿失敗（終了コード: {result.returncode}）")
    except Exception as e:
        print(f"[{now}] エラー: {e}")


def main():
    print("=== 自動投稿スケジューラー起動 ===")
    print(f"投稿時刻: {' / '.join(POST_TIMES)}")
    print("停止するには Ctrl+C を押してください\n")

    for t in POST_TIMES:
        schedule.every().day.at(t).do(run_post)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
