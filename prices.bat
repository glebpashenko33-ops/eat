@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate
python -m collector collect
where git >nul 2>nul && (
  git add web/data/prices.json
  git commit -q -m "Обновить цены" && git pull -q --rebase && git push -q
)
if /i not "%1"=="auto" pause
