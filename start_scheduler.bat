@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
echo スケジューラーを起動します...
echo 投稿時刻: 8:00 / 12:00 / 18:00 / 20:00
echo 停止するにはこのウィンドウを閉じてください
echo.
python scheduler.py
pause
