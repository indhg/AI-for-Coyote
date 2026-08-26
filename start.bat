@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

REM ============ 找 Bun（中继服务器运行时） ============
set "BUN=%APPDATA%\npm\node_modules\bun\bin\bun.exe"
if not exist "%BUN%" set "BUN="
if not defined BUN (
  where bun >nul 2>nul && set "BUN=bun"
)
if not defined BUN (
  echo [错误] 找不到 Bun。请先安装：npm install -g bun
  pause
  exit /b 1
)

REM ============ 启动本地视觉模型服务（可选，Ollama） ============
set "OLLAMA=..\ollama\ollama.exe"
netstat -an | findstr ":11434" | findstr "LISTENING" >nul 2>nul
if errorlevel 1 (
  if exist "%OLLAMA%" (
    echo [0/3] 启动本地视觉模型服务 Ollama ...
    start "ollama" cmd /k "set OLLAMA_MODELS=%~dp0ollama\models&& %OLLAMA% serve"
  ) else (
    echo [提示] 未找到本地视觉模型（..\ollama\ollama.exe），视觉任务将走云模型。
  )
) else (
  echo [0/3] Ollama 已在运行。
)

echo [1/3] 启动中继服务器 dglab-websocket-server v4 ^(端口 9998^) ...
start "dglab-relay" cmd /k "cd /d %~dp0relay && %BUN% run v4-server.ts"

echo [2/3] 启动主程序 ...
start "AI-for-Coyote" cmd /k "cd /d %~dp0 && python -m backend.main"

timeout /t 4 /nobreak >nul
echo [3/3] 打开浏览器 ...
start http://127.0.0.1:8000

echo.
echo 已启动。关闭对应的命令行窗口即可停止程序。
echo 配对：手机连同一 Wi-Fi，用 DG-LAB 4.0 App 扫页面上的二维码。
pause