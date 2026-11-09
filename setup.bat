@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || (echo Установите Python 3.11+ с python.org, при установке отметьте "Add python.exe to PATH". & pause & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -q --upgrade pip
python -m pip install -q -r collector\requirements.txt
echo.
echo Сейчас откроется браузер с сайтами сетей. Выберите на каждом свой город и магазин, затем закройте браузер.
python -m collector setup
echo.
set /p AUTO="Обновлять цены автоматически каждый день в 7:40? (y/n) "
if /i "%AUTO%"=="y" schtasks /Create /F /SC DAILY /ST 07:40 /TN "eat-prices" /TR "\"%~dp0prices.bat\" auto" >nul && echo Готово: задача eat-prices в Планировщике заданий.
echo.
echo Дальше: prices.bat - собрать цены, start.bat - открыть приложение.
pause
