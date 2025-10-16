@echo off
echo Starting Stock Analyzer...
echo.
echo Frontend: http://localhost:3000
echo Backend API: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.

docker-compose up --build

echo.
echo Services stopped.
pause
