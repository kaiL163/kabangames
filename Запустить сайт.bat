@echo off
cd /d "%~dp0"
docker compose up --build -d
if errorlevel 1 (
  echo Не удалось запустить сайт. Проверьте, что Docker Desktop запущен.
  pause
  exit /b 1
)
echo Сайт запущен: http://localhost:8000
start http://localhost:8000
pause
