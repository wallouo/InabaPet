@echo off
chcp 65001 >nul
echo 正在停止所有服务...
taskkill /F /IM inference.exe >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq*pet.py*" >nul 2>&1
echo ✅ 已停止所有服务
pause
