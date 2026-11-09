@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate
start "" http://localhost:8080
python -m collector serve
