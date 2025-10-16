@echo off
echo Starting Stock Analyzer in DEBUG mode...
echo.
echo This will start all services with debugging enabled on port 5678
echo.

docker-compose -f docker-compose.yml -f docker-compose.debug.yml up --build

echo.
echo Services stopped.
pause
